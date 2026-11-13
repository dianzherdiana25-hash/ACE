"""Bake-off 02 finalize (2026-11-13): compose the three
instrument records under the LOCKED preregistered rule
(PR #153): margins A = +-1 (validator, Reading S);
B = (score - 2) / 2 with any citation violation zeroing
the score; C = (cases_passed - 3) / 3 against the sealed
evaluator run independently here; speed = (535.6 -
B wall) / 535.6. succession_margin = min of the four;
verdict pass iff margin >= 0. V-5: every rejection the
pinned validator emitted during A and B is appended to
the append-only rejection ledger in the experiment
kernel root and the chain verified. ONE result row is
recorded in bakeoff02-kernel; audit must read CLEAN.
"""
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, "/home/hatch/workspace/ace-omega/wt-bakeoff02val/code")

from ace_operational.experiment_kernel import ExperimentKernel
from ace_operational.models_backend import _gguf_expected_total_size


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


BASE = Path("/home/hatch/workspace/ace-omega")
GGUF = BASE / "models" / "Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf"
EXPECTED_SHA = ("7b064f5842bf9532c91456deda288a1b672397a54f"
                "a729aa665952863033557c")
INCUMBENT_B_WALL = 535.6
KERNEL_ROOT = BASE / "bakeoff02-kernel"

vspec = importlib.util.spec_from_file_location(
    "citation_validator",
    "/home/hatch/workspace/ace-omega/wt-bakeoff02val/code/"
    "ace_operational/citation_validator.py")
validator = importlib.util.module_from_spec(vspec)
vspec.loader.exec_module(validator)

measured = hashlib.sha256(GGUF.read_bytes()).hexdigest()
gate = {"sha256_matches_custodied_expectation":
        measured == EXPECTED_SHA,
        "measured_sha256": measured,
        "file_bytes": GGUF.stat().st_size,
        "gguf_expected_total_size":
        _gguf_expected_total_size(GGUF)}
gate["gguf_size_consistent"] = (
    gate["gguf_expected_total_size"] == gate["file_bytes"])

a = json.loads((BASE / "evidence" / "bakeoff02_a_run.json").read_text())
b = json.loads((BASE / "evidence" / "bakeoff02_b_run.json").read_text())
c = json.loads((BASE / "evidence" / "bakeoff02_c_run.json").read_text())

# Instrument C scored independently: sealed evaluator
# verbatim against the bake-off-02 worktree's akun.py.
env = dict(os.environ)
env["PYTHONPATH"] = str(BASE / "security-test" / "fixture-wt-bakeoff02")
ev = subprocess.run(
    [sys.executable,
     str(BASE / "security-test" / "evaluator" / "evaluator.py")],
    capture_output=True, text=True, env=env)
ev_lines = [ln for ln in ev.stdout.splitlines()
            if ln.startswith(("PASS", "FAIL"))]
c_passed = sum(1 for ln in ev_lines if ln.startswith("PASS"))
c_total = len(ev_lines)

a_ok = bool(a.get("instrument_A_accepted"))
b_score = float((b.get("scores") or {}).get("decision_score") or 0.0)
b_wall = float(b.get("wall_seconds") or 0.0)
margin_a = 1.0 if a_ok else -1.0
margin_b = (b_score - 2.0) / 2.0
margin_c = (c_passed - 3.0) / 3.0
margin_speed = (INCUMBENT_B_WALL - b_wall) / INCUMBENT_B_WALL
succession_margin = min(margin_a, margin_b, margin_c, margin_speed)
verdict = "pass" if (succession_margin >= 0 and all(
    gate[k] for k in ("sha256_matches_custodied_expectation",
                      "gguf_size_consistent"))) else "fail"

# V-5 rejection ledger (append-only, hash-chained).
ledger = validator.RejectionLedger()
for rec in (a, b):
    rep = rec.get("validator_report")
    if rep:
        ledger.append_report(rep)
ledger_check = ledger.verify()
_atomic_write((KERNEL_ROOT / "rejection_ledger.json"), json.dumps(
    {"schema": "ace.rejection_ledger.v1",
     "experiment": "brain-bakeoff-02",
     "entries": ledger.entries, "verify": ledger_check},
    indent=1, ensure_ascii=False))

kernel = ExperimentKernel(KERNEL_ROOT,
                          candidate_key=b"bakeoff02-candidate-key",
                          evaluator_key=b"bakeoff02-evaluator-key")
metrics = {"succession_margin": succession_margin,
           "A_margin": margin_a, "B_margin": margin_b,
           "C_margin": margin_c, "speed_margin": margin_speed,
           "B_wall_seconds": b_wall,
           "C_cases_passed": float(c_passed)}
instruments = {
    "A_director_cycle": {
        "validator_accepted": a_ok,
        "loop_status": a.get("status"),
        "raw_proposals": a.get("raw_proposal_count"),
        "rejected_proposals": (a.get("validator_report") or {}).get(
            "rejected_proposals"),
        "extract_error": a.get("extract_error"),
        "wall_seconds": a.get("elapsed_seconds")},
    "B_b2a02_dossier": {
        "decision_score": b_score,
        "citation_violation": b.get("citation_violation"),
        "harness_rejection": b.get("rejection"),
        "wall_seconds": b_wall},
    "C_repair_fixture": {
        "cases_passed": c_passed, "cases_total": c_total,
        "evaluator_exit": ev.returncode,
        "workflow_status": c.get("status"),
        "workflow_wall_seconds": c.get("wall_seconds")},
    "speed": {"bar": f"B wall < {INCUMBENT_B_WALL} s",
              "margin": margin_speed}}
entry = kernel.record_result(
    experiment_id="brain-bakeoff-02",
    candidate_id="llama-3.1-8b-challenger",
    candidate_artifact=(
        "Meta-Llama-3.1-8B-Instruct Q4_K_M GGUF, sha256 "
        + EXPECTED_SHA + ", 4920739232 bytes, custodied "
        "candidate kernel digest 396c050823028cc22a").encode(),
    metrics=metrics, claimed_verdict=verdict,
    raw_telemetry={"gate": gate, "instruments": instruments,
                   "rejection_ledger": {
                       "entries": len(ledger.entries),
                       "verify": ledger_check},
                   "evaluator_output_tail": ev.stdout[-800:]})
audit = kernel.audit("brain-bakeoff-02")

out = {"experiment": "brain-bakeoff-02",
       "protocol_hash": "6f2bfcd52d40d8302885c65cd894b274fb"
                        "36862116e7dede3ebe9ce340edb802",
       "verdict": verdict,
       "succession_margin": succession_margin,
       "margins": {"A": margin_a, "B": margin_b, "C": margin_c,
                   "speed": margin_speed},
       "gate": gate, "instruments": instruments,
       "rejection_ledger": {"entries": len(ledger.entries),
                            "verify": ledger_check},
       "ledger_seq": entry["seq"],
       "audit_status": audit.get("status"),
       "consequence": ("Llama-3.1-8B recorded as successor "
                       "director (registry swap per the locked "
                       "consequence rule)" if verdict == "pass"
                       else "Qwen3-8B stays on duty; Llama-3.1-8B "
                       "recorded as a measured candidate that did "
                       "not pass")}
_atomic_write((BASE / "evidence" / "bakeoff02_result.json"), json.dumps(out, indent=1, ensure_ascii=False))
print(json.dumps(out, indent=1, ensure_ascii=False))
