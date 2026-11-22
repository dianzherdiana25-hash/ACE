"""Laporkan keputusan yang benar-benar menautkan studi dan delta observasi sebelum/sesudah."""
import re

from ._contracts import (ResearchError, anchor, cli, day, fmt, identifier, integer,
                         items, obj, schema, source_bytes, text)
from ._evidence import quantity
from .number_provenance import scan_prose


def _cited(root, row):
    obj(row, ("path", "sha256", "line", "marker"))
    lines = source_bytes(root, row["path"], row["sha256"], 300000).decode("utf-8").splitlines()
    number = integer(row["line"], "Baris bukti", 1, len(lines))
    needle = text(row["marker"], "Penanda kutipan", 220)
    if needle not in lines[number - 1]:
        raise ResearchError("Penanda tidak ditemukan pada baris bukti.")
    return row


def impact(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.institute.impact-plan.v1", ("studies", "decisions"))
    studies = {}
    for row in items(plan["studies"], 140, 1):
        obj(row, ("id", "date", "source"))
        key = identifier(row["id"], "Studi")
        if key in studies:
            raise ResearchError("Studi ganda.")
        studies[key] = (day(row["date"]), _cited(root, row["source"]))
    known = set()
    rows = []
    for row in items(plan["decisions"], 180):
        obj(row, ("id", "date", "study", "decision_ref", "before", "after", "metric"))
        key = identifier(row["id"], "Keputusan")
        reference = identifier(row["study"], "Studi sumber")
        decision_date = day(row["date"])
        if key in known or reference not in studies:
            raise ResearchError("Keputusan ganda atau studi tidak tercatat.")
        known.add(key)
        produced, source = studies[reference]
        paper = _cited(root, row["decision_ref"])
        if re.search(r"(?<!\w)" + re.escape(reference) + r"(?!\w)", paper["marker"]) is None or produced > decision_date:
            raise ResearchError("Penanda keputusan harus menunjuk studi yang telah tersedia.")
        comparison = []
        if row["before"] is not None and row["after"] is not None:
            for item in (row["before"], row["after"]):
                obj(item, ("date", "value", "unit", "evidence"))
                date = day(item["date"])
                unit, estimate = quantity(item["value"], item["unit"])
                proof = _cited(root, item["evidence"])
                declared = {value for _, (_, value, _) in scan_prose(proof["marker"])}
                if str(item["value"]) not in declared:
                    raise ResearchError("Penanda hasil tidak memuat nilai observasi yang dicatat.")
                comparison.append((date, unit, estimate, proof))
        delta, unit, span = None, None, None
        if comparison:
            a, b = comparison
            if a[0] >= decision_date or b[0] < decision_date or a[1] != b[1]:
                raise ResearchError("Tanggal atau satuan pre/post tidak sesuai keputusan.")
            delta, unit = fmt(b[2] - a[2]), a[1]
            span = [{"date": rec[0].isoformat(), "estimate": fmt(rec[2]), "source": rec[3]} for rec in comparison]
        rows.append({"id": key, "study": reference, "decision_date": row["date"], "study_evidence": source,
                     "decision_evidence": paper, "metric": identifier(row["metric"], "Metrik tindak lanjut"),
                     "observational_delta": delta, "unit": unit, "paired_observations": span,
                     "status": "cited_with_observed_change" if comparison else "cited_outcome_missing"})
    return {"schema": "ace.institute.research-impact.v1", "plan_sha256": expected, "basis": "citation_and_observational_pre_post",
            "decision_count": len(rows), "paired_outcome_count": sum(row["paired_observations"] is not None for row in rows),
            "decisions": sorted(rows, key=lambda row: (row["decision_date"], row["id"]))}


if __name__ == "__main__":
    raise SystemExit(cli(impact, __doc__, rooted=True))
