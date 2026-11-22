"""Susun tiga tingkat laporan dengan kedalaman berbeda dan rujukan yang sama."""
from ._contracts import anchor, cli, decode, identity, integer, items, obj, schema, source_bytes
from .executive_summarizer import summarize


def build_tiers(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.institute.tiers-plan.v1", ("report", "owner_points", "technical_points"))
    owner_limit = integer(plan["owner_points"], "Poin eksekutif", 1, 12)
    technical_limit = integer(plan["technical_points"], "Poin pengulas", owner_limit, 20)
    ref = obj(plan["report"], ("path", "sha256"))
    body = decode(source_bytes(root, ref["path"], ref["sha256"], 2_000_000))
    summary_plan = {"schema": "ace.institute.executive-summary-plan.v1", "report": ref, "max_points": technical_limit,
                    "max_held": 20}
    summary = summarize(summary_plan, identity(summary_plan), root)
    owner = summary["highlights"][:owner_limit]
    details = []
    for row in items(body["sections"], 30, 1):
        for result in items(row["claims"], 80, 1):
            details.append({"section": row["id"], "claim_id": result["id"], "status": result["status"],
                            "amount": result["amount"], "dimensions": result["dimensions"],
                            "source_ref": result["source_ref"], "evidence_refs": [item["id"] for item in result["sources"]]})
    picked = {row["claim_id"] for row in summary["highlights"]} | {row["claim_id"] for row in summary["named_gaps"]}
    return {"schema": "ace.institute.report-tiers.v1", "plan_sha256": expected, "report": ref,
            "reader_levels": {"owner": {"question": summary["question"], "highlights": owner,
                                        "named_gaps": summary["named_gaps"][:owner_limit], "limitations": summary["limitations"]},
                              "reviewer": {"items": [row for row in details if row["claim_id"] in picked],
                                           "references": body["sources"], "limitations": summary["limitations"]},
                              "technical": {"markdown": body["markdown"], "markdown_sha256": body["markdown_sha256"],
                                            "sections": body["sections"], "references": body["sources"]}}}


if __name__ == "__main__":
    raise SystemExit(cli(build_tiers, __doc__, rooted=True))
