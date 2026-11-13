"""Bake-off 02 instrument B (2026-11-13): the B2A-02
dossier with the CANDIDATE (Meta-Llama-3.1-8B-Instruct)
as director — same packet construction as bake-off 01
(build_packet(computed_table=True)), same router
config, one attempt. Preregistration PR #153 (LOCKED).

Judging: the dossier harness validates + scores the
decision (score_decision); the PINNED hardened citation
validator (PR #162) judges the decision reply's
citations against the packet's fact ids — ANY citation
violation zeroes the score outright (locked text SS4).
B's wall clock is the speed-margin input.
"""
import importlib.util
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, "/home/hatch/workspace/ace-omega/wt-b2a02/code")
sys.path.insert(0, "/home/hatch/workspace/ace-omega/wt-resume/code")

from ace_operational.attested_server import spawn_attested_server
from ace_operational.b2a_market import (DecisionRejected,
                                        build_dossiers,
                                        build_packet,
                                        render_prompt,
                                        score_decision,
                                        validate_decision)
from ace_operational.director_loop import _extract_json
from ace_operational.models_backend import ModelRouter
from ace_operational.store import OperationalStore


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
MODELS = BASE / "models"
GGUF = MODELS / "Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf"
SERVER_BIN = Path("/home/hatch/workspace/tools/llama.cpp/"
                  "llama-b12316/llama-server")
os.environ["ACE_MODEL_CACHE"] = str(MODELS)

with open(GGUF, "rb") as fh:
    while fh.read(1 << 24):
        pass
print("model pre-warmed", flush=True)

vspec = importlib.util.spec_from_file_location(
    "citation_validator",
    "/home/hatch/workspace/ace-omega/wt-bakeoff02val/code/"
    "ace_operational/citation_validator.py")
validator = importlib.util.module_from_spec(vspec)
vspec.loader.exec_module(validator)

dossiers = build_dossiers()
packet = build_packet(dossiers, computed_table=True)
prompt = render_prompt(packet)

store = OperationalStore(BASE / "bakeoff02-b-store")
process, attestation = spawn_attested_server(
    GGUF, SERVER_BIN, threads=4, health_timeout_s=600,
    log_path=BASE / "evidence" / "bakeoff02_b_server.log")
os.environ["ACE_LLAMA_SERVER_URL"] = attestation["server_url"]
try:
    router = ModelRouter(store)
    assert router.register_attestation(attestation)
    t0 = time.time()
    receipt = router.generate_text(
        [{"role": "user", "content": prompt}],
        target_model="Meta-Llama-3.1-8B", max_tokens=700,
        temperature=0.3, timeout_seconds=900)
    wall = round(time.time() - t0, 1)
    reply_text = receipt.get("text") or ""
    rejection = None
    try:
        decision = validate_decision(reply_text, packet)
    except DecisionRejected as exc:
        decision, rejection = None, str(exc)

    # Pinned-validator citation verdict over the raw decisions.
    report = None
    extract_error = None
    raw_decisions = None
    try:
        data = _extract_json(reply_text)
        if isinstance(data, dict) and isinstance(
                data.get("decisions"), list):
            raw_decisions = data["decisions"]
    except Exception as exc:
        extract_error = f"{type(exc).__name__}: {exc}"
    if raw_decisions is not None:
        report = validator.validate_reply(
            packet={"fact_ids": [f["id"] for f in packet["facts"]]},
            proposals=raw_decisions,
            experiment_id="brain-bakeoff-02-B")
    citation_violation = bool(
        report and report["rejected_proposals"])
    if decision is None or citation_violation:
        scores = score_decision(None, dossiers)
        scores["decision_score"] = 0.0
    else:
        scores = score_decision(decision, dossiers)
    out = {"experiment": "brain-bakeoff-02-B",
           "scores": scores, "decision": decision,
           "rejection": rejection, "wall_seconds": wall,
           "validator_report": report,
           "extract_error": extract_error,
           "citation_violation": citation_violation,
           "reply": reply_text,
           "receipt_success": receipt.get("success"),
           "attestation": {k: attestation[k] for k in (
               "model_sha256", "binary_sha256", "model_id")}}
    path = BASE / "evidence" / "bakeoff02_b_run.json"
    _atomic_write(path, json.dumps(out, indent=1, ensure_ascii=False))
    print("BAKEOFF02_B_RESULT " + json.dumps(
        {"scores": scores, "rejection": rejection,
         "citation_violation": citation_violation,
         "wall_seconds": wall}, ensure_ascii=False), flush=True)
    print("saved:", path, flush=True)
finally:
    process.kill()
    print("server stopped", flush=True)
