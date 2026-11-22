"""Jalankan dua lengan tersegel hanya apabila tepat satu operan yang diumumkan berubah."""
from copy import deepcopy

from ._contracts import GuardianError, anchor, cli, identity, integer, obj, schema
from .twin_diff import compare
from .twin_runner import MAX_VALUE, run

def experiment(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.guardian.counterfactual.v1", ("runner", "treatment"))
    baseline = plan["runner"]
    schema(baseline, "ace.guardian.twin-run.v1", ("initial", "cycles", "must_keep"))
    selection = obj(plan["treatment"], ("cycle", "action", "replacement"))
    cycle = integer(selection["cycle"], "Siklus intervensi", 1, len(baseline["cycles"]))
    action = integer(selection["action"], "Aksi intervensi", 1, len(baseline["cycles"][cycle - 1]))
    replacement = integer(selection["replacement"], "Operan intervensi", -MAX_VALUE, MAX_VALUE)
    candidate = deepcopy(baseline)
    change = candidate["cycles"][cycle - 1][action - 1]
    if change["value"] == replacement:
        raise GuardianError("Intervensi perlu nilai berbeda.")
    changed_from = change["value"]
    change["value"] = replacement
    left, right = run(baseline, identity(baseline)), run(candidate, identity(candidate))
    diff = {"schema": "ace.guardian.twin-diff.v1", "baseline": left, "candidate": right}
    report = {"manifest_sha256": expected, "baseline_sha256": identity(baseline), "candidate_sha256": identity(candidate),
              "field": change["field"], "before": changed_from, "after": replacement,
              "comparison": compare(diff, identity(diff))}
    return {**report, "seal_sha256": identity(report)}

if __name__ == "__main__":
    raise SystemExit(cli(experiment, __doc__))
