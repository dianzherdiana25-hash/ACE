"""Urutkan antrean tempa dari rencana tertambat dan kapasitas yang tersisa.

Prioritas mendapat satu poin per jendela tunggu penuh. Tenggat lebih
dekat memecah seri, disusul waktu daftar dan ID. Antrean memberi
rekomendasi penerimaan satu batch berdasarkan RAM, unit, dan slot
bersamaan. Dependensi dianggap selesai hanya pada snapshot sumber.
"""
import argparse
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import sys

from ._forge_io import InputError, canonical, decode, digest, entries, identity, integer, object_fields, read_bytes, string, utc_stamp
from .dataset_forge import MAX_BYTES


MAX_JOBS = 3000
MAX_CAPACITY = 10**12


@dataclass(frozen=True, slots=True)
class Job:
    key: str
    ref: str
    priority: int
    arrived: datetime
    deadline: datetime | None
    duration: int
    ram: int
    units: int
    dependencies: tuple

    @classmethod
    def read(cls, raw):
        object_fields(raw, ("id", "recipe_ref", "priority", "enqueued_at", "deadline",
                            "duration_minutes", "ram_mib", "units", "depends_on"))
        deps = tuple(string(value, "ID dependensi") for value in entries(raw["depends_on"], MAX_JOBS))
        if len(set(deps)) != len(deps):
            raise InputError("Dependensi ganda.")
        arrived = utc_stamp(raw["enqueued_at"])
        deadline = None if raw["deadline"] is None else utc_stamp(raw["deadline"])
        if deadline is not None and deadline < arrived:
            raise InputError("Tenggat mendahului waktu daftar.")
        return cls(string(raw["id"], "ID antrean"), string(raw["recipe_ref"], "rujukan resep"),
                   integer(raw["priority"], 0, MAX_CAPACITY), arrived, deadline,
                   integer(raw["duration_minutes"], 1, 365*24*60),
                   integer(raw["ram_mib"], 1, MAX_CAPACITY), integer(raw["units"], 0, MAX_CAPACITY),
                   tuple(sorted(deps)))


def _check_dependencies(jobs):
    counts = {key: 0 for key in jobs}
    successors = {key: [] for key in jobs}
    for key, job in jobs.items():
        for dep in job.dependencies:
            if dep not in jobs:
                continue
            counts[key] += 1
            successors[dep].append(key)
    ready = deque(key for key, count in counts.items() if count == 0)
    resolved = 0
    while ready:
        key = ready.popleft()
        resolved += 1
        for child in successors[key]:
            counts[child] -= 1
            if counts[child] == 0:
                ready.append(child)
    if resolved != len(jobs):
        raise InputError("Siklus dependensi pada rencana antrean.")


def _completed(raw, jobs, now):
    completed = {}
    refs = set()
    for row in entries(raw, MAX_JOBS):
        object_fields(row, ("id", "receipt_ref", "completed_at"))
        key = string(row["id"], "ID selesai")
        ref = string(row["receipt_ref"], "rujukan receipt")
        stamp = utc_stamp(row["completed_at"])
        job = jobs.get(key)
        if job is None or key in completed or ref in refs or not job.arrived <= stamp <= now:
            raise InputError("Receipt selesai tidak sesuai rencana, waktu, atau identitas.")
        refs.add(ref)
        completed[key] = (ref, stamp)
    for key, (_, stamp) in completed.items():
        if any(dep not in completed or completed[dep][1] > stamp for dep in jobs[key].dependencies):
            raise InputError("Receipt selesai mendahului dependensi.")
    return completed


def schedule(raw, expected):
    object_fields(raw, ("queue_ref", "as_of", "policy", "capacity", "jobs", "completed"))
    if identity(raw) != digest(expected):
        raise InputError("Antrean berbeda dari anchor.")
    source = string(raw["queue_ref"], "rujukan antrean")
    now = utc_stamp(raw["as_of"])
    policy = raw["policy"]
    object_fields(policy, ("aging_minutes",))
    aging = integer(policy["aging_minutes"], 1, 365*24*60) * 60
    capacity = raw["capacity"]
    object_fields(capacity, ("ram_mib", "units", "slots"))
    remaining = {key: integer(value, 0, MAX_CAPACITY) for key, value in capacity.items()}
    jobs = {}
    for row in entries(raw["jobs"], MAX_JOBS):
        job = Job.read(row)
        if job.key in jobs:
            raise InputError("ID antrean ganda.")
        jobs[job.key] = job
    _check_dependencies(jobs)
    completed = _completed(raw["completed"], jobs, now)
    pending = {}
    admitted = []
    for key, job in jobs.items():
        effective = job.priority + max(0, int((now - job.arrived).total_seconds()) // aging)
        reasons = []
        if job.arrived > now:
            reasons.append("not_arrived")
        if job.deadline is not None and (job.deadline - now) < timedelta(minutes=job.duration):
            reasons.append("deadline_unreachable")
        missing = [dep for dep in job.dependencies if dep not in jobs]
        waiting = [dep for dep in job.dependencies if dep in jobs and dep not in completed]
        if missing:
            reasons.append("unknown_dependency")
        if waiting:
            reasons.append("waiting_dependency")
        pending[key] = (effective, reasons, missing, waiting)

    ordered = sorted(jobs.values(), key=lambda job: (-pending[job.key][0], job.deadline is None,
                                                     job.deadline or job.arrived, job.arrived, job.key))
    rows = []
    for job in ordered:
        key = job.key
        effective, reasons, missing, waiting = pending[key]
        if key in completed:
            status, reasons = "completed", []
        elif reasons:
            status = "deferred"
        else:
            needed = {"ram_mib": job.ram, "units": job.units, "slots": 1}
            reasons = [f"insufficient_{item}" for item in needed if needed[item] > remaining[item]]
            status = "deferred" if reasons else "admitted"
            if not reasons:
                admitted.append(key)
                for item, amount in needed.items():
                    remaining[item] -= amount
        rows.append({"id": key, "recipe_ref": job.ref, "effective_priority": effective,
                     "status": status, "reasons": reasons, "unknown_dependencies": missing,
                     "waiting_dependencies": waiting,
                     "completed_ref": completed[key][0] if key in completed else None})
    return {"schema": "ace.forge-priority-queue.v1", "queue_ref": source, "queue_sha256": expected,
            "as_of": raw["as_of"], "admitted": admitted, "remaining": remaining, "jobs": rows}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("queue", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        product = schedule(decode(read_bytes(args.queue, MAX_BYTES)), args.expect_sha256)
        sys.stdout.buffer.write(canonical(product) + b"\n")
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
