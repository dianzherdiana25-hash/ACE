"""Independent, stdlib-only consistency audit for ACE E1.4b evidence.

This checks the SAVED scoring report, not the correctness of the frozen solver,
question-pool generator, evaluator isolation, or oracle labels. It imports no
code from the candidate or evaluator. Run it after the frozen experiment.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from fractions import Fraction
from pathlib import Path

ALLOWED_REASONS = {"agreement", "disagreement", "initial_fit_not_exact", "query_budget_exhausted"}


class AuditError(ValueError):
    pass


def require(ok: bool, explanation: str):
    if not ok:
        raise AuditError(explanation)


def integer(value, where, minimum=0):
    require(type(value) is int and value >= minimum, f"{where}: expected integer >= {minimum}")
    return value


def score_arm(arm, family, regime, task_id, where, question=None):
    require(isinstance(arm, dict), f"{where}: not an object")
    for key, expected in (("task_id", task_id), ("family", family), ("regime", regime)):
        require(arm.get(key) == expected, f"{where}: {key} mismatch")
    if question is not None:
        require(arm.get("question") == question, f"{where}: question slot mismatch")
        require(arm.get("labels") == 1, f"{where}: exactly one oracle label required")
        integer(arm.get("oracle_cpu_us"), f"{where}.oracle_cpu_us")
    total = integer(arm.get("total"), f"{where}.total", minimum=1)
    correct = integer(arm.get("correct"), f"{where}.correct")
    require(correct <= total, f"{where}: correct exceeds total")
    scores = arm.get("scores")
    require(isinstance(scores, dict) and scores, f"{where}: missing score strata")
    subtotals = [(integer(v.get("correct"), f"{where}.{k}.correct"),
                  integer(v.get("total"), f"{where}.{k}.total"))
                 for k, v in scores.items() if isinstance(v, dict)]
    require(len(subtotals) == len(scores), f"{where}: invalid score object")
    require(sum(x for x, _ in subtotals) == correct and
            sum(t for _, t in subtotals) == total,
            f"{where}: subtotal mismatch")
    require(all(0 <= x <= t for x, t in subtotals), f"{where}: incorrect stratum range")
    require(type(arm.get("cap_reached")) is bool, f"{where}: missing cap marker")
    require(isinstance(arm.get("fit_status"), str), f"{where}: missing fit status")
    return correct, total


def audit(report, *, kind="replication"):
    """Return a deterministic audit summary; raise AuditError on inconsistencies."""
    require(kind in ("replication", "pilot"), "unsupported audit kind")
    target_regimes = ("unconditioned_pool",) if kind == "replication" else (
        "witness_pool", "low_information", "out_of_basis")
    expected_n = 12 if kind == "replication" else 18
    expected_per_group = 6 if kind == "replication" else 3
    expected_mode = ("public_development_replication" if kind == "replication"
                     else "public_development")
    require(isinstance(report, dict) and report.get("mode") == expected_mode,
            "missing or mismatched mode")
    require(integer(report.get("episodes"), "episodes", 1) == expected_n,
            "wrong number of episodes")
    require(report.get("isolated_fits") == 11 * expected_n,
            "isolated fit count does not include all interventions")
    rows = report.get("rows")
    require(isinstance(rows, list) and len(rows) == expected_n, "wrong number of rows")
    for name in ("bank_sha256", "source_sha256"):
        value = report.get(name)
        require(isinstance(value, str) and len(value) == 64 and
                all(ch in "0123456789abcdef" for ch in value), f"malformed {name}")

    groups = {}
    tasks = set()
    number_arms = 0
    caps = 0
    observed_fit_caps = 0
    observed_predict_caps = 0
    for i, row in enumerate(rows):
        where = f"row[{i}]"
        require(isinstance(row, dict), f"{where}: not an object")
        family, regime, task_id = (row.get(key) for key in ("family", "regime", "task_id"))
        require(family in ("S", "G") and regime in target_regimes,
                f"{where}: invalid family/regime")
        require(isinstance(task_id, str) and len(task_id) == 32 and
                all(c in "0123456789abcdef" for c in task_id), f"{where}: invalid task ID")
        require(task_id not in tasks, f"{where}: duplicate task ID")
        tasks.add(task_id)
        selector = row.get("selector")
        require(isinstance(selector, dict), f"{where}: missing selector")
        index = integer(row.get("active_question"), f"{where}.active_question")
        require(index < 8 and selector.get("index") == index,
                f"{where}: active question inconsistent with selector")
        reason, disagreements = selector.get("reason"), selector.get("disagreements")
        require(reason in ALLOWED_REASONS, f"{where}: unknown selector outcome")
        require(isinstance(disagreements, list) and
                all(type(j) is int and 0 <= j < 8 for j in disagreements) and
                len(set(disagreements)) == len(disagreements),
                f"{where}: malformed disagreement indices")
        if reason == "disagreement":
            require(len(disagreements) > 0 and index in disagreements,
                    f"{where}: selector did not choose a disagreement")
        else:
            require(not disagreements, f"{where}: unexpected disagreement indices")
        integer(selector.get("steps"), f"{where}.selector.steps")
        integer(selector.get("cpu_us"), f"{where}.selector.cpu_us")
        integer(selector.get("wall_us"), f"{where}.selector.wall_us")
        initial = row.get("initial")
        initial_correct, initial_total = score_arm(initial, family, regime, task_id,
                                                  f"{where}.initial")
        require(initial_total == 8, f"{where}: expected eight held-out probes")
        hypotheses = row.get("hypotheses")
        require(isinstance(hypotheses, list) and len(hypotheses) == 2,
                f"{where}: two initial hypotheses required")
        for h in hypotheses:
            require(isinstance(h, dict) and isinstance(h.get("status"), str),
                    f"{where}: invalid initial fit")
            integer(h.get("fit_steps"), f"{where}.hypothesis.fit_steps")
            if h["status"] == "fuel_exhausted":
                observed_fit_caps += 1
        arms = row.get("uniform_one_label_arms")
        require(isinstance(arms, list) and len(arms) == 8,
                f"{where}: eight uniform one-label branches required")
        scores = []
        for j, arm in enumerate(arms):
            correct, total = score_arm(arm, family, regime, task_id,
                                       f"{where}.arm[{j}]", j)
            require(total == initial_total, f"{where}: unmatched held-out denominator")
            scores.append(correct)
            number_arms += 1
        for arm in [initial, *arms]:
            observed_fit_caps += arm["fit_status"] == "fuel_exhausted"
            observed_predict_caps += int(arm["cap_reached"])
        limits = report.get("limits")
        require(isinstance(limits, dict), "limits missing")
        max_cpu = integer(limits.get("query_cpu_us"), "limits.query_cpu_us", 1)
        max_wall = integer(limits.get("query_wall_us"), "limits.query_wall_us", 1)
        if (reason == "query_budget_exhausted" or
                selector["cpu_us"] > max_cpu or selector["wall_us"] > max_wall):
            caps += 1
        key = (family, regime)
        stats = groups.setdefault(key, {"episodes": 0, "total": 0,
                                        "initial": 0, "active": 0,
                                        "uniform": Fraction(0),
                                        "wins": 0, "ties": 0, "losses": 0,
                                        "reasons": Counter()})
        mean = Fraction(sum(scores), 8)
        active = scores[index]
        stats["episodes"] += 1
        stats["total"] += initial_total
        stats["initial"] += initial_correct
        stats["active"] += active
        stats["uniform"] += mean
        stats["wins" if active > mean else "losses" if active < mean else "ties"] += 1
        stats["reasons"][reason] += 1

    require(len(groups) == len(target_regimes) * 2, "missing S/G or required regime")
    for key, stats in groups.items():
        require(stats["episodes"] == expected_per_group, f"{key}: episode count mismatch")
    summary = report.get("summary")
    require(isinstance(summary, list) and len(summary) == len(groups), "summary group count")
    seen = set()
    for row in summary:
        require(isinstance(row, dict), "nonobject summary row")
        key = (row.get("family"), row.get("regime"))
        require(key in groups and key not in seen, "unknown/duplicate summary group")
        seen.add(key)
        x = groups[key]
        for field, value in (("episodes", x["episodes"]),
                             ("total_per_policy", x["total"]),
                             ("initial_correct", x["initial"]),
                             ("active_correct", x["active"])):
            require(row.get(field) == value, f"{key}: {field} mismatch")
        val = row.get("uniform_expected_correct")
        require(type(val) in (int, float) and
                abs(Fraction(str(val)) - x["uniform"]) < Fraction(1, 10**9),
                f"{key}: uniform expected score mismatch")
        require(row.get("selection_reasons") == dict(x["reasons"]),
                f"{key}: selector reasons mismatch")
        require(row.get("active_vs_uniform") ==
                {field: x[field] for field in ("wins", "ties", "losses")},
                f"{key}: active-vs-random counts mismatch")

    budget = report.get("budget")
    require(isinstance(budget, dict), "budget missing")
    for field, observed in (("selector_caps", caps), ("fit_caps", observed_fit_caps),
                            ("prediction_caps", observed_predict_caps)):
        require(budget.get(field) == observed, f"budget {field} mismatch")
    gated = caps or observed_fit_caps or observed_predict_caps
    target = target_regimes[0]
    supports_go = all(groups[(family, target)]["active"] >
                      max(groups[(family, target)]["initial"],
                          groups[(family, target)]["uniform"])
                      for family in ("S", "G"))
    expected_decision = ("hold_for_resource_review" if gated else
                         "go_to_cross_episode_development" if supports_go and kind == "replication" else
                         "go_to_public_replication" if supports_go else "hold_for_diagnosis")
    require(report.get("decision") == expected_decision,
            f"decision mismatch: expected {expected_decision}")

    return {
        "audit": "INTERNAL_REPORT_CONSISTENCY_PASS",
        "kind": kind,
        "episodes": len(rows),
        "one_label_control_arms": number_arms,
        "reported_isolated_fits": report["isolated_fits"],
        "total_probes_per_policy": sum(x["total"] for x in groups.values()),
        "observed_fit_caps": observed_fit_caps,
        "observed_prediction_caps": observed_predict_caps,
        "selector_budget_exhaustions": caps,
        "per_group": [{"family": k[0], "regime": k[1], "episodes": x["episodes"],
                       "initial_correct": x["initial"], "active_correct": x["active"],
                       "uniform_expected_numerator": x["uniform"].numerator,
                       "uniform_expected_denominator": x["uniform"].denominator,
                       "total": x["total"]} for k, x in sorted(groups.items())],
        "decision": expected_decision,
        "limitations": ["This validates SAVED report internal arithmetic and structure only.",
                        "It does not rerun candidate fits, re-evaluate oracle labels,",
                        "or prove that inputs were independent of labels or candidates."],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--kind", choices=("replication", "pilot"), default="replication")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    raw = args.input.read_bytes()
    if len(raw) > 20_000_000:
        raise AuditError("evidence report exceeds 20 MB")
    result = audit(json.loads(raw), kind=args.kind)
    result["input_sha256"] = hashlib.sha256(raw).hexdigest()
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.write_text(encoded)
    else:
        print(encoded, end="")


if __name__ == "__main__":
    main()
