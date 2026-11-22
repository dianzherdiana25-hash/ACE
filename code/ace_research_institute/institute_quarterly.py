"""Rekap mutu institut per kuartal dari laporan ber-anchor dan hasil audit yang dihitung ulang."""
from datetime import date
import re

from ._contracts import ResearchError, anchor, cli, day, decode, digest, identifier, integer, items, obj, schema, source_bytes, text
from .research_qa import audit_report


def quarter_bounds(raw):
    match = re.fullmatch(r"([0-9]{4})-Q([1-4])", raw) if isinstance(raw, str) else None
    if match is None:
        raise ResearchError("Kuartal perlu bentuk YYYY-Qn.")
    year, which = map(int, match.groups())
    if not 1 <= year <= 9998:
        raise ResearchError("Tahun kuartal berada di luar batas.")
    month = 1 + (which - 1) * 3
    next_year, next_month = (year + 1, 1) if which == 4 else (year, month + 3)
    return date(year, month, 1), date(next_year, next_month, 1)


def quarterly(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.institute.quarter-plan.v1", ("quarter", "sources", "minimum_score_bp"))
    start, stop = quarter_bounds(plan["quarter"])
    limit = integer(plan["minimum_score_bp"], "Ambang rubrik kuartal", 1, 10000)
    seen = set()
    hashes = set()
    reviewed = []
    gaps = []
    ignored = []
    for row in items(plan["sources"], 200):
        obj(row, ("id", "completed_date", "source_ref", "report"))
        key = identifier(row["id"], "Riset")
        if key in seen:
            raise ResearchError("Studi terulang dalam roster kuartal.")
        seen.add(key)
        stamp = day(row["completed_date"])
        source = text(row["source_ref"], "Pointer studi")
        if not start <= stamp < stop:
            ignored.append({"id": key, "completed_date": row["completed_date"]})
            continue
        if row["report"] is None:
            gaps.append({"id": key, "source_ref": source, "reason": "report_unlisted"})
            continue
        ref = obj(row["report"], ("path", "sha256"))
        expected_report = digest(ref["sha256"])
        if expected_report in hashes:
            raise ResearchError("Satu hash laporan tidak boleh dihitung untuk beberapa studi.")
        hashes.add(expected_report)
        evidence = source_bytes(root, ref["path"], expected_report, 3_000_000)
        report = decode(evidence)
        readout = audit_report(report, min_score=limit, min_sources=1, minimum_limits=1, root=root)
        reviewed.append({"id": key, "source_ref": source, "report": ref, "date": row["completed_date"],
                         "rubric_bp": readout["score_bp"], "status": readout["status"],
                         "numeric_verified": len(readout["verified_claims"]), "numeric_missing": len(readout["missing_support"]),
                         "source_findings": readout["source_findings"]})
    total = len(reviewed)
    values = sorted(row["rubric_bp"] for row in reviewed)
    median = None if not values else (values[(total - 1) // 2] + values[total // 2]) // 2
    return {"schema": "ace.institute.quarterly.v1", "plan_sha256": expected, "quarter": plan["quarter"],
            "scope": "supplied_report_roster", "period": [start.isoformat(), stop.isoformat()],
            "rubric_passes": sum(row["status"] == "passes_rubric" for row in reviewed),
            "reviewed_count": total, "median_rubric_bp": median, "minimum_score_bp": limit,
            "verified_numeric_total": sum(row["numeric_verified"] for row in reviewed),
            "reviewed": sorted(reviewed, key=lambda row: (row["date"], row["id"])),
            "evidence_gaps": sorted(gaps, key=lambda row: row["id"]), "out_of_quarter": sorted(ignored, key=lambda row: row["id"])}


if __name__ == "__main__":
    raise SystemExit(cli(quarterly, __doc__, rooted=True))
