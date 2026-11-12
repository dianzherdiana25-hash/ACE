"""Multi-backend Model Router and Offline Guard (Sections 22, 25-27, Appendix M).

Implements:
- `ModelBackend` unified contract (`generate_text`, `generate_structured`, `health_check`, `capabilities`)
- Local GGUF / llama.cpp backend discovery with SHA-256 verification and RAM budget check (`A44`)
- Truthful inference receipts persisted in the existing OperationalStore
- Explicit failures instead of fabricated deterministic work or structured success
- Strict offline enforcement (`allow_remote_in_offline_mode: false`, `A07`, `WEB17`)
- Bounded JSON schema validation and malformed-JSON extraction/repair (`A43`)
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import uuid
try:
    import resource
except ImportError:  # Windows does not expose POSIX child resource counters.
    resource = None
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
from typing import Any

from .attested_server import load_attestation, match_attestation, \
    verify_attestation
from .brain_registry import BrainRegistry
from .store import OperationalStore


def get_available_ram_mb() -> int:
    """Available host memory capped by remaining Linux cgroup-v2 memory."""
    available = 2048
    try:
        lines = Path("/proc/meminfo").read_text(encoding="utf-8").splitlines()
        for key in ("MemAvailable:", "MemFree:"):
            match = next((line for line in lines if line.startswith(key)), None)
            if match:
                available = int(match.split()[1]) // 1024
                break
    except (OSError, ValueError, IndexError):
        pass
    # The mounted cgroup can be a container root; include nested process groups.
    group_dirs = {Path("/sys/fs/cgroup")}
    try:
        for line in Path("/proc/self/cgroup").read_text().splitlines():
            if line.startswith("0::"):
                relative = line[3:].lstrip("/")
                nested = Path("/sys/fs/cgroup") / relative
                if ".." not in nested.parts:
                    group_dirs.update([nested, *nested.parents])
    except OSError:
        pass
    for directory in group_dirs:
        if not str(directory).startswith("/sys/fs/cgroup"):
            continue
        try:
            limit = (directory / "memory.max").read_text().strip()
            if limit != "max":
                used = int((directory / "memory.current").read_text().strip())
                available = min(available, max(0, int(limit) - used) // (1024 * 1024))
        except (OSError, ValueError):
            continue
    return available


def extract_and_repair_json(raw_text: str, required_keys: list[str] | None = None) -> dict[str, Any]:
    """Bounded malformed-JSON parser and repairer (`A43`).

    Handles markdown code fences, trailing commas,
    or truncated closing braces, and validates required keys.
    """
    if not isinstance(raw_text, str) or not raw_text.strip():
        raise ValueError("Respons JSON kosong")

    cleaned = raw_text.strip()
    # Strip markdown ```json ... ``` fences
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, flags=re.DOTALL)
    if fence_match:
        cleaned = fence_match.group(1).strip()
    else:
        first_brace = cleaned.find("{")
        last_brace = cleaned.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            cleaned = cleaned[first_brace : last_brace + 1]
        elif first_brace != -1 and last_brace == -1:
            # Attempt bounded bracket completion for truncated JSON object
            cleaned = cleaned[first_brace:] + "}"

    # Remove trailing commas before } or ]
    cleaned_no_trailing = re.sub(r",\s*([}\]])", r"\1", cleaned)

    parsed: dict[str, Any] | None = None
    for candidate in (cleaned, cleaned_no_trailing):
        try:
            obj = json.loads(candidate)
            if isinstance(obj, dict):
                parsed = obj
                break
        except Exception:
            continue

    if parsed is None:
        raise ValueError(f"Gagal mengurai JSON terstruktur setelah pemulihan terbatas: {raw_text[:120]}")

    if required_keys:
        missing = [k for k in required_keys if k not in parsed]
        if missing:
            raise ValueError(f"Field JSON wajib tidak lengkap: kurang {missing}")

    return parsed


class CircuitBreaker:
    """Trips on consecutive remote failures, quota limits, auth errors, or timeouts (`A41`, `A42`)."""

    def __init__(self, failure_threshold: int = 2, cooldown_seconds: float = 120.0):
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.failure_count = 0
        self.last_error_reason = ""
        self.tripped_until = 0.0

    def is_open(self) -> bool:
        if self.tripped_until <= 0:
            return False
        if time.time() >= self.tripped_until:
            self.tripped_until = 0.0
            self.failure_count = 0
            return False
        return True

    def record_failure(self, reason: str, immediate_trip: bool = False) -> None:
        self.failure_count += 1
        self.last_error_reason = reason
        lower = reason.lower()
        if immediate_trip or any(k in lower for k in ("quota", "429", "rate limit", "401", "403", "unauthorized", "offline")):
            self.tripped_until = time.time() + self.cooldown_seconds
        elif self.failure_count >= self.failure_threshold:
            self.tripped_until = time.time() + self.cooldown_seconds

    def record_success(self) -> None:
        self.failure_count = 0
        self.tripped_until = 0.0
        self.last_error_reason = ""


def _compute_sha256_stream(file_path: Path, chunk_size: int = 65536) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as fp:
        while chunk := fp.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


class _NoLocalRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise HTTPError(req.full_url, code, "Local inference redirects are forbidden", headers, fp)


def _loopback_url(raw_url: str) -> str:
    """Normalize a literal loopback endpoint; never resolve an arbitrary hostname."""
    parts = urlsplit(raw_url)
    if (parts.scheme not in ("http", "https") or parts.username or parts.password
            or parts.query or parts.fragment or parts.path not in ("", "/")):
        raise ValueError("ACE_LLAMA_SERVER_URL must be a loopback HTTP origin")
    host = parts.hostname or ""
    if host == "localhost":
        host = "127.0.0.1"
    try:
        if not ipaddress.ip_address(host).is_loopback:
            raise ValueError("Inference endpoint is not loopback")
    except ValueError as exc:
        raise ValueError("Inference endpoint must use localhost or a loopback IP") from exc
    host = f"[{host}]" if ":" in host else host
    return f"{parts.scheme}://{host}" + (f":{parts.port}" if parts.port else "")


def _local_json(url: str, *, body: dict[str, Any] | None = None, timeout: float = 0.6) -> dict[str, Any]:
    # Inherited cloud proxies must never receive local prompts or health checks.
    opener = build_opener(ProxyHandler({}), _NoLocalRedirect())
    request = Request(url, headers={"Content-Type": "application/json", "User-Agent": "ACE/omega"},
                      data=None if body is None else json.dumps(body).encode("utf-8"))
    with opener.open(request, timeout=timeout) as response:
        raw = response.read(4 * 1024 * 1024 + 1)
        if len(raw) > 4 * 1024 * 1024:
            raise ValueError("Local inference response exceeds 4 MiB")
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise ValueError("Local inference response is not an object")
        return result


class _ThinkingBudgetExhausted(Exception):
    """The server spent the whole token budget inside reasoning and produced no final content."""


# GGML tensor types: id -> (elements per block, bytes per block). Plain types use block size 1.
_GGUF_TYPE_BLOCKS: dict[int, tuple[int, int]] = {
    0: (1, 4),      # F32
    1: (1, 2),      # F16
    2: (32, 18),    # Q4_0
    3: (32, 20),    # Q4_1
    6: (32, 22),    # Q5_0
    7: (32, 24),    # Q5_1
    8: (32, 34),    # Q8_0
    9: (32, 36),    # Q8_1
    10: (256, 84),  # Q2_K
    11: (256, 110), # Q3_K
    12: (256, 144), # Q4_K
    13: (256, 176), # Q5_K
    14: (256, 210), # Q6_K
    15: (256, 292), # Q8_K
    16: (1, 1),     # I8
    17: (1, 2),     # I16
    18: (1, 4),     # I32
    19: (1, 8),     # I64
    20: (1, 8),     # F64
    30: (1, 2),     # BF16
}
_GGUF_SCALAR_SIZES = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4, 6: 4, 7: 1, 10: 8, 11: 8, 12: 8}


def _estimated_ram_mb(size_bytes: int) -> int:
    """Admission estimate for running a GGUF with llama.cpp on this class of host.

    Basis (measured 2026-11-12, llama.cpp b12316, ctx 4096, q8_0 KV): the
    Qwen3-8B Q4_K_M server peaked at RSS/file ratio 1.06. The previous flat
    1.25x multiplier never admitted that model on the operator VM even though
    it demonstrably runs there, silently demoting routing to a 3B baseline.
    Estimate is therefore file size + 12.5% (about twice the measured
    overhead), floored at 256 MB; the caller's available-RAM figure is
    already capped by the cgroup-v2 remainder, which stays the hard guard.
    """
    size_mb = size_bytes // (1024 * 1024)
    return max(256, size_mb + size_mb // 8)


def _gguf_expected_total_size(path: Path) -> int | None:
    """Compute the exact file size a GGUF header declares, or None when a tensor
    type is unknown to this checker (size then stays unverified, never assumed).

    Raises ValueError for a malformed header. A truncated download keeps a valid
    magic and header, so magic-only admission is not structural validation: the
    declared tensor layout must account for every byte of the file.

    The parser is total: arbitrary file content must surface as ValueError
    (which discovery records as a corrupted model), never as an uncaught
    struct.error/OverflowError from absurd header counts or offsets.
    """
    import struct

    try:
        return _gguf_expected_total_size_inner(path, struct)
    except (struct.error, OverflowError) as exc:
        raise ValueError(f"malformed_gguf_header: {exc}") from exc


def _gguf_expected_total_size_inner(path: Path, struct: Any) -> int | None:
    with path.open("rb") as stream:
        def read_exact(n: int) -> bytes:
            data = stream.read(n)
            if len(data) != n:
                raise ValueError("truncated_gguf_header")
            return data

        def u32() -> int:
            return struct.unpack("<I", read_exact(4))[0]

        def u64() -> int:
            return struct.unpack("<Q", read_exact(8))[0]

        def gguf_string() -> bytes:
            return read_exact(u64())

        def skip_value(vtype: int) -> None:
            if vtype == 8:  # STRING
                gguf_string()
            elif vtype == 9:  # ARRAY
                elem_type = u32()
                count = u64()
                if elem_type == 8:
                    for _ in range(count):
                        gguf_string()
                else:
                    stream.seek(_GGUF_SCALAR_SIZES[elem_type] * count, 1)
            else:
                stream.seek(_GGUF_SCALAR_SIZES[vtype], 1)

        if read_exact(4) != b"GGUF":
            raise ValueError("invalid_gguf_magic")
        version = u32()
        if version not in (2, 3):
            raise ValueError(f"unsupported_gguf_version:{version}")
        tensor_count = u64()
        kv_count = u64()
        if tensor_count > 10_000_000 or kv_count > 10_000_000:
            raise ValueError("gguf_counts_implausible")
        alignment = 32
        for _ in range(kv_count):
            key = gguf_string()
            vtype = u32()
            if key == b"general.alignment" and vtype == 4:
                alignment = u32()
            else:
                skip_value(vtype)
        data_end = 0
        verifiable = True
        for _ in range(tensor_count):
            gguf_string()  # tensor name
            n_dims = u32()
            elements = 1
            for _ in range(n_dims):
                elements *= u64()
            ttype = u32()
            offset = u64()
            block = _GGUF_TYPE_BLOCKS.get(ttype)
            if block is None:
                verifiable = False
                continue
            per_block, block_bytes = block
            if elements % per_block:
                raise ValueError("gguf_tensor_not_block_aligned")
            data_end = max(data_end, offset + elements // per_block * block_bytes)
        if not verifiable:
            return None
        header_end = stream.tell()
        data_start = (header_end + alignment - 1) // alignment * alignment
        return data_start + data_end


class ModelRouter:
    """Local inference with explicit failure and durable, attributable receipts.

    A response's ``success`` means inference/validation completed, never that the
    requested task was executed or independently verified. No synthetic fallback
    is an inference backend. Existing deterministic tools remain in CodingAgentLoop.
    """

    def __init__(self, store: OperationalStore):
        self.store = store
        self.circuit_breaker = CircuitBreaker()
        default_cache = self.store.workspace / "models"
        self.model_cache_dir = Path(os.environ.get("ACE_MODEL_CACHE", str(default_cache))).expanduser()
        self.model_cache_dir.mkdir(parents=True, exist_ok=True)
        self._digest_cache: dict[tuple[str, int, int, int], str] = {}
        # Harness-attested servers (stage E): only servers this
        # harness spawned and digest-recorded may produce identified
        # receipts. ACE_ATTESTATION_FILE lets a spawning process hand
        # the record across a process boundary; the record is
        # digest-verified at load and again at match time.
        self.attestations: list[dict[str, Any]] = []
        attestation_file = os.environ.get("ACE_ATTESTATION_FILE")
        if attestation_file:
            loaded = load_attestation(Path(attestation_file).expanduser())
            if loaded is not None:
                self.attestations.append(loaded)
        # Multi-brain sovereignty (stage G): an optional brain
        # registry whose dismissals this router enforces fail-closed.
        self.brain_registry: BrainRegistry | None = None
        registry_file = os.environ.get("ACE_BRAIN_REGISTRY_FILE")
        if registry_file:
            self.brain_registry = BrainRegistry(
                Path(registry_file).expanduser())

    def register_attestation(self, attestation: dict[str, Any]) -> bool:
        """Register a harness attestation; False if it does not verify."""
        if not verify_attestation(attestation):
            return False
        self.attestations.append(attestation)
        return True

    def _digest(self, path: Path) -> str:
        stat = path.stat()
        key = (str(path.resolve()), stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
        if key not in self._digest_cache:
            self._digest_cache[key] = _compute_sha256_stream(path)
        return self._digest_cache[key]

    def discover_local_gguf(self, candidate_dirs: list[Path] | None = None) -> dict[str, Any]:
        """Inspect GGUF files and a completion binary; HTTP health alone proves no capability."""
        search_paths = [os.environ.get("ACE_LLAMA_BIN"), os.environ.get("LLAMA_BIN"),
                        shutil.which("llama-completion"), shutil.which("llama-cli")]
        cli_bin = next((str(p) for p in search_paths if p and "llama-server" not in Path(p).name
                        and (shutil.which(p) or (Path(p).is_file() and os.access(p, os.X_OK)))), "")
        endpoint_error = ""
        server_healthy = False
        server_url = ""
        server_models: list[dict[str, Any]] = []
        try:
            server_url = _loopback_url(os.environ.get("ACE_LLAMA_SERVER_URL", "http://127.0.0.1:8081"))
            health = _local_json(f"{server_url}/health")
            server_healthy = health.get("status") == "ok"
            if server_healthy:
                models = _local_json(f"{server_url}/v1/models").get("data", [])
                server_models = [m for m in models if isinstance(m, dict) and isinstance(m.get("id"), str)]
        except Exception as exc:
            endpoint_error = f"{type(exc).__name__}: {exc}"
        if candidate_dirs is None:
            candidate_dirs = [self.model_cache_dir, self.store.workspace / "models"]
            legacy_cache = Path.home() / ".cache" / "ace" / "models"
            if "ACE_MODEL_CACHE" not in os.environ and legacy_cache.exists():
                candidate_dirs.append(legacy_cache)
        candidate_dirs = list(dict.fromkeys(Path(d) for d in candidate_dirs))
        expected_hashes: dict[str, str] = {}
        manifest_errors = []
        for directory in candidate_dirs:
            manifest_path = directory / "manifest.json"
            if manifest_path.exists():
                try:
                    manifest = json.loads(manifest_path.read_text())
                    if not isinstance(manifest, dict):
                        raise ValueError("Model manifest must be an object")
                    entries = manifest.get("sha256", {})
                    if not isinstance(entries, dict) or any(not isinstance(v, str) for v in entries.values()):
                        raise ValueError("manifest sha256 must map model names to digest strings")
                    expected_hashes.update(entries)
                except (OSError, ValueError, TypeError) as exc:
                    manifest_errors.append({"file": str(manifest_path), "reason": str(exc)})
        available = get_available_ram_mb()
        valid_models, corrupted_models, ram_warnings = [], [], []
        seen = set()
        for directory in candidate_dirs:
            for path in sorted(directory.glob("*.gguf")):
                if path.resolve() in seen:
                    continue
                seen.add(path.resolve())
                try:
                    size = path.stat().st_size
                    expected_total = _gguf_expected_total_size(path)
                    if expected_total is not None and expected_total != size:
                        raise ValueError(f"gguf_size_mismatch expected={expected_total} actual={size}")
                    expected = expected_hashes.get(path.name, "")
                    digest = self._digest(path) if expected else ""
                    if expected and digest.lower() != expected.lower():
                        raise ValueError("checksum_mismatch")
                    estimate = _estimated_ram_mb(size)
                    entry = {"name": path.name, "path": str(path), "size_bytes": size,
                             "estimated_ram_mb": estimate, "fits_ram": estimate <= available,
                             "sha256": digest, "checksum_verified": bool(expected),
                             "size_verified": expected_total is not None,
                             "expected_size_bytes": expected_total}
                    valid_models.append(entry)
                    if not entry["fits_ram"]:
                        ram_warnings.append({"file": path.name, "estimated_ram_mb": estimate,
                                             "available_ram_mb": available})
                except (OSError, ValueError) as exc:
                    corrupted_models.append({"file": str(path), "reason": str(exc)})
        return {"llama_binary": cli_bin, "server_url": server_url if server_healthy else "",
                "server_healthy": server_healthy, "server_models": server_models,
                "endpoint_error": endpoint_error, "valid_models": valid_models,
                "corrupted_models": corrupted_models, "manifest_errors": manifest_errors,
                "ram_warnings": ram_warnings, "available_ram_mb": available,
                "ready": bool(server_healthy or (cli_bin and any(m["fits_ram"] for m in valid_models)))}

    def check_ram_budget_for_model(self, required_ram_mb: int) -> dict[str, Any]:
        available = get_available_ram_mb()
        allowed = 0 <= required_ram_mb <= available
        return {"allowed": allowed, "available_ram_mb": available, "required_ram_mb": required_ram_mb,
                "fallback_backend": None,
                "warning_id": "" if allowed else "RAM model melebihi batas; inferensi diblokir tanpa fallback palsu."}

    def health_check(self) -> dict[str, Any]:
        gguf = self.discover_local_gguf()
        offline = self.store.is_offline()
        fitting = [m for m in gguf["valid_models"] if m["fits_ram"]]
        if gguf["server_healthy"]:
            backend = f"local-gguf-server:{gguf['server_url']}"
        elif gguf["llama_binary"] and fitting:
            backend = f"local-gguf:{max(fitting, key=lambda m: m['size_bytes'])['name']}"
        else:
            backend = "unavailable"
        return {"active_backend": backend, "mode": "offline" if offline else "local",
                "profile": self.store.get_meta("profile", "local-complete"), "offline_mode": offline,
                "egress_attempts_blocked": int(self.store.get_meta("egress_attempts_blocked", "0") or "0"),
                "local_gguf": gguf,
                "local_deterministic": {"backend_id": "local-deterministic-v4", "ready": False,
                                        "capabilities": [], "reason": "No general deterministic inference implementation"},
                "host_bridge": {"backend_id": "host-bridge-ask-ai", "binary": shutil.which("ask-ai") or "",
                                "ready": False, "circuit_breaker_open": self.circuit_breaker.is_open(),
                                "last_error": self.circuit_breaker.last_error_reason}}

    def capabilities(self) -> dict[str, Any]:
        hc = self.health_check()
        ready = hc["local_gguf"]["ready"]
        return {"active_backend": hc["active_backend"], "mode": hc["mode"], "offline_mode": hc["offline_mode"],
                "supports_indonesian_chat": ready, "supports_local_coding": ready,
                "supports_offline_execution": ready, "supports_structured_json": ready,
                "supports_host_worker": False, "capability_evidence": "NOT_ASSESSED",
                "note": "Ready denotes an available interface, not measured task competence."}

    def classify_task_tier(self, prompt_or_task: str) -> str:
        lower = prompt_or_task.lower()
        if any(w in lower for w in ("ast", "regex", "preimage", "hash", "schema", "repair_json", "format json", "lint")):
            return "deterministic"
        if any(w in lower for w in ("arsitektur", "desain sistem", "blueprint", "perencanaan", "multi-agent", "komprehensif", "kompleks", "full-stack", "analisis mendalam")):
            return "deep"
        if any(w in lower for w in ("cepat", "fast", "snippet", "fungsi kecil", "helper", "sederhana", "terjemah", "konversi")):
            return "fast"
        return "deep"

    def _record(self, receipt: dict[str, Any]) -> dict[str, Any]:
        receipt.setdefault("verification_trace", ["nonempty_model_output" if receipt["success"] else receipt["error_code"]])
        event = self.store.emit_event(task_id=receipt["task_id"] or "system", kind="local_inference",
                                      status="COMPLETED" if receipt["success"] else "FAILED",
                                      model_backend=receipt["backend_used"], summary_code=receipt["status"],
                                      technical_detail=receipt, verification_passed=None)
        receipt["evidence_event_id"] = event["event_id"]
        return receipt

    def generate_text(self, messages: list[dict[str, str]], *, prefer_remote: bool = False,
                      simulated_remote_error: str | None = None, max_tokens: int = 128,
                      temperature: float = 0.2, tier: str = "auto", target_model: str | None = None,
                      task_id: str | None = None, timeout_seconds: float | None = None,
                      repeat_penalty: float = 1.15) -> dict[str, Any]:
        started = time.monotonic()
        child_usage_before = resource.getrusage(resource.RUSAGE_CHILDREN) if resource else None
        last_content = messages[-1].get("content", "") if isinstance(messages, list) and messages and isinstance(messages[-1], dict) else ""
        effective_tier = tier if tier in ("deep", "fast", "deterministic") else self.classify_task_tier(
            last_content if isinstance(last_content, str) else "")
        receipt: dict[str, Any] = {"schema": "ace.local_inference.v1", "inference_id": uuid.uuid4().hex,
            "task_id": task_id, "success": False, "status": "FAILED", "error_code": "NO_LOCAL_MODEL",
            "text": "", "raw_output": "", "input": messages, "backend_used": "unavailable",
            "model": None, "tier_used": effective_tier, "fallback_triggered": False,
            "offline_blocked": False, "failures": [], "task_verified": False,
            "resource_usage": {"available_ram_before_mb": get_available_ram_mb()}}

        def finish() -> dict[str, Any]:
            receipt["duration_seconds"] = round(time.monotonic() - started, 6)
            receipt["resource_usage"]["available_ram_after_mb"] = get_available_ram_mb()
            if resource and child_usage_before:
                usage = resource.getrusage(resource.RUSAGE_CHILDREN)
                receipt["resource_usage"].update(
                    child_cpu_user_seconds=round(usage.ru_utime - child_usage_before.ru_utime, 6),
                    child_cpu_system_seconds=round(usage.ru_stime - child_usage_before.ru_stime, 6),
                    child_maxrss_raw=usage.ru_maxrss,
                    child_maxrss_scope="All exited children of router process; cumulative high-water, not per-inference peak",
                    child_maxrss_unit="bytes on macOS, KiB on Linux")
            return self._record(receipt)

        def fail(code: str, detail: str, backend: str = "unavailable") -> None:
            receipt["error_code"] = code
            receipt["failures"].append({"backend": backend, "code": code, "detail": detail})

        def succeed(text_value: str, backend: str, model: dict[str, Any]) -> dict[str, Any]:
            receipt.update(success=True, status="SUCCESS", error_code=None, text=text_value,
                           backend_used=backend, model=model, fallback_triggered=bool(receipt["failures"]))
            return finish()

        if not isinstance(messages, list) or not messages or any(not isinstance(m, dict) or m.get("role") not in ("system", "user", "assistant")
                               or not isinstance(m.get("content"), str) for m in messages):
            fail("INVALID_INPUT", "Expected nonempty chat messages with string content")
            return finish()
        if prefer_remote:
            receipt["fallback_triggered"] = True
            if self.store.is_offline():
                receipt["offline_blocked"] = True
                receipt["egress_attempts_blocked"] = self.store.record_blocked_egress()
                fail("OFFLINE_BLOCKED", "Remote inference forbidden in offline mode")
            elif simulated_remote_error:
                self.circuit_breaker.record_failure(simulated_remote_error)
                fail("REMOTE_ERROR", simulated_remote_error)
            elif self.circuit_breaker.is_open():
                fail("CIRCUIT_OPEN", self.circuit_breaker.last_error_reason)
            else:
                fail("REMOTE_UNIMPLEMENTED", "No remote generation adapter is implemented")
            # A fallback is permitted only if a real local inference succeeds.
        if tier == "deterministic":
            fail("UNSUPPORTED_DETERMINISTIC_INFERENCE", "Use an actual typed AST/JSON tool; text generation performs no transformation")
            return finish()
        try:
            context = int(os.environ.get("ACE_LLAMA_CONTEXT", "4096"))
            threads = int(os.environ.get("ACE_LLAMA_THREADS", "2"))
            if not 512 <= context <= 32768 or not 1 <= threads <= 16:
                raise ValueError("context must be 512..32768 and threads 1..16")
            try:
                quota, period = Path("/sys/fs/cgroup/cpu.max").read_text().split()
                if quota != "max":
                    threads = min(threads, max(1, (int(quota) + int(period) - 1) // int(period)))
            except (OSError, ValueError):
                pass
            if isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or not 1 <= max_tokens <= min(8192, context):
                raise ValueError("max_tokens exceeds bounded context or 8192")
            if isinstance(temperature, bool) or not isinstance(temperature, (int, float)) or not 0 <= temperature <= 2:
                raise ValueError("temperature must be 0..2")
            if timeout_seconds is not None and (isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)) or not 1 <= timeout_seconds <= 900):
                raise ValueError("timeout_seconds must be 1..900")
            if isinstance(repeat_penalty, bool) or not isinstance(repeat_penalty, (int, float)) or not 0.8 <= repeat_penalty <= 1.5:
                raise ValueError("repeat_penalty must be 0.8..1.5")
            if sum(len(m["content"]) for m in messages) > 131072:
                raise ValueError("Prompt exceeds 131072 characters")
        except ValueError as exc:
            fail("INVALID_BUDGET", str(exc))
            return finish()
        receipt["inference_config"] = {"max_tokens": max_tokens, "temperature": temperature,
                                       "context": context, "threads": threads,
                                       "timeout_seconds": timeout_seconds, "repeat_penalty": repeat_penalty}
        if self.brain_registry is not None:
            requested_brain = target_model or os.environ.get(
                "ACE_DEFAULT_MODEL")
            if requested_brain and self.brain_registry.is_dismissed(
                    requested_brain):
                fail("BRAIN_DISMISSED",
                     f"Brain {requested_brain} was dismissed in the "
                     "registry; dismissal is absolute until an "
                     "explicit reinstatement", "brain-registry")
                return finish()
        gguf = self.discover_local_gguf()
        fitting = [m for m in gguf.get("valid_models", []) if m.get("fits_ram")]
        preference = target_model or os.environ.get("ACE_DEFAULT_MODEL")
        target = next((m for m in fitting if preference and preference in m["name"]), None)
        if not preference and fitting:
            target = (next((m for m in fitting if "3b" in m["name"].lower()), None)
                      if effective_tier == "fast" else None) or max(fitting, key=lambda m: m["size_bytes"])
        if target is not None and self.brain_registry is not None \
                and self.brain_registry.is_dismissed(target["name"]):
            # The only selectable brain is dismissed: stop, never
            # silently substitute another organ for the dismissed one.
            fail("BRAIN_DISMISSED",
                 f"Selected brain {target['name']} was dismissed in "
                 "the registry", f"local-gguf:{target['name']}")
            return finish()
        total_timeout = timeout_seconds if timeout_seconds is not None else min(900.0, max(60.0, max_tokens * 0.8 + 20.0))
        timeout = total_timeout - (time.monotonic() - started)
        if timeout <= 0:
            fail("INFERENCE_TIMEOUT", "Inference budget exhausted during discovery")
            return finish()
        if gguf.get("server_healthy"):
            server_model = next((m for m in gguf.get("server_models", [])
                                 if not preference or preference in m["id"]), None)
            if preference and server_model is None:
                fail("SERVER_MODEL_MISMATCH", f"Requested model {preference} is not advertised", "local-gguf-server")
            else:
                try:
                    body: dict[str, Any] = {"messages": messages, "max_tokens": max_tokens,
                                            "temperature": temperature, "repeat_penalty": repeat_penalty}
                    if server_model:
                        body["model"] = server_model["id"]
                    effective_id = (server_model or {}).get("id") or next(
                        (m["id"] for m in gguf.get("server_models", [])), "")
                    if "qwen3" in effective_id.lower():
                        # Qwen3 thinking models otherwise spend the whole
                        # token budget inside reasoning_content and return
                        # no answer (THINKING_BUDGET_EXHAUSTED). The vendor
                        # template switch keeps the answer in the content
                        # channel; if a server ignores it, the receipt
                        # still fails closed on the empty content.
                        body["chat_template_kwargs"] = {"enable_thinking": False}
                    response = _local_json(f"{gguf['server_url']}/v1/chat/completions", body=body, timeout=timeout)
                    receipt["raw_response"] = response
                    choice = response.get("choices", [{}])[0]
                    value = choice.get("message", {}).get("content", "")
                    receipt["raw_output"] = value
                    receipt["finish_reason"] = choice.get("finish_reason")
                    receipt["resource_usage"]["server_reported_usage"] = response.get("usage")
                    if not isinstance(value, str) or not value.strip():
                        reasoning = choice.get("message", {}).get("reasoning_content", "")
                        if isinstance(reasoning, str) and reasoning.strip() and choice.get("finish_reason") == "length":
                            raise _ThinkingBudgetExhausted(
                                "token budget exhausted inside reasoning_content; no final content produced")
                        raise ValueError("Empty or non-string model response")
                    served_id = response.get("model") or (server_model or {}).get("id")
                    model_record: dict[str, Any] = {
                        "id": served_id, "source": gguf["server_url"],
                        "sha256": None, "checksum_verified": False,
                        "identity_note": "Server-advertised identity; artifact custody not attested by HTTP"}
                    attested = match_attestation(self.attestations,
                                                 gguf["server_url"],
                                                 served_id)
                    if attested is not None:
                        # Stage E: the harness spawned this server and
                        # recorded the artifact digests at spawn; the
                        # receipt binds to them. Any mismatch already
                        # failed closed inside match_attestation.
                        model_record.update({
                            "sha256": attested["model_sha256"],
                            "checksum_verified": True,
                            "identity_note": "Harness-attested server: model digest recorded by the harness at spawn",
                            "attestation": {
                                "schema": attested["schema"],
                                "binary_sha256": attested["binary_sha256"],
                                "launch_param_hash": attested["launch_param_hash"],
                                "spawned_by": attested["spawned_by"]}})
                    return succeed(value.strip(), "local-gguf-server",
                                   model_record)
                except Exception as exc:
                    code = ("THINKING_BUDGET_EXHAUSTED" if isinstance(exc, _ThinkingBudgetExhausted)
                            else "SERVER_INFERENCE_FAILED")
                    fail(code, f"{type(exc).__name__}: {exc}", "local-gguf-server")
        cli_bin = gguf.get("llama_binary")
        if preference and not target:
            fail("MODEL_NOT_FOUND", f"Requested model {preference} has no RAM-fitting local artifact")
        if cli_bin and target:
            receipt["fallback_triggered"] = bool(receipt["failures"])
            cli_messages = messages
            if "qwen3" in str(target.get("name", "")).lower():
                # Same thinking discipline as the server path, in the
                # form raw completion understands: the vendor /no_think
                # directive on the final user turn. Without it the model
                # spends the CLI budget reasoning and the completion
                # contains no answer.
                cli_messages = [dict(m) for m in messages]
                for m in reversed(cli_messages):
                    if m.get("role") == "user":
                        m["content"] = m["content"] + "\n/no_think"
                        break
            prompt = "\n".join(f"<|im_start|>{m['role']}\n{m['content']}<|im_end|>" for m in cli_messages)
            prompt += "\n<|im_start|>assistant\n"
            command = [cli_bin, "-m", target["path"], "-p", prompt, "-n", str(max_tokens),
                       "--temp", str(temperature), "--repeat-penalty", str(repeat_penalty), "--ctx-size", str(context),
                       "--threads", str(threads), "--no-display-prompt", "-no-cnv", "-lv", "0", "--simple-io"]
            receipt["command"] = command
            try:
                model = {"id": target["name"], "source": target["path"],
                         "sha256": self._digest(Path(target["path"])),
                         "checksum_verified": target.get("checksum_verified", False)}
                receipt["model"] = model
                if model["checksum_verified"] and target.get("sha256") != model["sha256"]:
                    raise ValueError("Model artifact changed after checksum admission")
                remaining_timeout = total_timeout - (time.monotonic() - started)
                if remaining_timeout <= 0:
                    raise subprocess.TimeoutExpired(command, total_timeout)
                process = subprocess.run(command, capture_output=True, text=True, timeout=remaining_timeout)
                receipt["raw_output"] = process.stdout
                receipt["stderr"] = process.stderr
                receipt["exit_code"] = process.returncode
                if process.returncode != 0:
                    raise ValueError(f"Completion process exited {process.returncode}: {process.stderr[-2000:]}")
                cleaned = process.stdout.strip()
                for token in ("[end of text]", "<|im_end|>", "<|endoftext|>", "</s>"):
                    cleaned = cleaned.replace(token, "")
                if not cleaned.strip():
                    raise ValueError("Completion produced no answer")
                return succeed(cleaned.strip(), f"local-gguf:{target['name']}", model)
            except subprocess.TimeoutExpired as exc:
                receipt["raw_output"] = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else exc.stdout or ""
                receipt["stderr"] = exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else exc.stderr or ""
                fail("INFERENCE_TIMEOUT", f"Timeout after {timeout}s", f"local-gguf:{target['name']}")
            except Exception as exc:
                fail("CLI_INFERENCE_FAILED", f"{type(exc).__name__}: {exc}", f"local-gguf:{target['name']}")
        elif not receipt["failures"]:
            fail("NO_LOCAL_MODEL", "No ready local completion backend; no work was performed")
        return finish()

    def generate_structured(self, messages: list[dict[str, str]], *, required_keys: list[str] | None = None,
                            raw_candidate_override: str | None = None, max_tokens: int = 256,
                            temperature: float = 0.1, tier: str = "auto", target_model: str | None = None,
                            task_id: str | None = None, timeout_seconds: float | None = None,
                            repeat_penalty: float = 1.15) -> dict[str, Any]:
        """Validate actual JSON; no missing values or success statuses are invented."""
        keys = required_keys if required_keys is not None else ["action", "status", "summary_id"]
        if raw_candidate_override is not None:
            # Explicit parser utility, never evidence of local model inference.
            parsed = extract_and_repair_json(raw_candidate_override, required_keys=keys)
            return {"data": parsed, "success": True, "status": "PARSED_OVERRIDE",
                    "backend_used": "parser-only", "raw_output": raw_candidate_override,
                    "model": None, "repaired": True, "inference_performed": False, "task_verified": False}
        instruction = "Return exactly one valid JSON object, without markdown, with required keys: " + json.dumps(keys)
        augmented = [{"role": "system", "content": instruction}, *messages]
        result = self.generate_text(augmented, max_tokens=max_tokens, temperature=temperature,
                                    tier=tier, target_model=target_model, task_id=task_id,
                                    timeout_seconds=timeout_seconds, repeat_penalty=repeat_penalty)
        result.update(data=None, repaired=False, inference_performed=result["success"], valid_json=False)
        if not result["success"]:
            return result
        try:
            parsed = json.loads(result["text"])
            if not isinstance(parsed, dict) or any(key not in parsed for key in keys):
                raise ValueError("JSON object is missing required keys")
            if result.get("finish_reason") == "length":
                raise ValueError("Model response reached the output-token budget")
            result.update(data=parsed, valid_json=True)
            result["verification_trace"].append("json_object_required_keys")
        except (ValueError, TypeError) as exc:
            result.update(success=False, status="INVALID_OUTPUT", error_code="INVALID_JSON")
            result["failures"].append({"backend": result["backend_used"], "code": "INVALID_JSON", "detail": str(exc)})
            result["verification_trace"].append("INVALID_JSON")
        # Persist validation separately, preserving the original inference event.
        result["inference_event_id"] = result.pop("evidence_event_id", None)
        return self._record(result)
