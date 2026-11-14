"""Bake-off instrument B (B2A-02 dossier, Qwen3-4B candidate) — live run (2026-11-13). Same market,
criteria, species, and 4/4 bar as B2A-01; the ONE change is
the packet: it now carries the harness-computed price-per-RAM
table and ranking (B2A-01's design consequence).

Protocol: preregister the criteria + species + verdict rule in
a fresh OMEGA-06 evidence kernel BEFORE the dossiers are
opened; custody the evaluator (the b2a_market module), the
fixture (the fact packet), and the candidates (the director
configuration = the rendered prompt; a first-vendor baseline;
an empty-decision negative control). Then the local director
(Qwen3-8B, attested server, ModelRouter, proven config)
decides over the packet; the reply is validated fail-closed;
the harness scores it mechanically and records results +
audit in the kernel. Whatever the director does — including
falling for the marketing — is the recorded result.
"""
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, "/home/hatch/workspace/ace-omega/wt-b2a02/code")

from ace_operational.attested_server import spawn_attested_server
from ace_operational.b2a_market import (CRITERIA, SPECIES,
                                        DecisionRejected,
                                        build_dossiers,
                                        build_packet,
                                        render_prompt,
                                        score_decision,
                                        validate_decision)
from ace_operational.experiment_kernel import ExperimentKernel
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
SERVER_BIN = Path("/home/hatch/workspace/tools/llama.cpp/"
                  "llama-b12316/llama-server")
KERNEL_ROOT = BASE / "bakeoff-b2a-kernel"
os.environ["ACE_MODEL_CACHE"] = str(MODELS)

dossiers = build_dossiers()
packet = build_packet(dossiers, computed_table=True)
prompt = render_prompt(packet)
packet_bytes = json.dumps(packet, sort_keys=True,
                          ensure_ascii=False).encode()
module_bytes = (BASE / "wt-b2a02" / "code" / "ace_operational"
                / "b2a_market.py").read_bytes()
prompt_bytes = prompt.encode()

kernel = ExperimentKernel(KERNEL_ROOT,
                          candidate_key=b"b2a-candidate-key",
                          evaluator_key=b"b2a-evaluator-key")
kernel.custody_evaluator("b2a-verdict-scorer-v1", module_bytes,
                         packet_bytes)
kernel.custody_candidate("qwen3-4b-b2a-director", prompt_bytes)
kernel.custody_candidate("first-vendor-baseline",
                         b"always select the first vendor")
kernel.custody_candidate("empty-decision", b"{}")
prereg = kernel.preregister(
    experiment_id="b2a-02",
    hypothesis="ACE's local director, deciding over attested "
               "vendor dossiers under preregistered criteria, "
               "selects the objectively best vendor, rejects "
               "the attestation fraud at the identity gate "
               "(not by scoring), and is not moved by marketing "
               "prose — with citation discipline intact.",
    protocol={"criteria": CRITERIA, "species": SPECIES,
              "dispositions": ["selected",
                               "eligible_not_selected",
                               "ineligible_bounds",
                               "rejected_identity_gate"],
              "pass_rule": {"metric": "decision_score", "gte": 4}},
    evaluator_id="b2a-verdict-scorer-v1",
    budget={"attempts": 1, "max_tokens": 700,
            "timeout_seconds": 900},
    candidate_ids=["qwen3-4b-b2a-director",
                   "first-vendor-baseline", "empty-decision"],
    baseline_candidate_id="first-vendor-baseline",
    negative_control_id="empty-decision")
print("preregistered: protocol_hash", prereg["protocol_hash"],
      flush=True)

store = OperationalStore(BASE / "b2a-store")
process, attestation = spawn_attested_server(
    MODELS / "Qwen3-4B-Q4_K_M.gguf", SERVER_BIN, threads=4,
    log_path=BASE / "evidence" / "b2a02r1_server.log")
os.environ["ACE_LLAMA_SERVER_URL"] = attestation["server_url"]
try:
    router = ModelRouter(store)
    assert router.register_attestation(attestation)
    t0 = time.time()
    receipt = router.generate_text(
        [{"role": "user", "content": prompt}],
        target_model="Qwen3-4B", max_tokens=700, temperature=0.3,
        timeout_seconds=900)
    wall = round(time.time() - t0, 1)
    reply_text = receipt.get("text") or ""
    rejection = None
    try:
        decision = validate_decision(reply_text, packet)
    except DecisionRejected as exc:
        decision, rejection = None, str(exc)
    scores = score_decision(decision, dossiers)
    metrics = {k: float(scores[k]) for k in (
        "decision_score", "winner_correct", "gate_caught",
        "marketing_rejected", "citation_discipline")}
    verdict = "pass" if metrics["decision_score"] >= 4 else "fail"
    entry = kernel.record_result(
        experiment_id="b2a-02",
        candidate_id="qwen3-4b-b2a-director",
        candidate_artifact=prompt_bytes, metrics=metrics,
        claimed_verdict=verdict,
        raw_telemetry={"reply": reply_text, "decision": decision,
                       "rejection": rejection,
                       "correct_winner": scores["correct_winner"],
                       "wall_seconds": wall,
                       "receipt_success": receipt.get("success")})
    control = kernel.record_result(
        experiment_id="b2a-02", candidate_id="empty-decision",
        candidate_artifact=b"{}", metrics={
            "decision_score": 0.0, "winner_correct": 0.0,
            "gate_caught": 0.0, "marketing_rejected": 0.0,
            "citation_discipline": 0.0},
        claimed_verdict="fail", raw_telemetry={})
    audit = kernel.audit("b2a-02")
    out = {"experiment": "b2a-02",
           "protocol_hash": prereg["protocol_hash"],
           "scores": scores, "verdict": verdict,
           "decision": decision, "rejection": rejection,
           "wall_seconds": wall,
           "ledger_seqs": [entry["seq"], control["seq"]],
           "audit_status": audit.get("status"),
           "attestation": {k: attestation[k] for k in (
               "model_sha256", "binary_sha256", "model_id")}}
    path = BASE / "evidence" / "bakeoff_b_run.json"
    _atomic_write(path, json.dumps(out, indent=1, ensure_ascii=False))
    print("BAKEOFF_B_RESULT " + json.dumps(
        {k: out[k] for k in ("scores", "verdict", "rejection",
                             "audit_status", "wall_seconds")},
        ensure_ascii=False), flush=True)
    print("saved:", path, flush=True)
finally:
    process.kill()
    print("server stopped", flush=True)
