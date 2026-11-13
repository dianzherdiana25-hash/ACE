"""Bake-off 02 instrument C (2026-11-13): the sealed
Keamanan-01 repair fixture through the OFFICIAL path
with the CANDIDATE (Meta-Llama-3.1-8B-Instruct) —
LocalRepoWorkflow (sandbox v2) + attested server, on a
FRESH worktree of the pristine fixture (branch
eksperimen/keamanan-bakeoff02) and a fresh store.
Mirror of bake-off 01's instrument C; the sealed
evaluator is untouched and scores independently in
the finalize step. Preregistration PR #153 (LOCKED).
"""
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, "/home/hatch/workspace/ace-omega/wt-schemexp/code")

from ace_operational.attested_server import save_attestation, \
    spawn_attested_server
from ace_operational.local_repo_workflow import LocalRepoWorkflow
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


BASE = Path("/home/hatch/workspace/ace-omega/security-test")
MODELS = Path("/home/hatch/workspace/ace-omega/models")
GGUF = MODELS / "Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf"
BIN = Path("/home/hatch/workspace/tools/llama.cpp/llama-b12316/llama-server")

with open(GGUF, "rb") as fh:
    while fh.read(1 << 24):
        pass
print("model pre-warmed", flush=True)

process, attestation = spawn_attested_server(
    GGUF, BIN, threads=4, health_timeout_s=600,
    log_path=Path("/home/hatch/workspace/ace-omega/evidence/"
                  "bakeoff02_c_server.log"))
print("attested server up:", attestation["server_url"],
      "| model_id:", attestation["model_id"], flush=True)
save_attestation(attestation, Path(
    "/home/hatch/workspace/ace-omega/evidence/"
    "attestation_bakeoff02_c.json"))
os.environ["ACE_LLAMA_SERVER_URL"] = attestation["server_url"]

try:
    store = OperationalStore(BASE / "store-bakeoff02")
    router = ModelRouter(store)
    assert router.register_attestation(attestation), \
        "attestation failed router verification"
    workflow = LocalRepoWorkflow(store, router=router)
    t0 = time.monotonic()
    result = workflow.run(
        repository=BASE / "fixture-wt-bakeoff02",
        issue=("Uji keamanan gagal pada modul akun.py. Fungsi "
               "cari_pengguna membangun query SQL dengan f-string "
               "dari input nama, sehingga injeksi SQL bisa "
               "membocorkan baris pengguna lain (mis. tautologi "
               "' OR '1'='1 atau UNION SELECT) dan merusak tabel. "
               "Perbaiki akun.py agar query aman terhadap injeksi "
               "dengan parameterisasi. Pertahankan API buat_db dan "
               "cari_pengguna serta perilaku fungsional persis: "
               "nama yang cocok mengembalikan (id, nama, peran); "
               "nama tak dikenal mengembalikan None; tabel tidak "
               "boleh rusak oleh input apa pun."),
        evaluator_dir=BASE / "evaluator",
        max_attempts=3, max_tokens=512, wall_budget_seconds=1200,
        patch_format="symbol")
    result["wall_seconds"] = round(time.monotonic() - t0, 1)
    result["attestation"] = {k: attestation[k] for k in (
        "model_sha256", "binary_sha256", "launch_param_hash",
        "model_id", "server_url")}
    out = Path("/home/hatch/workspace/ace-omega/evidence/"
               "bakeoff02_c_run.json")
    _atomic_write(out, json.dumps(result, indent=1, default=str))
    print("STATUS:", result.get("status"))
    print("attempts:", len(result.get("attempts", [])))
    print("wall:", result["wall_seconds"], "s | saved:", out)
finally:
    process.kill()
    print("attested server stopped", flush=True)
