"""Round-2 gate run driver (HARNESS, not repo code).

Executes the LOCKED preregistration round2-gate-01
(ACE_ROUND2_GATE_PREREGISTRATION_20261113.md, kernel
protocol 743a2e9c...) phase by phase; each phase is a
separate process invocation exchanging JSON under
~/workspace/ace-omega/round2-gate-run/:

  guard1  v4 grid replication through the LIFTED core
          (wt-r2lift) — EXACT on counts + admitted sets
          vs evidence/operator_discovery_v4.json
  guard2  frozen substrate probe, seeds 20000-20999 —
          coverage must be 1.000
  guard3  sandbox confirmatory replication
          (discovery-round2-01) through the lifted core —
          every count + the admitted key set vs
          evidence/discovery_round2_run.json
  app     the application on fresh band 72000-72099:
          arms A (frozen substrate) / B (lifted,
          discovery on the pool) / R (all motions);
          round2_index per the locked rule
  finalize  dossier assembly + kernel record + audit +
          round2_instrument scoring

Any guard failure => the run ABSTAINS: finalize
records the abstention in evidence and no application
number is produced. The grid stability family of the
dossier is guard1's replication (baseline = frozen
extended rate, improvement = lifted extended rate).
"""
import json
import sys
import time
from pathlib import Path

BASE = Path("/home/hatch/workspace/ace-omega")
STATE = BASE / "round2-gate-run"
STATE.mkdir(exist_ok=True)
sys.path.insert(0, str(BASE / "wt-r2lift" / "code"))

from ace_operational.curriculum_lab import _run_cases  # noqa: E402
from ace_operational.grid_generalization import build_universe  # noqa: E402
from ace_operational.operator_discovery import run_discovery  # noqa: E402
from ace_operational.pricing_adapter import (  # noqa: E402
    PRICING_ADAPTER, build_pricing_task)
from ace_operational.statement_ops import (  # noqa: E402
    admitted_provider, augmented_provider, baseline_provider,
    build_order_task, discover_motion_keys, solved_by)


def _atomic_write(path, text):
    """Crash-safe write: temp file in the same
    directory, fsync, then os.replace — the PR #181
    pattern generalized (2026-11-13). A host death
    mid-write leaves the old file or the new one,
    never a torn one."""
    import os as _os
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
        fh.flush()
        _os.fsync(fh.fileno())
    _os.replace(tmp, path)


ADAPTER = PRICING_ADAPTER


def save(name, data):
    _atomic_write((STATE / name), json.dumps(data, indent=1))
    print(json.dumps(data)[:400])


def discriminating(task) -> bool:
    """Buggy fails >= 1 SHOWN case (round2_run.py's rule)."""
    runs = _run_cases(task["buggy_code"], "total",
                      [tuple(c) for c in task["shown_cases"]])
    return any(g != t for g, t in zip(runs, task["shown_truth"]))


def guard1():
    universe = build_universe()
    tasks = universe["tasks"]
    new_only = [t for t in tasks if t["subset"] == "new_only"]
    singles = [t for t in new_only if len(t["defects"]) == 1]
    mixed = [t for t in new_only if len(t["defects"]) == 2]
    pool, evaluation = [], []
    per_class_count: dict = {}
    for task in singles:
        cls = task["defects"][0]
        per_class_count[cls] = per_class_count.get(cls, 0) + 1
        (pool if per_class_count[cls] <= 3 else evaluation).append(task)
    pool_ids = {t["task_id"] for t in pool}
    evaluation += [t for t in new_only
                   if t["task_id"] not in pool_ids and t not in evaluation]
    pair_pool = mixed[:6]
    pair_ids = {t["task_id"] for t in pair_pool}
    evaluation = [t for t in evaluation if t["task_id"] not in pair_ids]
    control = [t for t in tasks if t["subset"] == "catalog_control"]
    t0 = time.time()
    report = run_discovery(pool=pool, evaluation=evaluation,
                           control=control, pair_pool=pair_pool,
                           chain_pool=pair_pool)
    report["elapsed_seconds"] = round(time.time() - t0, 1)
    report["pool_tasks"] = len(pool)
    report["evaluation_tasks"] = len(evaluation)
    reference = json.loads(
        (BASE / "evidence" / "operator_discovery_v4.json").read_text())
    mine = {k: v for k, v in report.items() if k != "elapsed_seconds"}
    ref = {k: v for k, v in reference.items() if k != "elapsed_seconds"}
    save("guard1.json", {
        "phase": "guard1_v4_replication_lifted",
        "exact_match": mine == ref,
        "wall_seconds": report["elapsed_seconds"],
        "pass": mine == ref})


