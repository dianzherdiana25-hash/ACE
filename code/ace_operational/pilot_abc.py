"""Phase 2 — the A/B/C pilot: substrate v2 + full-custody harness.

Implements the design in `ACE_PHASE2_PILOT_ABC_DESIGN_20261112.md`:

* **Substrate v2** — the OMEGA-11 grammar grouped into named operator
  groups (boundary, basis, nudge) plus the operator the shipping
  measurement proved missing: **multiplier** (restore a dropped
  multiplier constant from the spec). v1 in `reasoning_lab` stays
  frozen as the OMEGA-11 record; v2 is a new, versioned substrate,
  frozen identically for all three arms before preregistration.
* **Arms (PRD v0.1)** — A Fixed: frozen config, no cross-cycle change.
  B Adaptive: operator order adapts between cycles from per-group
  credit earned on TRAIN tasks; no new operators, no successors.
  C Evolutionary: a population of configs mutated (operator swap /
  drop / add / rounds tweak) and selected on TRAIN fitness, with full
  lineage in the OMEGA-08 archive.
* **Custody** — the OMEGA-06 kernel holds preregistration (hypothesis,
  pass floor, budget), the evaluator and fixture digests, and every
  arm's result. Held-out tasks are touched only by the final
  evaluation; selection and adaptation never see them.
* Inside the pilot, direction is ACE's own mechanisms (credit rules,
  mutation, selection) — neither the local director nor the operator
  steers arms mid-run.
"""
from __future__ import annotations

import ast
import json
import random
import re
from pathlib import Path
from typing import Any

from ace_operational.curriculum_lab import generate_task, split_of, verify_candidate
from ace_operational.experiment_kernel import ExperimentKernel
from ace_operational.population_archive import PopulationArchive
from ace_operational.reasoning_lab import Budget

OPERATOR_GROUPS = ("boundary", "basis", "nudge", "multiplier")
BASE_CONFIG = {"operators": list(OPERATOR_GROUPS), "rounds": 3}
PILOT_ID = "pilot-abc-v1"
PASS_FLOOR = 0.5


# ---------------------------------------------------------------------------
# Substrate v2: grouped operators
# ---------------------------------------------------------------------------

def _spec_numbers(spec: str) -> set[int]:
    return {int(n) for n in re.findall(r"\d+", spec)}


def _boundary(code: str, spec: str, tree: Any = None) -> list[str]:
    numbers = _spec_numbers(spec)
    out = []
    for node in ast.walk(tree if tree is not None else ast.parse(code)):
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            comp = node.comparators[0]
            if isinstance(comp, ast.Constant) and comp.value in numbers:
                for old, new in ((">=", ">"), (">", ">="), ("<=", "<"), ("<", "<=")):
                    if old in code:
                        out.append(code.replace(old, new, 1))
    return out


def _basis(code: str, spec: str, tree: Any = None) -> list[str]:
    tree = tree if tree is not None else ast.parse(code)
    lines = code.splitlines()
    out = []
    func = next((n for n in tree.body if isinstance(n, ast.FunctionDef)), None)
    if func is None:
        return out
    params = [a.arg for a in func.args.args]
    accumulators = [t.id for stmt in func.body if isinstance(stmt, ast.Assign)
                    for t in stmt.targets if isinstance(t, ast.Name)
                    and isinstance(stmt.value, ast.Name) and stmt.value.id in params]
    if not accumulators:
        return out
    acc = accumulators[0]
    for param in params:
        pattern = re.compile(rf"\b{re.escape(param)}\b")
        for i, line in enumerate(lines):
            if (" += " in line or " -= " in line) and pattern.search(line):
                changed = lines.copy()
                changed[i] = pattern.sub(acc, line, count=1)
                out.append("\n".join(changed) + "\n")
    return out


def _nudge(code: str, spec: str, tree: Any = None) -> list[str]:
    out = []
    for n in _spec_numbers(spec):
        for delta in (-1, 1):
            out.append(re.sub(rf"\b{n}\b", str(n + delta), code, count=1))
    return out


