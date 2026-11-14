"""Bake-off 02 post-lock step 3 — preregister the
LOCKED text on bakeoff02-kernel (custodies from
step 1, dry-intake PASS in step 2). One-shot per
experiment id; records the protocol hash.
"""
import hashlib
import json
import secrets
import sys
from pathlib import Path

BASE = Path("/home/hatch/workspace/ace-omega")
sys.path.insert(0, str(BASE / "wt-bakeoff02val" / "code"))
from ace_operational.experiment_kernel import ExperimentKernel

ROOT = BASE / "bakeoff02-kernel"
assert ROOT.exists(), "custody step must run first"
text = (BASE / "wt-bakeoff02prereg" / "docs" / "research"
        / "ACE_BAKEOFF_02_PREREGISTRATION_20261113.md"
        ).read_bytes()
text_sha = hashlib.sha256(text).hexdigest()
assert text_sha == ("8b2fa02e6ec2c7b71f22ad8a708d6b952027ee62"
                    "d46aa2128bcadbe8ccfd3dd0"), text_sha

kernel = ExperimentKernel(
    ROOT, candidate_key=b"bakeoff02-candidate-key",
    evaluator_key=b"bakeoff02-evaluator-key")
canary = "CANARY-BAKEOFF02-" + secrets.token_hex(2)
record = kernel.preregister(
    experiment_id="brain-bakeoff-02",
    hypothesis="Meta-Llama-3.1-8B-Instruct Q4_K_M passes "
               "instruments A (director cycle, Reading S: zero "
               "proposals rejected), B (B2A-02 dossier 4/4, "
               "wall < 535.6 s) and C (sealed repair 6/6) with "
               "succession_margin >= 0 against the incumbent "
               "Qwen3-8B's bake-off 01 numbers.",
    protocol={
        "preregistration_text_sha256": text_sha,
        "pass_rule": {"metric": "succession_margin", "gte": 0},
        "instrument_A_bar": "Reading S (hub act 2026-11-13 "
                            "19:50 WIB): ACCEPTED iff zero "
                            "proposals rejected under "
                            "PER-PROPOSAL semantics",
        "validator": "ace.citation_validator v1.0.0, "
                     "code_digest b18e9d3a25b19f2d57797fafcd"
                     "27d4e8d9b1d7d10e6f530c2acd2559cc3700ba",
        "inference_path": "VM attested server; sandbox bench "
                          "numbers excluded",
        "dry_intake": "PASS (evidence/"
                      "bakeoff02_dryintake_record.json)"},
    evaluator_id="ace-citation-validator-v1",
    budget={"wall_seconds": 7200},
    candidate_ids=["llama-3.1-8b-challenger",
                   "qwen3-8b-incumbent"],
    baseline_candidate_id="qwen3-8b-incumbent",
    negative_control_id=None,
    canary_tokens=[canary])
out = {"experiment": "brain-bakeoff-02",
       "text_sha256": text_sha,
       "kernel_protocol_hash": record["protocol_hash"],
       "canary": canary, "budget_wall_seconds": 7200,
       "budget_note": "kernel-side execution metadata set at "
                      "lock; the locked text fixes the pass "
                      "rule, not the wall budget"}
(BASE / "evidence"
 / "bakeoff02_preregistration_record.json").write_text(
    json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
