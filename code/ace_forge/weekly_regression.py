"""Audit regresi mingguan dari snapshot artefak aktif yang direkam.

Minggu memakai Senin 00:00 UTC sampai awal Senin berikutnya.
Satu baseline dan roster dipakai sepanjang seri. Minggu tanpa
snapshot dilaporkan missing, atau pending saat jendelanya masih
terbuka. Gate per domain mengikuti forgetting_guard.
"""
import argparse
from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
import sys

from . import forgetting_guard
from ._forge_io import InputError, canonical, decode, digest, entries, identity, integer, object_fields, read_bytes, string, utc_stamp
from ._numeric import reference
from .dataset_forge import MAX_BYTES


MAX_WEEKS = 104
MAX_CELLS = 150_000
WEEK = timedelta(days=7)


def _week(day):
    return (day - timedelta(days=day.weekday())).isoformat()


def _windows(start_raw, weeks):
    raw = string(start_raw, "Senin awal")
    try:
        first = date.fromisoformat(raw)
        if first.isoformat() != raw or first.weekday() != 0:
            raise ValueError
        return {start.isoformat(): datetime.combine(start + WEEK, time.min, timezone.utc)
                for start in (first + index * WEEK for index in range(weeks))}
    except (ValueError, OverflowError) as exc:
        raise InputError("Minggu mulai pada tanggal Senin ISO.") from exc


def _arms(rows, names, refs):
    result = {}
    for row in entries(rows, forgetting_guard.MAX_CASES):
        object_fields(row, ("case_id", "assessment"))
        key = string(row["case_id"], "ID penilaian")
        if key not in names or key in result:
            raise InputError("Penilaian mingguan ganda atau di luar roster.")
        result[key] = forgetting_guard._arm(row["assessment"], refs)
    return result


def _snapshot(raw, now, windows, refs, cases):
    snapshots = {}
    for row in entries(raw, MAX_WEEKS):
        object_fields(row, ("snapshot_ref", "active_sha256", "observed_at", "assessments"))
        stamp = utc_stamp(row["observed_at"])
        key = _week(stamp.date())
        if key not in windows or key in snapshots or stamp > now:
            raise InputError("Snapshot berada di luar jendela, ganda, atau dari masa depan.")
        pointer = reference(row["snapshot_ref"], refs, "rujukan snapshot")
        active = digest(row["active_sha256"])
        snapshots[key] = (stamp.isoformat(), pointer, active, _arms(row["assessments"], cases, refs))
    return snapshots


def assess(raw, evidence, expected):
    object_fields(raw, ("series_ref", "start_week", "week_count", "as_of", "baseline_sha256", "protocol", "evidence_sha256"))
    if identity(raw) != digest(expected):
        raise InputError("Rencana regresi mingguan berbeda dari anchor.")
    if identity(evidence) != digest(raw["evidence_sha256"]):
        raise InputError("Snapshot mingguan berbeda dari komitmen.")
    proto, cases, refs = forgetting_guard._protocol(raw["protocol"])
    p_sha = identity(proto)
    source = reference(raw["series_ref"], refs, "rujukan seri")
    now = utc_stamp(raw["as_of"])
    windows = _windows(raw["start_week"], integer(raw["week_count"], 1, MAX_WEEKS))
    if len(windows) * len(cases) > MAX_CELLS:
        raise InputError("Matriks mingguan melampaui batas.")
    base_sha = digest(raw["baseline_sha256"])
    object_fields(evidence, ("evidence_ref", "baseline_sha256", "baseline", "snapshots"))
    if digest(evidence["baseline_sha256"]) != base_sha:
        raise InputError("Receipt mingguan memakai baseline berbeda.")
    evidence_ref = reference(evidence["evidence_ref"], refs, "rujukan receipt")
    baseline = _arms(evidence["baseline"], cases, refs)
    snapshots = _snapshot(evidence["snapshots"], now, windows, refs, cases)
    schedule = []
    for week, end in windows.items():
        value = snapshots.get(week)
        if value is None:
            status = "pending" if now < end else "missing"
            schedule.append({"week_start_utc": week, "observed_at": None, "snapshot_ref": None, "active_sha256": None,
                             "status": status, "blocked_domains": [], "domains": []})
            continue
        at, pointer, artifact, tests = value
        raw_results = [{"case_id": key, "baseline": baseline.get(key), "candidate": tests.get(key)} for key in sorted(cases)]
        product = forgetting_guard.screen({"protocol": proto, "results": raw_results}, p_sha)
        schedule.append({"week_start_utc": week, "observed_at": at, "snapshot_ref": pointer, "active_sha256": artifact,
                         "status": product["status"], "blocked_domains": product["blocked_domains"], "domains": product["domains"]})

    counts = Counter(row["status"] for row in schedule)
    return {"schema": "ace.forge-weekly-regression.v1", "series_ref": source, "series_sha256": expected,
            "baseline_sha256": base_sha, "as_of": now.isoformat(), "protocol_ref": proto["protocol_ref"],
            "protocol_sha256": p_sha, "evidence_ref": evidence_ref, "evidence_sha256": raw["evidence_sha256"],
            "summary": {state: counts[state] for state in ("pass", "hold", "missing", "pending")},
            "weeks": schedule}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("series", type=Path)
    parser.add_argument("evidence", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        result = assess(decode(read_bytes(args.series, MAX_BYTES)), decode(read_bytes(args.evidence, MAX_BYTES)),
                        args.expect_sha256)
        sys.stdout.write(canonical(result).decode("utf-8") + "\n")
    except (OSError, ValueError, OverflowError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return int(bool(result["summary"]["hold"] or result["summary"]["missing"]))


if __name__ == "__main__":
    raise SystemExit(main())