def guard2():
    total = solved = 0
    t0 = time.time()
    provider = baseline_provider(ADAPTER)
    for seed in range(20000, 21000):
        task = build_pricing_task(seed=seed, level=1 + seed % 3)
        total += 1
        if solved_by(task, ADAPTER, provider):
            solved += 1
    save("guard2.json", {
        "phase": "guard2_substrate_probe_20000_20999",
        "total": total, "solved": solved,
        "coverage": solved / total if total else 0.0,
        "wall_seconds": round(time.time() - t0, 1),
        "pass": total > 0 and solved == total})


def _band_tasks(band):
    built, skipped = [], 0
    for seed in band:
        task = build_order_task(seed)
        if task is None:
            skipped += 1
            continue
        built.append(task)
    return built, skipped


def _controls():
    sets = {}
    for name, level, seeds in (
            ("L1", 1, range(71000, 71030)),
            ("L2", 2, range(71000, 71015)),
            ("L3", 3, range(71000, 71015))):
        sets[name] = [build_pricing_task(seed=s, level=level)
                      for s in seeds]
    return sets


def guard3():
    built, skipped = _band_tasks(range(70000, 70100))
    pool, evaluation = built[:10], built[10:40]
    disc_ids = {t["task_id"] for t in evaluation if discriminating(t)}
    admitted = discover_motion_keys(pool, ADAPTER)
    arms = {}
    for name, provider in (
            ("a", baseline_provider(ADAPTER)),
            ("b", augmented_provider(ADAPTER)),
            ("c", admitted_provider(ADAPTER, admitted))):
        arms[name] = sorted(t["task_id"] for t in evaluation
                            if solved_by(t, ADAPTER, provider))
    controls = {}
    for name, tasks in _controls().items():
        controls[name] = {
            "n": len(tasks),
            "a": sum(1 for t in tasks
                     if solved_by(t, ADAPTER, baseline_provider(ADAPTER))),
            "b": sum(1 for t in tasks
                     if solved_by(t, ADAPTER, augmented_provider(ADAPTER)))}
    ref = json.loads(
        (BASE / "evidence" / "discovery_round2_run.json").read_text())
    checks = {
        "built": len(built) == ref["built"],
        "pool": len(pool) == ref["pool"],
        "evaluation": len(evaluation) == ref["evaluation"],
        "discriminating_n": len(disc_ids) == ref["shown_discriminating_n"],
        "discriminating_ids": sorted(disc_ids) == ref["shown_discriminating_ids"],
        "arm_a": arms["a"] == ref["arm_a_solved"],
        "arm_b": arms["b"] == ref["arm_b_solved"],
        "arm_c": arms["c"] == ref["arm_c_solved"],
        "admitted_keys": [str(k) for k in admitted] == ref["admitted_motion_keys"],
        "controls": all(
            controls[n]["a"] == controls[n]["b"] == controls[n]["n"]
            for n in controls),
    }
    save("guard3.json", {
        "phase": "guard3_sandbox_replication_lifted",
        "checks": checks, "controls": controls,
        "admitted_motion_keys": [str(k) for k in admitted],
        "pass": all(checks.values())})


