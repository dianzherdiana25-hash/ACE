"""Rencanakan antrean tempa terhadap jendela RAM dan tenggat.

Kapasitas setiap slot berasal dari jendela yang didaftarkan setelah
reserve RAM. Prioritas menurun diikuti tenggat, durasi, dan ID.
Setiap pekerjaan ditempatkan pada rentang kontigu pertama yang muat.
Laporan membawa alasan untuk pekerjaan yang tertahan dan jejak RAM.
"""
import argparse
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
import sys

from ._forge_io import InputError, canonical, decode, digest, entries, identity, integer, object_fields, read_bytes, string, utc_stamp
from ._numeric import reference
from .dataset_forge import MAX_BYTES


MAX_SLOTS = 10_080
MAX_JOBS = 1000
MAX_RAM_MIB = 2**20


def _slot(value, start, width, maximum):
    distance = utc_stamp(value) - start
    seconds = distance.days * 86_400 + distance.seconds
    if distance.microseconds or not 0 <= seconds <= maximum * width or seconds % width:
        raise InputError("Cap waktu di luar horizon atau tidak sejajar slot.")
    return seconds // width


@dataclass(frozen=True, slots=True)
class Job:
    key: str
    pointer: str
    earliest: int
    deadline: int
    duration: int
    ram: int
    priority: int

    @classmethod
    def read(cls, raw, start, width, horizon, ids, refs):
        object_fields(raw, ("id", "source_ref", "earliest", "deadline", "duration_slots", "ram_mib", "priority"))
        first = _slot(raw["earliest"], start, width, horizon)
        after = _slot(raw["deadline"], start, width, horizon)
        if first >= after:
            raise InputError("Tenggat pekerjaan harus sesudah earliest.")
        return cls(reference(raw["id"], ids, "ID pekerjaan"), reference(raw["source_ref"], refs, "rujukan pekerjaan"),
                   first, after, integer(raw["duration_slots"], 1, horizon),
                   integer(raw["ram_mib"], 1, MAX_RAM_MIB), integer(raw["priority"], 0, 10**6))

    def rank(self):
        return (-self.priority, self.deadline, self.duration, self.key)


def _first_fit(job, memory):
    consecutive = 0
    for index in range(job.earliest, job.deadline):
        consecutive = consecutive + 1 if memory[index] >= job.ram else 0
        if consecutive == job.duration:
            return index + 1 - consecutive
    return None


def schedule(raw, expected):
    object_fields(raw, ("calendar_ref", "start", "end", "slot_minutes", "reserve_mib", "windows", "jobs"))
    if identity(raw) != digest(expected):
        raise InputError("Rencana RAM berbeda dari anchor.")
    source = string(raw["calendar_ref"], "rujukan kalender")
    start = utc_stamp(raw["start"])
    width = integer(raw["slot_minutes"], 1, 1440) * 60
    horizon = _slot(raw["end"], start, width, MAX_SLOTS)
    if not horizon:
        raise InputError("Horizon penjadwalan kosong.")
    reserve = integer(raw["reserve_mib"], 0, MAX_RAM_MIB)
    refs, ids = {source}, set()
    capacity = [0] * horizon
    windows = []
    for row in entries(raw["windows"], 1000):
        object_fields(row, ("start", "end", "ram_mib", "source_ref"))
        begin, end = (_slot(row[key], start, width, horizon) for key in ("start", "end"))
        if begin >= end:
            raise InputError("Jendela RAM harus berdurasi positif.")
        raw_ram = integer(row["ram_mib"], 0, MAX_RAM_MIB)
        pointer = reference(row["source_ref"], refs, "rujukan jendela")
        windows.append((begin, end, raw_ram, pointer))
    windows.sort()
    if any(last[1] > current[0] for last, current in zip(windows, windows[1:])):
        raise InputError("Jendela RAM tumpang tindih.")
    for begin, end, memory, _ in windows:
        capacity[begin:end] = [max(0, memory - reserve)] * (end - begin)
    remaining = capacity[:]

    def stamp(slot):
        return (start + timedelta(seconds=slot * width)).isoformat()

    jobs = sorted((Job.read(row, start, width, horizon, ids, refs) for row in entries(raw["jobs"], MAX_JOBS)), key=Job.rank)
    planned, held = [], []
    for job in jobs:
        location = _first_fit(job, remaining)
        row = {"id": job.key, "source_ref": job.pointer, "ram_mib": job.ram, "duration_slots": job.duration,
               "priority": job.priority, "earliest": stamp(job.earliest), "deadline": stamp(job.deadline)}
        if location is None:
            if job.duration > job.deadline - job.earliest:
                reason = "duration_exceeds_window"
            else:
                reason = "capacity_reserved" if _first_fit(job, capacity) is not None else "no_ram_window"
            held.append({**row, "reason": reason})
            continue
        end = location + job.duration
        for index in range(location, end):
            remaining[index] -= job.ram
        planned.append({**row, "start": stamp(location), "end": stamp(end)})
    spans = []
    for begin, end, memory, pointer in windows:
        net = capacity[begin]
        free = min(remaining[begin:end])
        spans.append({"start": stamp(begin), "end": stamp(end), "source_ref": pointer, "total_ram_mib": memory,
                      "usable_ram_mib": net, "peak_scheduled_ram_mib": net - free, "minimum_free_mib": free})
    return {"schema": "ace.forge-ram-schedule.v1", "calendar_ref": source, "input_sha256": expected,
            "reserve_mib": reserve, "status": "partial" if held else "scheduled",
            "slots": horizon, "windows": spans, "planned": sorted(planned, key=lambda row: (row["start"], row["id"])),
            "held": held}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--expect-input-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        report = schedule(decode(read_bytes(args.input, MAX_BYTES)), args.expect_input_sha256)
        sys.stdout.write(canonical(report).decode("utf-8") + "\n")
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return int(report["status"] == "partial")


if __name__ == "__main__":
    raise SystemExit(main())
