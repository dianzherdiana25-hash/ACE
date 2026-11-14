"""ACE Omega - Proposer Engine Stage 2 (Isolated Staging & Constitution Engine).

Implements the constitutional Stage-2 staging harness specified in:
  - ``handover/PETA_ARAH_SERIBU_TAHUN.md`` (Addendum §5 and panen #8C)
  - ``handover/PROPOSER_STAGE1_V2_EXIT_GATE_VERDICT_20261114.md``

Key invariants enforced fail-closed:
  1. **Internal ratification only:** ``FORBIDDEN_RATIFICATION_TERMS`` (such as
     ``owner_approval``, ``izin_pemilik``) are rejected across packages,
     ratification metadata, revocation reasons, and environment profiles. Only
     ``RATIFICATION_AUDIENCE`` (``hub``, ``kernel``, ``evidence``) may ratify.
  2. **Threefold identity separation (#8C):** ``request_id`` + ``payload_sha256``
     govern idempotent staging (conflicting payloads on the same ``request_id``
     are rejected); ``payload_sha256`` pins immutable canonical package content;
     every intentional ``dispatch_staged`` mints a fresh ``execution_run_id``.
  3. **Exact payload-hash-pinned ratification, expiry & irrevocable revocation:**
     A ratification is bound to one exact ``payload_sha256`` and finite TTL.
     Revocation records an exact ``revocation_ledger_seq``, is irrevocable for
     that ``staging_id``, blocks all new dispatches, and signals active runs
     to stop cleanly.
  4. **Isolated staging environment bridge (§5):** Enforces ``staging-only``
     identity, ``egress_blocked=True``, ``dummy_credentials_only=True``, path-
     escape-checked dummy resources inside the workspace, and records exact
     versions/SHA-256 digests of the real runtime enforcing modules.
  5. **Visible bounded stop, hard ceilings & no-auto-retry:** Enforces
     ``max_calls``, ``max_wall_seconds``, and ``max_cost_units``, accounts
     in-flight work when interrupted by explicit ``request_stop`` or revocation,
     and blocks auto-retry after any ``STOPPED``/``ABORTED_CEILING``/``FAILED`` run.
  6. **Immutable-blob-then-verify-then-commit (#8C) + Pre-Audit:** All run
     artifacts are written read-only, hash-verified on disk, and checked via
     ``preaudit_validator`` (C1/C2/C3 -> ``SESUAI``) BEFORE the finalized DB
     run row and ledger entry commit.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import copy
import ctypes
import hashlib
import json
import math
import os
from pathlib import Path
import secrets
import shutil
import sqlite3
import threading
import time
from typing import Any, Callable

from ace_mission.bus import MissionBus
from ace_mission.schema import validate_mission

from . import preaudit_validator
from .proposer_schema import (
    FORBIDDEN_RATIFICATION_TERMS,
    RATIFICATION_AUDIENCE,
)
from .proposer_validator import validate_package
from .store import OperationalStore

SCHEMA_STAGE2_PREREG = "ace.stage2.preregistration.v1"
SCHEMA_STAGE2_SUMMARY = "ace.stage2.execution_summary.v1"
STAGE2_VERSION = "proposer-stage2-1.0.0"

_DUMMY_CRED_PREFIXES = ("dummy_", "stg_dummy_")
_SUSPICIOUS_SECRET_PREFIXES = ("sk-", "ghp_", "gho_", "ghu_", "aiza", "xoxb-", "akia")
_FORBIDDEN_ENV_ID_TOKENS = ("prod", "production", "live", "owner", "real")


class Stage2Error(Exception):
    """Base error for fail-closed Stage-2 constitutional rejections."""


class ValidationRejectedError(Stage2Error):
    """Raised when validate_package or metadata invariants reject an input."""

    def __init__(self, reasons: list[str] | str):
        self.reasons = [reasons] if isinstance(reasons, str) else list(reasons)
        super().__init__("; ".join(self.reasons))


class RatificationVocabularyError(Stage2Error):
    """Raised when forbidden owner-approval vocabulary or invalid audience is seen."""


class RequestConflictError(Stage2Error):
    """Raised when a request_id is reused with a different payload_sha256."""


class RatificationError(Stage2Error):
    """Raised for missing, hash-mismatched, or expired ratification."""


class RevokedError(Stage2Error):
    """Raised when an irrevocable revocation blocks ratification or dispatch."""


class AutoRetryBlockedError(Stage2Error):
    """Raised when dispatch attempts to retry a STOPPED/ABORTED/FAILED staged package."""


class DoNotRunError(Stage2Error):
    """Raised when attempting to dispatch a package whose recommended_option is do_not_run."""


class EnvironmentIsolationError(Stage2Error):
    """Raised when StagingEnvironmentProfile fails isolated runtime verification."""


class LedgerTamperError(Stage2Error):
    """Raised when hash-chain verification detects ledger tampering."""


class BlobIntegrityError(Stage2Error):
    """Raised when immutable blob write/digest verification fails before DB commit."""


class _StopTriggered(Exception):
    """Internal control-flow signal raised cleanly inside a run when stopped."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


class _CeilingExceeded(Exception):
    """Internal control-flow signal raised cleanly when a hard ceiling is reached."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


class _WorkerInterrupted(BaseException):
    """Supervisor unwind signal injected when a blocked worker exceeds stop/wall deadlines."""


def _interrupt_thread(tid: int | None, exc_type: type[BaseException]) -> bool:
    """Inject an asynchronous unwind exception into an active worker thread."""
    if not tid:
        return False
    set_async = ctypes.pythonapi.PyThreadState_SetAsyncExc
    set_async.argtypes = [ctypes.c_ulong, ctypes.py_object]
    set_async.restype = ctypes.c_int
    res = set_async(ctypes.c_ulong(tid), ctypes.py_object(exc_type))
    if res > 1:
        # Undo unintended multi-thread match per CPython C-API contract.
        set_async(ctypes.c_ulong(tid), None)
        return False
    return res == 1


def _utc_iso(ts: float | None = None) -> str:
    dt = datetime.now(timezone.utc) if ts is None else datetime.fromtimestamp(ts, tz=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _check_no_forbidden_terms(value: Any, *, field_name: str) -> None:
    flat = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).lower()
    for term in FORBIDDEN_RATIFICATION_TERMS:
        if term in flat:
            raise RatificationVocabularyError(
                f"{field_name} uses forbidden owner-approval term {term!r}; "
                "ACE Stage 2 allows internal ratification only"
            )


def canonical_package_bytes(pkg: dict[str, Any]) -> bytes:
    """Validate and serialize an ace.proposal.v1 dict into canonical UTF-8 JSON bytes."""
    ok, reasons = validate_package(pkg)
    if not ok:
        raise ValidationRejectedError(reasons)
    _check_no_forbidden_terms(pkg, field_name="package")
    try:
        canonical = json.dumps(
            pkg,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ValidationRejectedError(f"package serialization rejected: {exc}") from exc
    return canonical.encode("utf-8")


def package_sha256(pkg: dict[str, Any]) -> str:
    """Return canonical SHA-256 hex digest of a validated ace.proposal.v1 package."""
    return _sha256_bytes(canonical_package_bytes(pkg))


def _write_immutable_bytes(path: Path, data: bytes) -> tuple[str, int]:
    """Atomically write bytes with fsync, lock file mode 0o444, then re-read O_RDONLY and verify."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp.{secrets.token_hex(4)}")
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        view = memoryview(data)
        total = 0
        while total < len(view):
            written = os.write(fd, view[total:])
            if written <= 0:
                raise OSError("short write while persisting immutable blob")
            total += written
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(str(tmp), str(path))
    os.chmod(str(path), 0o444)

    expected = _sha256_bytes(data)
    rfd = os.open(str(path), os.O_RDONLY)
    try:
        chunks = []
        while True:
            blk = os.read(rfd, 1024 * 1024)
            if not blk:
                break
            chunks.append(blk)
        on_disk = b"".join(chunks)
    finally:
        os.close(rfd)
    actual = _sha256_bytes(on_disk)
    if actual != expected or len(on_disk) != len(data):
        raise BlobIntegrityError(
            f"immutable blob verification failed for {path.name}: "
            f"expected {expected} ({len(data)} B), got {actual} ({len(on_disk)} B)"
        )
    return actual, len(on_disk)


def _verify_existing_blob(path: Path, expected_sha256: str) -> bytes:
    """Read an immutable blob O_RDONLY and verify exact SHA-256 match."""
    if not path.is_file():
        raise BlobIntegrityError(f"staged blob missing: {path}")
    fd = os.open(str(path), os.O_RDONLY)
    try:
        chunks = []
        while True:
            blk = os.read(fd, 1024 * 1024)
            if not blk:
                break
            chunks.append(blk)
        raw = b"".join(chunks)
    finally:
        os.close(fd)
    actual = _sha256_bytes(raw)
    if actual != expected_sha256:
        raise BlobIntegrityError(
            f"staged blob digest mismatch at {path.name}: expected {expected_sha256}, got {actual}"
        )
    return raw


def _runtime_enforcer_stamps() -> dict[str, dict[str, str]]:
    """Pin exact versions and SHA-256 digests of real runtime constitutional enforcers."""
    here = Path(__file__).resolve().parent
    targets = {
        "proposer_validator": here / "proposer_validator.py",
        "preaudit_validator": here / "preaudit_validator.py",
        "proposer_stage2": Path(__file__).resolve(),
        "operational_store": here / "store.py",
    }
    stamps: dict[str, dict[str, str]] = {}
    for name, path in targets.items():
        data = path.read_bytes()
        ver = preaudit_validator.VALIDATOR_VERSION if name == "preaudit_validator" else (
            STAGE2_VERSION if name == "proposer_stage2" else "workspace-head"
        )
        stamps[name] = {
            "version": ver,
            "source_sha256": _sha256_bytes(data),
        }
    return stamps


