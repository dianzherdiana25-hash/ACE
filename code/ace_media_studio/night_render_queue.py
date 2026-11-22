"""Pilih pekerjaan dalam jendela malam UTC dan ulang resep lokal dengan batas anggaran."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import sys
from time import monotonic

from ._assets import asset
from ._contracts import (ContractError, canonical, checked, decode, entries,
                         identifier, identity, integer, obj, read, schema)
from .render_recipe import replay


def _utc(raw):
    if not isinstance(raw, str) or not raw.endswith("Z"):
        raise ContractError("Waktu antrean perlu UTC berakhiran Z.")
    try:
        converted = datetime.fromisoformat(raw[:-1]).replace(tzinfo=timezone.utc)
    except ValueError as error:
        raise ContractError("Waktu antrean tidak valid.") from error
    if converted.isoformat(timespec="seconds").replace("+00:00", "Z") != raw:
        raise ContractError("Waktu UTC perlu format detik kanonis.")
    return converted


def queue(plan, expected, now):
    checked(plan, expected)
    schema(plan, "ace.media.night-queue.v1", ("from_utc", "to_utc", "max_watts", "max_watt_seconds", "jobs"))
    start, end, current = [_utc(value) for value in (plan["from_utc"], plan["to_utc"], now)]
    available = int((end - max(current, start)).total_seconds())
    if not 1 <= (end - start).total_seconds() <= 12 * 3600:
        raise ContractError("Jendela malam perlu berdurasi maksimal 12 jam.")
    watts = integer(plan["max_watts"], "Batas daya", 1, 1500)
    watt_seconds = integer(plan["max_watt_seconds"], "Batas energi", 1, 64_800_000)
    found = []
    seen = set()
    for row in entries(plan["jobs"], 80, 1):
        obj(row, ("id", "priority", "seconds", "watts", "recipe"))
        key = identifier(row["id"], "Pekerjaan render")
        if key in seen:
            raise ContractError("ID pekerjaan render ganda.")
        seen.add(key)
        priority = integer(row["priority"], "Prioritas", 0, 1000)
        seconds = integer(row["seconds"], "Durasi perkiraan", 1, 1800)
        power = integer(row["watts"], "Daya perkiraan", 1, 2000)
        location = obj(row["recipe"], ("path", "sha256"))
        found.append((-priority, key, power, seconds, location))
    selected = []
    skipped = []
    total_time = 0
    total_energy = 0
    for _, key, power, seconds, location in sorted(found):
        if current < start or current >= end:
            reason = "outside_window"
        elif power > watts:
            reason = "peak_budget"
        elif total_time + seconds > available:
            reason = "time_budget"
        elif total_energy + power * seconds > watt_seconds:
            reason = "energy_budget"
        else:
            selected.append({"id": key, "recipe": location, "seconds": seconds, "watts": power})
            total_time += seconds
            total_energy += power * seconds
            continue
        skipped.append({"id": key, "reason": reason})
    return {"schema": "ace.media.night-queue-plan.v1", "plan_sha256": expected, "as_of_utc": now,
            "to_utc": plan["to_utc"], "remaining_seconds": max(0, available),
            "method": "priority_serial_declared_watt_seconds", "estimated_watt_seconds": total_energy,
            "selected": selected, "skipped": skipped}


def run_selected(plan, expected, now, root, clock=monotonic):
    report = queue(plan, expected, now)
    beginning = clock()
    payload = {}
    receipts = []
    for job in report["selected"]:
        key = job["id"]
        if clock() - beginning + job["seconds"] > report["remaining_seconds"]:
            receipts.append({"id": key, "status": "window_elapsed"})
            break
        ref = job["recipe"]
        try:
            recipe = decode(asset(root, ref["path"], ref["sha256"], 1_000_000))
            result, proof = replay(recipe, identity(recipe))
        except (OSError, ValueError, TypeError, RecursionError) as error:
            receipts.append({"id": key, "status": "failed", "reason": str(error)[:230]})
            break
        if clock() - beginning >= report["remaining_seconds"]:
            receipts.append({"id": key, "status": "completed_after_window"})
            break
        suffix = ".wav" if proof["profile"] == "formant_wav" else ".png"
        payload[key + suffix] = result
        receipts.append({"id": key, "status": "rendered", "sha256": sha256(result).hexdigest()})
    return payload, {**report, "receipts": receipts}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("asset_root", type=Path)
    parser.add_argument("--now", required=True)
    parser.add_argument("--expect-sha256", required=True)
    parser.add_argument("--execute-into", type=Path)
    args = parser.parse_args(argv)
    try:
        plan = decode(read(args.plan))
        if args.execute_into is None:
            report = queue(plan, args.expect_sha256, args.now)
        else:
            payload, report = run_selected(plan, args.expect_sha256, args.now, args.asset_root)
            args.execute_into.mkdir()
            for name, data in payload.items():
                (args.execute_into / name).write_bytes(data)
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, TypeError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return int(any(receipt["status"] != "rendered" for receipt in report.get("receipts", [])))


if __name__ == "__main__":
    raise SystemExit(main())
