"""Audit rubrik laporan dengan pembacaan ulang klaim dan byte sumber, serta kegagalan bernama."""
from decimal import Decimal, InvalidOperation
from hashlib import sha256

from ._contracts import (ResearchError, anchor, cli, decode, digest, identifier,
                         integer, items, obj, schema, source_bytes)
from ._evidence import dimension
from .paper_reader import extract


RULES = {"body_integrity": 1000, "source_custody": 2500, "numeric_entailment": 2500,
         "claim_accounting": 2000, "limitations": 1000, "distinct_source_documents": 1000}
STATES = ("supported", "contradicted", "mixed_evidence", "insufficient_evidence")


def _claimed(value):
    try:
        result = Decimal(value)
    except (TypeError, ValueError, InvalidOperation) as error:
        raise ResearchError("Angka keluaran laporan tidak sah.") from error
    if not result.is_finite():
        raise ResearchError("Angka keluaran laporan harus finite.")
    return result


def _claimed_status(report, minimum, sources):
    verified = {}
    missing = []
    faulty = []
    categories = dict.fromkeys(STATES, 0)
    groups = set()
    claim_ids = set()
    for section in items(report["sections"], 30, 1):
        for row in items(section["claims"], 80, 1):
            key = identifier(row["id"], "Klaim")
            if key in claim_ids or row["status"] not in STATES:
                raise ResearchError("Klaim ganda atau status laporan tidak dikenal.")
            claim_ids.add(key)
            categories[row["status"]] += 1
            if row["status"] != "supported":
                if row["amount"] is not None or row["candidate_text"] is not None:
                    faulty.append({"id": key, "reason": "unverified_amount_present"})
                continue
            amount = obj(row["amount"], ("value", "unit"))
            value = _claimed(amount["value"])
            radius = _claimed(row["tolerance"])
            linked = []
            for entry in items(row["sources"], 300):
                if entry["outcome"] != "supports":
                    continue
                candidate = sources.get(entry["id"])
                if (candidate is None or any(candidate["ref"][field] != entry[field] for field in
                                             ("path", "line", "sha256", "source_id"))):
                    continue
                measured = candidate["measurement"]
                if (measured is not None and measured["unit"] == amount["unit"]
                        and dimension(measured["dimensions"]) == dimension(row["dimensions"])
                        and abs(_claimed(measured["estimate"]) - value) <= radius
                        and measured["estimate"] == entry["value"]):
                    linked.append(entry["id"])
                    groups.add(candidate["ref"]["sha256"])
            if linked:
                verified[key] = sorted(set(linked))
            else:
                missing.append(key)
    matching = not faulty and categories == report["summary"]
    return verified, missing, categories, faulty, matching, len(groups) >= minimum


def audit_report(report, *, min_score, min_sources, minimum_limits, root):
    schema(report, "ace.institute.deep-report.v1", ("plan_sha256", "claim_check_sha256", "title", "question",
                                                  "sections", "limitations", "summary", "sources", "markdown_sha256", "markdown"))
    body = report["markdown"]
    valid_body = isinstance(body, str) and sha256(body.encode()).hexdigest() == digest(report["markdown_sha256"])
    docs = {}
    sources = {}
    defects = []
    for ref in items(report["sources"], 1000):
        obj(ref, ("id", "source_id", "path", "line", "sha256"))
        key = identifier(ref["id"], "ID sitasi")
        if key in sources:
            raise ResearchError("ID sitasi ganda di daftar sumber.")
        row = {"ref": ref, "measurement": None}
        sources[key] = row
        anchor = digest(ref["sha256"])
        identity_key = (ref["path"], anchor)
        try:
            if identity_key not in docs:
                data = source_bytes(root, ref["path"], anchor)
                trace = extract(data, ref["source_id"], ref["path"], ref["source_id"], anchor)
                docs[identity_key] = {item["source"]["line"]: item for item in trace["claims"]}
            row["measurement"] = docs[identity_key].get(integer(ref["line"], "Baris sitasi", 1, 1000000))
            if row["measurement"] is None:
                defects.append({"source": key, "reason": "measurement_line_unavailable"})
        except (OSError, ValueError, TypeError) as error:
            defects.append({"source": key, "reason": f"evidence_unavailable:{type(error).__name__}"})
    verified, missing, status_counts, defects_claims, reconciled, group_progress = _claimed_status(report, min_sources, sources)
    statements = items(report["limitations"], 30)
    checks = {"body_integrity": valid_body, "source_custody": bool(sources) and not defects,
              "numeric_entailment": bool(verified) and not missing,
              "claim_accounting": reconciled, "limitations": len(statements) >= minimum_limits,
              "distinct_source_documents": group_progress}
    score = sum(RULES[rule] for rule, passed in checks.items() if passed)
    required = valid_body and bool(verified) and not missing and reconciled
    return {"schema": "ace.institute.report-qa.v1", "rules": [{"id": key, "weight_bp": RULES[key], "pass": passed}
                                                              for key, passed in checks.items()],
            "verified_claims": verified, "missing_support": missing, "source_findings": defects,
            "claim_findings": defects_claims, "claim_status_counts": status_counts,
            "score_bp": score, "minimum_bp": min_score, "status": "passes_rubric" if required and score >= min_score else "hold"}


def quality(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.institute.qa-plan.v1", ("report", "minimum_bp", "minimum_unique_documents", "minimum_limitations"))
    link = obj(plan["report"], ("path", "sha256"))
    raw = source_bytes(root, link["path"], link["sha256"], 3_000_000)
    minimum = integer(plan["minimum_bp"], "Ambang rubrik", 0, 10000)
    docs = integer(plan["minimum_unique_documents"], "Dokumen unik minimum", 1, 100)
    limitations = integer(plan["minimum_limitations"], "Batasan minimum", 0, 30)
    return {**audit_report(decode(raw), min_score=minimum, min_sources=docs, minimum_limits=limitations, root=root),
            "plan_sha256": expected, "report": link}


if __name__ == "__main__":
    raise SystemExit(cli(quality, __doc__, rooted=True))
