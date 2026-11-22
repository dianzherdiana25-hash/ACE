"""Turunkan usulan riset dari kekurangan bukti yang terukur pada pemeriksaan klaim."""
from ._contracts import anchor, cli, identifier, identity, integer, schema, text
from .claim_checker import check_claims


PRIORITY = {"mixed_evidence": 3000, "insufficient_evidence": 1800, "contradicted": 1200}
STEPS = {
    "mixed_evidence": "Bandingkan protokol kedua kelompok dengan pengukuran konteks yang sama.",
    "insufficient_evidence": "Cari studi pada konteks yang sama dan tambah kelompok sumber independen.",
    "contradicted": "Periksa ulang klaim dan tetapkan bukti apa yang dapat mengubah kesimpulan.",
}


def propose_agenda(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.institute.agenda-plan.v1", ("checks", "origin", "limit", "source_ref"))
    origin = identifier(plan["origin"], "Brain-of-origin rencana")
    link = text(plan["source_ref"], "Pointer pemeriksaan")
    cap = integer(plan["limit"], "Jumlah usulan", 1, 100)
    check = check_claims(plan["checks"], identity(plan["checks"]), root)
    candidates = []
    for row in check["claims"]:
        status = row["status"]
        if status == "supported":
            continue
        independent = set(row["support_groups"]) | set(row["contradict_groups"])
        missing = max(0, row["minimum_groups"] - len(independent))
        citations = sorted({(item["source"]["path"], item["source"]["line"], item["source"]["sha256"])
                            for item in row["measurements"]})
        candidate = {"proposal_id": "check_" + row["id"],
                     "brain_of_origin": origin, "state": "draft", "based_on": [link, row["source_ref"]],
                     "claim_id": row["id"], "why": status, "proposal": STEPS[status],
                     "priority": PRIORITY[status] + min(30, missing) * 25,
                     "support_group_gap": missing, "dimensions": row["dimensions"],
                     "evidence": [{"path": path, "line": line, "sha256": digest} for path, line, digest in citations]}
        candidates.append(candidate)
    order = sorted(candidates, key=lambda row: (-row["priority"], row["claim_id"]))
    return {"schema": "ace.institute.agenda-draft.v1", "plan_sha256": expected, "check_sha256": identity(check),
            "candidates": order[:cap], "deferred_claims": [row["claim_id"] for row in order[cap:]]}


if __name__ == "__main__":
    raise SystemExit(cli(propose_agenda, __doc__, rooted=True))
