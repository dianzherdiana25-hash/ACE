"""Hitung waktu kerja bersih tiap kedalaman dari interval kerja berkas receipt."""
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
import re

from ._contracts import ResearchError, anchor, cli, decode, fmt, identifier, obj, schema, source_bytes
from ._tabular import quantile


DURATION = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z")


def _time(raw):
    if not isinstance(raw, str) or not DURATION.fullmatch(raw):
        raise ResearchError("Timestamp biaya waktu wajib UTC sampai detik.")
    try:
        return datetime.fromisoformat(raw[:-1])
    except ValueError as error:
        raise ResearchError("Tanggal biaya waktu tidak valid.") from error


def _union(intervals):
    combined = []
    for start, end in sorted(intervals):
        if combined and combined[-1][1] >= start:
            combined[-1][1] = max(combined[-1][1], end)
        else:
            combined.append([start, end])
    return sum(int((end - start).total_seconds()) for start, end in combined)


def cost(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.institute.research-cost-plan.v1", ("receipts",))
    link = obj(plan["receipts"], ("path", "sha256"))
    raw = source_bytes(root, link["path"], link["sha256"], 1_500_000)
    studies = {}
    receipt_ids = set()
    for line, token in enumerate(raw.splitlines(), 1):
        if line > 15000:
            raise ResearchError("Anggaran baris receipt waktu terlampaui.")
        if not token.strip():
            continue
        row = obj(decode(token), ("id", "study", "depth", "start", "end", "kind"))
        key = identifier(row["id"], "Receipt waktu")
        name = identifier(row["study"], "Studi")
        depth = identifier(row["depth"], "Kedalaman laporan")
        if key in receipt_ids or row["kind"] not in ("active", "wait"):
            raise ResearchError("Receipt duplikat atau tipe waktu tak didukung.")
        receipt_ids.add(key)
        start, end = _time(row["start"]), _time(row["end"])
        if not 0 < (end - start).total_seconds() <= 30 * 86400:
            raise ResearchError("Interval waktu terbalik, nol atau di luar batas.")
        group = studies.setdefault(name, {"depth": depth, "active": [], "wait": [], "lines": []})
        if group["depth"] != depth:
            raise ResearchError("Kedalaman satu studi tidak konsisten.")
        group[row["kind"]].append((start, end))
        group["lines"].append(line)
    data = defaultdict(list)
    for study, record in sorted(studies.items()):
        active = _union(record["active"])
        waiting = _union(record["wait"])
        if active == 0:
            active = None
        data[record["depth"]].append({"study": study, "active_seconds": active,
                                      "declared_wait_seconds": waiting, "source_lines": record["lines"]})
    report = []
    for depth, cohort in sorted(data.items()):
        counted = [Decimal(row["active_seconds"]) for row in cohort if row["active_seconds"] is not None]
        report.append({"depth": depth, "complete": len(counted), "total": len(cohort),
                       "median_active_seconds": fmt(quantile(counted, 1, 2)) if counted else None,
                       "active_seconds_total": fmt(sum(counted)), "studies": cohort})
    return {"schema": "ace.institute.research-time-cost.v1", "plan_sha256": expected, "receipts": link,
            "basis": "union_active_intervals_per_study", "by_depth": report}


if __name__ == "__main__":
    raise SystemExit(cli(cost, __doc__, rooted=True))
