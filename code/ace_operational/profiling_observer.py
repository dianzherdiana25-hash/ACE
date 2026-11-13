"""Profiling pilot — observer-only telemetry for the ACE experiment driver.

PROPOSED instrument, development band only. It observes the A/B/C pilot
solver (`pilot_abc.solve_with_config` + `reasoning_lab.Budget`) from
OUTSIDE its decision loop:

* No value produced here is ever read by the solver. Hooks wrap module
  entry points (`GROUP_FN`, `variants_by_group`) and subclass `Budget`
  with a score method whose return values are equivalence-tested
  against the plain `Budget`. The observer can be switched off
  (``enabled=False`` / simply not installed) and the solver then runs
  through none of this machinery.
* Output is a sidecar (``profiling_manifest.json`` + append-only
  ``events-*.jsonl`` segments) that lives OUTSIDE the scientific
  records. Scientific records keep their existing shape and never
  carry telemetry fields.
* Fail-open for the work, fail-closed for the claim: a telemetry
  failure is counted (``dropped_events``) and marks the run partial;
  it never raises into the solver and never blocks a job.

Schema ``ace-profiling/1.0`` — event set:

* manifest (once per run, separate file): run_id, digests of
  build/solver/catalog/config, schema version, clock domain per
  source, job process model, timeout policy, instrumentation flag +
  sampling, buffer limit, segment rotation + retention policy.
* ``job_lifecycle`` per job/attempt: job_id, attempt_id, task/family,
  arm, seed, worker, monotonic seq per source, timestamps.
* ``phase_span`` per coarse span (and per-job aggregates for micro
  spans): span_id, parent_span_id, wall inclusive/self, CPU
  user/system. Self time subtracts the UNION of child intervals —
  children are sequential in this single-threaded solver, so the union
  is their sum; parent and child CPU are reported as separate,
  non-overlapping components and are never summed twice.
* ``job_summary`` per attempt: queue wait (explicitly N/A while no
  coordinator exists), logical score calls, cache hit/miss (N/A —
  no active cache; the shadow potential-hit counter is a different
  metric and is reported under its own name), peak RSS with scope,
  I/O bytes with scope, solved / shown score, termination_reason and
  infra_status as separate fields, duration.

The nine phases reported separately: ``queue_startup``,
``enumeration``, ``transform_serialize``, ``parse``, ``compile``,
``exec_shown``, ``dedup_frontier``, ``checkpoint_io``, ``aggregation``.

Phase measurement notes (also recorded in the manifest):

* ``parse`` is measured by a dedicated ``ast.parse`` pass inside the
  profiling budget; the baseline ``compile()`` parses internally too,
  so ``parse`` is an attribution of the scoring path, and inclusive
  totals are never summed naively across nested spans.
* ``transform_serialize`` includes the operator functions' own
  internal ``ast.parse`` calls — that is where that work happens.
* ``dedup_frontier`` is a derived residual: enumeration self time
  (dedup lives inside ``variants_by_group``) plus the solve-loop self
  time (frontier selection + loop glue). It is labelled
  ``derived_residual``, never presented as a directly bracketed span.
* ``checkpoint_io`` is the dev runner's per-job scientific-record
  write — the development-band analogue of driver checkpointing.
* Queue wait is N/A: with no coordinator there is no enqueue/eligible
  timestamp in a shared clock domain, and building a lease
  coordinator is NOT a prerequisite of this pilot.
"""
from __future__ import annotations

import ast
import contextlib
import hashlib
import json
import os
import resource
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

SCHEMA_VERSION = "ace-profiling/1.0"

PHASES = (
    "queue_startup",
    "enumeration",
    "transform_serialize",
    "parse",
    "compile",
    "exec_shown",
    "dedup_frontier",
    "checkpoint_io",
    "aggregation",
)

# Children whose inclusive time is subtracted to get a parent's self
# time. Single-threaded, sequential solver: child intervals never
# overlap inside a parent, so union == sum.
SPAN_CHILDREN = {
    "exec_shown": ("parse", "compile"),
    "enumeration": ("transform_serialize",),
}

SEGMENT_MAX_BYTES = 16 * 1024 * 1024


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _digest_value(value: Any) -> str:
    blob = json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")
    return _digest_bytes(blob)


def _rusage_self() -> tuple[float, float]:
    ru = resource.getrusage(resource.RUSAGE_SELF)
    return ru.ru_utime, ru.ru_stime


def _rusage_children() -> tuple[float, float, int]:
    ru = resource.getrusage(resource.RUSAGE_CHILDREN)
    return ru.ru_utime, ru.ru_stime, ru.ru_maxrss


