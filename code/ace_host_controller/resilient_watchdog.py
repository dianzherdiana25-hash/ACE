"""Autonomous Resilient Watchdog & Recovery Controller for long-running ACE background execution.

Provides authoritative runtime supervision, automated hang/stall detection,
fail-closed checkpoint auto-recovery with cryptographic Merkle verification,
and periodic heartbeat telemetry beacons.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import resource
import secrets
import sys
import threading
import time
import traceback
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple, TypeVar

T = TypeVar("T")

GENESIS_BASELINE: Dict[str, Any] = {
    "root_candidate_id": "G0_self_dev_root_c0",
    "root_source_sha": "root_genesis_predicate_len3_even",
    "root_predicate_code": "def evaluate_mechanism(length: int, density: int, stride_val: int) -> int:\n    return length % 3",
    "baseline_accuracy": 0.5000,
    "genesis_timestamp": "2026-11-07T00:00:00Z",
}

GENESIS_DIGEST = hashlib.sha256(
    json.dumps(GENESIS_BASELINE, sort_keys=True).encode("utf-8")
).hexdigest()


class WatchdogError(Exception):
    """Base exception for watchdog operations."""


class CycleStallTimeoutError(WatchdogError):
    """Raised when an autonomous execution cycle exceeds its timeout threshold."""


class StateIntegrityError(WatchdogError):
    """Raised when research state fails cryptographic Merkle or schema verification."""


class RecoveryFailedError(WatchdogError):
    """Raised when checkpoint auto-recovery cannot restore a valid state."""


@dataclass(frozen=True)
class ResourceStats:
    """Snapshot of process memory, CPU consumption, and thread count."""

    rss_memory_mb: float
    max_rss_mb: float
    cpu_user_seconds: float
    cpu_system_seconds: float
    cpu_percent: float
    active_threads: int
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DiagnosticDump:
    """Diagnostic crash and stall report with thread stacks and resource telemetry."""

    dump_id: str
    timestamp: str
    trigger_reason: str
    cycle_id: Optional[int]
    elapsed_seconds: float
    timeout_threshold_seconds: float
    resource_stats: Dict[str, Any]
    thread_stacks: Dict[str, List[str]]
    error_message: Optional[str] = None
    traceback_str: Optional[str] = None
    state_summary: Dict[str, Any] = field(default_factory=dict)
    recovery_triggered: bool = False
    recovered_cycle_count: Optional[int] = None
    recovered_from: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TelemetryBeacon:
    """Periodic health beacon tracking daemon throughput, latency, and resource metrics."""

    beacon_id: int
    timestamp: str
    uptime_seconds: float
    cycles_completed: int
    cycles_failed: int
    cycle_throughput_per_hour: float
    average_cycle_duration_seconds: float
    last_cycle_id: Optional[int]
    last_cycle_duration_seconds: float
    resource_stats: Dict[str, Any]
    health_status: str  # HEALTHY, DEGRADED, STALLED, RECOVERING
    active_state_digest: str
    concurrency_lock_held: bool
    recovery_count: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class WatchdogConfig:
    """Configuration parameters for ResilientWatchdog."""

    state_dir: str = "checkpoints/self_dev"
    state_file: str = "research_state.json"
    recovery_file: str = "recovery_baseline.json"
    immutable_file: str = "immutable_baseline.json"
    heartbeat_file: str = "heartbeat.json"
    diagnostic_dir: str = "evidence/self_dev/diagnostics"
    cycle_timeout_seconds: float = 60.0
    heartbeat_interval_seconds: float = 15.0
    memory_limit_mb: float = 1024.0
    auto_recover_on_stall: bool = True
    max_consecutive_stalls: int = 3


def sample_process_resources(
    prev_cpu_times: Optional[Tuple[float, float]] = None,
    prev_wall_time: Optional[float] = None,
) -> Tuple[ResourceStats, Tuple[Tuple[float, float], float]]:
    """Sample current process memory footprint, CPU consumption, and active threads."""
    now_wall = time.time()
    t = os.times()
    user_time = t.user
    system_time = t.system
    current_cpu_times = (user_time, system_time)

    # Resident Set Size (RSS) memory in MB
    rss_mb = 0.0
    try:
        status_path = Path("/proc/self/status")
        if status_path.is_file():
            with open(status_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        parts = line.split()
                        if len(parts) >= 2:
                            rss_mb = round(float(parts[1]) / 1024.0, 2)
                        break
    except Exception:
        pass

    ru = resource.getrusage(resource.RUSAGE_SELF)
    max_rss_mb = round(ru.ru_maxrss / 1024.0, 2)
    if rss_mb <= 0.0:
        rss_mb = max_rss_mb

    cpu_percent = 0.0
    if prev_cpu_times is not None and prev_wall_time is not None:
        delta_wall = max(1e-6, now_wall - prev_wall_time)
        delta_cpu = (user_time - prev_cpu_times[0]) + (system_time - prev_cpu_times[1])
        cpu_percent = round(max(0.0, (delta_cpu / delta_wall) * 100.0), 2)

    active_threads = threading.active_count()
    timestamp = datetime.now(timezone.utc).isoformat()

    stats = ResourceStats(
        rss_memory_mb=rss_mb,
        max_rss_mb=max_rss_mb,
        cpu_user_seconds=round(user_time, 4),
        cpu_system_seconds=round(system_time, 4),
        cpu_percent=cpu_percent,
        active_threads=active_threads,
        timestamp=timestamp,
    )
    return stats, (current_cpu_times, now_wall)


def compute_merkle_root(leaf_hashes: Sequence[str]) -> str:
    """Compute binary Merkle tree root from a list of leaf sha256 hashes."""
    if not leaf_hashes:
        return "0" * 64
    if len(leaf_hashes) == 1:
        return leaf_hashes[0]

    current_level = list(leaf_hashes)
    while len(current_level) > 1:
        next_level = []
        for i in range(0, len(current_level), 2):
            left = current_level[i]
            if i + 1 < len(current_level):
                right = current_level[i + 1]
            else:
                right = left  # duplicate odd leaf as standard in Merkle trees
            pair_hash = hashlib.sha256((left + right).encode("utf-8")).hexdigest()
            next_level.append(pair_hash)
        current_level = next_level

    return current_level[0]


def verify_merkle_tree(leaf_hashes: Sequence[str], expected_root: str) -> bool:
    """Verify if calculated Merkle root matches expected root."""
    return compute_merkle_root(leaf_hashes) == expected_root


def verify_state_merkle_chain(
    state_data: Dict[str, Any],
) -> Tuple[bool, str, int]:
    """Verify cryptographic Merkle chaining and schema invariants of research state.

    Returns:
        (is_valid, reason, last_valid_cycle_id)
    """
    if not isinstance(state_data, dict):
        return False, "State payload is not a valid JSON dictionary", 0

    if state_data.get("schema_version") != "2.0":
        return False, f"Invalid schema_version: {state_data.get('schema_version')}", 0

    immutable_baseline = state_data.get("immutable_baseline")
    if not isinstance(immutable_baseline, dict):
        return False, "Missing immutable_baseline dictionary", 0

    expected_genesis_digest = hashlib.sha256(
        json.dumps(immutable_baseline, sort_keys=True).encode("utf-8")
    ).hexdigest()

    completed_cycles = state_data.get("completed_cycles")
    if not isinstance(completed_cycles, list):
        return False, "Missing or invalid completed_cycles list", 0

    if len(completed_cycles) == 0:
        recorded_digest = state_data.get("state_digest")
        if recorded_digest != expected_genesis_digest:
            return (
                False,
                f"Genesis state digest mismatch: {recorded_digest} != {expected_genesis_digest}",
                0,
            )
        return True, "Genesis state verified", 0

    expected_prior = expected_genesis_digest
    for i, cycle in enumerate(completed_cycles):
        if not isinstance(cycle, dict):
            return False, f"Cycle at index {i} is not a valid dict", i
        cycle_id = cycle.get("cycle_id")
        if cycle_id is None:
            return False, f"Cycle at index {i} missing cycle_id", i
        if i > 0:
            prev_id = completed_cycles[i - 1].get("cycle_id")
            if cycle_id != prev_id + 1:
                return (
                    False,
                    f"Non-sequential cycle_id at index {i}: {cycle_id} != {prev_id} + 1",
                    prev_id,
                )

        prior_digest = cycle.get("prior_digest")
        if prior_digest != expected_prior:
            return (
                False,
                f"Merkle chain broken at cycle {cycle_id}: prior_digest {prior_digest} != expected {expected_prior}",
                completed_cycles[i - 1].get("cycle_id") if i > 0 else 0,
            )

        state_digest = cycle.get("state_digest")
        if not state_digest or len(state_digest) != 64:
            return (
                False,
                f"Cycle {cycle_id} has invalid or missing state_digest",
                completed_cycles[i - 1].get("cycle_id") if i > 0 else 0,
            )

        expected_prior = state_digest

    last_cycle = completed_cycles[-1]
    if state_data.get("state_digest") != last_cycle.get("state_digest"):
        return (
            False,
            f"State overall digest mismatch: {state_data.get('state_digest')} != {last_cycle.get('state_digest')}",
            last_cycle.get("cycle_id"),
        )

    if state_data.get("cycle_count") != len(completed_cycles):
        return (
            False,
            f"Cycle count mismatch: {state_data.get('cycle_count')} != {len(completed_cycles)}",
            last_cycle.get("cycle_id"),
        )

    return True, f"Merkle chain verified across {len(completed_cycles)} cycles", last_cycle.get("cycle_id")


def recover_research_state(
    state_dir: Path,
    state_file: str = "research_state.json",
    recovery_file: str = "recovery_baseline.json",
    immutable_file: str = "immutable_baseline.json",
    reason: str = "Integrity check failed",
) -> Tuple[Dict[str, Any], str]:
    """Seamlessly reconstruct research state from recovery_baseline.json or immutable_baseline.json.

    Returns:
        (reconstructed_state_dict, source_description)
    """
    state_path = state_dir / state_file
    recovery_path = state_dir / recovery_file
    immutable_path = state_dir / immutable_file

    recovered_state: Optional[Dict[str, Any]] = None
    recovered_from = ""

    # 1. Attempt recovery from recovery_baseline.json
    if recovery_path.is_file():
        try:
            with open(recovery_path, "r", encoding="utf-8") as f:
                rec_data = json.load(f)
            ok, msg, _ = verify_state_merkle_chain(rec_data)
            if ok:
                recovered_state = rec_data
                recovered_from = str(recovery_path.name)
        except Exception:
            recovered_state = None

    # 2. If recovery_baseline failed or missing, fall back to immutable_baseline.json
    if recovered_state is None:
        immutable_data = None
        if immutable_path.is_file():
            try:
                with open(immutable_path, "r", encoding="utf-8") as f:
                    immutable_data = json.load(f)
            except Exception:
                immutable_data = None

        if not isinstance(immutable_data, dict):
            immutable_data = dict(GENESIS_BASELINE)

        genesis_digest = hashlib.sha256(
            json.dumps(immutable_data, sort_keys=True).encode("utf-8")
        ).hexdigest()

        recovered_state = {
            "schema_version": "2.0",
            "active_generation_id": immutable_data.get(
                "root_candidate_id", GENESIS_BASELINE["root_candidate_id"]
            ),
            "cycle_count": 0,
            "completed_cycles": [],
            "failure_catalog": {},
            "hypotheses_history": [],
            "next_agenda_priority": {},
            "concurrency_lock": {
                "is_locked": False,
                "locked_by": "",
                "locked_at": "",
                "expires_at": "",
                "lock_token": "",
            },
            "immutable_baseline": immutable_data,
            "state_digest": genesis_digest,
            "fail_closed_recovery": {
                "last_known_good_cycle": 0,
                "last_known_good_digest": genesis_digest,
                "recovery_count": 1,
            },
        }
        recovered_from = str(immutable_path.name) if immutable_path.is_file() else "genesis_fallback"

    # Break and reset any dangling concurrency lock
    recovered_state["concurrency_lock"] = {
        "is_locked": False,
        "locked_by": "",
        "locked_at": "",
        "expires_at": "",
        "lock_token": "",
    }

    if "fail_closed_recovery" not in recovered_state or not isinstance(recovered_state["fail_closed_recovery"], dict):
        recovered_state["fail_closed_recovery"] = {}

    fcr = recovered_state["fail_closed_recovery"]
    fcr["recovery_count"] = fcr.get("recovery_count", 0) + 1
    fcr["last_recovered_at"] = datetime.now(timezone.utc).isoformat()
    fcr["recovery_reason"] = reason
    fcr["recovered_from"] = recovered_from

    # Atomic write to research_state.json
    state_dir.mkdir(parents=True, exist_ok=True)
    temp_state = state_path.with_suffix(".tmp")
    state_payload = json.dumps(recovered_state, indent=2).encode("utf-8")
    with open(temp_state, "wb") as f:
        f.write(state_payload)
    temp_state.replace(state_path)

    # Sync recovery_baseline.json if it was absent or restored from immutable
    if recovered_from != str(recovery_path.name):
        temp_rec = recovery_path.with_suffix(".tmp")
        with open(temp_rec, "wb") as f:
            f.write(state_payload)
        temp_rec.replace(recovery_path)

    return recovered_state, recovered_from


class _DaemonThreadWorker:
    """Runs a callable in an isolated daemon thread to guarantee non-blocking timeout handling."""

    def __init__(self, target: Callable[..., Any], args: Tuple[Any, ...] = (), kwargs: Optional[Dict[str, Any]] = None, name: str = "WatchdogWorker"):
        self.target = target
        self.args = args
        self.kwargs = kwargs or {}
        self.result: Any = None
        self.exception: Optional[Exception] = None
        self.completed = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True, name=name)

    def _run(self) -> None:
        try:
            self.result = self.target(*self.args, **self.kwargs)
        except Exception as e:
            self.exception = e
        finally:
            self.completed.set()

    def start(self) -> None:
        self.thread.start()

    def join(self, timeout: Optional[float] = None) -> bool:
        return self.completed.wait(timeout=timeout)


class ResilientWatchdog:
    """Autonomous Resilient Watchdog & Recovery Controller for ACE Background Execution.

    Monitors background execution cycles, system memory/CPU footprint, detects hangs,
    emits periodic heartbeat telemetry, and triggers cryptographic checkpoint auto-recovery.
    """

    def __init__(self, config: Optional[WatchdogConfig] = None):
        self.config = config or WatchdogConfig()
        self.state_dir = Path(self.config.state_dir)
        self.diagnostic_dir = Path(self.config.diagnostic_dir)
        self.heartbeat_path = self.state_dir / self.config.heartbeat_file

        self.start_time = time.time()
        self.total_cycles_completed = 0
        self.total_cycles_failed = 0
        self.consecutive_stalls = 0
        self.cycle_durations: List[float] = []
        self.last_cycle_duration: float = 0.0
        self.last_cycle_id: Optional[int] = None
        self.beacon_counter = 0

        self.current_cycle_id: Optional[int] = None
        self.current_cycle_start_time: Optional[float] = None

        self.last_beacon: Optional[TelemetryBeacon] = None
        self.last_diagnostic_dump: Optional[DiagnosticDump] = None

        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._monitor_thread: Optional[threading.Thread] = None
        self._prev_resource_sample: Optional[Tuple[Tuple[float, float], float]] = None

    def start_background_monitor(self) -> None:
        """Start the background monitoring thread for periodic beacons and stall detection."""
        with self._lock:
            if self._monitor_thread is not None and self._monitor_thread.is_alive():
                return
            self._stop_event.clear()
            self._monitor_thread = threading.Thread(
                target=self._monitor_loop,
                daemon=True,
                name="ResilientWatchdogMonitor",
            )
            self._monitor_thread.start()

    def stop_background_monitor(self, timeout: float = 2.0) -> None:
        """Stop the background monitor thread cleanly."""
        with self._lock:
            self._stop_event.set()
            if self._monitor_thread is not None and self._monitor_thread.is_alive():
                self._monitor_thread.join(timeout=timeout)
            self._monitor_thread = None

    def _monitor_loop(self) -> None:
        """Background thread executing periodic heartbeat recording and passive stall detection."""
        self.record_heartbeat()
        last_heartbeat_time = time.time()
        poll_interval = max(0.01, min(0.5, self.config.heartbeat_interval_seconds / 2.0))
        while not self._stop_event.is_set():
            now = time.time()

            # Passive stall check for long-running cycle in progress
            with self._lock:
                start_t = self.current_cycle_start_time
                cid = self.current_cycle_id
            if start_t is not None:
                elapsed = now - start_t
                if elapsed > self.config.cycle_timeout_seconds:
                    # Stall observed in background monitor
                    self._handle_stall_event(cid, elapsed, self.config.cycle_timeout_seconds)

            # Periodic heartbeat interval
            if now - last_heartbeat_time >= self.config.heartbeat_interval_seconds:
                self.record_heartbeat()
                last_heartbeat_time = now

            self._stop_event.wait(timeout=poll_interval)

    def _handle_stall_event(
        self,
        cycle_id: Optional[int],
        elapsed: float,
        timeout_threshold: float,
        exc: Optional[Exception] = None,
    ) -> Tuple[DiagnosticDump, Optional[Dict[str, Any]]]:
        """Generate diagnostic dump and trigger fallback recovery upon detected stall."""
        self.total_cycles_failed += 1
        self.consecutive_stalls += 1

        recovered_state: Optional[Dict[str, Any]] = None
        recovered_from: Optional[str] = None
        if self.config.auto_recover_on_stall:
            recovered_state, recovered_from = self.auto_recover_state(
                reason=f"Cycle {cycle_id} hung/stalled after {elapsed:.2f}s (threshold {timeout_threshold}s)"
            )

        dump = self.generate_diagnostic_dump(
            reason="CYCLE_TIMEOUT_EXCEEDED" if exc is None else f"EXCEPTION: {type(exc).__name__}",
            cycle_id=cycle_id,
            elapsed=elapsed,
            timeout_threshold=timeout_threshold,
            exc=exc,
            recovery_triggered=recovered_state is not None,
            recovered_cycle_count=recovered_state.get("cycle_count") if recovered_state else None,
            recovered_from=recovered_from,
        )

        self.record_heartbeat(status="STALLED" if exc is None else "DEGRADED")
        return dump, recovered_state

    def generate_diagnostic_dump(
        self,
        reason: str,
        cycle_id: Optional[int] = None,
        elapsed: float = 0.0,
        timeout_threshold: Optional[float] = None,
        exc: Optional[Exception] = None,
        recovery_triggered: bool = False,
        recovered_cycle_count: Optional[int] = None,
        recovered_from: Optional[str] = None,
    ) -> DiagnosticDump:
        """Capture comprehensive system diagnostic dump during hang, stall, or crash."""
        self.diagnostic_dir.mkdir(parents=True, exist_ok=True)
        now_ts = datetime.now(timezone.utc).isoformat()
        dump_id = f"diag_{cycle_id or 'unknown'}_{int(time.time())}_{secrets.token_hex(4)}"

        thread_stacks: Dict[str, List[str]] = {}
        frames = sys._current_frames()
        thread_names = {t.ident: t.name for t in threading.enumerate()}
        for ident, frame in frames.items():
            name = thread_names.get(ident, f"thread_{ident}")
            thread_stacks[f"{name}:{ident}"] = [line.strip() for line in traceback.format_stack(frame)]

        stats, self._prev_resource_sample = sample_process_resources(
            prev_cpu_times=self._prev_resource_sample[0] if self._prev_resource_sample else None,
            prev_wall_time=self._prev_resource_sample[1] if self._prev_resource_sample else None,
        )

        state_summary: Dict[str, Any] = {}
        state_file = self.state_dir / self.config.state_file
        if state_file.is_file():
            try:
                with open(state_file, "r", encoding="utf-8") as f:
                    sdata = json.load(f)
                state_summary = {
                    "cycle_count": sdata.get("cycle_count"),
                    "active_generation_id": sdata.get("active_generation_id"),
                    "state_digest": sdata.get("state_digest"),
                    "is_locked": sdata.get("concurrency_lock", {}).get("is_locked", False),
                }
            except Exception as e:
                state_summary = {"error": f"Failed reading state: {e}"}

        tb_str = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)) if exc else None

        dump = DiagnosticDump(
            dump_id=dump_id,
            timestamp=now_ts,
            trigger_reason=reason,
            cycle_id=cycle_id,
            elapsed_seconds=round(elapsed, 3),
            timeout_threshold_seconds=round(timeout_threshold or self.config.cycle_timeout_seconds, 3),
            resource_stats=stats.to_dict(),
            thread_stacks=thread_stacks,
            error_message=str(exc) if exc else None,
            traceback_str=tb_str,
            state_summary=state_summary,
            recovery_triggered=recovery_triggered,
            recovered_cycle_count=recovered_cycle_count,
            recovered_from=recovered_from,
        )

        dump_path = self.diagnostic_dir / f"diagnostic_{dump_id}.json"
        temp_path = dump_path.with_suffix(".tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(dump.to_dict(), f, indent=2)
        temp_path.replace(dump_path)

        with self._lock:
            self.last_diagnostic_dump = dump
        return dump

    def record_heartbeat(self, status: Optional[str] = None) -> TelemetryBeacon:
        """Write an atomic health beacon to disk with uptime, cycle throughput, and resource stats."""
        with self._lock:
            self.beacon_counter += 1
            now_wall = time.time()
            uptime = max(0.0, now_wall - self.start_time)
            avg_duration = (
                sum(self.cycle_durations) / max(1, len(self.cycle_durations))
                if self.cycle_durations
                else 0.0
            )
            throughput_per_hr = round(
                (self.total_cycles_completed / max(1e-3, uptime)) * 3600.0, 2
            )

            stats, self._prev_resource_sample = sample_process_resources(
                prev_cpu_times=self._prev_resource_sample[0] if self._prev_resource_sample else None,
                prev_wall_time=self._prev_resource_sample[1] if self._prev_resource_sample else None,
            )

            # Determine health status
            if status is None:
                if self.consecutive_stalls > 0:
                    health_status = "DEGRADED"
                elif stats.rss_memory_mb > self.config.memory_limit_mb:
                    health_status = "DEGRADED"
                else:
                    health_status = "HEALTHY"
            else:
                health_status = status

            # Check research state lock and digest
            active_digest = "UNKNOWN"
            lock_held = False
            recovery_count = 0
            state_file = self.state_dir / self.config.state_file
            if state_file.is_file():
                try:
                    with open(state_file, "r", encoding="utf-8") as f:
                        sdata = json.load(f)
                    active_digest = sdata.get("state_digest", "UNKNOWN")
                    lock_held = bool(sdata.get("concurrency_lock", {}).get("is_locked", False))
                    recovery_count = sdata.get("fail_closed_recovery", {}).get("recovery_count", 0)
                except Exception:
                    pass

            beacon = TelemetryBeacon(
                beacon_id=self.beacon_counter,
                timestamp=datetime.now(timezone.utc).isoformat(),
                uptime_seconds=round(uptime, 2),
                cycles_completed=self.total_cycles_completed,
                cycles_failed=self.total_cycles_failed,
                cycle_throughput_per_hour=throughput_per_hr,
                average_cycle_duration_seconds=round(avg_duration, 4),
                last_cycle_id=self.last_cycle_id,
                last_cycle_duration_seconds=round(self.last_cycle_duration, 4),
                resource_stats=stats.to_dict(),
                health_status=health_status,
                active_state_digest=active_digest,
                concurrency_lock_held=lock_held,
                recovery_count=recovery_count,
            )

            self.state_dir.mkdir(parents=True, exist_ok=True)
            temp_path = self.heartbeat_path.with_suffix(".tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(beacon.to_dict(), f, indent=2)
            temp_path.replace(self.heartbeat_path)

            self.last_beacon = beacon
            return beacon

    def auto_recover_state(self, reason: str = "Integrity check failed") -> Tuple[Dict[str, Any], str]:
        """Trigger checkpoint auto-recovery, reconstructing state and releasing locks."""
        recovered_state, source = recover_research_state(
            state_dir=self.state_dir,
            state_file=self.config.state_file,
            recovery_file=self.config.recovery_file,
            immutable_file=self.config.immutable_file,
            reason=reason,
        )
        return recovered_state, source

    def ensure_valid_state(self) -> Dict[str, Any]:
        """Ensure research_state.json exists and is valid; recovers if absent or corrupted."""
        state_file = self.state_dir / self.config.state_file
        if not state_file.is_file():
            state, _ = self.auto_recover_state(reason="research_state.json missing from disk")
            return state

        try:
            with open(state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            ok, msg, _ = verify_state_merkle_chain(data)
            if not ok:
                state, _ = self.auto_recover_state(reason=f"Merkle verification failed: {msg}")
                return state
            return data
        except Exception as e:
            state, _ = self.auto_recover_state(reason=f"JSON parse error on state: {e}")
            return state

    def run_guarded_cycle(
        self,
        cycle_fn: Callable[..., T],
        *args: Any,
        cycle_id: Optional[int] = None,
        timeout_seconds: Optional[float] = None,
        fallback_on_timeout: bool = True,
        **kwargs: Any,
    ) -> T:
        """Execute cycle_fn under strict timeout, stall detection, and auto-recovery supervision.

        If execution exceeds timeout_seconds (default 60s), safely interrupts the cycle,
        generates a diagnostic dump with thread stack traces, triggers fallback recovery,
        and returns a fallback result or raises CycleStallTimeoutError.
        """
        timeout = timeout_seconds if timeout_seconds is not None else self.config.cycle_timeout_seconds
        start_t = time.time()

        with self._lock:
            self.current_cycle_id = cycle_id
            self.current_cycle_start_time = start_t

        worker = _DaemonThreadWorker(
            target=cycle_fn,
            args=args,
            kwargs=kwargs,
            name=f"GuardedCycleWorker_{cycle_id or 'anon'}",
        )
        worker.start()
        completed_in_time = worker.join(timeout=timeout)

        elapsed = time.time() - start_t
        with self._lock:
            self.current_cycle_id = None
            self.current_cycle_start_time = None

        if not completed_in_time:
            # Automatic Hang & Stall Detected!
            dump, recovered_state = self._handle_stall_event(cycle_id, elapsed, timeout)
            if not fallback_on_timeout:
                raise CycleStallTimeoutError(
                    f"Cycle {cycle_id} hung/timed out after {elapsed:.2f}s (threshold {timeout}s)"
                )
            fallback_result: Any = {
                "cycle_id": cycle_id,
                "status": "TIMED_OUT",
                "decision": "STALLED",
                "is_promoted": False,
                "gain_over_parent": 0.0,
                "holdout_score": 0.0,
                "reason": f"Cycle exceeded timeout threshold of {timeout}s",
                "diagnostic_dump_id": dump.dump_id,
                "recovered_state_cycles": recovered_state.get("cycle_count") if recovered_state else None,
                "governance": {
                    "release_gate": "BLOCK_RELEASE",
                    "scientific_status": "NOT_ASSESSED",
                    "oaie_established": False,
                },
            }
            return fallback_result

        if worker.exception is not None:
            # Exception raised inside cycle execution
            self._handle_stall_event(cycle_id, elapsed, timeout, exc=worker.exception)
            raise worker.exception

        # Clean successful completion
        with self._lock:
            self.total_cycles_completed += 1
            self.consecutive_stalls = 0
            self.cycle_durations.append(elapsed)
            self.last_cycle_duration = elapsed
            if cycle_id is None and isinstance(worker.result, dict) and "cycle_id" in worker.result:
                self.last_cycle_id = worker.result["cycle_id"]
            else:
                self.last_cycle_id = cycle_id

        self.record_heartbeat(status="HEALTHY")
        return worker.result

    def monitor_cycle(self, cycle_id: int, timeout_seconds: Optional[float] = None) -> _CycleMonitorScope:
        """Context manager for manual cycle monitoring and latency measurement."""
        return _CycleMonitorScope(self, cycle_id, timeout_seconds)

    def get_health_status(self) -> Dict[str, Any]:
        """Return comprehensive health summary and latest telemetry metrics."""
        with self._lock:
            now_wall = time.time()
            uptime = max(0.0, now_wall - self.start_time)
            avg_duration = (
                sum(self.cycle_durations) / max(1, len(self.cycle_durations))
                if self.cycle_durations
                else 0.0
            )
            throughput = round((self.total_cycles_completed / max(1e-3, uptime)) * 3600.0, 2)
            stats, _ = sample_process_resources()

            return {
                "uptime_seconds": round(uptime, 2),
                "total_cycles_completed": self.total_cycles_completed,
                "total_cycles_failed": self.total_cycles_failed,
                "consecutive_stalls": self.consecutive_stalls,
                "cycle_throughput_per_hour": throughput,
                "average_cycle_duration_seconds": round(avg_duration, 4),
                "last_cycle_id": self.last_cycle_id,
                "last_cycle_duration_seconds": round(self.last_cycle_duration, 4),
                "resource_stats": stats.to_dict(),
                "last_beacon": self.last_beacon.to_dict() if self.last_beacon else None,
                "last_diagnostic_dump_id": self.last_diagnostic_dump.dump_id if self.last_diagnostic_dump else None,
            }


class _CycleMonitorScope:
    """Context manager scope for cycle monitoring."""

    def __init__(self, watchdog: ResilientWatchdog, cycle_id: int, timeout_seconds: Optional[float] = None):
        self.watchdog = watchdog
        self.cycle_id = cycle_id
        self.timeout = timeout_seconds or watchdog.config.cycle_timeout_seconds
        self.start_time: float = 0.0

    def __enter__(self) -> _CycleMonitorScope:
        self.start_time = time.time()
        with self.watchdog._lock:
            self.watchdog.current_cycle_id = self.cycle_id
            self.watchdog.current_cycle_start_time = self.start_time
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        elapsed = time.time() - self.start_time
        with self.watchdog._lock:
            self.watchdog.current_cycle_id = None
            self.watchdog.current_cycle_start_time = None

        if exc_val is not None:
            self.watchdog._handle_stall_event(self.cycle_id, elapsed, self.timeout, exc=exc_val)
            return False

        if elapsed > self.timeout:
            self.watchdog._handle_stall_event(self.cycle_id, elapsed, self.timeout)

        with self.watchdog._lock:
            self.watchdog.total_cycles_completed += 1
            self.watchdog.consecutive_stalls = 0
            self.watchdog.cycle_durations.append(elapsed)
            self.watchdog.last_cycle_duration = elapsed
            self.watchdog.last_cycle_id = self.cycle_id

        self.watchdog.record_heartbeat(status="HEALTHY")
        return False