def _multiplier(code: str, spec: str, tree: Any = None) -> list[str]:
    """Restore a dropped multiplier: `x *= <const>` -> spec constants."""
    out = []
    numbers = sorted(_spec_numbers(spec))
    for node in ast.walk(tree if tree is not None else ast.parse(code)):
        if isinstance(node, ast.AugAssign) and isinstance(node.op, ast.Mult) \
                and isinstance(node.value, ast.Constant) \
                and isinstance(node.value.value, int):
            segment = ast.get_source_segment(code, node)
            if segment is None:
                continue
            for n in numbers:
                if n != node.value.value and n >= 2:
                    fixed = re.sub(r"\*\s*=\s*\d+", f"*= {n}", segment, count=1)
                    if fixed != segment:
                        out.append(code.replace(segment, fixed, 1))
    return out


GROUP_FN = {"boundary": _boundary, "basis": _basis,
            "nudge": _nudge, "multiplier": _multiplier}


def variants_by_group(code: str, spec: str) -> dict[str, list[str]]:
    """Candidate variants per operator group.

    Parse-once: the source is parsed a single time here and the tree
    is shared by every group function (they only read it). Before
    this, each group re-parsed the same source on every round — the
    profiling pilot (PR #178) measured source-text processing at
    87.6% of solver wall. Group functions called without a tree keep
    the original parse-it-yourself behaviour, so the unshared path
    remains available as the equivalence reference.
    """
    tree = ast.parse(code)
    groups: dict[str, list[str]] = {}
    for name, fn in GROUP_FN.items():
        seen: list[str] = []
        for variant in fn(code, spec, tree=tree):
            if variant != code and variant not in seen:
                seen.append(variant)
        groups[name] = seen
    return groups


class CachingBudget(Budget):
    """Budget with compile-once scoring.

    ``compile`` is a pure function of the source text, so the code
    object for a distinct source is built once per budget and reused;
    it is still executed in a fresh namespace on every call, exactly
    as ``Budget.score`` does. Scores, ``used`` accounting and the
    -1-on-any-exception behaviour are unchanged (equivalence-tested
    against the plain Budget). This is not a score cache: every call
    genuinely re-executes; only the redundant re-compilation of an
    identical source is removed.
    """

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self._compiled: dict[str, Any] = {}

    def score(self, code: str) -> int:
        self.used += 1
        try:
            code_obj = self._compiled.get(code)
            if code_obj is None:
                code_obj = compile(code, "<cand>", "exec")
                self._compiled[code] = code_obj
            namespace: dict[str, Any] = {}
            exec(code_obj, namespace)
            fn = namespace[self._entrypoint]
            return sum(1 for case, expected in self._shown
                       if fn(*case) == expected)
        except Exception:
            return -1


def solve_with_config(task: dict[str, Any], budget: Budget,
                      config: dict[str, Any]) -> dict[str, Any]:
    """Greedy composition in the config's operator order, with credit."""
    current = task["buggy_code"]
    best = budget.score(current)
    credits: dict[str, int] = {g: 0 for g in config["operators"]}
    for _ in range(config["rounds"]):
        improved = False
        groups = variants_by_group(current, task["spec"])
        for group in config["operators"]:
            for variant in groups.get(group, []):
                if budget.used >= budget.limit:
                    return {"code": current, "shown_score": best,
                            "credits": credits, "evals": budget.used}
                score = budget.score(variant)
                if score > best:
                    current, best, improved = variant, score, True
                    credits[group] += 1
                    break
            if improved:
                break
        if not improved:
            break
    return {"code": current, "shown_score": best,
            "credits": credits, "evals": budget.used}


# ---------------------------------------------------------------------------
# Arm machinery (train-split only)
# ---------------------------------------------------------------------------

def _budget_for(task: dict[str, Any], limit: int) -> Budget:
    shown = [tuple(c) for c in task["shown_cases"]]
    by_case = {tuple(c): e for c, e in zip(task["cases"], task["expected"])}
    return CachingBudget(limit, entrypoint=task["entrypoint"],
                         shown_cases=shown,
                         shown_expected=[by_case[c] for c in shown])


def _public(task: dict[str, Any]) -> dict[str, Any]:
    return {k: task[k] for k in ("buggy_code", "spec", "shown_cases",
                                 "entrypoint", "seed")}


