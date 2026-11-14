"""Bake-off 02 dry-intake COMPLETION — the first
script recorded dryintake-pos into the scratch kernel
and the kernel derived verdict 'pass' correctly, then
the script died reading the result at the wrong key
path (rec['verdict'] instead of
rec['result']['verdict'] — harness defect, disclosed
in the record). This script verifies the pos case
from the ledger + audit, then runs the negative case.
"""
import json
import sys
from pathlib import Path

BASE = Path("/home/hatch/workspace/ace-omega")
sys.path.insert(0, str(BASE / "wt-bakeoff02val" / "code"))
from ace_operational.experiment_kernel import ExperimentKernel

ROOT = BASE / "bakeoff02-dryintake-kernel"
assert ROOT.exists()
kernel = ExperimentKernel(
    ROOT, candidate_key=b"bakeoff02-dryintake-candidate-key",
    evaluator_key=b"bakeoff02-dryintake-evaluator-key")
artifact = b"synthetic-dryintake-candidate"

checks = []
rows = [json.loads(l) for l in
        open(ROOT / "results.jsonl")]
pos = [r for r in rows
       if r["result"]["experiment_id"] == "dryintake-pos"]
assert len(pos) == 1
audit_pos = kernel.audit("dryintake-pos")
checks.append({"experiment": "dryintake-pos", "margin": 0.25,
               "claimed": "pass",
               "derived": pos[0]["result"]["verdict"],
               "audit": audit_pos["status"],
               "ok": pos[0]["result"]["verdict"] == "pass"
               and audit_pos["status"] == "CLEAN"})
print("dryintake-pos derived", checks[-1]["derived"],
      "audit", checks[-1]["audit"], "ok", checks[-1]["ok"])

kernel.preregister(
    experiment_id="dryintake-neg",
    hypothesis="dry-intake synthetic",
    protocol={"pass_rule": {"metric": "succession_margin",
                            "gte": 0}},
    evaluator_id="synthetic-evaluator",
    budget={"wall_seconds": 60},
    candidate_ids=["synthetic-candidate"],
    baseline_candidate_id="synthetic-candidate",
    negative_control_id=None,
    canary_tokens=["CANARY-DRYINTAKE"])
rec = kernel.record_result(
    experiment_id="dryintake-neg",
    candidate_id="synthetic-candidate",
    candidate_artifact=artifact,
    metrics={"succession_margin": -0.75},
    claimed_verdict="fail", raw_telemetry={"synthetic": True})
audit_neg = kernel.audit("dryintake-neg")
checks.append({"experiment": "dryintake-neg", "margin": -0.75,
               "claimed": "fail",
               "derived": rec["result"]["verdict"],
               "audit": audit_neg["status"],
               "ok": rec["result"]["verdict"] == "fail"
               and audit_neg["status"] == "CLEAN"})
print("dryintake-neg derived", checks[-1]["derived"],
      "audit", checks[-1]["audit"], "ok", checks[-1]["ok"])

ok = all(c["ok"] for c in checks)
out = {"step": "dry-intake", "scratch_kernel": str(ROOT),
       "checks": checks, "verdict": "PASS" if ok else "FAIL",
       "harness_note": "first script (bakeoff02_dryintake.py) "
                       "recorded dryintake-pos correctly, then "
                       "raised KeyError reading rec['verdict'] "
                       "instead of rec['result']['verdict']; "
                       "completed by bakeoff02_dryintake_fix.py; "
                       "the kernel intake path itself never "
                       "failed"}
(BASE / "evidence"
 / "bakeoff02_dryintake_record.json").write_text(
    json.dumps(out, indent=1))
print(json.dumps({"dry_intake": out["verdict"]}))
sys.exit(0 if ok else 1)
