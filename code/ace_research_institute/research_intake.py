"""Normalisasi draf permintaan riset dan sebutkan prasyarat yang belum tersedia."""
from ._contracts import ResearchError, anchor, cli, day, identifier, integer, items, obj, schema, source_bytes, text


def intake(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.institute.intake-plan.v1", ("as_of", "requests"))
    as_of = day(plan["as_of"])
    used = set()
    ready = []
    pending = []
    for row in items(plan["requests"], 180, 1):
        obj(row, ("id", "question", "outcome", "purpose", "submitted", "requested_due", "effort_hours",
                  "impact", "approved_scope", "evidence"))
        key = identifier(row["id"], "Permintaan")
        if key in used or type(row["approved_scope"]) is not bool:
            raise ResearchError("ID permintaan ganda atau penanda cakupan tidak sah.")
        used.add(key)
        queued = day(row["submitted"])
        due = day(row["requested_due"])
        if queued > as_of or due < queued:
            raise ResearchError("Tanggal intake atau tenggat tidak konsisten.")
        hours = integer(row["effort_hours"], "Jam estimasi", 1, 600)
        influence = integer(row["impact"], "Dampak deklaratif", 0, 100)
        gaps = []
        if not row["approved_scope"]:
            gaps.append("scope_unapproved")
        if row["outcome"] is None:
            gaps.append("outcome_missing")
            outcome = None
        else:
            outcome = text(row["outcome"], "Artefak yang diharapkan")
        references = []
        work = 0
        for evidence in items(row["evidence"], 20):
            obj(evidence, ("path", "sha256", "label"))
            title = text(evidence["label"], "Label bukti intake", 120)
            data = source_bytes(root, evidence["path"], evidence["sha256"], 200000)
            work += len(data)
            if work > 1_000_000:
                raise ResearchError("Lampiran bukti intake melampaui batas.")
            if data:
                references.append({**evidence, "label": title})
        if not references:
            gaps.append("no_evidence_input")
        recorded = {"id": key, "question": text(row["question"], "Pertanyaan riset"), "expected_outcome": outcome,
                    "purpose": text(row["purpose"], "Tujuan"), "submitted": row["submitted"],
                    "requested_due": row["requested_due"], "days_until_due": (due - as_of).days,
                    "queue_age_days": (as_of - queued).days, "effort_hours": hours,
                    "declared_impact": influence, "evidence": references}
        if gaps:
            pending.append({**recorded, "needs": gaps})
        else:
            ready.append(recorded)
    return {"schema": "ace.institute.intake-result.v1", "plan_sha256": expected, "as_of": plan["as_of"],
            "state": "local_draft", "eligible": sorted(ready, key=lambda row: row["id"]),
            "held": sorted(pending, key=lambda row: row["id"])}


if __name__ == "__main__":
    raise SystemExit(cli(intake, __doc__, rooted=True))