def _rss_kb() -> int | None:
    try:
        for line in Path("/proc/self/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1])
    except Exception:
        pass
    return None


def _io_counters() -> dict[str, int] | None:
    try:
        out = {}
        for line in Path("/proc/self/io").read_text().splitlines():
            key, _, val = line.partition(":")
            if key in ("read_bytes", "write_bytes"):
                out[key] = int(val.strip())
        return out or None
    except Exception:
        return None


def unavailable(reason: str) -> dict[str, Any]:
    return {"value": None, "availability": "unavailable", "reason": reason}


# ---------------------------------------------------------------------------
# Collector: bounded buffer -> append-only JSONL segments + manifest
# ---------------------------------------------------------------------------

class Collector:
    """Observer sink. Never raises into the observed code."""

    def __init__(self, run_dir: str | Path, run_id: str, *,
                 buffer_limit: int = 512,
                 segment_max_bytes: int = SEGMENT_MAX_BYTES,
                 enabled: bool = True):
        self.run_dir = Path(run_dir)
        self.run_id = run_id
        self.buffer_limit = buffer_limit
        self.segment_max_bytes = segment_max_bytes
        self.enabled = enabled
        self.dropped_events = 0
        self.emitted_events = 0
        self._seq = 0
        self._buffer: list[str] = []
        self._segment_idx = 0
        self._segment_bytes = 0
        self.segments: list[dict[str, Any]] = []
        if self.enabled:
            self.run_dir.mkdir(parents=True, exist_ok=True)

    # -- internals ------------------------------------------------------
    def _segment_path(self) -> Path:
        return self.run_dir / f"events-{self._segment_idx:03d}.jsonl"

    def _flush(self) -> None:
        if not self._buffer:
            return
        blob = "".join(self._buffer)
        self._buffer = []
        data = blob.encode("utf-8")
        if self._segment_bytes and \
                self._segment_bytes + len(data) > self.segment_max_bytes:
            self._segment_idx += 1
            self._segment_bytes = 0
        with self._segment_path().open("ab") as fh:
            fh.write(data)
        self._segment_bytes += len(data)

    def emit(self, event: dict[str, Any]) -> bool:
        """Assign seq/event_id and buffer the event. Fail-open."""
        if not self.enabled:
            return False
        try:
            self._seq += 1
            event = {"schema_version": SCHEMA_VERSION,
                     "run_id": self.run_id,
                     "seq": self._seq,
                     "event_id": f"{self.run_id}:{self._seq}",
                     "emitted_at": _now_iso(), **event}
            line = json.dumps(event, sort_keys=True, ensure_ascii=False) + "\n"
            if len(self._buffer) >= self.buffer_limit:
                self._flush()
            self._buffer.append(line)
            self.emitted_events += 1
            return True
        except Exception:
            self.dropped_events += 1
            return False

    # -- coarse spans ----------------------------------------------------
    @contextlib.contextmanager
    def span(self, phase: str, *, job_id: str,
             parent_span_id: str | None = None) -> Iterator[dict[str, Any]]:
        """Bracket a coarse phase. Yields the span record (span_id)."""
        rec: dict[str, Any] = {"span_id": uuid.uuid4().hex[:16]}
        if not self.enabled:
            yield rec
            return
        stack = self.__dict__.setdefault("_span_stack", [])
        wall0 = time.perf_counter()
        cpu0 = _rusage_self()
        stack.append(rec)
        try:
            yield rec
        finally:
            stack.pop()
            wall = time.perf_counter() - wall0
            cpu1 = _rusage_self()
            child_wall = sum(c.get("_wall_inclusive", 0.0)
                             for c in rec.get("_children", []))
            rec["_wall_inclusive"] = wall
            if stack:
                stack[-1].setdefault("_children", []).append(rec)
            self.emit({
                "type": "phase_span", "job_id": job_id, "phase": phase,
                "span_id": rec["span_id"], "parent_span_id": parent_span_id,
                "wall_inclusive_s": wall,
                "wall_self_s": max(0.0, wall - child_wall),
                "cpu_user_s": max(0.0, cpu1[0] - cpu0[0]),
                "cpu_system_s": max(0.0, cpu1[1] - cpu0[1]),
                "cpu_scope": "process_self_rusage_delta",
                "count": 1, "availability": "measured",
            })

    def footer(self, *, jobs_registered: int, jobs_completed: int,
               completeness: str) -> None:
        try:
            self.emit({"type": "run_footer",
                       "jobs_registered": jobs_registered,
                       "jobs_completed": jobs_completed,
                       "dropped_events": self.dropped_events,
                       "completeness": completeness})
            self._flush()
            for idx in range(self._segment_idx + 1):
                path = self.run_dir / f"events-{idx:03d}.jsonl"
                if path.exists():
                    self.segments.append({
                        "file": path.name,
                        "bytes": path.stat().st_size,
                        "sha256": _digest_bytes(path.read_bytes())})
        except Exception:
            self.dropped_events += 1


class PhaseAggregator:
    """Aggregate micro-span timings per job (high-volume events).

    Micro spans (per score call) are accumulated, not emitted one by
    one; the per-job aggregate is emitted once as ``phase_span`` rows
    with a ``count``. Self time for parents in SPAN_CHILDREN is the
    inclusive total minus the union (= sum, sequential) of children.
    """

    def __init__(self, collector: Collector, job_id: str):
        self.collector = collector
        self.job_id = job_id
        self.totals: dict[str, dict[str, float]] = {}

    @contextlib.contextmanager
    def measure(self, phase: str) -> Iterator[None]:
        wall0 = time.perf_counter()
        cpu0 = _rusage_self()
        try:
            yield
        finally:
            cpu1 = _rusage_self()
            slot = self.totals.setdefault(
                phase, {"count": 0, "wall": 0.0, "cpu_user": 0.0,
                        "cpu_system": 0.0})
            slot["count"] += 1
            slot["wall"] += time.perf_counter() - wall0
            slot["cpu_user"] += max(0.0, cpu1[0] - cpu0[0])
            slot["cpu_system"] += max(0.0, cpu1[1] - cpu0[1])

    def wall(self, phase: str) -> float:
        return self.totals.get(phase, {}).get("wall", 0.0)

    def flush(self, *, parent_span_id: str | None = None) -> None:
        for phase, slot in sorted(self.totals.items()):
            child_wall = sum(self.wall(c)
                             for c in SPAN_CHILDREN.get(phase, ()))
            self.collector.emit({
                "type": "phase_span", "job_id": self.job_id,
                "phase": phase, "span_id": uuid.uuid4().hex[:16],
                "parent_span_id": parent_span_id,
                "wall_inclusive_s": slot["wall"],
                "wall_self_s": max(0.0, slot["wall"] - child_wall),
                "cpu_user_s": slot["cpu_user"],
                "cpu_system_s": slot["cpu_system"],
                "cpu_scope": "process_self_rusage_delta_aggregated",
                "count": int(slot["count"]),
                "availability": "measured", "aggregated": True,
            })


# ---------------------------------------------------------------------------
# Profiling Budget: identical scores, observed decomposition
# ---------------------------------------------------------------------------

class ProfilingBudget:
    """Drop-in observant twin of ``reasoning_lab.Budget``.

    Same constructor, same ``used`` accounting, same return values
    (pinned by equivalence tests against the plain Budget). The extra
    work — a dedicated parse pass and timing — is observer overhead,
    measured by the paired instrumented/off pilot blocks; it never
    feeds a solver decision. A shadow key counter tracks would-be
    cache duplicates; there is NO active cache, so real hit/miss
    stays N/A and every score is genuinely computed.
    """

    def __init__(self, limit: int, *, entrypoint: str,
                 shown_cases: list[tuple], shown_expected: list[Any],
                 aggregator: PhaseAggregator):
        from ace_operational.reasoning_lab import Budget
        self._inner = Budget(limit, entrypoint=entrypoint,
                             shown_cases=shown_cases,
                             shown_expected=shown_expected)
        self.limit = limit
        self._entrypoint = entrypoint
        self._shown = list(zip(shown_cases, shown_expected))
        self._agg = aggregator
        self._seen_keys: set[str] = set()
        self.potential_hits = 0

    @property
    def used(self) -> int:
        return self._inner.used

    @used.setter
    def used(self, value: int) -> None:
        self._inner.used = value

    @property
    def distinct_keys(self) -> int:
        return len(self._seen_keys)

    def score(self, code: str) -> int:
        self._inner.used += 1
        key = _digest_bytes(code.encode("utf-8"))
        if key in self._seen_keys:
            self.potential_hits += 1
        else:
            self._seen_keys.add(key)
        agg = self._agg
        wall0 = time.perf_counter()
        try:
            with agg.measure("parse"):
                ast.parse(code)
            with agg.measure("compile"):
                code_obj = compile(code, "<cand>", "exec")
            namespace: dict[str, Any] = {}
            exec(code_obj, namespace)
            fn = namespace[self._entrypoint]
            result = sum(1 for case, expected in self._shown
                         if fn(*case) == expected)
        except Exception:
            result = -1
        slot = agg.totals.setdefault(
            "exec_shown", {"count": 0, "wall": 0.0, "cpu_user": 0.0,
                           "cpu_system": 0.0})
        slot["count"] += 1
        slot["wall"] += time.perf_counter() - wall0
        return result


@contextlib.contextmanager
def instrumented_solver(aggregator: PhaseAggregator) -> Iterator[None]:
    """Install phase hooks around the solver's outer boundaries.

    Wraps ``pilot_abc.GROUP_FN`` entries (transform/serialize) and
    ``pilot_abc.variants_by_group`` (enumeration). Wrappers return the
    original results untouched and are removed on exit. When this
    context is not entered, the solver runs exactly as shipped.
    """
    from ace_operational import pilot_abc

    orig_variants = pilot_abc.variants_by_group
    orig_groups = dict(pilot_abc.GROUP_FN)

    def variants_wrapper(code: str, spec: str):
        with aggregator.measure("enumeration"):
            return orig_variants(code, spec)

    def wrap_group(fn):
        def group_wrapper(code: str, spec: str):
            with aggregator.measure("transform_serialize"):
                return fn(code, spec)
        return group_wrapper

    pilot_abc.variants_by_group = variants_wrapper
    for name, fn in orig_groups.items():
        pilot_abc.GROUP_FN[name] = wrap_group(fn)
    try:
        yield
    finally:
        pilot_abc.variants_by_group = orig_variants
        pilot_abc.GROUP_FN.clear()
        pilot_abc.GROUP_FN.update(orig_groups)


# ---------------------------------------------------------------------------
# Sidecar reading + completeness reconciliation
# ---------------------------------------------------------------------------

def load_sidecar(run_dir: str | Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    run_dir = Path(run_dir)
    manifest = json.loads((run_dir / "profiling_manifest.json")
                          .read_text(encoding="utf-8"))
    events: list[dict[str, Any]] = []
    for seg in manifest.get("segments", []):
        path = run_dir / seg["file"]
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                events.append(json.loads(line))
    if not manifest.get("segments"):
        for path in sorted(run_dir.glob("events-*.jsonl")):
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    events.append(json.loads(line))
    return manifest, events


def validate_sidecar(manifest: dict[str, Any],
                     events: list[dict[str, Any]]) -> dict[str, Any]:
    """Reconcile: dropped=0 alone is NOT completeness. Requires the
    footer, contiguous seq, registered==summarised jobs, paired spans,
    and segment checksums (checked by the caller against files)."""
    problems: list[str] = []
    seqs = [e["seq"] for e in events]
    if seqs != list(range(1, len(events) + 1)):
        problems.append("seq not contiguous from 1")
    footers = [e for e in events if e.get("type") == "run_footer"]
    if not footers:
        problems.append("run_footer missing (no final flush)")
    summaries = [e for e in events if e.get("type") == "job_summary"]
    registered = manifest.get("jobs_registered")
    if registered is not None and len(summaries) != registered:
        problems.append(
            f"job_summary count {len(summaries)} != registered {registered}")
    if footers and footers[-1].get("jobs_registered") != registered:
        problems.append("footer jobs_registered != manifest")
    dropped = footers[-1].get("dropped_events") if footers else None
    if dropped:
        problems.append(f"dropped_events={dropped}")
    span_ids = {e["span_id"] for e in events if e.get("type") == "phase_span"}
    for e in events:
        if e.get("type") == "phase_span":
            parent = e.get("parent_span_id")
            if parent and parent not in span_ids and not e.get("aggregated"):
                problems.append(f"span {e['span_id']} parent {parent} missing")
                break
    partial = any(s.get("completeness") != "complete" for s in summaries)
    return {"complete": not problems and not partial,
            "problems": problems,
            "jobs_summarised": len(summaries),
            "events": len(events),
            "dropped_events": dropped}


# ---------------------------------------------------------------------------
# Development-band pilot runner
# ---------------------------------------------------------------------------

def _file_digest(path: Path) -> str:
    return _digest_bytes(path.read_bytes())


def build_manifest(*, run_id: str, run_dir: Path, config: dict[str, Any],
                   task_ids: list[str], jobs_registered: int,
                   instrumented: bool) -> dict[str, Any]:
    here = Path(__file__)
    pkg = here.parent
    digests = {}
    for name in ("profiling_observer.py", "pilot_abc.py",
                 "reasoning_lab.py", "curriculum_lab.py"):
        digests[name] = _file_digest(pkg / name)
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "created_at": _now_iso(),
        "band": "development",
        "instrumented": instrumented,
        "instrumentation": {
            "flag": "profiling_observer enabled per-job (dev runner arg)",
            "default": "off — solver runs unmodified unless installed",
            "sampling_rate": 1.0,
            "micro_spans": "aggregated per job (count + totals)",
            "buffer_limit_events": 512,
        },
        "digests": {
            "build": digests,
            "build_digest": _digest_value(digests),
            "config_digest": _digest_value(config),
            "catalog_digest": _digest_value(sorted(task_ids)),
        },
        "clock_domains": {
            "wall": "time.perf_counter (monotonic, this process)",
            "timestamp": "UTC wall clock (datetime.now(timezone.utc))",
            "cpu": "resource.getrusage RUSAGE_SELF / RUSAGE_CHILDREN",
            "queue": "none — no coordinator exists",
        },
        "job_process_model": "in-process sequential (mirrors "
                             "pilot_abc.evaluate_config); no child "
                             "processes are spawned by the solver",
        "timeout_policy": {
            "per_job_soft_budget_s": config.get("timeout_soft_s"),
            "enforcement": "observed-not-enforced in-process (pilot v1): "
                           "overruns are flagged in termination_reason, "
                           "never killed, so durations are uncensored",
        },
        "retention_rotation": {
            "sidecar_location": str(run_dir),
            "rotation": f"segment at {SEGMENT_MAX_BYTES} bytes, sha256 "
                        "index in manifest",
            "retention": "development band; append-only during the run; "
                         "kept until hub review; deletion only on owner "
                         "order. Append-only is a run property, not a "
                         "forever-storage promise.",
            "access": "same as the run's development artifacts",
        },
        "phase_map": {
            "parse": "dedicated ast.parse pass in ProfilingBudget "
                     "(baseline compile() also parses internally — "
                     "attribution, not an additive total)",
            "transform_serialize": "operator group functions, "
                                   "including their internal ast.parse",
            "dedup_frontier": "derived residual: enumeration self "
                              "(dedup inside variants_by_group) + "
                              "solve-loop self (frontier selection)",
            "checkpoint_io": "dev runner per-job scientific-record "
                             "append (development-band analogue of "
                             "driver checkpointing)",
            "queue_wait": "N/A — no coordinator; see job_summary",
        },
        "jobs_registered": jobs_registered,
        "config": config,
    }


def _run_one_job(task: dict[str, Any], *, mode: str, rep: int,
                 budget_limit: int, config: dict[str, Any],
                 collector: Collector | None,
                 records_path: Path) -> dict[str, Any]:
    """One dev-band job: solve one task with arm-A config + verify.

    mode "on" installs the observer; mode "off" runs the plain solver
    through the same runner machinery (paired overhead baseline).
    Returns the scientific record plus (mode on) the telemetry summary.
    """
    from ace_operational import pilot_abc
    from ace_operational.curriculum_lab import verify_candidate
    from ace_operational.reasoning_lab import Budget

    on = mode == "on" and collector is not None
    job_id = f"job-{task['task_id']}-{mode}-r{rep}"
    attempt_id = f"{job_id}:1"
    wall_job0 = time.perf_counter()
    child0 = _rusage_children()
    io0 = _io_counters()
    rss_samples: list[int] = []
    if (r := _rss_kb()) is not None:
        rss_samples.append(r)

    agg = PhaseAggregator(collector, job_id) if on else None
    summary: dict[str, Any] = {
        "type": "job_lifecycle", "job_id": job_id,
        "attempt_id": attempt_id, "event": "start",
        "task_id": task["task_id"], "family": task["family"],
        "level": task["level"], "seed": task["seed"], "arm": "A-fixed",
        "worker": "in-process:dev-runner", "mode": mode, "rep": rep,
        "ts": _now_iso(),
        "queue_wait": unavailable("no_coordinator: no enqueue/eligible "
                                  "timestamps in a shared clock domain"),
    }
    if on:
        collector.emit(summary)

    infra_status, termination = "ok", None
    result, outcome = None, None
    budget = None
    startup_s = solve_s = verify_s = 0.0
    try:
        # --- queue_startup: public projection + budget construction
        t0 = time.perf_counter()
        public = pilot_abc._public(task)
        shown = [tuple(c) for c in task["shown_cases"]]
        by_case = {tuple(c): e for c, e in
                   zip(task["cases"], task["expected"])}
        if on:
            budget = ProfilingBudget(
                budget_limit, entrypoint=task["entrypoint"],
                shown_cases=shown,
                shown_expected=[by_case[c] for c in shown],
                aggregator=agg)
        else:
            budget = Budget(budget_limit, entrypoint=task["entrypoint"],
                            shown_cases=shown,
                            shown_expected=[by_case[c] for c in shown])
        startup_s = time.perf_counter() - t0
        if on:
            collector.emit({
                "type": "phase_span", "job_id": job_id,
                "phase": "queue_startup", "span_id": uuid.uuid4().hex[:16],
                "parent_span_id": None, "wall_inclusive_s": startup_s,
                "wall_self_s": startup_s, "count": 1,
                "availability": "measured",
                "note": "job setup (public projection + budget "
                        "construction); worker is in-process, queue "
                        "component is N/A (no coordinator)"})

        # --- solve (the observed driver call)
        solve0 = time.perf_counter()
        if on:
            with instrumented_solver(agg):
                result = pilot_abc.solve_with_config(
                    public, budget, pilot_abc.BASE_CONFIG)
        else:
            result = pilot_abc.solve_with_config(
                public, budget, pilot_abc.BASE_CONFIG)
        solve_s = time.perf_counter() - solve0
        if (r := _rss_kb()) is not None:
            rss_samples.append(r)

        # --- full verification (runner-side, not a solver phase)
        v0 = time.perf_counter()
        outcome = verify_candidate(task, result["code"])
        verify_s = time.perf_counter() - v0

        if result["shown_score"] == len(shown):
            termination = "shown_perfect"
        elif result["evals"] >= budget_limit:
            termination = "budget_exhausted"
        else:
            termination = "rounds_exhausted"
        if config.get("timeout_soft_s") and \
                solve_s > config["timeout_soft_s"]:
            termination = "wall_flagged_overrun"
    except Exception as exc:  # job crash: record, never hide
        infra_status = "crash"
        termination = f"crash:{type(exc).__name__}"
        result = {"code": task["buggy_code"], "shown_score": -1,
                  "evals": 0}
        outcome = {"passed": 0, "total": len(task["cases"])}
        solve_s = time.perf_counter() - wall_job0
        verify_s = 0.0
        startup_s = 0.0

    solved = bool(outcome and outcome["passed"] == outcome["total"]
                  and outcome["total"] > 0)
    record = {"task_id": task["task_id"], "family": task["family"],
              "level": task["level"], "seed": task["seed"],
              "arm": "A-fixed", "mode": mode, "rep": rep,
              "code": result["code"], "shown_score": result["shown_score"],
              "evals": result["evals"], "solved": solved,
              "passed": outcome["passed"], "total": outcome["total"]}

    # --- checkpoint_io: append the scientific record (both modes)
    c0 = time.perf_counter()
    with records_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")
    checkpoint_s = time.perf_counter() - c0

    # --- aggregation: fold the record into the run aggregate
    a0 = time.perf_counter()
    _ = {"solved": int(solved), "evals": result["evals"]}
    aggregation_s = time.perf_counter() - a0

    job_wall = time.perf_counter() - wall_job0
    child1 = _rusage_children()
    io1 = _io_counters()
    if (r := _rss_kb()) is not None:
        rss_samples.append(r)

    if on:
        # derived dedup_frontier + aggregated micro spans + spans for
        # the runner phases, then the job summary.
        enum_incl = agg.wall("enumeration")
        enum_self = max(0.0, enum_incl - agg.wall("transform_serialize"))
        accounted = (startup_s + enum_incl + agg.wall("exec_shown")
                     + verify_s + checkpoint_s + aggregation_s)
        loop_self = max(0.0, solve_s - enum_incl - agg.wall("exec_shown"))
        collector.emit({
            "type": "phase_span", "job_id": job_id,
            "phase": "dedup_frontier",
            "span_id": uuid.uuid4().hex[:16], "parent_span_id": None,
            "wall_inclusive_s": enum_self + loop_self,
            "wall_self_s": enum_self + loop_self, "count": 1,
            "availability": "derived_residual",
            "note": "enumeration self (dedup inside variants_by_group) "
                    "+ solve-loop self (frontier selection + glue); "
                    "job time not in any span: "
                    f"{max(0.0, job_wall - accounted - loop_self):.6f}s"})
        for phase, secs in (("checkpoint_io", checkpoint_s),
                            ("aggregation", aggregation_s)):
            collector.emit({
                "type": "phase_span", "job_id": job_id, "phase": phase,
                "span_id": uuid.uuid4().hex[:16], "parent_span_id": None,
                "wall_inclusive_s": secs, "wall_self_s": secs,
                "count": 1, "availability": "measured"})
        agg.flush()
        io_delta = None
        if io0 is not None and io1 is not None:
            io_delta = {k: io1.get(k, 0) - io0.get(k, 0)
                        for k in ("read_bytes", "write_bytes")}
        collector.emit({
            "type": "job_summary", "job_id": job_id,
            "attempt_id": attempt_id, "task_id": task["task_id"],
            "family": task["family"], "level": task["level"],
            "seed": task["seed"], "arm": "A-fixed", "mode": mode,
            "rep": rep, "event": "end", "ts": _now_iso(),
            "completeness": "complete" if infra_status == "ok"
                            else "partial",
            "queue_wait": summary["queue_wait"],
            "duration_s": job_wall, "solve_s": solve_s,
            "verify_full_s": verify_s,
            "logical_score_calls": result["evals"],
            "cache": {"hit": None, "miss": None,
                      "availability": "unavailable",
                      "reason": "no_active_cache",
                      "potential_hits": getattr(budget, "potential_hits",
                                                None),
                      "potential_duplicate_keys":
                          getattr(budget, "distinct_keys", None)},
            "peak_rss": {
                "sampled_max_kb": max(rss_samples) if rss_samples else None,
                "availability": "sampled",
                "scope": "process VmRSS samples at job boundaries; "
                         "in-process model — not a per-job tree peak; "
                         "ru_maxrss is a lifetime high-water and is "
                         "not claimed as this job's peak"},
            "io_bytes": ({"value": io_delta, "availability": "measured",
                          "scope": "process /proc/self/io delta; not "
                                   "durable-commit bytes"}
                         if io_delta is not None else
                         unavailable("proc_self_io_unreadable")),
            "child_cpu": {"user_s": max(0.0, child1[0] - child0[0]),
                          "system_s": max(0.0, child1[1] - child0[1]),
                          "maxrss_kb": child1[2],
                          "scope": "RUSAGE_CHILDREN delta; solver "
                                   "spawns no children in this model"},
            "solved": solved, "shown_score": result["shown_score"],
            "termination_reason": termination,
            "infra_status": infra_status,
            "timeout": {"soft_budget_s": config.get("timeout_soft_s"),
                        "enforced": False,
                        "flagged": termination == "wall_flagged_overrun"},
        })
    record["_job_wall_s"] = job_wall
    record["_solve_s"] = solve_s
    return record


def run_dev_pilot(*, out_dir: str | Path,
                  families: tuple[str, ...] = ("pricing", "shipping"),
                  levels: tuple[int, ...] = (1, 2, 3),
                  seeds: tuple[int, ...] = tuple(range(1, 9)),
                  reps: int = 2, budget_limit: int = 200,
                  timeout_soft_s: float | None = None,
                  run_id: str | None = None) -> dict[str, Any]:
    """Paired instrumented/off pilot on the development band.

    Job order is ABBA per task (off, on, on, off for reps=2) so drift
    hits both modes symmetrically. Pilot numbers ESTIMATE variance
    and rank phases; they are not scientific evidence.
    """
    from ace_operational import pilot_abc

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    run_id = run_id or f"profiling-pilot-{uuid.uuid4().hex[:8]}"
    tasks = pilot_abc.generate_universe(families=list(families),
                                        levels=list(levels),
                                        seeds=list(seeds))
    config = {"families": list(families), "levels": list(levels),
              "seeds": list(seeds), "reps": reps,
              "budget_limit": budget_limit,
              "solver_config": pilot_abc.BASE_CONFIG,
              "timeout_soft_s": timeout_soft_s,
              "job_order": "ABBA per task (off,on,on,off)"}
    modes: list[str] = []
    for r in range(reps):
        modes.extend(["off", "on"] if r % 2 == 0 else ["on", "off"])
    # Only instrumented jobs emit summaries; that is the registered
    # denominator for the sidecar (scientific denominator = tasks).
    jobs_registered = len(tasks) * modes.count("on")
    collector = Collector(out_dir, run_id)
    manifest = build_manifest(run_id=run_id, run_dir=out_dir,
                              config=config,
                              task_ids=[t["task_id"] for t in tasks],
                              jobs_registered=jobs_registered,
                              instrumented=True)
    (out_dir / "profiling_manifest.json").write_text(
        json.dumps(manifest, indent=1, sort_keys=True), encoding="utf-8")
    records_path = out_dir / "records.jsonl"
    walls_path = out_dir / "job_walls.jsonl"
    records: list[dict[str, Any]] = []
    completed = 0
    for task in tasks:
        for rep, mode in enumerate(modes):
            rec = _run_one_job(task, mode=mode, rep=rep,
                               budget_limit=budget_limit, config=config,
                               collector=collector,
                               records_path=records_path)
            records.append(rec)
            with walls_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(
                    {"task_id": task["task_id"], "mode": mode,
                     "rep": rep, "job_wall_s": rec["_job_wall_s"],
                     "solve_s": rec["_solve_s"]}, sort_keys=True) + "\n")
            if mode == "on":
                completed += 1
    collector.footer(jobs_registered=jobs_registered,
                     jobs_completed=completed,
                     completeness="complete")
    manifest["segments"] = collector.segments
    manifest["dropped_events"] = collector.dropped_events
    (out_dir / "profiling_manifest.json").write_text(
        json.dumps(manifest, indent=1, sort_keys=True), encoding="utf-8")
    summary = {"run_id": run_id, "tasks": len(tasks),
               "records": len(records),
               "dropped_events": collector.dropped_events,
               "out_dir": str(out_dir)}
    (out_dir / "pilot_run_summary.json").write_text(
        json.dumps(summary, indent=1, sort_keys=True), encoding="utf-8")
    return summary


