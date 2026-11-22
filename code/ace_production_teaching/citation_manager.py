"""Satukan nomor sitasi lintas dokumen dengan sumber unik dan lintasan yang dapat diaudit."""
from collections import defaultdict
import re

from ._contracts import ProductionError, anchor, cli, digest, identifier, integer, items, obj, schema, source_bytes, text


CITATION = re.compile(r"\[@([a-z][a-z0-9_]{0,63})\]")
INLINE = re.compile(r"`[^`]*`")


def registry(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.production.citation-plan.v1", ("sources", "documents"))
    measured = {}
    by_digest = {}
    held = []
    for record in items(plan["sources"], 300):
        obj(record, ("id", "title", "reference", "evidence"))
        name = identifier(record["id"], "Sitasi")
        if name in measured:
            raise ProductionError("ID sumber sitasi ganda.")
        title = text(record["title"], "Judul sumber", 220)
        link = obj(record["evidence"], ("path", "line", "sha256"))
        body = source_bytes(root, link["path"], link["sha256"], 500000).decode("utf-8").splitlines()
        line = integer(link["line"], "Baris sumber", 1, len(body))
        key = (digest(link["sha256"]), line)
        current = {"id": name, "title": title, "reference": text(record["reference"], "Locator sitasi", 320),
                   "evidence": link, "aliases": [], "line_present": bool(body[line - 1].strip())}
        if key in by_digest:
            canonical = by_digest[key]
            if current["title"] != canonical["title"]:
                held.append({"id": name, "other": canonical["id"], "reason": "same_line_inconsistent_title"})
            canonical["aliases"].append(name)
        else:
            canonical = current
            by_digest[key] = canonical
        measured[name] = canonical
    citations = defaultdict(list)
    entries = {}
    unknown = []
    for doc in items(plan["documents"], 70, 1):
        obj(doc, ("id", "path", "sha256"))
        key = identifier(doc["id"], "Dokumen")
        if key in entries:
            raise ProductionError("ID dokumen sitasi ganda.")
        entries[key] = doc
        lines = source_bytes(root, doc["path"], doc["sha256"], 350000).decode("utf-8").splitlines()
        fence = None
        for number, content in enumerate(lines, 1):
            marker = content.strip()[:3]
            if marker in ("```", "~~~"):
                fence = marker if fence is None else (None if fence == marker else fence)
                continue
            if fence:
                continue
            clean = INLINE.sub(lambda found: " " * len(found[0]), content)
            for match in CITATION.finditer(clean):
                cited = measured.get(match[1])
                pointer = {"document": key, "path": doc["path"], "sha256": doc["sha256"], "source_line": number,
                           "column": match.start() + 1, "cited_id": match[1]}
                if cited is None or not cited["line_present"]:
                    unknown.append(pointer)
                else:
                    citations[cited["id"]].append(pointer)
    sources = []
    for idx, (label, points) in enumerate(citations.items(), 1):
        current = measured[label]
        sources.append({"number": idx, "canonical": label, "title": current["title"], "aliases": sorted(current["aliases"]),
                        "reference": current["reference"], "evidence": current["evidence"], "used_in": points})
    return {"schema": "ace.production.citation-register.v1", "plan_sha256": expected,
            "rule": "first_appearance_by_document_order", "bibliography": sources,
            "unresolved": unknown, "alias_conflicts": held, "unused_ids": sorted(measured.keys() - {ref["cited_id"]
                     for cites in citations.values() for ref in cites})}


if __name__ == "__main__":
    raise SystemExit(cli(registry, __doc__, rooted=True))
