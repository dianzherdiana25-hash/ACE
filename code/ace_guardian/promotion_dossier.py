"""Rakit dossier dari bukti bernama yang diverifikasi ulang dan scorecard dengan referensi lengkap."""
from ._contracts import GuardianError, anchor, cli, digest, identifier, identity, items, obj, schema, source_bytes
from .promotion_gate import screen

def dossier(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.guardian.promotion-dossier.v1", ("bundle", "artifacts", "scorecard"))
    key = identifier(plan["bundle"], "Bundel promosi")
    sources = {}
    names = set()
    for row in items(plan["artifacts"], 200, 1):
        obj(row, ("id", "path", "sha256"))
        name = identifier(row["id"], "Bukti")
        sha = digest(row["sha256"])
        if name in names or sha in sources:
            raise GuardianError("Bukti dossier ganda atau identitas ambigu.")
        names.add(name)
        data = source_bytes(root, row["path"], sha)
        sources[sha] = {**row, "bytes": len(data)}
    result = screen(plan["scorecard"], identity(plan["scorecard"]))
    required = {ref for row in result["metrics"] for ref in row["refs"]}
    required.update(row["source"] for row in result["validations"])
    if missing := sorted(required - sources.keys()):
        return {"bundle": key, "recommendation": "hold", "missing_evidence": missing}
    report = {"bundle": key, "recommendation": result["recommendation"], "scorecard": result,
              "custody": sorted(sources.values(), key=lambda row: row["id"])}
    return {**report, "dossier_sha256": identity(report)}

if __name__ == "__main__":
    raise SystemExit(cli(dossier, __doc__, rooted=True))
