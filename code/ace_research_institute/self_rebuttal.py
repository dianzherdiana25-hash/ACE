"""Tantang klaim laporan sendiri menggunakan sumber baru yang di luar bukti asal."""
from decimal import Decimal

from ._contracts import ResearchError, anchor, cli, decode, digest, identifier, identity, items, obj, schema, source_bytes
from ._evidence import quantity
from .rebuttal_writer import rebut


def challenge(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.institute.self-rebuttal-plan.v1", ("prior_report", "counter_plan"))
    pointer = obj(plan["prior_report"], ("path", "sha256"))
    report = decode(source_bytes(root, pointer["path"], pointer["sha256"], 3_000_000))
    schema(report, "ace.institute.deep-report.v1", ("plan_sha256", "claim_check_sha256", "title", "question",
                                                    "sections", "limitations", "summary", "sources", "markdown_sha256", "markdown"))
    known = {digest(row["sha256"]) for row in items(report["sources"], 1000)}
    counter = plan["counter_plan"]
    identifier(counter["target"], "ID klaim yang ditantang")
    matching = [row for section in report["sections"] for row in section["claims"] if row["id"] == counter["target"]]
    if len(matching) != 1 or matching[0]["status"] != "supported":
        raise ResearchError("Tantangan diri harus menunjuk klaim didukung di laporan asal.")
    claim = matching[0]
    matching_candidates = [row for row in counter["checks"]["claims"] if row["id"] == claim["id"]]
    if len(matching_candidates) != 1:
        raise ResearchError("Pemeriksaan baru tidak mencakup klaim yang ditantang.")
    candidate = matching_candidates[0]
    unit, expected_value = quantity(candidate["value"], candidate["unit"])
    if candidate["dimensions"] != claim["dimensions"] or unit != claim["amount"]["unit"]:
        raise ResearchError("Tantangan harus memakai konteks dan satuan awal.")
    if expected_value != Decimal(claim["amount"]["value"]):
        raise ResearchError("Tantangan tidak boleh mengubah nilai klaim asal.")
    for row in counter["checks"]["source_plan"]["sources"]:
        if digest(row["sha256"]) in known:
            raise ResearchError("Sumber kontra mengulang hash bukti asal.")
    response = rebut(counter, identity(counter), root)
    return {"schema": "ace.institute.self-rebuttal.v1", "plan_sha256": expected,
            "original_report": pointer, "original_claim": claim["id"], "prior_claim_refs": claim["sources"],
            "source_reuse_excluded_by": "sha256", "counter_review": response}


if __name__ == "__main__":
    raise SystemExit(cli(challenge, __doc__, rooted=True))
