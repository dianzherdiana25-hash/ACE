"""Rencanakan produksi media berulang di jendela resource yang terbatas dan bisa diperiksa."""
import argparse
from pathlib import Path
import sys

from ._contracts import (ContractError, canonical, checked, decode, entries,
                         identifier, integer, obj, read, schema)


def _free(blocks, resource, capacity, start, end):
    current = [block for block in blocks if block["start"] < end and start < block["end"]]
    events = [(start, capacity)]
    for block in current:
        events.extend([(max(start, block["start"]), block[resource]), (min(end, block["end"]), -block[resource])])
    used = 0
    peak = 0
    for _, change in sorted(events):
        used += change
        peak = max(peak, used)
    return peak


def _queue(tasks):
    order = []
    remaining = set(tasks)
    while remaining:
        ready = [key for key in remaining if not set(tasks[key]["after"]) & remaining]
        if not ready:
            raise ContractError("Prasyarat produksi membentuk putaran.")
        key = min(ready, key=lambda name: (tasks[name]["deadline"], -tasks[name]["priority"], name))
        remaining.remove(key)
        order.append(key)
    return order


def schedule(plan, expected):
    checked(plan, expected)
    schema(plan, "ace.media.schedule-plan.v1", ("horizon_minutes", "windows", "tasks"))
    horizon = integer(plan["horizon_minutes"], "Cakrawala menit", 1, 43_200)
    windows = {}
    for item in entries(plan["windows"], 80, 1):
        obj(item, ("id", "start", "end", "slots", "ram_mib"))
        key = identifier(item["id"], "Jendela")
        if key in windows:
            raise ContractError("Jendela sumber daya ganda.")
        start = integer(item["start"], "Awal jendela", 0, horizon - 1)
        end = integer(item["end"], "Akhir jendela", start + 1, horizon)
        windows[key] = {"start": start, "end": end, "slots": integer(item["slots"], "Slot jendela", 1, 16),
                        "ram_mib": integer(item["ram_mib"], "Memori jendela", 16, 131072), "booked": []}
    sequence = sorted(windows, key=lambda name: (windows[name]["start"], name))
    if any(windows[a]["end"] > windows[b]["start"] for a, b in zip(sequence, sequence[1:])):
        raise ContractError("Jendela resource tidak boleh saling tumpang tindih.")
    tasks = {}
    for item in entries(plan["tasks"], 240, 1):
        obj(item, ("id", "duration", "release", "deadline", "ram_mib", "slots", "after", "priority"))
        key = identifier(item["id"], "Pekerjaan")
        if key in tasks:
            raise ContractError("Pekerjaan ber-ID ganda.")
        release = integer(item["release"], "Tanggal mulai minimum", 0, horizon - 1)
        after = [identifier(ref, "Prasyarat") for ref in entries(item["after"], 50)]
        if len(set(after)) != len(after):
            raise ContractError("Prasyarat tidak boleh duplikat.")
        tasks[key] = {"release": release, "deadline": integer(item["deadline"], "Tenggat", release + 1, horizon),
                      "duration": integer(item["duration"], "Durasi", 1, horizon),
                      "ram_mib": integer(item["ram_mib"], "Memori tugas", 16, 131072),
                      "slots": integer(item["slots"], "Slot tugas", 1, 16), "after": after,
                      "priority": integer(item["priority"], "Prioritas", 0, 1000)}
    if any(ref not in tasks for task in tasks.values() for ref in task["after"]):
        raise ContractError("Prasyarat belum terdaftar.")
    planned = {}
    skipped = {}
    for key in _queue(tasks):
        item = tasks[key]
        missing = sorted(set(item["after"]) - planned.keys())
        if missing:
            skipped[key] = {"reason": "dependency_not_scheduled", "dependencies": missing}
            continue
        release = max([item["release"], *(planned[ref]["end"] for ref in item["after"])])
        for window_id in sequence:
            window = windows[window_id]
            left = max(window["start"], release)
            right = min(window["end"], item["deadline"])
            candidates = sorted({left, *(block["end"] for block in window["booked"] if left < block["end"] < right)})
            for start in candidates:
                end = start + item["duration"]
                if end <= right and all(_free(window["booked"], key, item[key], start, end) <= window[key]
                                        for key in ("ram_mib", "slots")):
                    planned[key] = {"id": key, "start": start, "end": end, "window": window_id,
                                    "ram_mib": item["ram_mib"], "slots": item["slots"], "after": item["after"]}
                    window["booked"].append(planned[key])
                    break
            if key in planned:
                break
        if key not in planned:
            skipped[key] = {"reason": "no_slot_in_greedy_plan"}
    return {"schema": "ace.media.scheduled.v1", "plan_sha256": expected, "method": "earliest_deadline_then_priority",
            "placements": sorted(planned.values(), key=lambda row: (row["start"], row["id"])),
            "unplaced": [{"id": key, **reason} for key, reason in sorted(skipped.items())]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        report = schedule(decode(read(args.plan)), args.expect_sha256)
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, TypeError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return int(bool(report["unplaced"]))


if __name__ == "__main__":
    raise SystemExit(main())
