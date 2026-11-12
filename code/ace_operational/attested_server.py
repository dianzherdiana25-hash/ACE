"""Harness-attested local inference servers (Phase 2, stage E).

The workflow's evidence rule is that coding may only consume
inference whose model identity is digest-identified. A plain HTTP
llama.cpp server cannot attest its own artifact custody, so the
router's server receipts carry ``sha256: None`` and the workflow
refuses them — correctly, for a server it did not launch.

This module supplies the approved replacement mechanism (director
decision recorded in Addendum 26): when the *harness itself* spawns
the server, it records — before/at spawn — the SHA-256 of the model
file, the SHA-256 of the server binary, and the exact launch
parameters. A receipt may then bind to those digests. Every check is
fail-closed:

- an attestation whose recorded digests no longer match the files
  on disk (stat-keyed re-hash, same standard as the router's own
  digest cache) never matches;
- an attestation whose launch-parameter hash does not recompute
  never matches;
- a server whose URL or advertised model id differs from the
  attestation never matches;
- servers without an attestation keep the old behaviour exactly
  (``sha256: None``, workflow gate untouched for that path).
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.request import urlopen

ATTESTATION_SCHEMA = "ace.attested_server.v1"

_digest_cache: dict[tuple[str, int, int, int], str] = {}


def sha256_file(path: Path) -> str:
    """SHA-256 of a file, cached on (path, size, mtime_ns, ctime_ns).

    The stat key means any modification forces a re-hash, so a
    cached verification can never bless changed bytes.
    """
    stat = path.stat()
    key = (str(path.resolve()), stat.st_size, stat.st_mtime_ns,
           stat.st_ctime_ns)
    if key not in _digest_cache:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                digest.update(chunk)
        _digest_cache[key] = digest.hexdigest()
    return _digest_cache[key]


def _param_hash(model_sha256: str, binary_sha256: str,
                argv: list[str]) -> str:
    canonical = json.dumps({"argv": argv, "binary_sha256": binary_sha256,
                            "model_sha256": model_sha256},
                           sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def verify_attestation(attestation: dict[str, Any]) -> bool:
    """Recompute every recorded digest; True only on a full match."""
    try:
        if attestation.get("schema") != ATTESTATION_SCHEMA:
            return False
        if sha256_file(Path(attestation["model_path"])) \
                != attestation["model_sha256"]:
            return False
        if sha256_file(Path(attestation["binary_path"])) \
                != attestation["binary_sha256"]:
            return False
        if _param_hash(attestation["model_sha256"],
                       attestation["binary_sha256"],
                       list(attestation["launch_argv"])) \
                != attestation["launch_param_hash"]:
            return False
    except (KeyError, TypeError, OSError):
        return False
    return True


def match_attestation(attestations: list[dict[str, Any]], server_url: str,
                      advertised_model_id: str | None
                      ) -> dict[str, Any] | None:
    """The attestation covering this exact server, or None.

    Fail-closed on every axis: URL equality, advertised-id equality,
    and a fresh digest verification at match time.
    """
    for attestation in attestations:
        if attestation.get("server_url") != server_url:
            continue
        if advertised_model_id is not None and \
                attestation.get("model_id") not in (None,
                                                   advertised_model_id):
            continue
        if verify_attestation(attestation):
            return attestation
    return None


def save_attestation(attestation: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(attestation, indent=1), encoding="utf-8")


def load_attestation(path: Path) -> dict[str, Any] | None:
    """Load an attestation record, verifying digests before trust."""
    try:
        attestation = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(attestation, dict):
        return None
    return attestation if verify_attestation(attestation) else None


def _http_json(url: str, timeout: float = 3.0) -> dict[str, Any] | None:
    try:
        with urlopen(url, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception:
        return None


def spawn_attested_server(model_path: Path, binary_path: Path, *,
                          host: str = "127.0.0.1", port: int = 8081,
                          context: int = 4096, threads: int = 4,
                          kv_type: str = "q8_0",
                          log_path: Path | None = None,
                          health_timeout_s: float = 180.0
                          ) -> tuple[subprocess.Popen, dict[str, Any]]:
    """Spawn llama-server and record its attestation *before* use.

    Digests are computed before the process exists, so the record can
    never be influenced by the server. Raises on any failure and
    leaves no process behind.
    """
    model_path = Path(model_path)
    binary_path = Path(binary_path)
    model_sha256 = sha256_file(model_path)
    binary_sha256 = sha256_file(binary_path)
    argv = [str(binary_path), "-m", str(model_path),
            "--host", host, "--port", str(port),
            "-c", str(context), "-t", str(threads),
            "-ctk", kv_type, "-ctv", kv_type, "-fa", "on"]
    server_url = f"http://{host}:{port}"
    log_handle = None
    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_handle = log_path.open("ab")
    process = subprocess.Popen(argv, stdout=log_handle,
                               stderr=subprocess.STDOUT,
                               start_new_session=True)
    try:
        deadline = time.monotonic() + health_timeout_s
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(
                    f"attested server exited early rc={process.returncode}")
            health = _http_json(f"{server_url}/health", timeout=2.0)
            if health and health.get("status") == "ok":
                break
            time.sleep(1.5)
        else:
            raise RuntimeError("attested server did not become healthy")
        models = _http_json(f"{server_url}/v1/models", timeout=5.0) or {}
        entries = models.get("data") or []
        model_id = entries[0].get("id") if entries else None
        attestation = {
            "schema": ATTESTATION_SCHEMA,
            "server_url": server_url,
            "model_id": model_id,
            "model_path": str(model_path),
            "model_sha256": model_sha256,
            "binary_path": str(binary_path),
            "binary_sha256": binary_sha256,
            "launch_argv": argv,
            "launch_param_hash": _param_hash(model_sha256, binary_sha256,
                                             argv),
            "pid": process.pid,
            "spawned_by": "ace-harness",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        if not verify_attestation(attestation):
            raise RuntimeError("fresh attestation failed verification")
        return process, attestation
    except Exception:
        process.kill()
        raise
