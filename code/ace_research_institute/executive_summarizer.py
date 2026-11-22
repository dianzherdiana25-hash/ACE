"""Saring laporan menjadi ringkasan eksekutif yang mempertahankan sumber dan batas bukti."""
from hashlib import sha256

from ._contracts import ResearchError, anchor, cli, decode, identifier, integer, items, obj, schema, source_bytes, text


def summarize(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.institute.executive-summary-plan.v1", ("report", "max_points", "max_held"))
    link = obj(plan["report"], ("path", "sha256"))
    raw = source_bytes(root, link["path"], link["sha256"], 2_000_000)
    report = decode(raw)
    schema(report, "ace.institute.deep-report.v1", ("plan_sha256", "claim_check_sha256", "title", "question",
            "sections", "limitations", "summary", "sources", "markdown_sha256", "markdown"))
    markdown = report["markdown"]
    if not isinstance(markdown, str) or sha256(markdown.encode()).hexdigest() != report["markdown_sha256"]:
        raise ResearchError("Markdown laporan tidak cocok dengan manifest.")
    max_points = integer(plan["max_points"], "Temuan maksimum", 1, 20)
    max_held = integer(plan["max_held"], "Celah maksimum", 0, 20)
    observed = []
    gaps = []
    registered = {row["id"]: row for row in items(report["sources"], 1000)}
    for sect in items(report["sections"], 30, 1):
        importance = integer(sect["importance"], "Kepentingan", 0, 100)
        for claim in items(sect["claims"], 80, 1):
            key = identifier(claim["id"], "Klaim")
            origin = text(claim["source_ref"], "Pointer klaim")
            if claim["status"] != "supported":
                gaps.append((-importance, key, {"claim_id": key, "source_ref": origin, "status": claim["status"]}))
                continue
            refs = []
            for source in items(claim["sources"], 250, 1):
                known = registered.get(source["id"])
                if known is None or any(known[field] != source[field] for field in ("path", "line", "sha256")):
                    raise ResearchError("Sitasi poin ringkas tidak cocok dengan daftar sumber.")
                if source["outcome"] == "supports":
                    refs.append(known)
            if not refs or claim["amount"] is None:
                raise ResearchError("Poin ringkas tidak memiliki angka atau bukti pendukung.")
            observed.append((-importance, -len({row["sha256"] for row in refs}), key,
                             {"claim_id": key, "source_ref": origin, "amount": claim["amount"], "evidence": refs}))
    highlights = [entry[-1] for entry in sorted(observed)[:max_points]]
    outstanding = [entry[-1] for entry in sorted(gaps)[:max_held]]
    return {"schema": "ace.institute.executive-summary.v1", "plan_sha256": expected, "report": link,
            "question": report["question"], "highlights": highlights, "named_gaps": outstanding,
            "verified_omitted": len(observed) - len(highlights), "gaps_omitted": len(gaps) - len(outstanding),
            "limitations": report["limitations"]}


if __name__ == "__main__":
    raise SystemExit(cli(summarize, __doc__, rooted=True))