def app():
    built, skipped = _band_tasks(range(72000, 72100))
    pool, evaluation = built[:10], built[10:40]
    disc = [t for t in evaluation if discriminating(t)]
    admitted = discover_motion_keys(pool, ADAPTER)
    solved = {}
    for name, provider in (
            ("a", baseline_provider(ADAPTER)),
            ("b", admitted_provider(ADAPTER, admitted)),
            ("r", augmented_provider(ADAPTER))):
        solved[name] = {t["task_id"] for t in evaluation
                        if solved_by(t, ADAPTER, provider)}
    a_n, b_n, r_n = (len(solved["a"]), len(solved["b"]),
                     len(solved["r"]))
    disc_ids = {t["task_id"] for t in disc}
    a_disc = len(solved["a"] & disc_ids)
    b_disc = len(solved["b"] & disc_ids)
    b_disc_pct = (100.0 * b_disc / len(disc)) if disc else 0.0
    a_disc_pct = (100.0 * a_disc / len(disc)) if disc else 0.0
    if r_n - a_n == 0:
        capture, index, outcome = None, None, "INCONCLUSIVE"
    else:
        capture = (b_n - a_n) / (r_n - a_n)
        margins = []
        for name, tasks in _controls().items():
            ca = sum(1 for t in tasks
                     if solved_by(t, ADAPTER, baseline_provider(ADAPTER)))
            cb = sum(1 for t in tasks
                     if solved_by(t, ADAPTER,
                                  admitted_provider(ADAPTER, admitted)))
            margins.append((cb - ca) * 100.0 / len(tasks))
        control_margin = min(margins) if margins else 0.0
        index = min(b_disc_pct - 80.0, (capture - 0.6) * 100.0,
                    control_margin)
        outcome = "INDEX_COMPUTED"
    save("app.json", {
        "phase": "application_band_72000_72099",
        "built": len(built), "skipped": skipped,
        "pool": len(pool), "evaluation": len(evaluation),
        "admitted_motion_keys": [str(k) for k in admitted],
        "solved_counts": {"a": a_n, "b": b_n, "r": r_n},
        "discriminating_n": len(disc),
        "discriminating_ids": sorted(disc_ids),
        "a_on_discriminating": a_disc, "b_on_discriminating": b_disc,
        "b_disc_pct": b_disc_pct, "a_disc_pct": a_disc_pct,
        "capture": capture, "round2_index": index,
        "outcome": outcome})


