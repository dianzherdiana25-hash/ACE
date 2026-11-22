"""Urutkan calon kerja masa depan dari temuan audit bernilai dan bukti yang disebutkan."""
from ._contracts import GuardianError, anchor, cli, digest, identifier, identity, integer, items, obj, schema, text
from .decade_verdict_board import evolve_label

PRIORITY = {"blocked": 4, "failed": 3, "null": 2, "not_assessed": 1}

def propose(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.guardian.next-decade.v1", ("audit", "limit", "approved_sources"))
    limit = integer(plan["limit"], "Ukuran tranche", 1, 100)
    approved = {digest(item) for item in items(plan["approved_sources"], 500)}
    seen = set()
    drafts = []
    missing = []
    for row in items(plan["audit"], 200):
        obj(row, ("id", "evo", "state", "claim", "source", "effort", "verify"))
        key = identifier(row["id"], "Temuan")
        evo = evolve_label(row["evo"])
        source = digest(row["source"])
        cost = integer(row["effort"], "Bobot usaha", 1, 100)
        text(row["claim"], "Kesenjangan", 500)
        text(row["verify"], "Uji penerimaan", 500)
        if key in seen or row["state"] not in PRIORITY:
            raise GuardianError("Temuan ganda atau belum layak menjadi calon kerja.")
        seen.add(key)
        if source not in approved:
            missing.append(key)
            continue
        rank = PRIORITY[row["state"]]
        suggestion = {"audit_id": key, "evo": evo, "gap": row["claim"], "source": source,
                      "verification": row["verify"], "priority": rank, "effort": cost}
        drafts.append((-rank, cost, evo, key, suggestion))
    result = {"drafts": [row[-1] for row in sorted(drafts)[:limit]], "unanchored": sorted(missing),
              "unlisted": max(0, len(drafts) - limit), "scope": "human_review_only"}
    return {**result, "draft_sha256": identity(result)}

if __name__ == "__main__":
    raise SystemExit(cli(propose, __doc__))