def evaluate_config(config: dict[str, Any], tasks: list[dict[str, Any]],
                    budget_limit: int) -> dict[str, Any]:
    """Full-verifier evaluation of a config over a task list."""
    solved = 0
    per_family: dict[str, dict[str, int]] = {}
    credits: dict[str, int] = {g: 0 for g in OPERATOR_GROUPS}
    evals = 0
    for task in tasks:
        result = solve_with_config(_public(task), _budget_for(task, budget_limit),
                                   config)
        outcome = verify_candidate(task, result["code"])
        full = outcome["passed"] == outcome["total"]
        solved += 1 if full else 0
        fam = per_family.setdefault(task["family"], {"solved": 0, "total": 0})
        fam["solved"] += 1 if full else 0
        fam["total"] += 1
        evals += result["evals"]
        for group, credit in result["credits"].items():
            credits[group] = credits.get(group, 0) + credit
    return {"solved": solved, "total": len(tasks),
            "rate": (solved / len(tasks)) if tasks else 0.0,
            "per_family": per_family, "credits": credits, "evals": evals}


def run_arm_b(train_tasks: list[dict[str, Any]], *, cycles: int,
              budget_limit: int) -> dict[str, Any]:
    """Adaptive: reorder operators by earned credit between cycles."""
    config = json.loads(json.dumps(BASE_CONFIG))
    history = []
    for _ in range(cycles):
        result = evaluate_config(config, train_tasks, budget_limit)
        history.append({"config": json.loads(json.dumps(config)),
                        "train_rate": result["rate"]})
        credits = result["credits"]
        config = {"operators": sorted(
            config["operators"],
            key=lambda g: (-credits.get(g, 0), config["operators"].index(g))),
            "rounds": config["rounds"]}
    return {"final_config": config, "history": history}


def _mutate(config: dict[str, Any], rng: random.Random) -> dict[str, Any]:
    child = json.loads(json.dumps(config))
    ops = child["operators"]
    move = rng.choice(["swap", "drop", "add", "rounds"])
    if move == "swap" and len(ops) >= 2:
        i, j = rng.sample(range(len(ops)), 2)
        ops[i], ops[j] = ops[j], ops[i]
    elif move == "drop" and len(ops) > 1:
        ops.remove(rng.choice(ops))
    elif move == "add":
        missing = [g for g in OPERATOR_GROUPS if g not in ops]
        if missing:
            ops.insert(rng.randrange(len(ops) + 1), rng.choice(missing))
    elif move == "rounds":
        child["rounds"] = max(1, min(5, child["rounds"] + rng.choice([-1, 1])))
    return child


def run_arm_c(train_tasks: list[dict[str, Any]], *, cycles: int,
              budget_limit: int, archive: PopulationArchive,
              rng_seed: int = 7) -> dict[str, Any]:
    """Evolutionary: mutate + select on train fitness, archive lineage."""
    rng = random.Random(rng_seed)

    def register(config: dict[str, Any], parents: list[str]) -> str:
        blob = json.dumps(config, sort_keys=True)
        return archive.register_candidate(
            kind="solver-config", descriptor=blob, artifact_bytes=blob.encode(),
            parents=parents, metadata={"arm": "C"})

    population = [BASE_CONFIG,
                  {"operators": ["multiplier", "boundary", "basis", "nudge"],
                   "rounds": 3},
                  {"operators": ["boundary", "multiplier"], "rounds": 2}]
    ids = {json.dumps(c, sort_keys=True): register(c, []) for c in population}
    scored: dict[str, dict[str, Any]] = {}
    for cycle in range(cycles):
        for config in population:
            key = json.dumps(config, sort_keys=True)
            if key not in scored:
                scored[key] = evaluate_config(config, train_tasks, budget_limit)
        ranked = sorted(population,
                        key=lambda c: (-scored[json.dumps(c, sort_keys=True)]["rate"],
                                       scored[json.dumps(c, sort_keys=True)]["evals"]))
        parents = ranked[:2]
        offspring = []
        for parent in parents:
            child = _mutate(parent, rng)
            key = json.dumps(child, sort_keys=True)
            if key not in ids:
                ids[key] = register(child, [ids[json.dumps(parent, sort_keys=True)]])
            offspring.append(child)
        population = (ranked[:3] + offspring)[:5]
    for config in population:
        key = json.dumps(config, sort_keys=True)
        if key not in scored:
            scored[key] = evaluate_config(config, train_tasks, budget_limit)
    champion = min(population,
                   key=lambda c: (-scored[json.dumps(c, sort_keys=True)]["rate"],
                                  scored[json.dumps(c, sort_keys=True)]["evals"]))
    return {"final_config": champion,
            "train_rate": scored[json.dumps(champion, sort_keys=True)]["rate"],
            "candidates_registered": len(ids),
            "lineage_ids": ids}