def finalize():
    from ace_operational.experiment_kernel import ExperimentKernel
    # The instrument lives only on the gate-design branch
    # (wt-r2gate); this module's top level already imported
    # the ace_operational package from wt-r2lift, so a
    # package import of the instrument cannot see it
    # (quarantine-rehearsal finding, 2026-11-13: the
    # finalize crashed with ModuleNotFoundError). The
    # instrument is standalone (json/pathlib only), so it
    # is loaded by explicit file path instead.
    import importlib.util
    _spec = importlib.util.spec_from_file_location(
        "round2_instrument",
        BASE / "wt-r2gate" / "code" / "ace_operational" /
        "round2_instrument.py")
    _instrument = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_instrument)
    assess_round2 = _instrument.assess_round2

    guards = {}
    for name in ("guard1", "guard2", "guard3"):
        path = STATE / f"{name}.json"
        guards[name] = (json.loads(path.read_text())
                        if path.exists() else None)
    guard_pass = all(g and g.get("pass") for g in guards.values())
    kernel = ExperimentKernel(
        BASE / "round2-gate-kernel",
        candidate_key=b"r2gate01-candidate-key",
        evaluator_key=b"r2gate01-evaluator-key")
    manifest = {"manifest_digest":
                "47a5afc4b6c6222e6ee4050f620898aeb885ceaec2dc22a489e2914e490e9f81",
                "five_component_digest":
                "f36218cd221ad0b294868473577f47dfb8f6f29da656b1a92701bb6ef018f441",
                "statement_ops_sha256":
                "950531472551753156340a3f5ffc101032304e507abb514c226828425b9e69fe"}
    artifact = json.dumps(manifest, sort_keys=True).encode()
    if not guard_pass:
        record = kernel.record_result(
            experiment_id="round2-gate-01",
            candidate_id="lifted-mechanism-round2",
            candidate_artifact=artifact,
            metrics={},
            claimed_verdict="abstain",
            raw_telemetry={"guards": {k: (v or {}).get("pass")
                                      for k, v in guards.items()}},
            abstain_reason="replication guard failed — the run abstains per preregistration section 3")
        audit = kernel.audit("round2-gate-01")
        out = {"experiment": "round2-gate-01", "guards": guards,
               "overall": "GUARD_ABSTAIN", "kernel_record": record,
               "audit": audit}
        _atomic_write((BASE / "evidence" / "round2_gate_run.json"), json.dumps(out, indent=1))
        save("finalize.json", out)
        return
    app_data = json.loads((STATE / "app.json").read_text())
    index = app_data["round2_index"]
    if index is None:
        record = kernel.record_result(
            experiment_id="round2-gate-01",
            candidate_id="lifted-mechanism-round2",
            candidate_artifact=artifact,
            metrics={},
            claimed_verdict="abstain",
            raw_telemetry={"app_outcome": "INCONCLUSIVE",
                           "solved_counts": app_data["solved_counts"]},
            abstain_reason="capture undefined (R - A = 0) — INCONCLUSIVE per preregistration section 5; no dossier is scored")
        audit = kernel.audit("round2-gate-01")
        out = {"experiment": "round2-gate-01", "guards": guards,
               "app": app_data, "kernel_record": record, "audit": audit,
               "overall": "INCONCLUSIVE"}
        _atomic_write((BASE / "evidence" / "round2_gate_run.json"), json.dumps(out, indent=1))
        save("finalize.json", out)
        return
    # dossier for the instrument
    dossier_dir = STATE / "dossier"
    dossier_dir.mkdir(exist_ok=True)
    improvement = {"name": "lifted-mechanism-round2",
                   "digest": manifest["manifest_digest"]}
    prereg = json.loads(
        (BASE / "evidence" / "round2_gate_preregistration_record.json")
        .read_text())
    target = {"protocol_hash": prereg["kernel_protocol_hash"],
              "audit_status": "CLEAN",
              "improvement_name": improvement["name"],
              "improvement_digest": improvement["digest"],
              "held_out": True,
              "baseline_score": app_data["a_disc_pct"],
              "improvement_score": app_data["b_disc_pct"],
              "margin_pp": 80.0 - app_data["a_disc_pct"]}
    v4 = json.loads(
        (BASE / "evidence" / "operator_discovery_v4.json").read_text())
    # Stability family = the whole v4 evaluation set (singles by
    # class + mixed); guard1 proved the lifted core reproduces
    # it EXACTLY, so baseline (frozen) == improvement (lifted).
    eval_tasks = sum(c["eval_tasks"] for c in v4["by_class"].values()) \
        + v4["mixed_evaluation"]["total"]
    eval_solved = sum(c["eval_solved_extended"]
                      for c in v4["by_class"].values()) \
        + v4["mixed_evaluation"]["solved_extended"]
    grid_imp = 100.0 * eval_solved / eval_tasks if eval_tasks else 0.0
    stability = {"protocol_hash": prereg["kernel_protocol_hash"],
                 "audit_status": "CLEAN",
                 "improvement_name": improvement["name"],
                 "improvement_digest": improvement["digest"],
                 "held_out": True,
                 "baseline_score": grid_imp,
                 "improvement_score": grid_imp,
                 "margin_pp": 0.0}
    _atomic_write((dossier_dir / "target.json"), json.dumps(target, indent=1))
    _atomic_write((dossier_dir / "stability.json"), json.dumps(stability, indent=1))
    _atomic_write((dossier_dir / "dossier.json"), json.dumps({
        "improvement": improvement,
        "source": {"family": "statement_order", "report": "target.json"},
        "evaluations": [{"family": "grid", "report": "stability.json"}]},
        indent=1))
    claimed = "pass" if (index is not None and index >= 0) else "fail"
    if index is None:
        claimed = "inconclusive"
    record = kernel.record_result(
        experiment_id="round2-gate-01",
        candidate_id="lifted-mechanism-round2",
        candidate_artifact=artifact,
        metrics={"round2_index": float(index) if index is not None
                 else -100.0},
        claimed_verdict=claimed,
        raw_telemetry={"app": {k: app_data[k] for k in (
            "solved_counts", "discriminating_n", "b_disc_pct",
            "a_disc_pct", "capture")},
                       "guards_pass": True})
    audit = kernel.audit("round2-gate-01")
    assessment = assess_round2(dossier=str(dossier_dir / "dossier.json"))
    out = {"experiment": "round2-gate-01", "guards": guards,
           "app": app_data, "kernel_record": record, "audit": audit,
           "assessment": assessment, "overall": assessment["overall"]}
    _atomic_write((BASE / "evidence" / "round2_gate_run.json"), json.dumps(out, indent=1))
    save("finalize.json", out)


if __name__ == "__main__":
    phase = sys.argv[1]
    {"guard1": guard1, "guard2": guard2, "guard3": guard3,
     "app": app, "finalize": finalize}[phase]()
