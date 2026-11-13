"""Bake-off 02 instrument A (2026-11-13): one director
cycle with the CANDIDATE (Meta-Llama-3.1-8B-Instruct
Q4_K_M) over the SAME fixed observation packet as
bake-off 01 (evidence/bakeoff_packet.json, loaded
verbatim), through the attested server + ModelRouter +
DirectorLoop — preregistration PR #153 (LOCKED).

Judging (locked text, Reading S + hub ruling 16:07):
the cycle record's own status is telemetry only; the
verdict comes from the PINNED hardened citation
validator (PR #162) applied per-proposal to the raw
reply's proposals against the packet: ACCEPTED iff
ZERO proposals are rejected. The raw reply is captured
from the infer() channel (the loop's own whole-reply
parser would otherwise discard it). One attempt.
"""
import importlib.util
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, "/home/hatch/workspace/ace-omega/wt-resume/code")

from ace_operational.attested_server import spawn_attested_server
from ace_operational.cognitive_memory import CognitiveMemory
from ace_operational.director_loop import DirectorLoop, _extract_json
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

# Pre-warm the page cache (cold-cache lesson, 2026-11-13).
with open(GGUF, "rb") as fh:
    while fh.read(1 << 24):
        pass
print("model pre-warmed", flush=True)

observation = json.loads(
    (BASE / "evidence" / "bakeoff_packet.json").read_text())
print("packet loaded: fact_count", observation.get("fact_count"),
      flush=True)

vspec = importlib.util.spec_from_file_location(
    "citation_validator",
    "/home/hatch/workspace/ace-omega/wt-bakeoff02val/code/"
    "ace_operational/citation_validator.py")
validator = importlib.util.module_from_spec(vspec)
vspec.loader.exec_module(validator)

store = OperationalStore(BASE / "bakeoff02-store")
memory = CognitiveMemory(BASE / "bakeoff02-memory")
loop = DirectorLoop(BASE / "evidence" / "bakeoff02_agenda.json",
                    memory=memory)
process, attestation = spawn_attested_server(
    GGUF, SERVER_BIN, threads=4, health_timeout_s=600,
    log_path=BASE / "evidence" / "bakeoff02_a_server.log")
os.environ["ACE_LLAMA_SERVER_URL"] = attestation["server_url"]
try:
    router = ModelRouter(store)
    assert router.register_attestation(attestation)
    durations = []
    replies = []

    def infer(prompt: str) -> str:
        receipt = router.generate_text(
            [{"role": "user", "content": prompt}],
            target_model="Meta-Llama-3.1-8B", max_tokens=700,
            temperature=0.3, timeout_seconds=900)
        durations.append(receipt.get("duration_seconds"))
        text = receipt.get("text") or ""
        replies.append(text)
        return text

    t0 = time.time()
    record = loop.run_cycle(observation, infer)
    record["elapsed_seconds"] = round(time.time() - t0, 1)
    record["generation_durations"] = durations
    record["attestation"] = {k: attestation[k] for k in (
        "model_sha256", "binary_sha256", "model_id")}
    record["raw_reply"] = replies[0] if replies else ""

    # Pinned-validator judging over the raw reply's proposals.
    report = None
    extract_error = None
    raw_proposals = None
    try:
        data = _extract_json(record["raw_reply"])
        if isinstance(data, dict) and isinstance(
                data.get("proposals"), list):
            raw_proposals = data["proposals"]
    except Exception as exc:  # extraction failure = reply-level
        extract_error = f"{type(exc).__name__}: {exc}"
    if raw_proposals is not None:
        report = validator.validate_reply(
            packet=observation, proposals=raw_proposals,
            experiment_id="brain-bakeoff-02-A")
        accepted = not report["rejected_proposals"]
    else:
        accepted = False
    record["validator_report"] = report
    record["extract_error"] = extract_error
    record["raw_proposal_count"] = (
        len(raw_proposals) if raw_proposals is not None else None)
    record["instrument_A_accepted"] = accepted
    print("BAKEOFF02_A_RESULT " + json.dumps(
        {"loop_status": record.get("status"),
         "validator_accepted": accepted,
         "raw_proposals": record["raw_proposal_count"],
         "rejected": (report or {}).get("rejected_proposals"),
         "elapsed_seconds": record["elapsed_seconds"]},
        ensure_ascii=False), flush=True)
    _atomic_write((BASE / "evidence" / "bakeoff02_a_run.json"), json.dumps(record, indent=1, ensure_ascii=False))
    print("saved evidence/bakeoff02_a_run.json", flush=True)
finally:
    process.kill()
    print("server stopped", flush=True)