# ---------------------------------------------------------------------------
# Pilot analysis: variance estimate, phase ranking, overhead.
# Pilot numbers ESTIMATE and RANK. They are not scientific evidence.
# ---------------------------------------------------------------------------

def _job_phase_rows(events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Per-job attributed (disjoint) phase times from sidecar events.

    Attributed partition per job — rows sum to the job wall together
    with verify_full and the unattributed remainder:
    queue_startup, transform_serialize, parse, compile,
    exec_shown(self), dedup_frontier(derived), checkpoint_io,
    aggregation. ``enumeration`` is kept as an inclusive memo
    (it contains transform_serialize and part of dedup_frontier).
    """
    spans: dict[str, dict[str, float]] = {}
    summaries: dict[str, dict[str, Any]] = {}
    for e in events:
        if e.get("type") == "phase_span":
            slot = spans.setdefault(e["job_id"], {})
            slot[e["phase"]] = slot.get(e["phase"], 0.0) + \
                e["wall_inclusive_s"]
            if e["phase"] in ("parse", "compile", "exec_shown"):
                self_key = f"{e['phase']}__self"
                slot[self_key] = slot.get(self_key, 0.0) + \
                    e["wall_self_s"]
        elif e.get("type") == "job_summary":
            summaries[e["job_id"]] = e
    rows: dict[str, dict[str, Any]] = {}
    for job_id, s in summaries.items():
        sp = spans.get(job_id, {})
        attributed = {
            "queue_startup": sp.get("queue_startup", 0.0),
            "transform_serialize": sp.get("transform_serialize", 0.0),
            "parse": sp.get("parse", 0.0),
            "compile": sp.get("compile", 0.0),
            "exec_shown": sp.get("exec_shown__self",
                                 sp.get("exec_shown", 0.0)),
            "dedup_frontier": sp.get("dedup_frontier", 0.0),
            "checkpoint_io": sp.get("checkpoint_io", 0.0),
            "aggregation": sp.get("aggregation", 0.0),
        }
        rows[job_id] = {
            "task_id": s["task_id"], "family": s["family"],
            "seed": s["seed"], "duration_s": s["duration_s"],
            "verify_full_s": s.get("verify_full_s", 0.0),
            "enumeration_inclusive_s": sp.get("enumeration", 0.0),
            "attributed": attributed,
            "unattributed_s": max(
                0.0, s["duration_s"] - sum(attributed.values())
                - s.get("verify_full_s", 0.0)),
            "logical_score_calls": s["logical_score_calls"],
            "solved": s["solved"],
        }
    return rows


def _percentile(sorted_vals: list[float], q: float) -> float:
    if not sorted_vals:
        return 0.0
    idx = min(len(sorted_vals) - 1, max(0, int(q * len(sorted_vals))))
    return sorted_vals[idx]


def cluster_bootstrap_shares(rows: dict[str, dict[str, Any]], *,
                             iterations: int = 2000,
                             seed: int = 20261113) -> dict[str, Any]:
    """Bootstrap phase shares resampling TASK clusters (each cluster
    carries all its seeds/reps) — never individual jobs."""
    import random
    clusters: dict[str, list[dict[str, Any]]] = {}
    for row in rows.values():
        clusters.setdefault(row["task_id"], []).append(row)
    cluster_keys = sorted(clusters)
    phases = list(next(iter(rows.values()))["attributed"].keys()) \
        if rows else []

    def shares(sample_keys: list[str]) -> dict[str, float]:
        tot_phase = {p: 0.0 for p in phases}
        tot_wall = 0.0
        for k in sample_keys:
            for row in clusters[k]:
                tot_wall += row["duration_s"]
                for p in phases:
                    tot_phase[p] += row["attributed"][p]
        return {p: (tot_phase[p] / tot_wall if tot_wall else 0.0)
                for p in phases}

    point = shares(cluster_keys)
    rng = random.Random(seed)
    boot: dict[str, list[float]] = {p: [] for p in phases}
    for _ in range(iterations):
        sample = [rng.choice(cluster_keys) for _ in cluster_keys]
        for p, v in shares(sample).items():
            boot[p].append(v)
    out = {}
    for p in phases:
        vals = sorted(boot[p])
        out[p] = {"share": point[p],
                  "ci95_lo": _percentile(vals, 0.025),
                  "ci95_hi": _percentile(vals, 0.975)}
    return out


def analyze_pilot(out_dir: str | Path) -> dict[str, Any]:
    out_dir = Path(out_dir)
    manifest, events = load_sidecar(out_dir)
    completeness = validate_sidecar(manifest, events)
    rows = _job_phase_rows(events)
    records = [json.loads(line) for line in
               (out_dir / "records.jsonl").read_text().splitlines()
               if line.strip()]

    # Scientific-field equality between modes, per task.
    mismatches = []
    by_task: dict[str, list[dict[str, Any]]] = {}
    for r in records:
        by_task.setdefault(r["task_id"], []).append(r)
    for task_id, rs in sorted(by_task.items()):
        fields = {(r["code"], r["shown_score"], r["evals"], r["solved"])
                  for r in rs}
        if len(fields) != 1:
            mismatches.append(task_id)

    # Paired overhead per task (median on vs median off job wall).
    import statistics
    walls_by_task: dict[str, list[dict[str, Any]]] = {}
    walls_file = out_dir / "job_walls.jsonl"
    if walls_file.exists():
        for line in walls_file.read_text().splitlines():
            if line.strip():
                w = json.loads(line)
                walls_by_task.setdefault(w["task_id"], []).append(w)
    diffs, ratios = [], []
    for task_id, ws in sorted(walls_by_task.items()):
        on = [w["job_wall_s"] for w in ws if w["mode"] == "on"]
        off = [w["job_wall_s"] for w in ws if w["mode"] == "off"]
        if on and off:
            diffs.append(statistics.median(on) - statistics.median(off))
            ratios.append(statistics.median(on) /
                          statistics.median(off) if off else 0.0)

    totals: dict[str, float] = {}
    total_wall = 0.0
    for row in rows.values():
        total_wall += row["duration_s"]
        for p, v in row["attributed"].items():
            totals[p] = totals.get(p, 0.0) + v
    ranking = sorted(
        ({"phase": p, "attributed_s": v,
          "share_of_instrumented_wall": v / total_wall if total_wall
          else 0.0} for p, v in totals.items()),
        key=lambda d: -d["attributed_s"])
    walls = [r["duration_s"] for r in rows.values()]
    heavy = max(rows.values(), key=lambda r: r["duration_s"],
                default=None)
    return {
        "run_id": manifest["run_id"],
        "completeness": completeness,
        "jobs_instrumented": len(rows),
        "tasks": len(by_task),
        "scientific_field_mismatches": mismatches,
        "phase_ranking_attributed": ranking,
        "enumeration_inclusive_s": sum(
            r["enumeration_inclusive_s"] for r in rows.values()),
        "verify_full_s": sum(r["verify_full_s"] for r in rows.values()),
        "unattributed_s": sum(r["unattributed_s"] for r in rows.values()),
        "instrumented_job_wall": {
            "mean_s": statistics.mean(walls) if walls else 0.0,
            "stdev_s": statistics.stdev(walls) if len(walls) > 1 else 0.0,
            "total_s": total_wall,
        },
        "heaviest_job": ({"task_id": heavy["task_id"],
                          "duration_s": heavy["duration_s"],
                          "share": heavy["duration_s"] / total_wall
                          if total_wall else 0.0}
                         if heavy else None),
        "overhead_paired_per_task": {
            "median_diff_s": statistics.median(diffs) if diffs else None,
            "median_ratio_on_over_off":
                statistics.median(ratios) if ratios else None,
            "tasks_paired": len(diffs),
        },
        "bootstrap_phase_shares": cluster_bootstrap_shares(rows),
        "note": "Pilot estimates only: variance + phase ranking + "
                "first optimisation candidate. Not evidence.",
    }


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in ("pilot", "analyze"):
        out = argv[argv.index("--out") + 1] if "--out" in argv else \
            "profiling_pilot_run"
        if argv[0] == "pilot":
            print(json.dumps(run_dev_pilot(out_dir=out), indent=1))
        else:
            print(json.dumps(analyze_pilot(out), indent=1))
        return 0
    print("usage: python -m ace_operational.profiling_observer "
          "pilot|analyze --out <dir>", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