@dataclass(frozen=True)
class StagingEnvironmentProfile:
    """Isolated runtime environment descriptor verified before every Stage-2 dispatch.

    Addresses PETA ARAH Addendum §5: matching config hashes do NOT prove runtime
    equivalence; each dispatch must bind real enforcer digests alongside explicit
    staging-only identity, blocked egress, dummy credentials, and confined dummy paths.
    """

    identity_mode: str
    effective_identity: str
    egress_blocked: bool
    dummy_credentials_only: bool
    dummy_credentials: dict[str, str]
    dummy_resource_root: Path
    mount_permissions: tuple[str, ...] = ("source:ro", "bundle_out:rw_isolated", "egress:blocked")
    enforcer_versions: dict[str, dict[str, str]] = field(default_factory=_runtime_enforcer_stamps)

    def validate(self, *, allowed_dummy_base: Path) -> Path:
        _check_no_forbidden_terms(
            {
                "identity_mode": self.identity_mode,
                "effective_identity": self.effective_identity,
                "dummy_credentials": self.dummy_credentials,
            },
            field_name="env_profile",
        )
        if self.identity_mode != "staging-only":
            raise EnvironmentIsolationError(
                f"identity_mode must be 'staging-only', got {self.identity_mode!r}"
            )
        eid = self.effective_identity.strip().lower()
        if not (eid.startswith("staging:") or eid.startswith("stg:")):
            raise EnvironmentIsolationError(
                f"effective_identity must use 'staging:' or 'stg:' prefix, got {self.effective_identity!r}"
            )
        for tok in _FORBIDDEN_ENV_ID_TOKENS:
            if tok in eid:
                raise EnvironmentIsolationError(
                    f"effective_identity contains non-staging token {tok!r}"
                )
        if self.egress_blocked is not True:
            raise EnvironmentIsolationError("egress_blocked must be True for Stage-2 staging")
        if self.dummy_credentials_only is not True:
            raise EnvironmentIsolationError("dummy_credentials_only must be True for Stage-2 staging")
        if not isinstance(self.dummy_credentials, dict) or not self.dummy_credentials:
            raise EnvironmentIsolationError("dummy_credentials must be a non-empty mapping")
        for k, v in self.dummy_credentials.items():
            if not isinstance(k, str) or not k.strip() or not isinstance(v, str) or not v.strip():
                raise EnvironmentIsolationError("dummy_credentials keys/values must be non-empty strings")
            v_low = v.strip().lower()
            if any(v_low.startswith(pref) for pref in _SUSPICIOUS_SECRET_PREFIXES):
                raise EnvironmentIsolationError(
                    f"credential {k!r} looks like a live token prefix; dummy credentials only"
                )
            if not any(v_low.startswith(pref) for pref in _DUMMY_CRED_PREFIXES):
                raise EnvironmentIsolationError(
                    f"credential {k!r} must use dummy_/stg_dummy_ prefix"
                )

        if "egress:blocked" not in self.mount_permissions:
            raise EnvironmentIsolationError("mount_permissions must declare 'egress:blocked'")

        base_resolved = allowed_dummy_base.resolve()
        raw_root = Path(self.dummy_resource_root)
        if ".." in raw_root.parts:
            raise EnvironmentIsolationError("dummy_resource_root must not contain '..'")
        resolved = raw_root.resolve()
        if resolved != base_resolved and base_resolved not in resolved.parents:
            raise EnvironmentIsolationError(
                f"dummy_resource_root {resolved} escapes isolated staging root {base_resolved}"
            )
        expected_stamps = _runtime_enforcer_stamps()
        if (
            not isinstance(self.enforcer_versions, dict)
            or set(self.enforcer_versions.keys()) != set(expected_stamps.keys())
        ):
            raise EnvironmentIsolationError(
                f"enforcer_versions must pin exact enforcer module set {sorted(expected_stamps.keys())}"
            )
        for mod_name, exp in expected_stamps.items():
            got = self.enforcer_versions.get(mod_name)
            if (
                not isinstance(got, dict)
                or got.get("version") != exp["version"]
                or got.get("source_sha256") != exp["source_sha256"]
            ):
                raise EnvironmentIsolationError(
                    f"enforcer_versions digest/version mismatch for {mod_name!r}"
                )
        resolved.mkdir(parents=True, exist_ok=True)
        return resolved

    def to_snapshot(self) -> dict[str, Any]:
        return {
            "identity_mode": self.identity_mode,
            "effective_identity": self.effective_identity,
            "egress_blocked": self.egress_blocked,
            "dummy_credentials_only": self.dummy_credentials_only,
            "dummy_credential_keys": sorted(self.dummy_credentials.keys()),
            "dummy_resource_root": str(self.dummy_resource_root),
            "mount_permissions": list(self.mount_permissions),
            "enforcer_versions": copy.deepcopy(self.enforcer_versions),
        }


class StagingRunContext:
    """In-flight budget, dummy resource, and bounded-stop enforcement handle."""

    def __init__(
        self,
        *,
        engine: "Stage2StagingEngine",
        execution_run_id: str,
        staging_id: str,
        bound_payload_sha256: str,
        ceiling: dict[str, Any],
        dummy_root: Path,
        dummy_credentials: dict[str, str],
        stop_event: threading.Event,
        now_fn: Callable[[], float],
    ):
        self._engine = engine
        self.execution_run_id = execution_run_id
        self.staging_id = staging_id
        self.bound_payload_sha256 = bound_payload_sha256
        self.ceiling = copy.deepcopy(ceiling)
        self.dummy_root = dummy_root
        self.dummy_credentials = dict(dummy_credentials)
        self._stop_event = stop_event
        self._now = now_fn
        self._start_t = now_fn()
        self._lock = threading.Lock()
        self._sealed_kind = ""
        self._sealed_reason = ""
        self._frozen_snapshot: dict[str, Any] | None = None
        self.calls_used = 0
        self.cost_units = 0.0
        self.work_completed_units = 0
        self.steps: list[dict[str, Any]] = []

    def elapsed_seconds(self) -> float:
        return round(max(0.0, self._now() - self._start_t), 6)

    def remaining_budget(self) -> dict[str, float | int]:
        with self._lock:
            return {
                "calls": max(0, int(self.ceiling["max_calls"]) - self.calls_used),
                "wall_seconds": round(max(0.0, float(self.ceiling["max_wall_seconds"]) - self.elapsed_seconds()), 6),
                "cost_units": round(max(0.0, float(self.ceiling["max_cost_units"]) - self.cost_units), 6),
            }

    def _raise_if_sealed_locked(self) -> None:
        if self._sealed_kind == "STOPPED":
            raise _StopTriggered(self._sealed_reason or "stop requested")
        if self._sealed_kind == "ABORTED_CEILING":
            raise _CeilingExceeded(self._sealed_reason or "hard ceiling exceeded")

    def _seal(self, kind: str, reason: str) -> dict[str, Any]:
        with self._lock:
            if not self._sealed_kind:
                self._sealed_kind = kind
                self._sealed_reason = reason
            if self._frozen_snapshot is None:
                self._frozen_snapshot = {
                    "calls_used": int(self.calls_used),
                    "elapsed_seconds": self.elapsed_seconds(),
                    "cost_units": round(float(self.cost_units), 6),
                    "work_completed_units": int(self.work_completed_units),
                    "steps": copy.deepcopy(self.steps),
                }
            return copy.deepcopy(self._frozen_snapshot)

    def _sealed_outcome(self) -> tuple[str, str]:
        with self._lock:
            return self._sealed_kind, self._sealed_reason

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            if self._frozen_snapshot is not None:
                return copy.deepcopy(self._frozen_snapshot)
            return {
                "calls_used": int(self.calls_used),
                "elapsed_seconds": self.elapsed_seconds(),
                "cost_units": round(float(self.cost_units), 6),
                "work_completed_units": int(self.work_completed_units),
                "steps": copy.deepcopy(self.steps),
            }

    def _check_gates_locked(self) -> None:
        self._raise_if_sealed_locked()
        persisted_stop, _ = self._engine._persisted_stop_state(self.execution_run_id)
        if persisted_stop:
            self._stop_event.set()
        if self._stop_event.is_set() or persisted_stop or self._engine.is_revoked(self.staging_id):
            reason = self._engine._stop_reason_for(self.execution_run_id, self.staging_id)
            raise _StopTriggered(reason or "stop requested")
        elapsed = self.elapsed_seconds()
        if elapsed > float(self.ceiling["max_wall_seconds"]):
            raise _CeilingExceeded(
                f"wall_seconds {elapsed} exceeds max_wall_seconds {self.ceiling['max_wall_seconds']}"
            )
        if self.calls_used > int(self.ceiling["max_calls"]):
            raise _CeilingExceeded(
                f"calls {self.calls_used} exceeds max_calls {self.ceiling['max_calls']}"
            )
        if self.cost_units > float(self.ceiling["max_cost_units"]) + 1e-9:
            raise _CeilingExceeded(
                f"cost_units {self.cost_units} exceeds max_cost_units {self.ceiling['max_cost_units']}"
            )

    def check_gates(self) -> None:
        with self._lock:
            self._check_gates_locked()

    def should_stop(self) -> bool:
        with self._lock:
            if self._sealed_kind:
                return True
        persisted_stop, _ = self._engine._persisted_stop_state(self.execution_run_id)
        if persisted_stop:
            self._stop_event.set()
        return bool(
            self._stop_event.is_set()
            or persisted_stop
            or self._engine.is_revoked(self.staging_id)
        )

    def record_step(
        self,
        *,
        step_name: str,
        calls: int = 1,
        cost_units: float = 0.1,
        work_units: int = 1,
        dummy_artifact_rel: str | None = None,
        dummy_content: bytes | None = None,
    ) -> dict[str, Any]:
        """Account resource consumption strictly and enforce stop & ceiling gates."""
        with self._lock:
            self._check_gates_locked()
            if (
                isinstance(cost_units, bool)
                or not isinstance(cost_units, (int, float))
                or not math.isfinite(float(cost_units))
                or float(cost_units) < 0
            ):
                raise ValidationRejectedError("step cost_units must be finite and >= 0")
            if calls < 0 or work_units < 0:
                raise ValidationRejectedError("step costs and work_units must be >= 0")

            next_calls = self.calls_used + int(calls)
            next_cost = round(self.cost_units + float(cost_units), 6)
            elapsed = self.elapsed_seconds()
            if elapsed > float(self.ceiling["max_wall_seconds"]):
                raise _CeilingExceeded(
                    f"wall_seconds {elapsed} exceeds max_wall_seconds {self.ceiling['max_wall_seconds']}"
                )
            if next_calls > int(self.ceiling["max_calls"]):
                raise _CeilingExceeded(
                    f"projected calls {next_calls} exceeds max_calls {self.ceiling['max_calls']}"
                )
            if next_cost > float(self.ceiling["max_cost_units"]) + 1e-9:
                raise _CeilingExceeded(
                    f"projected cost_units {next_cost} exceeds max_cost_units {self.ceiling['max_cost_units']}"
                )

            artifact_digest = ""
            if dummy_artifact_rel is not None:
                rel = Path(dummy_artifact_rel)
                if rel.is_absolute() or ".." in rel.parts:
                    raise EnvironmentIsolationError(f"dummy artifact path escapes sandbox: {dummy_artifact_rel!r}")
                target = (self.dummy_root / rel).resolve()
                root_res = self.dummy_root.resolve()
                if target != root_res and root_res not in target.parents:
                    raise EnvironmentIsolationError(f"resolved artifact path escapes sandbox: {target}")
                payload = dummy_content if dummy_content is not None else b""
                artifact_digest, _ = _write_immutable_bytes(target, payload)

            self.calls_used = next_calls
            self.cost_units = next_cost
            self.work_completed_units += int(work_units)
            rec = {
                "step": step_name,
                "calls": int(calls),
                "cost_units": float(cost_units),
                "work_units": int(work_units),
                "elapsed_seconds": self.elapsed_seconds(),
                "artifact": dummy_artifact_rel or "",
                "artifact_sha256": artifact_digest,
            }
            self.steps.append(rec)
            # Re-check post-step so concurrent stop requests during step I/O halt immediately.
            self._check_gates_locked()
            return rec


