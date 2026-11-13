"""Bake-off 02 post-lock step 2 — MANDATORY dry-intake
on a SCRATCH kernel (the real bakeoff02-kernel stays
pristine). Pushes synthetic results carrying
succession_margin through the kernel's verdict
derivation both ways (positive margin -> pass,
negative -> fail) and audits. If any expectation
fails, the post-lock sequence STOPS here.
"""
import json
import sys
from pathlib import Path

BASE = Path("/home/hatch/workspace/ace-omega")
sys.path.insert(0, str(BASE / "wt-bakeoff02val" / "code"))
from ace_operational.experiment_kernel import ExperimentKernel

ROOT = BASE / "bakeoff02-dryintake-kernel"
assert not ROOT.exists(), "scratch kernel already exists"

kernel = ExperimentKernel(
    ROOT, candidate_key=b"bakeoff02-dryintake-candidate-key",
    evaluator_key=b"bakeoff02-dryintake-evaluator-key")
artifact = b"synthetic-dryintake-candidate"
kernel.custody_candidate("synthetic-candidate", artifact)
kernel.custody_evaluator("synthetic-evaluator", b"synthetic",
                         b"synthetic-fixture")

checks = []
for exp_id, margin, claimed in (
        ("dryintake-pos", 0.25, "pass"),
        ("dryintake-neg", -0.75, "fail")):
    kernel.preregister(
        experiment_id=exp_id,
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
        experiment_id=exp_id, candidate_id="synthetic-candidate",
        candidate_artifact=artifact,
        metrics={"succession_margin": margin},
        claimed_verdict=claimed,
        raw_telemetry={"synthetic": True})
    audit = kernel.audit(exp_id)
    derived = rec["verdict"]
    checks.append({"experiment": exp_id, "margin": margin,
                   "claimed": claimed, "derived": derived,
                   "audit": audit["status"],
                   "ok": derived == claimed
                   and audit["status"] == "CLEAN"})
    print(exp_id, "derived", derived, "audit",
          audit["status"], "ok", checks[-1]["ok"])

ok = all(c["ok"] for c in checks)
out = {"step": "dry-intake", "scratch_kernel": str(ROOT),
       "checks": checks, "verdict": "PASS" if ok else "FAIL"}
(BASE / "evidence"
 / "bakeoff02_dryintake_record.json").write_text(
    json.dumps(out, indent=1))
print(json.dumps({"dry_intake": out["verdict"]}))
sys.exit(0 if ok else 1)
