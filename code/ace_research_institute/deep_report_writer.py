"""Susun laporan riset dari klaim yang diperiksa dan tampilkan setiap celah bukti."""
from hashlib import sha256

from ._contracts import (ResearchError, anchor, cli, identifier, identity, integer,
                         items, obj, schema, text)
from .claim_checker import check_claims


def _safe_markdown(raw):
    return raw.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("`", "'")


def _cite(checked, results):
    evidence = []
    for item in checked["measurements"]:
        ref = item["source"]
        key = (item["source_id"], ref["line"], ref["sha256"])
        if key not in results:
            results[key] = {"id": f"e{len(results) + 1}", "source_id": item["source_id"],
                            "path": ref["path"], "line": ref["line"], "sha256": ref["sha256"]}
        evidence.append({**results[key], "value": item["estimate"], "outcome": item["classification"]})
    return evidence


def make_report(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.institute.report-plan.v1", ("title", "question", "checks", "sections", "limitations"))
    title = text(plan["title"], "Judul laporan", 180)
    question = text(plan["question"], "Pertanyaan laporan")
    limits = [text(item, "Batasan") for item in items(plan["limitations"], 30, 1)]
    checked = check_claims(plan["checks"], identity(plan["checks"]), root)
    matrix = {claim["id"]: claim for claim in checked["claims"]}
    bibliography = {}
    ordered = []
    used = set()
    section_ids = set()
    lines = [f"# {_safe_markdown(title)}", "", _safe_markdown(question), ""]
    for section in items(plan["sections"], 30, 1):
        obj(section, ("id", "title", "claims", "importance"))
        key = identifier(section["id"], "Bagian")
        if key in section_ids:
            raise ResearchError("Bagian laporan ganda.")
        section_ids.add(key)
        title_section = text(section["title"], "Judul bagian")
        priority = integer(section["importance"], "Kepentingan bagian", 0, 100)
        lines.extend([f"## {_safe_markdown(title_section)}", ""])
        reports = []
        for candidate in items(section["claims"], 80, 1):
            claim = identifier(candidate, "Klaim bagian")
            if claim in used or claim not in matrix:
                raise ResearchError("Klaim ganda atau belum diperiksa.")
            used.add(claim)
            observed = matrix[claim]
            sources = _cite(observed, bibliography)
            verified = observed["status"] == "supported"
            line = {"id": claim, "source_ref": observed["source_ref"], "status": observed["status"], "sources": sources,
                    "dimensions": observed["dimensions"],
                    "candidate_text": observed["claim"] if verified else None,
                    "amount": {"value": observed["value"], "unit": observed["unit"]} if verified else None}
            reports.append(line)
            pointers = " ".join(f"[{row['id']}]" for row in sources)
            dimension = observed["dimensions"]
            description = (f"Nilai {dimension['outcome']} pada {dimension['population']} di {dimension['context']} "
                           f"didukung untuk {observed['value']} {observed['unit']}.") if verified else (
                f"Klaim {claim} memerlukan telaah tambahan ({observed['status']}).")
            lines.append(f"- {_safe_markdown(description)} {pointers}".rstrip())
        ordered.append({"id": key, "title": title_section, "importance": priority, "claims": reports})
        lines.append("")
    if used != matrix.keys():
        raise ResearchError("Ada klaim yang diperiksa dan belum ditempatkan pada bagian laporan.")
    lines.extend(["## Batasan", "", *["- " + _safe_markdown(value) for value in limits], "", "## Sumber", ""])
    lines.extend(f"- [{ref['id']}] `{ref['path']}:{ref['line']}` · SHA-256 `{ref['sha256']}`"
                 for ref in bibliography.values())
    markdown = "\n".join(lines) + "\n"
    return {"schema": "ace.institute.deep-report.v1", "plan_sha256": expected, "claim_check_sha256": identity(checked),
            "title": title, "question": question, "sections": ordered, "limitations": limits,
            "summary": checked["summary"], "sources": list(bibliography.values()),
            "markdown_sha256": sha256(markdown.encode()).hexdigest(), "markdown": markdown}


if __name__ == "__main__":
    raise SystemExit(cli(make_report, __doc__, rooted=True))