class Stage2StagingEngine:
    """Isolated staging, internal ratification, and constitution harness for Proposer Stage 2."""

    def __init__(
        self,
        store: OperationalStore,
        *,
        mission_bus: MissionBus | None = None,
        now_fn: Callable[[], float] | None = None,
    ):
        self.store = store
        self.mission_bus = mission_bus
        self._now = now_fn or time.time
        self.stage_root = (self.store.workspace / "proposer_stage2").resolve()
        self.pkg_blobs_dir = self.stage_root / "blobs" / "pkgs"
        self.dummy_base_dir = self.stage_root / "dummy_resources"
        self.bundles_dir = self.stage_root / "bundles"
        for d in (self.pkg_blobs_dir, self.dummy_base_dir, self.bundles_dir):
            d.mkdir(parents=True, exist_ok=True)
        self._active_lock = threading.Lock()
        self._stop_events: dict[str, threading.Event] = {}
        self._stop_meta: dict[str, dict[str, Any]] = {}

    def default_environment_profile(self, *, dummy_subdir: str = "default") -> StagingEnvironmentProfile:
        clean = Path(dummy_subdir)
        if clean.is_absolute() or ".." in clean.parts or not str(dummy_subdir).strip():
            raise EnvironmentIsolationError(f"invalid dummy_subdir: {dummy_subdir!r}")
        dummy_dir = (self.dummy_base_dir / clean).resolve()
        return StagingEnvironmentProfile(
            identity_mode="staging-only",
            effective_identity="staging:ace-proposer-stage2",
            egress_blocked=True,
            dummy_credentials_only=True,
            dummy_credentials={
                "staging_api_key": "dummy_stg_api_key_isolated",
                "staging_account": "stg_dummy_account_001",
            },
            dummy_resource_root=dummy_dir,
        )

    # --- Tamper-evident hash-chained ledger ---
    def _ledger_entry_digest(
        self,
        *,
        seq: int,
        event_type: str,
        staging_id: str,
        execution_run_id: str,
        payload_sha256: str,
        detail_json: str,
        prev_hash: str,
        created_at: str,
    ) -> str:
        body = {
            "seq": seq,
            "event_type": event_type,
            "staging_id": staging_id,
            "execution_run_id": execution_run_id,
            "payload_sha256": payload_sha256,
            "detail_json": detail_json,
            "prev_hash": prev_hash,
            "created_at": created_at,
        }
        return hashlib.sha256(
            json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    def _append_ledger_locked(
        self,
        *,
        event_type: str,
        staging_id: str,
        execution_run_id: str = "",
        payload_sha256: str = "",
        detail: dict[str, Any] | None = None,
    ) -> int:
        last = self.store._conn.execute(
            "SELECT seq, entry_hash FROM proposer_stage2_ledger ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        next_seq = (int(last["seq"]) + 1) if last else 1
        prev_hash = str(last["entry_hash"]) if last else ""
        created_at = _utc_iso(self._now())
        detail_json = json.dumps(detail or {}, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        entry_hash = self._ledger_entry_digest(
            seq=next_seq,
            event_type=event_type,
            staging_id=staging_id,
            execution_run_id=execution_run_id,
            payload_sha256=payload_sha256,
            detail_json=detail_json,
            prev_hash=prev_hash,
            created_at=created_at,
        )
        self.store._conn.execute(
            """
            INSERT INTO proposer_stage2_ledger(
                seq, event_type, staging_id, execution_run_id, payload_sha256,
                detail_json, prev_hash, entry_hash, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                next_seq,
                event_type,
                staging_id,
                execution_run_id,
                payload_sha256,
                detail_json,
                prev_hash,
                entry_hash,
                created_at,
            ),
        )
        return next_seq

    def list_ledger(self, staging_id: str | None = None) -> list[dict[str, Any]]:
        with self.store._lock:
            if staging_id is None:
                rows = self.store._conn.execute(
                    "SELECT * FROM proposer_stage2_ledger ORDER BY seq ASC"
                ).fetchall()
            else:
                rows = self.store._conn.execute(
                    "SELECT * FROM proposer_stage2_ledger WHERE staging_id = ? ORDER BY seq ASC",
                    (staging_id,),
                ).fetchall()
            return [
                {
                    "seq": int(r["seq"]),
                    "event_type": r["event_type"],
                    "staging_id": r["staging_id"],
                    "execution_run_id": r["execution_run_id"],
                    "payload_sha256": r["payload_sha256"],
                    "detail": json.loads(r["detail_json"] or "{}"),
                    "prev_hash": r["prev_hash"],
                    "entry_hash": r["entry_hash"],
                    "created_at": r["created_at"],
                }
                for r in rows
            ]

    def verify_ledger(self) -> bool:
        with self.store._lock:
            rows = self.store._conn.execute(
                "SELECT * FROM proposer_stage2_ledger ORDER BY seq ASC"
            ).fetchall()
        prev = ""
        for idx, r in enumerate(rows, start=1):
            if int(r["seq"]) != idx or str(r["prev_hash"]) != prev:
                return False
            expected = self._ledger_entry_digest(
                seq=int(r["seq"]),
                event_type=str(r["event_type"]),
                staging_id=str(r["staging_id"]),
                execution_run_id=str(r["execution_run_id"]),
                payload_sha256=str(r["payload_sha256"]),
                detail_json=str(r["detail_json"]),
                prev_hash=prev,
                created_at=str(r["created_at"]),
            )
            if str(r["entry_hash"]) != expected:
                return False
            prev = str(r["entry_hash"])
        return True

    def _require_clean_ledger(self) -> None:
        if not self.verify_ledger():
            raise LedgerTamperError("proposer_stage2_ledger hash chain is broken; failing closed")

    # --- MissionBus review-only hook (leaves code/ace_mission untouched) ---
    def _queue_review_mission(
        self,
        *,
        staging_id: str,
        proposal_id: str,
        payload_sha256: str,
        blob_path: Path,
    ) -> str:
        if self.mission_bus is None:
            return ""
        rel_blob_path = blob_path.resolve().relative_to(self.store.workspace.resolve()).as_posix()
        mission_id = "mission_" + hashlib.sha256(
            f"ace.proposer_stage2.review.v1:{staging_id}".encode("utf-8")
        ).hexdigest()[:24]
        now_dt = datetime.fromtimestamp(self._now(), tz=timezone.utc)
        deadline = datetime.fromtimestamp(self._now() + 3600, tz=timezone.utc).isoformat()
        doc = {
            "schema_version": "ace.mission.v1",
            "id": mission_id,
            "goal": f"Review Stage-2 package {proposal_id} ({staging_id}); staging-only internal audit",
            "hypothesis": (
                f"Package payload sha256:{payload_sha256} passed Stage-2 validator in staging-only mode"
            ),
            "task_family_ids": ["proposer_stage2_internal_review"],
            "inputs": [{"path": rel_blob_path, "sha256": payload_sha256}],
            "budget": {"time_sec": 120, "max_candidates": 1},
            "acceptance": {"metric": "internal_ratification_only", "threshold": 1, "comparator": ">="},
            "forbidden": [".git/", "main", "production", "owner_approval"],
            "deadline": deadline,
            "status": "PENDING",
            "staging_id": staging_id,
            "payload_sha256": payload_sha256,
        }
        validate_mission(doc)
        immutable = (
            "schema_version", "id", "goal", "hypothesis", "task_family_ids",
            "inputs", "budget", "acceptance", "forbidden", "staging_id", "payload_sha256",
        )
        with self.mission_bus._get_connection() as con:
            con.execute("BEGIN IMMEDIATE")
            found = con.execute("SELECT data_json FROM missions WHERE id = ?", (mission_id,)).fetchone()
            if found is not None:
                prior = json.loads(found[0])
                if any(prior.get(k) != doc.get(k) for k in immutable):
                    raise RequestConflictError("review mission key reused with changed contract")
                return mission_id
            con.execute(
                "INSERT INTO missions (id,goal,hypothesis,data_json,status,created_at) VALUES (?,?,?,?,?,?)",
                (mission_id, doc["goal"], doc["hypothesis"], json.dumps(doc), "PENDING", now_dt.isoformat()),
            )
            self.mission_bus._append_hash_chain(
                con,
                "MISSION_CREATED",
                {"mission_id": mission_id, "goal": doc["goal"], "hypothesis": doc["hypothesis"]},
            )
            con.commit()
        return mission_id

    # --- 1. Idempotent Staging ---
    def _row_to_staged(self, r: Any) -> dict[str, Any]:
        return {
            "staging_id": r["staging_id"],
            "request_id": r["request_id"],
            "proposal_id": r["proposal_id"],
            "payload_sha256": r["payload_sha256"],
            "identity_mode": r["identity_mode"],
            "blob_path": r["blob_path"],
            "mission_id": r["mission_id"],
            "revoked": bool(r["revoked"]),
            "revoked_by": r["revoked_by"],
            "revoked_reason": r["revoked_reason"],
            "revocation_ledger_seq": int(r["revocation_ledger_seq"]),
            "revoked_at": r["revoked_at"],
            "created_at": r["created_at"],
        }

    def get_staged(self, staging_id: str) -> dict[str, Any] | None:
        with self.store._lock:
            row = self.store._conn.execute(
                "SELECT * FROM proposer_staged_packages WHERE staging_id = ?",
                (staging_id,),
            ).fetchone()
            return self._row_to_staged(row) if row else None

    def stage_package(
        self,
        pkg: dict[str, Any],
        *,
        request_id: str,
        pre_commit_blob_hook: Callable[[Path], None] | None = None,
    ) -> tuple[dict[str, Any], bool]:
        """Validate, persist an immutable canonical package blob, verify digest, then commit DB."""
        if not isinstance(request_id, str) or not request_id.strip():
            raise ValidationRejectedError("request_id must be a non-empty string")
        _check_no_forbidden_terms(request_id, field_name="request_id")
        self._require_clean_ledger()

        canon_bytes = canonical_package_bytes(pkg)
        payload_sha = _sha256_bytes(canon_bytes)
        req_id = request_id.strip()

        with self.store._lock:
            existing = self.store._conn.execute(
                "SELECT * FROM proposer_staged_packages WHERE request_id = ?",
                (req_id,),
            ).fetchone()
            if existing is not None:
                if existing["payload_sha256"] != payload_sha:
                    self._append_ledger_locked(
                        event_type="STAGING_CONFLICT_REJECTED",
                        staging_id=existing["staging_id"],
                        payload_sha256=payload_sha,
                        detail={"request_id": req_id, "expected_sha256": existing["payload_sha256"]},
                    )
                    self.store._conn.commit()
                    raise RequestConflictError(
                        f"request_id {req_id!r} already bound to {existing['payload_sha256']}, "
                        f"cannot restage mismatched payload {payload_sha}"
                    )
                _verify_existing_blob(Path(existing["blob_path"]), payload_sha)
                return self._row_to_staged(existing), False

        staging_id = "stg_" + _sha256_bytes(f"{req_id}:{payload_sha}".encode("utf-8"))[:20]
        blob_path = self.pkg_blobs_dir / f"{payload_sha}_{staging_id}.json"

        # Rule #8C: write immutable blob -> verify digest -> THEN commit DB!
        _write_immutable_bytes(blob_path, canon_bytes)
        if pre_commit_blob_hook is not None:
            pre_commit_blob_hook(blob_path)
        _verify_existing_blob(blob_path, payload_sha)

        mission_id = self._queue_review_mission(
            staging_id=staging_id,
            proposal_id=pkg["proposal_id"],
            payload_sha256=payload_sha,
            blob_path=blob_path,
        )
        now_iso = _utc_iso(self._now())
        with self.store._lock:
            # Double-check idempotency race under lock before inserting.
            existing = self.store._conn.execute(
                "SELECT * FROM proposer_staged_packages WHERE request_id = ?",
                (req_id,),
            ).fetchone()
            if existing is not None:
                if existing["payload_sha256"] != payload_sha:
                    raise RequestConflictError(
                        f"request_id {req_id!r} conflicted concurrently"
                    )
                return self._row_to_staged(existing), False
            self.store._conn.execute(
                """
                INSERT INTO proposer_staged_packages(
                    staging_id, request_id, proposal_id, payload_sha256,
                    identity_mode, blob_path, mission_id, created_at
                ) VALUES (?, ?, ?, ?, 'staging-only', ?, ?, ?)
                """,
                (
                    staging_id,
                    req_id,
                    pkg["proposal_id"],
                    payload_sha,
                    str(blob_path),
                    mission_id,
                    now_iso,
                ),
            )
            self._append_ledger_locked(
                event_type="PACKAGE_STAGED",
                staging_id=staging_id,
                payload_sha256=payload_sha,
                detail={
                    "request_id": req_id,
                    "proposal_id": pkg["proposal_id"],
                    "identity_mode": "staging-only",
                    "mission_id": mission_id,
                },
            )
            self.store._conn.commit()
            return self.get_staged(staging_id), True  # type: ignore[return-value]

    # --- 2. Internal Ratification & Irrevocable Revocation ---
    def _row_to_ratification(self, r: Any) -> dict[str, Any]:
        return {
            "ratification_id": r["ratification_id"],
            "staging_id": r["staging_id"],
            "audience": r["audience"],
            "ratified_by": r["ratified_by"],
            "bound_payload_sha256": r["bound_payload_sha256"],
            "issued_at_epoch": float(r["issued_at_epoch"]),
            "expires_at_epoch": float(r["expires_at_epoch"]),
            "revoked": bool(r["revoked"]),
            "created_at": r["created_at"],
        }

    def ratify_staged(
        self,
        staging_id: str,
        *,
        audience: str,
        payload_sha256: str,
        ttl_seconds: float = 300.0,
        ratified_by: str | None = None,
    ) -> dict[str, Any]:
        """Issue an internal ratification pinned to an exact payload_sha256 and finite TTL."""
        self._require_clean_ledger()
        _check_no_forbidden_terms(
            {"audience": audience, "ratified_by": ratified_by or ""},
            field_name="ratification",
        )
        if audience not in RATIFICATION_AUDIENCE:
            raise RatificationVocabularyError(
                f"invalid internal ratification audience {audience!r}; "
                f"must be one of {RATIFICATION_AUDIENCE}"
            )
        if (
            isinstance(ttl_seconds, bool)
            or not isinstance(ttl_seconds, (int, float))
            or not math.isfinite(float(ttl_seconds))
            or float(ttl_seconds) <= 0.0
        ):
            raise RatificationError(f"ttl_seconds must be a finite number > 0, got {ttl_seconds!r}")
        signer = (ratified_by or f"{audience}:internal-arbiter").strip()
        if not signer:
            raise RatificationError("ratified_by must be non-empty")

        with self.store._lock:
            staged = self.get_staged(staging_id)
            if staged is None:
                raise KeyError(f"unknown staging_id: {staging_id}")
            if staged["revoked"]:
                self._append_ledger_locked(
                    event_type="RATIFICATION_REJECTED_REVOKED",
                    staging_id=staging_id,
                    payload_sha256=payload_sha256,
                    detail={"audience": audience, "effective_seq": staged["revocation_ledger_seq"]},
                )
                self.store._conn.commit()
                raise RevokedError(
                    f"staging_id {staging_id} was irrevocably revoked at seq {staged['revocation_ledger_seq']}"
                )
            if payload_sha256 != staged["payload_sha256"]:
                self._append_ledger_locked(
                    event_type="RATIFICATION_REJECTED_HASH_MISMATCH",
                    staging_id=staging_id,
                    payload_sha256=payload_sha256,
                    detail={"expected": staged["payload_sha256"], "audience": audience},
                )
                self.store._conn.commit()
                raise RatificationError(
                    f"ratification hash mismatch for {staging_id}: "
                    f"expected {staged['payload_sha256']}, got {payload_sha256}"
                )

            now_ep = float(self._now())
            expires_ep = now_ep + float(ttl_seconds)
            rat_id = f"rat_{int(now_ep * 1000)}_{secrets.token_hex(4)}"
            now_iso = _utc_iso(now_ep)
            self.store._conn.execute(
                """
                INSERT INTO proposer_stage2_ratifications(
                    ratification_id, staging_id, audience, ratified_by,
                    bound_payload_sha256, issued_at_epoch, expires_at_epoch, revoked, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)
                """,
                (rat_id, staging_id, audience, signer, payload_sha256, now_ep, expires_ep, now_iso),
            )
            self._append_ledger_locked(
                event_type="INTERNAL_RATIFICATION_GRANTED",
                staging_id=staging_id,
                payload_sha256=payload_sha256,
                detail={
                    "ratification_id": rat_id,
                    "audience": audience,
                    "ratified_by": signer,
                    "expires_at_epoch": expires_ep,
                },
            )
            self.store._conn.commit()
            row = self.store._conn.execute(
                "SELECT * FROM proposer_stage2_ratifications WHERE ratification_id = ?",
                (rat_id,),
            ).fetchone()
            return self._row_to_ratification(row)

    def is_revoked(self, staging_id: str) -> bool:
        with self.store._lock:
            row = self.store._conn.execute(
                "SELECT revoked FROM proposer_staged_packages WHERE staging_id = ?",
                (staging_id,),
            ).fetchone()
            return bool(row and row["revoked"])

    def revoke_staged(
        self,
        staging_id: str,
        *,
        actor: str,
        reason: str,
    ) -> dict[str, Any]:
        """Irrevocably revoke a staged package, record exact ledger seq, and stop active runs."""
        self._require_clean_ledger()
        _check_no_forbidden_terms({"actor": actor, "reason": reason}, field_name="revocation")
        if actor not in RATIFICATION_AUDIENCE and actor != "constitution_guard":
            raise RatificationVocabularyError(
                f"revocation actor must be one of {RATIFICATION_AUDIENCE + ('constitution_guard',)}, got {actor!r}"
            )
        if not isinstance(reason, str) or not reason.strip():
            raise ValidationRejectedError("revocation reason must be non-empty")

        now_iso = _utc_iso(self._now())
        with self.store._lock:
            staged = self.get_staged(staging_id)
            if staged is None:
                raise KeyError(f"unknown staging_id: {staging_id}")
            if staged["revoked"]:
                return staged
            seq = self._append_ledger_locked(
                event_type="RATIFICATION_REVOKED_IRREVOCABLY",
                staging_id=staging_id,
                payload_sha256=staged["payload_sha256"],
                detail={"actor": actor, "reason": reason.strip()},
            )
            self.store._conn.execute(
                """
                UPDATE proposer_staged_packages
                SET revoked = 1, revoked_by = ?, revoked_reason = ?,
                    revocation_ledger_seq = ?, revoked_at = ?
                WHERE staging_id = ?
                """,
                (actor, reason.strip(), seq, now_iso, staging_id),
            )
            self.store._conn.execute(
                "UPDATE proposer_stage2_ratifications SET revoked = 1 WHERE staging_id = ?",
                (staging_id,),
            )
            self.store._conn.commit()
            updated = self.get_staged(staging_id)

        # Signal any active runs (local or cross-engine) for this staging_id immediately.
        with self.store._lock:
            db_running = [
                str(r["execution_run_id"])
                for r in self.store._conn.execute(
                    "SELECT execution_run_id FROM proposer_stage2_runs WHERE staging_id = ? AND status = 'RUNNING'",
                    (staging_id,),
                ).fetchall()
            ]
        with self._active_lock:
            local_running = [
                rid for rid, meta in self._stop_meta.items() if meta.get("staging_id") == staging_id
            ]
        for rid in sorted(set(db_running) | set(local_running)):
            self.request_stop(rid, reason=f"revoked_at_seq:{seq}:{reason.strip()}")
        return updated  # type: ignore[return-value]

    def _persisted_stop_state(self, execution_run_id: str) -> tuple[bool, str]:
        with self.store._lock:
            row = self.store._conn.execute(
                "SELECT stop_requested, stop_reason FROM proposer_stage2_runs WHERE execution_run_id = ?",
                (execution_run_id,),
            ).fetchone()
            if row is None:
                return False, ""
            return bool(row["stop_requested"]), str(row["stop_reason"] or "")

    def request_stop(self, execution_run_id: str, *, reason: str = "explicit_stop") -> bool:
        """Signal an in-flight execution run to stop visibly at the next gate check."""
        _check_no_forbidden_terms(reason, field_name="stop_reason")
        clean_reason = reason.strip() or "explicit_stop"
        now_ep = float(self._now())
        with self.store._lock:
            cur = self.store._conn.execute(
                "UPDATE proposer_stage2_runs SET stop_requested = 1, stop_reason = ? "
                "WHERE execution_run_id = ? AND status = 'RUNNING'",
                (clean_reason, execution_run_id),
            )
            changed = cur.rowcount > 0
            if changed:
                row = self.store._conn.execute(
                    "SELECT staging_id, bound_payload_sha256 FROM proposer_stage2_runs "
                    "WHERE execution_run_id = ?",
                    (execution_run_id,),
                ).fetchone()
                if row is not None:
                    self._append_ledger_locked(
                        event_type="STOP_SIGNAL_RECORDED",
                        staging_id=row["staging_id"],
                        execution_run_id=execution_run_id,
                        payload_sha256=row["bound_payload_sha256"],
                        detail={"reason": clean_reason, "requested_at": now_ep},
                    )
                self.store._conn.commit()
        if not changed:
            return False
        with self._active_lock:
            ev = self._stop_events.get(execution_run_id)
            meta = self._stop_meta.get(execution_run_id)
            if meta is not None:
                meta.setdefault("stop_requested_at", now_ep)
                meta["reason"] = clean_reason
            if ev is not None:
                ev.set()
        return True

    def _stop_reason_for(self, execution_run_id: str, staging_id: str) -> str:
        with self._active_lock:
            meta = self._stop_meta.get(execution_run_id, {})
            if meta.get("reason"):
                return str(meta["reason"])
        persisted_stop, persisted_reason = self._persisted_stop_state(execution_run_id)
        if persisted_stop and persisted_reason:
            return persisted_reason
        staged = self.get_staged(staging_id)
        if staged and staged["revoked"]:
            return f"revoked_at_seq:{staged['revocation_ledger_seq']}"
        return "explicit_stop"

    # --- 3. Fail-Closed Dispatch, Isolated Execution, & Pre-Audit Export ---
    def list_runs(self, staging_id: str | None = None) -> list[dict[str, Any]]:
        with self.store._lock:
            if staging_id is None:
                rows = self.store._conn.execute(
                    "SELECT * FROM proposer_stage2_runs ORDER BY created_at ASC, rowid ASC"
                ).fetchall()
            else:
                rows = self.store._conn.execute(
                    "SELECT * FROM proposer_stage2_runs WHERE staging_id = ? "
                    "ORDER BY created_at ASC, rowid ASC",
                    (staging_id,),
                ).fetchall()
        return [self._row_to_run(r) for r in rows]

    def get_run(self, execution_run_id: str) -> dict[str, Any] | None:
        with self.store._lock:
            row = self.store._conn.execute(
                "SELECT * FROM proposer_stage2_runs WHERE execution_run_id = ?",
                (execution_run_id,),
            ).fetchone()
            return self._row_to_run(row) if row else None

    def _row_to_run(self, r: Any) -> dict[str, Any]:
        return {
            "execution_run_id": r["execution_run_id"],
            "staging_id": r["staging_id"],
            "request_id": r["request_id"],
            "bound_payload_sha256": r["bound_payload_sha256"],
            "ratification_id": r["ratification_id"],
            "identity_mode": r["identity_mode"],
            "status": r["status"],
            "stop_requested": bool(r["stop_requested"]),
            "stop_reason": r["stop_reason"],
            "stop_visible": bool(r["stop_visible"]),
            "calls_used": int(r["calls_used"]),
            "wall_seconds": float(r["wall_seconds"]),
            "cost_units": float(r["cost_units"]),
            "work_completed_units": int(r["work_completed_units"]),
            "bundle_dir": r["bundle_dir"],
            "bundle_manifest_sha256": r["bundle_manifest_sha256"],
            "preaudit_report_sha256": r["preaudit_report_sha256"],
            "preaudit_exit_code": int(r["preaudit_exit_code"]),
            "env_snapshot": json.loads(r["env_snapshot_json"] or "{}"),
            "result_summary": json.loads(r["result_summary_json"] or "{}"),
            "created_at": r["created_at"],
            "finished_at": r["finished_at"],
        }

    def _reject_dispatch(
        self,
        *,
        event_type: str,
        staging_id: str,
        payload_sha256: str,
        detail: dict[str, Any],
        exc: Exception,
    ) -> None:
        with self.store._lock:
            if not self.store._conn.in_transaction:
                self.store._conn.execute("BEGIN IMMEDIATE")
            try:
                self._append_ledger_locked(
                    event_type=event_type,
                    staging_id=staging_id,
                    payload_sha256=payload_sha256,
                    detail=detail,
                )
                self.store._conn.commit()
            except Exception:
                self.store._conn.rollback()
                raise
        raise exc

    def _export_and_verify_bundle(
        self,
        *,
        execution_run_id: str,
        staging_id: str,
        staged: dict[str, Any],
        canon_pkg_bytes: bytes,
        ratification: dict[str, Any],
        env_profile: StagingEnvironmentProfile,
        status: str,
        stop_requested: bool,
        stop_reason: str,
        stop_latency_seconds: float | None,
        ctx_snapshot: dict[str, Any],
        pre_commit_bundle_hook: Callable[[Path], None] | None = None,
    ) -> dict[str, Any]:
        if _sha256_bytes(canon_pkg_bytes) != staged["payload_sha256"]:
            raise BlobIntegrityError("canonical package bytes diverged from staged payload_sha256")
        verified_pkg = json.loads(canon_pkg_bytes.decode("utf-8"))
        ok_pkg, pkg_reasons = validate_package(verified_pkg)
        if not ok_pkg:
            raise ValidationRejectedError(pkg_reasons)

        bundle_root = self.bundles_dir / execution_run_id
        if bundle_root.exists():
            raise BlobIntegrityError(f"bundle directory already exists for {execution_run_id}")
        package_dir = bundle_root / "source"
        preaudit_out_dir = bundle_root / "preaudit_out"
        package_dir.mkdir(parents=True, exist_ok=True)

        # Write package.json using exact canonical bytes verified against payload_sha256.
        pkg_sha, pkg_size = _write_immutable_bytes(package_dir / "package.json", canon_pkg_bytes)
        if pkg_sha != staged["payload_sha256"]:
            raise BlobIntegrityError("package.json digest diverged from staged payload_sha256")

        run_completed = 1 if status == "COMPLETED" else 0
        prereg_doc = {
            "schema": SCHEMA_STAGE2_PREREG,
            "staging_id": staging_id,
            "execution_run_id": execution_run_id,
            "payload_sha256": staged["payload_sha256"],
            "cost_ceiling": verified_pkg["cost_ceiling"],
            "protocol": {
                "pass_rule": {
                    "metric": "run_completed",
                    "op": "eq",
                    "threshold": 1,
                }
            },
        }
        prereg_bytes = (
            json.dumps(prereg_doc, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"
        ).encode("utf-8")
        prereg_sha, prereg_size = _write_immutable_bytes(package_dir / "preregistration.json", prereg_bytes)

        rat_doc = {
            "staging_id": staging_id,
            "execution_run_id": execution_run_id,
            "ratification_id": ratification["ratification_id"],
            "audience": ratification["audience"],
            "ratified_by": ratification["ratified_by"],
            "bound_payload_sha256": ratification["bound_payload_sha256"],
            "expires_at_epoch": ratification["expires_at_epoch"],
            "revoked_at_dispatch": False,
            "identity_mode": "staging-only",
            "env_profile": env_profile.to_snapshot(),
        }
        rat_bytes = (
            json.dumps(rat_doc, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"
        ).encode("utf-8")
        rat_sha, rat_size = _write_immutable_bytes(package_dir / "ratification.json", rat_bytes)

        summary_doc = {
            "schema": SCHEMA_STAGE2_SUMMARY,
            "execution_run_id": execution_run_id,
            "staging_id": staging_id,
            "request_id": staged["request_id"],
            "proposal_id": verified_pkg["proposal_id"],
            "bound_payload_sha256": staged["payload_sha256"],
            "identity_mode": "staging-only",
            "status": status,
            "stop_visible": True,
            "stop_requested": stop_requested,
            "stop_reason": stop_reason,
            "stop_latency_seconds": stop_latency_seconds,
            "cost_used": {
                "calls": ctx_snapshot["calls_used"],
                "wall_seconds": ctx_snapshot["elapsed_seconds"],
                "cost_units": round(float(ctx_snapshot["cost_units"]), 6),
            },
            "work_completed_units": ctx_snapshot["work_completed_units"],
            "steps": ctx_snapshot["steps"],
            "gate_pairs": [{"pair": [run_completed, 1]}],
            "gate_total_pair": [run_completed, 1],
        }
        summary_bytes = (
            json.dumps(summary_doc, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"
        ).encode("utf-8")
        summary_sha, summary_size = _write_immutable_bytes(package_dir / "execution_summary.json", summary_bytes)

        result_rec = {
            "execution_run_id": execution_run_id,
            "staging_id": staging_id,
            "status": status,
            "result": {
                "metrics": {
                    "run_completed": run_completed,
                    "calls_used": ctx_snapshot["calls_used"],
                    "work_completed_units": ctx_snapshot["work_completed_units"],
                },
                "verdict": "pass" if run_completed == 1 else "fail",
            },
        }
        results_bytes = (
            json.dumps(result_rec, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"
        ).encode("utf-8")
        results_sha, results_size = _write_immutable_bytes(package_dir / "results.jsonl", results_bytes)

        manifest_doc = {
            "schema": preaudit_validator.SCHEMA_MANIFEST,
            "package_id": f"{staging_id}:{execution_run_id}",
            "artifacts": [
                {"path": "package.json", "sha256": pkg_sha, "size_bytes": pkg_size},
                {"path": "preregistration.json", "sha256": prereg_sha, "size_bytes": prereg_size},
                {"path": "ratification.json", "sha256": rat_sha, "size_bytes": rat_size},
                {"path": "execution_summary.json", "sha256": summary_sha, "size_bytes": summary_size},
                {"path": "results.jsonl", "sha256": results_sha, "size_bytes": results_size},
            ],
            "count_assertions": [
                {
                    "id": "proposal_id_matches",
                    "kind": "field_equals",
                    "left": {"artifact": "package.json", "pointer": "/proposal_id"},
                    "right": {"artifact": "execution_summary.json", "pointer": "/proposal_id"},
                },
                {
                    "id": "payload_sha256_matches_ratification",
                    "kind": "field_equals",
                    "left": {"artifact": "ratification.json", "pointer": "/bound_payload_sha256"},
                    "right": {"artifact": "execution_summary.json", "pointer": "/bound_payload_sha256"},
                },
                {
                    "id": "gate_pairs_sum",
                    "kind": "sum_pairs_equals",
                    "source": {"artifact": "execution_summary.json", "pointer": "/gate_pairs"},
                    "key": "pair",
                    "target": {"artifact": "execution_summary.json", "pointer": "/gate_total_pair"},
                },
            ],
            "verdict_check": {
                "preregistration": {"artifact": "preregistration.json", "rule_pointer": "/protocol/pass_rule"},
                "results": {"artifact": "results.jsonl"},
            },
        }
        manifest_bytes = (
            json.dumps(manifest_doc, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"
        ).encode("utf-8")
        manifest_path = bundle_root / "manifest.json"
        manifest_sha, _ = _write_immutable_bytes(manifest_path, manifest_bytes)

        if pre_commit_bundle_hook is not None:
            pre_commit_bundle_hook(package_dir)

        # Verify every immutable artifact matches expected digests BEFORE running preaudit and committing DB.
        _verify_existing_blob(package_dir / "package.json", pkg_sha)
        _verify_existing_blob(package_dir / "preregistration.json", prereg_sha)
        _verify_existing_blob(package_dir / "ratification.json", rat_sha)
        _verify_existing_blob(package_dir / "execution_summary.json", summary_sha)
        _verify_existing_blob(package_dir / "results.jsonl", results_sha)
        _verify_existing_blob(manifest_path, manifest_sha)

        pre_rc = preaudit_validator.main([
            "--manifest", str(manifest_path),
            "--source-root", str(package_dir),
            "--out-dir", str(preaudit_out_dir),
        ])
        if pre_rc != 0:
            raise BlobIntegrityError(
                f"preaudit_validator failed fail-closed on {execution_run_id} with exit={pre_rc}"
            )
        report_files = sorted(preaudit_out_dir.glob("report-*.json"))
        if len(report_files) != 1:
            raise BlobIntegrityError(
                f"expected exactly 1 preaudit report json in {preaudit_out_dir}, found {len(report_files)}"
            )
        report_sha = _sha256_bytes(report_files[0].read_bytes())
        return {
            "bundle_dir": str(bundle_root),
            "manifest_sha256": manifest_sha,
            "preaudit_report_sha256": report_sha,
            "preaudit_exit_code": int(pre_rc),
            "summary_doc": summary_doc,
        }

    def dispatch_staged(
        self,
        staging_id: str,
        *,
        expected_payload_sha256: str,
        env_profile: StagingEnvironmentProfile | None = None,
        worker: Callable[[StagingRunContext, dict[str, Any]], dict[str, Any] | None] | None = None,
        pre_commit_bundle_hook: Callable[[Path], None] | None = None,
    ) -> dict[str, Any]:
        """Execute an internally ratified staged package in isolated staging-only mode."""
        self._require_clean_ledger()
        staged = self.get_staged(staging_id)
        if staged is None:
            raise KeyError(f"unknown staging_id: {staging_id}")

        if expected_payload_sha256 != staged["payload_sha256"]:
            self._reject_dispatch(
                event_type="DISPATCH_REJECTED_HASH_MISMATCH",
                staging_id=staging_id,
                payload_sha256=expected_payload_sha256,
                detail={"expected": staged["payload_sha256"], "provided": expected_payload_sha256},
                exc=RatificationError(
                    f"dispatch payload_sha256 mismatch: staged {staged['payload_sha256']}, "
                    f"provided {expected_payload_sha256}"
                ),
            )

        # Read and verify immutable staged package blob BEFORE ratification / env checks.
        canon_bytes = _verify_existing_blob(Path(staged["blob_path"]), staged["payload_sha256"])
        pkg = json.loads(canon_bytes.decode("utf-8"))
        ok, reasons = validate_package(pkg)
        if not ok:
            self._reject_dispatch(
                event_type="DISPATCH_REJECTED_INVALID_PACKAGE",
                staging_id=staging_id,
                payload_sha256=staged["payload_sha256"],
                detail={"reasons": reasons},
                exc=ValidationRejectedError(reasons),
            )

        if pkg["recommended_option"] == "do_not_run":
            self._reject_dispatch(
                event_type="DISPATCH_REJECTED_DO_NOT_RUN",
                staging_id=staging_id,
                payload_sha256=staged["payload_sha256"],
                detail={"recommended_option": "do_not_run"},
                exc=DoNotRunError(
                    f"package {staged['proposal_id']} recommends 'do_not_run'; refusing active dispatch"
                ),
            )

        # Enforce no_auto_retry after RUNNING / FINALIZING / FINALIZE_FAILED / STOPPED / ABORTED_CEILING / FAILED.
        prior_runs = self.list_runs(staging_id)
        blocked_states = (
            "RUNNING",
            "FINALIZING",
            "FINALIZE_FAILED",
            "STOPPED",
            "ABORTED_CEILING",
            "FAILED",
        )
        halted = [r for r in prior_runs if r["status"] in blocked_states]
        if halted:
            self._reject_dispatch(
                event_type="DISPATCH_REJECTED_NO_AUTO_RETRY",
                staging_id=staging_id,
                payload_sha256=staged["payload_sha256"],
                detail={
                    "prior_run_id": halted[-1]["execution_run_id"],
                    "prior_status": halted[-1]["status"],
                },
                exc=AutoRetryBlockedError(
                    f"no_auto_retry=True forbids re-dispatch after {halted[-1]['status']} "
                    f"(run {halted[-1]['execution_run_id']})"
                ),
            )

        # Revocation check precedes expiry / missing ratification.
        if staged["revoked"]:
            self._reject_dispatch(
                event_type="DISPATCH_REJECTED_REVOKED",
                staging_id=staging_id,
                payload_sha256=staged["payload_sha256"],
                detail={"revocation_ledger_seq": staged["revocation_ledger_seq"]},
                exc=RevokedError(
                    f"dispatch refused: staging_id {staging_id} revoked at seq {staged['revocation_ledger_seq']}"
                ),
            )

        now_ep = float(self._now())
        with self.store._lock:
            rat_rows = self.store._conn.execute(
                """
                SELECT * FROM proposer_stage2_ratifications
                WHERE staging_id = ? AND bound_payload_sha256 = ?
                ORDER BY issued_at_epoch DESC, rowid DESC
                """,
                (staging_id, staged["payload_sha256"]),
            ).fetchall()

        if not rat_rows:
            self._reject_dispatch(
                event_type="DISPATCH_REJECTED_UNRATIFIED",
                staging_id=staging_id,
                payload_sha256=staged["payload_sha256"],
                detail={"reason": "no matching internal ratification"},
                exc=RatificationError(f"staging_id {staging_id} lacks internal ratification"),
            )

        active_rat = None
        any_revoked = False
        for row in rat_rows:
            rat = self._row_to_ratification(row)
            if rat["revoked"]:
                any_revoked = True
                continue
            if rat["audience"] not in RATIFICATION_AUDIENCE:
                raise RatificationVocabularyError(
                    f"stored ratification uses disallowed audience {rat['audience']!r}"
                )
            _check_no_forbidden_terms(rat, field_name="stored_ratification")
            if rat["expires_at_epoch"] > now_ep:
                active_rat = rat
                break
        if active_rat is None:
            if any_revoked:
                self._reject_dispatch(
                    event_type="DISPATCH_REJECTED_REVOKED",
                    staging_id=staging_id,
                    payload_sha256=staged["payload_sha256"],
                    detail={"reason": "all matching ratifications revoked"},
                    exc=RevokedError(f"ratification revoked for {staging_id}"),
                )
            self._reject_dispatch(
                event_type="DISPATCH_REJECTED_EXPIRED",
                staging_id=staging_id,
                payload_sha256=staged["payload_sha256"],
                detail={"now_epoch": now_ep, "latest_expiry": float(rat_rows[0]["expires_at_epoch"])},
                exc=RatificationError(f"internal ratification for {staging_id} has expired"),
            )

        profile = env_profile or self.default_environment_profile()
        try:
            dummy_root = profile.validate(allowed_dummy_base=self.dummy_base_dir)
        except EnvironmentIsolationError as exc:
            self._reject_dispatch(
                event_type="DISPATCH_REJECTED_ENV_ISOLATION",
                staging_id=staging_id,
                payload_sha256=staged["payload_sha256"],
                detail={"error": str(exc)},
                exc=exc,
            )
            raise  # unreachable; keeps type checker happy

        # Mint fresh execution_run_id (#8C: unique per intentional execution / replication).
        run_id = f"stgrun_{int(now_ep * 1000)}_{secrets.token_hex(4)}"
        run_dummy_root = (dummy_root / run_id).resolve()
        env_snap = profile.to_snapshot()
        created_iso = _utc_iso(now_ep)

        stop_event = threading.Event()
        with self._active_lock:
            self._stop_events[run_id] = stop_event
            self._stop_meta[run_id] = {"staging_id": staging_id}

        inserted = False
        try:
            with self.store._lock:
                self.store._conn.execute("BEGIN IMMEDIATE")
                try:
                    # Re-check active/blocked states & revocation inside write lock so
                    # concurrent dispatches across engine instances cannot both start.
                    blocked_placeholders = ",".join("?" for _ in blocked_states)
                    conflict_row = self.store._conn.execute(
                        f"SELECT execution_run_id, status FROM proposer_stage2_runs "
                        f"WHERE staging_id = ? AND status IN ({blocked_placeholders}) "
                        f"ORDER BY created_at DESC, rowid DESC LIMIT 1",
                        (staging_id, *blocked_states),
                    ).fetchone()
                    if conflict_row is not None:
                        self._append_ledger_locked(
                            event_type="DISPATCH_REJECTED_NO_AUTO_RETRY",
                            staging_id=staging_id,
                            payload_sha256=staged["payload_sha256"],
                            detail={
                                "prior_run_id": conflict_row["execution_run_id"],
                                "prior_status": conflict_row["status"],
                            },
                        )
                        self.store._conn.commit()
                        raise AutoRetryBlockedError(
                            f"no_auto_retry=True forbids re-dispatch after {conflict_row['status']} "
                            f"(run {conflict_row['execution_run_id']})"
                        )

                    pkg_rev_row = self.store._conn.execute(
                        "SELECT revoked, revocation_ledger_seq FROM proposer_staged_packages WHERE staging_id = ?",
                        (staging_id,),
                    ).fetchone()
                    if pkg_rev_row is not None and bool(pkg_rev_row["revoked"]):
                        seq = int(pkg_rev_row["revocation_ledger_seq"])
                        self._append_ledger_locked(
                            event_type="DISPATCH_REJECTED_REVOKED",
                            staging_id=staging_id,
                            payload_sha256=staged["payload_sha256"],
                            detail={"revocation_ledger_seq": seq},
                        )
                        self.store._conn.commit()
                        raise RevokedError(
                            f"dispatch refused: staging_id {staging_id} revoked at seq {seq}"
                        )

                    self.store._conn.execute(
                        """
                        INSERT INTO proposer_stage2_runs(
                            execution_run_id, staging_id, request_id, bound_payload_sha256,
                            ratification_id, identity_mode, status, env_snapshot_json, created_at
                        ) VALUES (?, ?, ?, ?, ?, 'staging-only', 'RUNNING', ?, ?)
                        """,
                        (
                            run_id,
                            staging_id,
                            staged["request_id"],
                            staged["payload_sha256"],
                            active_rat["ratification_id"],
                            json.dumps(env_snap, sort_keys=True, ensure_ascii=False),
                            created_iso,
                        ),
                    )
                    self._append_ledger_locked(
                        event_type="RUN_DISPATCHED",
                        staging_id=staging_id,
                        execution_run_id=run_id,
                        payload_sha256=staged["payload_sha256"],
                        detail={
                            "ratification_id": active_rat["ratification_id"],
                            "audience": active_rat["audience"],
                            "identity_mode": "staging-only",
                        },
                    )
                    self.store._conn.commit()
                    inserted = True
                except sqlite3.IntegrityError as exc:
                    self.store._conn.rollback()
                    conflict_row = self.store._conn.execute(
                        f"SELECT execution_run_id, status FROM proposer_stage2_runs "
                        f"WHERE staging_id = ? AND status IN ({','.join('?' for _ in blocked_states)}) "
                        f"ORDER BY created_at DESC, rowid DESC LIMIT 1",
                        (staging_id, *blocked_states),
                    ).fetchone()
                    prior_id = conflict_row["execution_run_id"] if conflict_row else ""
                    prior_status = conflict_row["status"] if conflict_row else "ACTIVE"
                    self.store._conn.execute("BEGIN IMMEDIATE")
                    self._append_ledger_locked(
                        event_type="DISPATCH_REJECTED_NO_AUTO_RETRY",
                        staging_id=staging_id,
                        payload_sha256=staged["payload_sha256"],
                        detail={"prior_run_id": prior_id, "prior_status": prior_status},
                    )
                    self.store._conn.commit()
                    raise AutoRetryBlockedError(
                        f"no_auto_retry=True forbids re-dispatch after {prior_status} (run {prior_id})"
                    ) from exc
                except BaseException:
                    if self.store._conn.in_transaction:
                        self.store._conn.rollback()
                    raise
        finally:
            if not inserted:
                with self._active_lock:
                    self._stop_events.pop(run_id, None)
                    self._stop_meta.pop(run_id, None)

        run_dummy_root.mkdir(parents=True, exist_ok=True)
        ctx = StagingRunContext(
            engine=self,
            execution_run_id=run_id,
            staging_id=staging_id,
            bound_payload_sha256=staged["payload_sha256"],
            ceiling=pkg["cost_ceiling"],
            dummy_root=run_dummy_root,
            dummy_credentials=profile.dummy_credentials,
            stop_event=stop_event,
            now_fn=self._now,
        )

        # Pass an isolated deep copy parsed directly from verified canonical bytes to the worker.
        worker_pkg = json.loads(canon_bytes.decode("utf-8"))
        worker_done = threading.Event()
        worker_holder: dict[str, Any] = {
            "status": "COMPLETED",
            "stop_requested": False,
            "stop_reason": "",
            "out": {},
        }

        def _worker_runner() -> None:
            try:
                ctx.check_gates()
                if worker is None:
                    est_calls = max(
                        1,
                        min(
                            int(worker_pkg["cost_estimate"]["calls"]),
                            int(worker_pkg["cost_ceiling"]["max_calls"]),
                        ),
                    )
                    ctx.record_step(
                        step_name="isolated_staging_dry_probe",
                        calls=est_calls,
                        cost_units=min(
                            float(worker_pkg["cost_estimate"]["cost_units"]),
                            float(worker_pkg["cost_ceiling"]["max_cost_units"]),
                        ),
                        work_units=1,
                        dummy_artifact_rel=f"{run_id}_probe.json",
                        dummy_content=json.dumps({
                            "execution_run_id": run_id,
                            "staging_id": staging_id,
                            "identity_mode": "staging-only",
                            "dummy_account": profile.dummy_credentials.get("staging_account", ""),
                        }).encode("utf-8"),
                    )
                else:
                    res = worker(ctx, worker_pkg)
                    if res is not None:
                        if not isinstance(res, dict):
                            raise ValidationRejectedError(
                                f"worker returned {type(res).__name__}, expected dict or None"
                            )
                        try:
                            serialized_out = json.dumps(
                                res,
                                sort_keys=True,
                                ensure_ascii=False,
                                allow_nan=False,
                            )
                            snapshot_out = json.loads(serialized_out)
                        except (TypeError, ValueError) as exc:
                            raise ValidationRejectedError(
                                f"worker output is not JSON-compatible: {exc}"
                            ) from exc
                        if not isinstance(snapshot_out, dict):
                            raise ValidationRejectedError("worker output snapshot must be a JSON object")
                        _check_no_forbidden_terms(snapshot_out, field_name="worker_output")
                        worker_holder["out"] = snapshot_out
                ctx.check_gates()
            except _StopTriggered as exc:
                worker_holder["status"] = "STOPPED"
                worker_holder["stop_requested"] = True
                worker_holder["stop_reason"] = exc.reason
            except _CeilingExceeded as exc:
                worker_holder["status"] = "ABORTED_CEILING"
                worker_holder["stop_requested"] = True
                worker_holder["stop_reason"] = exc.reason
            except BaseException as exc:
                sealed_kind, sealed_reason = ctx._sealed_outcome()
                if sealed_kind == "STOPPED":
                    worker_holder["status"] = "STOPPED"
                    worker_holder["stop_requested"] = True
                    worker_holder["stop_reason"] = sealed_reason
                elif sealed_kind == "ABORTED_CEILING":
                    worker_holder["status"] = "ABORTED_CEILING"
                    worker_holder["stop_requested"] = True
                    worker_holder["stop_reason"] = sealed_reason
                else:
                    worker_holder["status"] = "FAILED"
                    worker_holder["stop_reason"] = f"{type(exc).__name__}: {exc}"[:300]
            finally:
                worker_done.set()

        wt = threading.Thread(target=_worker_runner, name=f"stage2-{run_id}", daemon=True)
        wt.start()
        worker_tid = wt.ident

        max_wall = float(pkg["cost_ceiling"]["max_wall_seconds"])
        trigger_kind = ""
        trigger_reason = ""
        trigger_mono: float | None = None
        grace_sec = 0.0
        supervised_aborted = False

        while not worker_done.wait(timeout=0.02):
            elapsed_wall = ctx.elapsed_seconds()
            persisted_stop, _ = self._persisted_stop_state(run_id)
            if persisted_stop:
                stop_event.set()
            revoked_now = self.is_revoked(staging_id)
            if elapsed_wall > max_wall:
                if trigger_kind != "ABORTED_CEILING":
                    trigger_kind = "ABORTED_CEILING"
                    trigger_reason = f"wall_seconds {elapsed_wall} exceeds max_wall_seconds {pkg['cost_ceiling']['max_wall_seconds']}"
                    trigger_mono = time.monotonic()
                    grace_sec = 0.05
            elif stop_event.is_set() or persisted_stop or revoked_now:
                if not trigger_kind:
                    trigger_kind = "STOPPED"
                    trigger_reason = self._stop_reason_for(run_id, staging_id)
                    trigger_mono = time.monotonic()
                    grace_sec = 0.15

            if trigger_kind and trigger_mono is not None and (time.monotonic() - trigger_mono) >= grace_sec:
                ctx._seal(trigger_kind, trigger_reason)
                if wt.is_alive():
                    _interrupt_thread(worker_tid, _WorkerInterrupted)
                if not worker_done.wait(timeout=0.10):
                    if wt.is_alive():
                        _interrupt_thread(worker_tid, _WorkerInterrupted)
                    worker_done.wait(timeout=0.05)
                supervised_aborted = True
                break

        end_ep = float(self._now())

        if worker_done.is_set() and not supervised_aborted:
            final_status = str(worker_holder["status"])
            stop_requested = bool(worker_holder["stop_requested"])
            stop_reason = str(worker_holder["stop_reason"])
            worker_out = dict(worker_holder["out"]) if final_status == "COMPLETED" and isinstance(worker_holder["out"], dict) else {}
        else:
            if worker_done.is_set() and worker_holder["status"] in ("STOPPED", "ABORTED_CEILING"):
                final_status = str(worker_holder["status"])
                stop_requested = True
                stop_reason = str(worker_holder["stop_reason"]) or trigger_reason
            else:
                final_status = trigger_kind
                stop_requested = True
                stop_reason = trigger_reason
            worker_out = {}

        # Freeze metrics snapshot before entering finalization so late daemon thread wakes cannot mutate state.
        ctx_snapshot = ctx._seal(
            final_status if final_status in ("STOPPED", "ABORTED_CEILING") else "FINALIZED",
            stop_reason,
        )

        # Atomically serialize RUNNING -> FINALIZING with request_stop acceptance on store._lock.
        stop_req_at_db: float | None = None
        with self.store._lock:
            run_row = self.store._conn.execute(
                "SELECT stop_requested, stop_reason FROM proposer_stage2_runs WHERE execution_run_id = ?",
                (run_id,),
            ).fetchone()
            db_stop_requested = bool(run_row and run_row["stop_requested"])
            db_stop_reason = str(run_row["stop_reason"] or "") if run_row else ""

            pkg_row = self.store._conn.execute(
                "SELECT revoked, revocation_ledger_seq FROM proposer_staged_packages WHERE staging_id = ?",
                (staging_id,),
            ).fetchone()
            db_revoked = bool(pkg_row and pkg_row["revoked"])

            if final_status == "COMPLETED" and (stop_event.is_set() or db_stop_requested or db_revoked):
                final_status = "STOPPED"
                stop_requested = True
                if db_stop_reason:
                    stop_reason = db_stop_reason
                elif db_revoked:
                    stop_reason = f"revoked_at_seq:{int(pkg_row['revocation_ledger_seq'])}"
                else:
                    stop_reason = "explicit_stop"
            elif final_status == "STOPPED" and db_stop_requested and db_stop_reason:
                stop_reason = db_stop_reason

            if stop_requested:
                sig_row = self.store._conn.execute(
                    "SELECT detail_json FROM proposer_stage2_ledger "
                    "WHERE execution_run_id = ? AND event_type = 'STOP_SIGNAL_RECORDED' "
                    "ORDER BY seq DESC LIMIT 1",
                    (run_id,),
                ).fetchone()
                if sig_row is not None:
                    sig_detail = json.loads(sig_row["detail_json"] or "{}")
                    if "requested_at" in sig_detail:
                        stop_req_at_db = float(sig_detail["requested_at"])

            self.store._conn.execute(
                "UPDATE proposer_stage2_runs SET status = 'FINALIZING', stop_requested = ?, stop_reason = ? "
                "WHERE execution_run_id = ? AND status = 'RUNNING'",
                (1 if stop_requested else 0, stop_reason, run_id),
            )
            self.store._conn.commit()

        with self._active_lock:
            self._stop_events.pop(run_id, None)
            meta = self._stop_meta.pop(run_id, {})

        stop_latency: float | None = None
        req_at = meta.get("stop_requested_at", stop_req_at_db)
        if stop_requested and req_at is not None:
            stop_latency = round(max(0.0, end_ep - float(req_at)), 6)

        try:
            bundle_info = self._export_and_verify_bundle(
                execution_run_id=run_id,
                staging_id=staging_id,
                staged=staged,
                canon_pkg_bytes=canon_bytes,
                ratification=active_rat,
                env_profile=profile,
                status=final_status,
                stop_requested=stop_requested,
                stop_reason=stop_reason,
                stop_latency_seconds=stop_latency,
                ctx_snapshot=ctx_snapshot,
                pre_commit_bundle_hook=pre_commit_bundle_hook,
            )
        except Exception as exc:
            fail_iso = _utc_iso(float(self._now()))
            err_msg = f"{type(exc).__name__}: {exc}"[:300]
            comb_reason = err_msg if not stop_reason else f"{stop_reason} | finalize_error: {err_msg}"[:300]
            with self.store._lock:
                self.store._conn.execute(
                    """
                    UPDATE proposer_stage2_runs SET
                        status = 'FINALIZE_FAILED',
                        stop_requested = ?,
                        stop_reason = ?,
                        stop_visible = 1,
                        calls_used = ?,
                        wall_seconds = ?,
                        cost_units = ?,
                        work_completed_units = ?,
                        bundle_manifest_sha256 = '',
                        preaudit_report_sha256 = '',
                        preaudit_exit_code = -1,
                        result_summary_json = ?,
                        finished_at = ?
                    WHERE execution_run_id = ?
                    """,
                    (
                        1 if stop_requested else 0,
                        comb_reason,
                        ctx_snapshot["calls_used"],
                        ctx_snapshot["elapsed_seconds"],
                        round(float(ctx_snapshot["cost_units"]), 6),
                        ctx_snapshot["work_completed_units"],
                        json.dumps(
                            {
                                "worker_output": worker_out,
                                "steps": ctx_snapshot["steps"],
                                "stop_latency_seconds": stop_latency,
                                "finalize_error": err_msg,
                            },
                            sort_keys=True,
                            ensure_ascii=False,
                        ),
                        fail_iso,
                        run_id,
                    ),
                )
                self._append_ledger_locked(
                    event_type="RUN_FINALIZE_FAILED",
                    staging_id=staging_id,
                    execution_run_id=run_id,
                    payload_sha256=staged["payload_sha256"],
                    detail={
                        "prior_execution_status": final_status,
                        "error": err_msg,
                    },
                )
                self.store._conn.commit()
            raise

        finished_iso = _utc_iso(end_ep)
        result_summary = {
            "worker_output": worker_out,
            "steps": ctx_snapshot["steps"],
            "stop_latency_seconds": stop_latency,
        }
        # Commit finalized DB state ONLY after immutable blobs + preaudit verification passed!
        with self.store._lock:
            self.store._conn.execute(
                """
                UPDATE proposer_stage2_runs SET
                    status = ?,
                    stop_requested = ?,
                    stop_reason = ?,
                    stop_visible = 1,
                    calls_used = ?,
                    wall_seconds = ?,
                    cost_units = ?,
                    work_completed_units = ?,
                    bundle_dir = ?,
                    bundle_manifest_sha256 = ?,
                    preaudit_report_sha256 = ?,
                    preaudit_exit_code = ?,
                    result_summary_json = ?,
                    finished_at = ?
                WHERE execution_run_id = ?
                """,
                (
                    final_status,
                    1 if stop_requested else 0,
                    stop_reason,
                    ctx_snapshot["calls_used"],
                    ctx_snapshot["elapsed_seconds"],
                    round(float(ctx_snapshot["cost_units"]), 6),
                    ctx_snapshot["work_completed_units"],
                    bundle_info["bundle_dir"],
                    bundle_info["manifest_sha256"],
                    bundle_info["preaudit_report_sha256"],
                    bundle_info["preaudit_exit_code"],
                    json.dumps(result_summary, sort_keys=True, ensure_ascii=False),
                    finished_iso,
                    run_id,
                ),
            )
            self._append_ledger_locked(
                event_type="RUN_FINALIZED",
                staging_id=staging_id,
                execution_run_id=run_id,
                payload_sha256=staged["payload_sha256"],
                detail={
                    "status": final_status,
                    "calls_used": ctx_snapshot["calls_used"],
                    "wall_seconds": ctx_snapshot["elapsed_seconds"],
                    "cost_units": round(float(ctx_snapshot["cost_units"]), 6),
                    "work_completed_units": ctx_snapshot["work_completed_units"],
                    "stop_visible": True,
                    "stop_reason": stop_reason,
                    "bundle_manifest_sha256": bundle_info["manifest_sha256"],
                    "preaudit_exit_code": bundle_info["preaudit_exit_code"],
                },
            )
            self.store._conn.commit()
        return self.get_run(run_id)  # type: ignore[return-value]
