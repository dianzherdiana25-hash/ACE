"""Bake-off instrument A (2026-11-13): one director cycle
with the CANDIDATE (Qwen3-4B) over a FIXED observation
packet, through the attested server + ModelRouter +
fail-closed DirectorLoop — the same machinery as cycles
1-4 (which the incumbent passed: ACCEPTED). Scratch agenda
and scratch cognitive memory: a bake-off must not write
the candidate's proposals into ACE's real director memory.
Bar (preregistered, bakeoff-kernel 7db09764...): the
cycle record's status is ACCEPTED.
"""
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, "/home/hatch/workspace/ace-omega/wt-resume/code")

from ace_operational.attested_server import spawn_attested_server
from ace_operational.cognitive_memory import CognitiveMemory
from ace_operational.director_loop import DirectorLoop, build_observation
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
os.environ["ACE_MODEL_CACHE"] = str(MODELS)

observation = build_observation(
    gates={"G0": "PASS_SESSION_SCOPED",
           "G1": "MEASURED_DEMONSTRATED_UNQUALIFIED",
           "G2": "MEASURED_NULL_X2", "G3": "NOT_ASSESSED",
           "G4": "NOT_ASSESSED", "G5": "NOT_ASSESSED",
           "OAIE": "UNPROVEN"},
    gaps=[
        {"id": "gap-g3-application",
         "what": "Instrumen G3 terbangun dan terverifikasi "
                 "(PR #143), tetapi aplikasi pertamanya butuh "
                 "prasyarat P1 (decouple run_discovery dari "
                 "keluarga grid) dan teks praregistrasi"},
        {"id": "gap-g4-g5-instruments",
         "what": "Instrumen G4 dan G5 baru berupa desain "
                 "(PR #136); implementasinya belum dibangun"},
        {"id": "gap-abc-arms",
         "what": "Lengan A/B/C belum terbedakan oleh strategi "
                 "pada semesta tak-jenuh; desain v3 belum ditulis"},
        {"id": "gap-facebook-mission",
         "what": "Syarat misi $500 Facebook Pro belum terbaca "
                 "(panel hanya bisa ditunjukkan pemilik); "
                 "produksi konten menunggu verifikasi"},
        {"id": "gap-brain-succession",
         "what": "Suksesi direktur lokal sedang diuji banding "
                 "terpraregistrasi; kursi berpindah hanya bila "
                 "kandidat lulus ambang keandalan + kecepatan"},
    ],
    results=[
        {"id": "composition-v2",
         "summary": "Penemuan komposisi v2: rantai 3/6 vs "
                    "pasangan 0/6 pada tugas yang sama; "
                    "transfer tunggal naik 11 ke 15; kontrol "
                    "34/34 (PR #140)"},
        {"id": "b2a02-pass",
         "summary": "Uji B2A-02 LULUS 4/4 dengan tabel "
                    "perbandingan terhitung harness; audit "
                    "CLEAN (PR #141)"},
        {"id": "g3-instrument-verified",
         "summary": "Instrumen G3 dibangun Ian, diverifikasi "
                    "TAHAN oleh dua pos independen; dua "
                    "temuan minor terkoreksi (PR #143)"},
        {"id": "opportunity-register",
         "summary": "Register peluang dibuka: 12 aset "
                    "terdaftar, entri #1 asal FOUNDER, pangsa "
                    "sintesis sisi-ACE baseline 0,0 (PR #142)"},
    ])
packet_path = BASE / "evidence" / "bakeoff_packet.json"
_atomic_write(packet_path, json.dumps(observation, indent=1,
                                  ensure_ascii=False))
print("fixed packet saved:", packet_path, flush=True)

store = OperationalStore(BASE / "bakeoff-store")
memory = CognitiveMemory(BASE / "bakeoff-memory")
loop = DirectorLoop(BASE / "evidence" / "bakeoff_agenda.json",
                    memory=memory)
process, attestation = spawn_attested_server(
    MODELS / "Qwen3-4B-Q4_K_M.gguf", SERVER_BIN, threads=4,
    log_path=BASE / "evidence" / "bakeoff_a_server.log")
os.environ["ACE_LLAMA_SERVER_URL"] = attestation["server_url"]
try:
    router = ModelRouter(store)
    assert router.register_attestation(attestation)
    durations = []

    def infer(prompt: str) -> str:
        receipt = router.generate_text(
            [{"role": "user", "content": prompt}],
            target_model="Qwen3-4B", max_tokens=700,
            temperature=0.3, timeout_seconds=900)
        durations.append(receipt.get("duration_seconds"))
        return receipt.get("text") or ""

    t0 = time.time()
    record = loop.run_cycle(observation, infer)
    record["elapsed_seconds"] = round(time.time() - t0, 1)
    record["generation_durations"] = durations
    record["attestation"] = {k: attestation[k] for k in (
        "model_sha256", "binary_sha256", "model_id")}
    print("BAKEOFF_A_RESULT " + json.dumps(
        {k: record.get(k) for k in ("cycle", "status",
                                    "proposals",
                                    "elapsed_seconds")},
        ensure_ascii=False)[:1200], flush=True)
    _atomic_write((BASE / "evidence" / "bakeoff_a_run.json"), json.dumps(record, indent=1, ensure_ascii=False))
finally:
    process.kill()
    print("server stopped", flush=True)