# ---------------------------------------------------------------------------
# Pilot assembly, preregistration, run
# ---------------------------------------------------------------------------

def generate_universe(*, families: list[str], levels: list[int],
                      seeds: list[int]) -> list[dict[str, Any]]:
    tasks = []
    for family in families:
        for level in levels:
            for seed in seeds:
                try:
                    tasks.append(generate_task(family, level, seed=seed))
                except Exception:
                    continue
    return tasks


def _arm_artifact(arm: str, detail: dict[str, Any]) -> bytes:
    return json.dumps({"arm": arm, "substrate": "v2", "detail": detail},
                      sort_keys=True).encode()


def arm_artifacts(cycles: int) -> dict[str, bytes]:
    """The custodied method description of each arm — one definition,
    used identically at preregistration and at result recording."""
    arms = {
        "arm-a-fixed": {"config": BASE_CONFIG, "adaptation": "none"},
        "arm-b-adaptive": {"initial": BASE_CONFIG, "rule": "credit-reorder",
                           "cycles": cycles},
        "arm-c-evolutionary": {"initial": BASE_CONFIG, "rule": "mutate-select",
                               "cycles": cycles},
        "arm-null": {"config": "identity", "role": "negative-control"},
    }
    return {arm: _arm_artifact(arm, detail) for arm, detail in arms.items()}


def preregister_pilot(kernel: ExperimentKernel, tasks: list[dict[str, Any]],
                      *, budget_limit: int, cycles: int, reps: int,
                      pilot_id: str = PILOT_ID,
                      canary: str = "CANARY-PILOT-ABC-V1") -> dict[str, Any]:
    evaluator_bytes = Path(__file__).with_name("curriculum_lab.py").read_bytes()
    fixture = {"tasks": sorted(t["task_id"] for t in tasks),
               "canary": canary}
    fixture_bytes = json.dumps(fixture, sort_keys=True).encode()
    kernel.custody_evaluator("omega10-verifier", evaluator_bytes, fixture_bytes)
    artifacts = arm_artifacts(cycles)
    for arm, artifact in artifacts.items():
        kernel.custody_candidate(arm, artifact)
    arms = list(artifacts)
    protocol = {
        "pass_rule": {"metric": "heldout_solve_rate", "gte": PASS_FLOOR},
        "primary_metric": "heldout_solve_rate_per_family",
        "decision_language": ("C above A on held-out across both families = "
                              "transfer signal; one family only = specialization; "
                              "below sample target or within noise = INCONCLUSIVE"),
        "sample_target_per_family": 30,
        "budget_limit_per_task": budget_limit,
        "repetitions": reps,
        "heldout_use": "final evaluation only; never selection",
    }
    return kernel.preregister(
        experiment_id=pilot_id,
        hypothesis=("Evolutionary adaptation (C) yields a held-out solve rate "
                    "above the fixed substrate (A), with adaptive (B) between."),
        protocol=protocol, evaluator_id="omega10-verifier",
        budget={"budget_limit_per_task": budget_limit, "cycles": cycles,
                "repetitions": reps},
        candidate_ids=list(arms), baseline_candidate_id="arm-a-fixed",
        negative_control_id="arm-null",
        canary_tokens=[canary])


