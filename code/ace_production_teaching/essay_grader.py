"""Nilai lapisan esai pada struktur, sitasi, dan bukti isi yang ditentukan rubrik."""
import re

from ._contracts import ProductionError, anchor, cli, identifier, identity, integer, items, obj, schema, source_bytes, text
from .grader import assess


CITE = re.compile(r"\[@([a-z][a-z0-9_]{0,63})\]")
HEADING = re.compile(r"^## ([a-z][a-z0-9_]{0,63})\s*$")


def grade_essay(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.teaching.essay-plan.v1", ("essay", "id", "rubric", "section_order", "sources", "passing_bp"))
    case = identifier(plan["id"], "Esai")
    source = obj(plan["essay"], ("path", "sha256"))
    doc = source_bytes(root, source["path"], source["sha256"], 190000).decode("utf-8")
    required = [identifier(value, "Bagian wajib") for value in items(plan["section_order"], 20, 1)]
    if len(set(required)) != len(required):
        raise ProductionError("Urutan lapisan esai ganda.")
    keys = {identifier(item, "Kunci sitasi") for item in items(plan["sources"], 70)}
    headings = []
    cited = {}
    parts = []
    for line, body in enumerate(doc.splitlines(), 1):
        clean = body.strip()
        if not clean:
            continue
        if (heading := HEADING.fullmatch(clean)) is not None:
            headings.append({"id": heading[1], "line": line})
            continue
        for marker in CITE.finditer(clean):
            cited.setdefault(marker[1], []).append(line)
        parts.append(CITE.sub("", clean))
    body = " ".join(parts)
    rubric = {"schema": "ace.teaching.open-grade-plan.v1", "exercise": case,
              "passing_bp": 1, "response": {"text": text(body, "Isi esai", 5000), "source_ref": source["path"]},
              "criteria": plan["rubric"]}
    content = assess(rubric, identity(rubric))
    by_section = [row["id"] for row in headings]
    coverage = int(by_section == required)
    unresolved = sorted(cited.keys() - keys)
    realized = sorted(cited.keys() & keys)
    citations = int(bool(realized) and not unresolved)
    score = 7 * content["score_bp"] // 10 + coverage * 1800 + citations * 1200
    needed = integer(plan["passing_bp"], "Ambang esai", 1, 10000)
    return {"schema": "ace.teaching.essay-grade.v1", "plan_sha256": expected, "essay": source, "score_bp": score,
            "structure": {"expected": required, "observed": headings, "earned_bp": coverage * 1800},
            "citations": {"used": {key: cited[key] for key in realized}, "unresolved": unresolved, "earned_bp": citations * 1200},
            "content": content, "status": "passes_rubric" if score >= needed else "revise"}


if __name__ == "__main__":
    raise SystemExit(cli(grade_essay, __doc__, rooted=True))
