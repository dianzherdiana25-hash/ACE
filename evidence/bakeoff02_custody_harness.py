"""Bake-off 02 post-lock step 1 — custodies on the fresh
kernel (bakeoff02-kernel). One-shot: refuses if the
root already exists. Custodies ONLY; preregistration
is step 3, after the mandatory dry-intake (step 2).
Locked text: ACE_BAKEOFF_02_PREREGISTRATION_20261113.md
sha256 8b2fa02e... (hub lock act 2026-11-13 19:51 WIB).
"""
import hashlib
import json
import sys
from pathlib import Path

BASE = Path("/home/hatch/workspace/ace-omega")
sys.path.insert(0, str(BASE / "wt-bakeoff02val" / "code"))
from ace_operational.experiment_kernel import ExperimentKernel

ROOT = BASE / "bakeoff02-kernel"
assert not ROOT.exists(), "kernel root already exists — one-shot"

kernel = ExperimentKernel(
    ROOT, candidate_key=b"bakeoff02-candidate-key",
    evaluator_key=b"bakeoff02-evaluator-key")

candidate_identity = {
    "role": "challenger",
    "model_file": "Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf",
    "size_bytes": 4920739232,
    "sha256": "7b064f5842bf9532c91456deda288a1b672397a54fa"
              "729aa665952863033557c",
    "repo": "bartowski/Meta-Llama-3.1-8B-Instruct-GGUF",
    "repo_revision": "bf5b95e96dac0462e2a09145ec66cae9a3f12067",
    "custody": "by identity per preregistration §6; artifact "
               "ACCEPTED on the VM 2026-11-13 (intake record "
               "evidence/bakeoff02_intake_record.json)",
}
cand = kernel.custody_candidate(
    "llama-3.1-8b-challenger",
    json.dumps(candidate_identity, sort_keys=True).encode())

incumbent_identity = {
    "role": "incumbent baseline",
    "model_file": "Qwen3-8B-Q4_K_M.gguf",
    "size_bytes": 5027783488,
    "sha256": "d98cdcbd03e17ce47681435b5150e34c1417f50b5c0019"
              "dd560e4882c5745785",
    "custody": "by identity per preregistration §6; bake-off 01 "
               "recorded numbers are the baseline (A accepted, "
               "B decision 4/4 wall 535.6 s, C 6/6)",
}
base = kernel.custody_candidate(
    "qwen3-8b-incumbent",
    json.dumps(incumbent_identity, sort_keys=True).encode())

validator_code = (BASE / "wt-bakeoff02val" / "code"
                  / "ace_operational"
                  / "citation_validator.py").read_bytes()
code_digest = hashlib.sha256(validator_code).hexdigest()
assert code_digest == ("b18e9d3a25b19f2d57797fafcd27d4e8d9b1d7"
                       "d10e6f530c2acd2559cc3700ba"), code_digest
fixture = {
    "instrument_A": "director-cycle packet, identical to "
                    "bake-off 01 (design C-2)",
    "instrument_B": "B2A-02 dossier packet with harness-computed "
                    "comparison table, identical to bake-off 01",
    "instrument_C": "sealed Keamanan-01 repair fixture, "
                    "identical to bake-off 01",
    "validator": {"name": "ace.citation_validator",
                  "version": "1.0.0",
                  "ruleset_digest": "59ce35e814d0b88f3d1d2ee3c"
                                    "fe3410d6ee3899dc8d99ff4ec2"
                                    "625ef2e689295",
                  "code_digest": code_digest,
                  "operative_semantics": "PER-PROPOSAL",
                  "instrument_A_bar": "Reading S — ACCEPTED iff "
                                      "zero proposals rejected"},
    "inference_path": "VM attested server, router config "
                      "temperature 0.3 / max_tokens 700 / "
                      "timeout 900 s (bake-off 01 proven config)",
}
ev, fx = kernel.custody_evaluator(
    "ace-citation-validator-v1", validator_code,
    json.dumps(fixture, sort_keys=True).encode())

out = {"step": "custodies", "kernel_root": str(ROOT),
       "candidate_digest_kernel": cand,
       "baseline_digest_kernel": base,
       "evaluator_digest": ev, "fixture_digest": fx,
       "validator_code_digest": code_digest}
(BASE / "evidence"
 / "bakeoff02_custody_record.json").write_text(
    json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