def run_pilot(*, kernel_root: str | Path, archive_root: str | Path,
              families: list[str] = ("pricing", "shipping"),
              levels: list[int] = (1, 2, 3), seeds: list[int] | None = None,
              reps: int = 3, cycles: int = 3, budget_limit: int = 200,
              kernel_keys: tuple[bytes, bytes] = (b"pilot-candidate-key",
                                                  b"pilot-evaluator-key"),
              pilot_id: str = PILOT_ID,
              canary: str = "CANARY-PILOT-ABC-V1"
              ) -> dict[str, Any]:
    seeds = seeds if seeds is not None else list(range(1, 51))
    kernel = ExperimentKernel(kernel_root, candidate_key=kernel_keys[0],
                              evaluator_key=kernel_keys[1])
    archive = PopulationArchive(archive_root)
    # Generate every repetition's universe first, then preregister
    # BEFORE any arm runs: the kernel record must precede the results
    # it will judge.
    universes = []
    all_tasks: list[dict[str, Any]] = []
    for rep in range(reps):
        offset = rep * 1000
        tasks = generate_universe(families=list(families), levels=list(levels),
                                  seeds=[s + offset for s in seeds])
        universes.append(tasks)
        all_tasks.extend(tasks)
    prereg = preregister_pilot(kernel, all_tasks, budget_limit=budget_limit,
                               cycles=cycles, reps=reps, pilot_id=pilot_id,
                               canary=canary)
    artifacts = arm_artifacts(cycles)
    per_rep = []
    for rep, tasks in enumerate(universes):
        train = [t for t in tasks if split_of(t) == "train"]
        holdout = [t for t in tasks if split_of(t) == "holdout"]
        arm_a = {"final_config": BASE_CONFIG}
        arm_b = run_arm_b(train, cycles=cycles, budget_limit=budget_limit)
        arm_c = run_arm_c(train, cycles=cycles, budget_limit=budget_limit,
                          archive=archive, rng_seed=7 + rep)
        rep_result: dict[str, Any] = {"rep": rep, "train_tasks": len(train),
                                      "holdout_tasks": len(holdout), "arms": {}}
        for arm, outcome in (("arm-a-fixed", arm_a), ("arm-b-adaptive", arm_b),
                             ("arm-c-evolutionary", arm_c)):
            evaluation = evaluate_config(outcome["final_config"], holdout,
                                         budget_limit)
            rep_result["arms"][arm] = {
                "final_config": outcome["final_config"],
                "heldout": evaluation}
        null_eval = evaluate_config({"operators": [], "rounds": 1}, holdout,
                                    budget_limit)
        rep_result["arms"]["arm-null"] = {"final_config": "identity",
                                          "heldout": null_eval}
        per_rep.append(rep_result)
    aggregate: dict[str, Any] = {}
    for arm in ("arm-a-fixed", "arm-b-adaptive", "arm-c-evolutionary", "arm-null"):
        rates = [r["arms"][arm]["heldout"]["rate"] for r in per_rep]
        solved = sum(r["arms"][arm]["heldout"]["solved"] for r in per_rep)
        total = sum(r["arms"][arm]["heldout"]["total"] for r in per_rep)
        per_family: dict[str, dict[str, int]] = {}
        for r in per_rep:
            for fam, vals in r["arms"][arm]["heldout"]["per_family"].items():
                agg = per_family.setdefault(fam, {"solved": 0, "total": 0})
                agg["solved"] += vals["solved"]
                agg["total"] += vals["total"]
        aggregate[arm] = {"mean_rate": sum(rates) / len(rates) if rates else 0.0,
                          "solved": solved, "total": total,
                          "pooled_rate": (solved / total) if total else 0.0,
                          "per_family": per_family}
        verdict = "pass" if aggregate[arm]["mean_rate"] >= PASS_FLOOR else "fail"
        kernel.record_result(
            experiment_id=pilot_id, candidate_id=arm,
            candidate_artifact=artifacts[arm],
            metrics={"heldout_solve_rate": aggregate[arm]["mean_rate"]},
            claimed_verdict=verdict,
            raw_telemetry={"rep_rates": rates,
                           "final_config": per_rep[-1]["arms"][arm]["final_config"]})
    audit = kernel.audit(pilot_id)
    holdout_per_family = {
        fam: sum(1 for t in all_tasks if split_of(t) == "holdout"
                 and t["family"] == fam) for fam in families}
    return {"experiment": pilot_id, "protocol_hash": prereg["protocol_hash"],
            "reps": per_rep, "aggregate": aggregate, "audit": audit,
            "holdout_tasks_per_family": holdout_per_family,
            "sample_target_met": all(v >= 30 for v in holdout_per_family.values())}
