"""Susun sanggahan dengan pengukuran berlawanan, inklusi dukungan dan batas cakupan."""
from collections import defaultdict
from decimal import Decimal

from ._contracts import ResearchError, anchor, cli, identifier, identity, integer, schema, text
from .claim_checker import check_claims


def rebut(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.institute.rebuttal-plan.v1", ("checks", "target", "minimum_conflicting_groups", "max_cites", "limitation"))
    target = identifier(plan["target"], "Klaim yang ditelaah")
    required = integer(plan["minimum_conflicting_groups"], "Grup kontra minimum", 1, 30)
    limit = integer(plan["max_cites"], "Batas sitasi", required, 50)
    caveat = text(plan["limitation"], "Batas telaah")
    checks = check_claims(plan["checks"], identity(plan["checks"]), root)
    claim = next((row for row in checks["claims"] if row["id"] == target), None)
    if claim is None:
        raise ResearchError("Klaim target belum diperiksa.")
    ranked = defaultdict(dict)
    for row in claim["measurements"]:
        kind = row["classification"]
        group = row["independence_group"]
        rank = (-row["sample_size"], Decimal(row["difference"]) if kind == "supports" else -Decimal(row["difference"]),
                row["source"]["path"], row["source"]["line"])
        prior = ranked[kind].get(group)
        if prior is None or rank < prior[0]:
            ranked[kind][group] = rank, row
    counter = [row for _, row in sorted(ranked["contradicts"].values())[:limit]]
    support = [row for _, row in sorted(ranked["supports"].values())[:limit]]
    ready = len(counter) >= required
    prefix = f"## Telaah klaim {target}\n\n"
    lines = [prefix.rstrip(), "", f"Cakupan numerik {claim['dimensions']['outcome']} pada "
             f"{claim['dimensions']['population']} di {claim['dimensions']['context']}.", ""]
    if ready:
        lines.append("Bukti berlawanan tersedia dari kelompok sumber yang berbeda.")
    else:
        lines.append("Bukti berlawanan belum memenuhi ambang kelompok sumber.")
    for title, entries_ in (("Temuan berlawanan", counter), ("Temuan pendukung", support)):
        lines.extend(["", f"### {title}", ""])
        for row in entries_:
            evidence = row["source"]
            lines.append(f"- {row['estimate']} {claim['unit']} pada `{evidence['path']}:{evidence['line']}`.")
    lines.extend(["", "### Batasan", "", caveat])
    return {"schema": "ace.institute.rebuttal.v1", "plan_sha256": expected, "target": target,
            "source_ref": claim["source_ref"], "qualifier": "numerical_scope_only",
            "check_sha256": identity(checks), "status": "counterevidence_found" if ready else "waiting_for_evidence",
            "contradicting": counter, "supporting": support, "excluded": claim["excluded"],
            "limitations": caveat, "markdown": "\n".join(lines) + "\n"}


if __name__ == "__main__":
    raise SystemExit(cli(rebut, __doc__, rooted=True))
