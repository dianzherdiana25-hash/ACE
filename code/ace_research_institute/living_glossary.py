"""Bangun glosarium topik yang menyimpan riwayat definisi dan konflik pada tanggal sama."""
from collections import defaultdict
import re

from ._contracts import ResearchError, anchor, cli, day, identifier, items, obj, schema, source_bytes, text


HEADER = re.compile(r"^\*\*([a-z][a-z0-9_]{0,63})\*\*\s+—\s+(.+)$")


def glossary(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.institute.glossary-plan.v1", ("topic", "as_of", "documents", "aliases"))
    topic = identifier(plan["topic"], "Topik glosarium")
    now = day(plan["as_of"])
    by_term = defaultdict(list)
    known = set()
    for row in items(plan["documents"], 100, 1):
        obj(row, ("id", "path", "sha256", "date"))
        key = identifier(row["id"], "Dokumen glosarium")
        date = day(row["date"])
        if key in known or date > now:
            raise ResearchError("Dokumen ganda atau tanggal melebihi as-of.")
        known.add(key)
        raw = source_bytes(root, row["path"], row["sha256"], 200000)
        seen_here = set()
        for line, value in enumerate(raw.decode("utf-8").splitlines(), 1):
            match = HEADER.fullmatch(value.strip())
            if match is None:
                continue
            term, description = match.groups()
            if term in seen_here:
                raise ResearchError("Definisi berulang dalam dokumen yang sama.")
            seen_here.add(term)
            by_term[term].append({"definition": text(description, "Definisi", 650), "date": row["date"],
                                 "source": {"id": key, "path": row["path"], "line": line, "sha256": row["sha256"]}})
    aliases = defaultdict(set)
    references = {}
    for row in items(plan["aliases"], 150):
        obj(row, ("alias", "term", "source_ref"))
        key = identifier(row["alias"], "Alias")
        preferred = identifier(row["term"], "Istilah")
        if preferred not in by_term or key in by_term:
            raise ResearchError("Alias menunjuk istilah belum ada atau bertabrakan dengan istilah kanonis.")
        pointer = text(row["source_ref"], "Pointer alias")
        if (key, preferred) in references:
            raise ResearchError("Alias dan istilah ganda.")
        aliases[key].add(preferred)
        references[(key, preferred)] = pointer
    entries = []
    for term, records in sorted(by_term.items()):
        records.sort(key=lambda row: (row["date"], row["source"]["id"]))
        newest = records[-1]["date"]
        latest = [record for record in records if record["date"] == newest]
        variants = {row["definition"] for row in latest}
        entries.append({"term": term, "current_value": next(iter(variants)) if len(variants) == 1 else None,
                        "status": "current" if len(variants) == 1 else "ambiguous_latest_definitions",
                        "definitions": records})
    return {"schema": "ace.institute.living-glossary.v1", "plan_sha256": expected, "topic": topic, "as_of": plan["as_of"],
            "entries": entries, "aliases": [{"alias": alias, "status": "unique" if len(terms) == 1 else "ambiguous",
                           "matches": [{"term": term, "source_ref": references[alias, term]} for term in sorted(terms)]}
                          for alias, terms in sorted(aliases.items())]}


if __name__ == "__main__":
    raise SystemExit(cli(glossary, __doc__, rooted=True))
