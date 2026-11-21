"""Urutkan antrean persepsi dengan deadline, aging dan budget kelas operasi.

Rencana memberi cap waktu pengambilan keputusan dan biaya
deklaratif. Pekerjaan yang semakna hanya menyisakan satu wakil.
Keluaran mencatat setiap penundaan dan anggaran yang tersisa
tanpa mengeksekusi pekerjaan.
"""
import argparse
from datetime import timedelta
from hashlib import sha256
from pathlib import Path
import sys

from . import _raster, _vision
from .audio_pipeline import _canonical, _integer, _sha
from .document_extractor import _token
from .perceptual_memory import _digest, _utc


MAX_JOBS = 512


def _limits(raw):
    if not isinstance(raw, dict) or not 1 <= len(raw) <= 32:
        raise ValueError("Kuota harus berisi kelas operasi.")
    return {_token(name, "Kelas operasi"): _integer(count, 0, MAX_JOBS, "Kuota kelas") for name, count in raw.items()}


def schedule(plan, expected):
    fields = ("as_of", "plan_ref", "age_minutes_per_point", "budget_ms", "budget_bytes", "maximum_jobs", "class_caps", "jobs")
    raw = _vision.spec(plan, "ace.perception-priority.v1", fields)
    if _sha(raw) != _digest(expected):
        raise ValueError("Rencana antrean berbeda dari anchor.")
    now = _utc(raw["as_of"])
    age_window = _integer(raw["age_minutes_per_point"], 1, 1440, "Interval aging")
    time_left = _integer(raw["budget_ms"], 0, 7*86_400_000, "Batas waktu kerja")
    bytes_left = _integer(raw["budget_bytes"], 0, 1_000_000_000, "Batas byte")
    slots_left = _integer(raw["maximum_jobs"], 0, MAX_JOBS, "Slot pekerjaan")
    class_left = _limits(raw["class_caps"])
    rows = raw["jobs"]
    if not isinstance(rows, list) or len(rows) > MAX_JOBS:
        raise ValueError("Panjang antrean di luar batas.")
    initial_time_budget = time_left
    jobs, known = [], set()
    for row in rows:
        required = {"id", "class", "media_sha256", "config_sha256", "created_at", "deadline",
                    "priority", "estimated_ms", "estimated_bytes", "source_ref"}
        if not isinstance(row, dict) or set(row) != required:
            raise ValueError("Bentuk pekerjaan persepsi tidak sah.")
        key, kind, ref = (_token(row[field], field) for field in ("id", "class", "source_ref"))
        if key in known or kind not in class_left:
            raise ValueError("ID ganda atau kelas belum didaftarkan.")
        known.add(key)
        created = _utc(row["created_at"])
        deadline = None if row["deadline"] is None else _utc(row["deadline"])
        if deadline is not None and created > deadline:
            raise ValueError("Deadline mendahului waktu pendaftaran.")
        identity = kind, _digest(row["media_sha256"]), _digest(row["config_sha256"])
        wait = max(0, int((now-created).total_seconds())//60)
        priority = _integer(row["priority"], 0, 10_000, "Prioritas")
        duration = _integer(row["estimated_ms"], 1, 86_400_000, "Perkiraan waktu")
        amount = _integer(row["estimated_bytes"], 1, 128_000_000, "Perkiraan byte")
        jobs.append((priority+wait//age_window, created, deadline, key, identity, ref, duration, amount))
    jobs.sort(key=lambda row: (-row[0], row[2] is None, row[2] or now, row[1], row[3]))
    winners = {}
    results = []
    for rating, created, deadline, key, identity, ref, duration, amount in jobs:
        kind = identity[0]
        reasons = []
        duplicate = winners.get(identity)
        if created > now:
            reasons.append("not_arrived")
        elif deadline is not None and deadline-now < timedelta(milliseconds=initial_time_budget-time_left+duration):
            reasons.append("deadline_unreachable")
        elif duplicate is not None:
            reasons.append("duplicate")
        else:
            winners[identity] = key
            for reason, blocked in (("no_slots", not slots_left), ("class_cap", not class_left[kind]),
                                    ("time_budget", duration > time_left), ("byte_budget", amount > bytes_left)):
                if blocked:
                    reasons.append(reason)
        if not reasons:
            slots_left -= 1
            class_left[kind] -= 1
            time_left -= duration
            bytes_left -= amount
        results.append({"id": key, "class": kind, "source_ref": ref, "effective_priority": rating,
                        "estimated_ms": duration, "estimated_bytes": amount, "reasons": reasons,
                        "status": "deferred" if reasons else "scheduled",
                        "duplicate_of": duplicate if reasons == ["duplicate"] else None})
    return {"schema": "ace.perception-priority-schedule.v1", "plan_ref": _token(raw["plan_ref"], "Rujukan antrean"),
            "plan_sha256": expected, "plan_bytes_sha256": sha256(plan).hexdigest(), "as_of": now.isoformat(),
            "remaining": {"bytes": bytes_left, "milliseconds": time_left, "slots": slots_left, "by_class": class_left},
            "schedule": results}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        result = schedule(_raster.read(args.plan, _vision.MAX_SPEC_BYTES), args.expect_sha256)
        sys.stdout.buffer.write(_canonical(result)+b"\n")
    except (OSError, OverflowError, ValueError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
