"""Indeks sitasi antar-dokumen dengan canonical DOI/URL dan jejak kemunculan."""
from collections import defaultdict
import re
from urllib.parse import urlsplit, urlunsplit

from ._contracts import ResearchError, anchor, cli, identifier, items, obj, schema, source_bytes


LOCATOR = re.compile(r"https://[^\s<>()\]\x60]+|(?<![\w/])doi:\s*10\.[0-9]{4,9}/[^\s<>()\]\x60]+", re.I)
DOI = re.compile(r"10\.[0-9]{4,9}/[^\s]+", re.I)


def canonical_citation(raw):
    value = raw.rstrip(".,;:")
    if value.lower().startswith("doi:"):
        ref = value.partition(":")[2].strip().lower()
        return "doi:" + ref if DOI.fullmatch(ref) else None
    try:
        address = urlsplit(value)
        if address.scheme != "https" or not address.hostname or address.username or address.password:
            return None
        port = address.port
    except ValueError:
        return None
    netloc = address.hostname.lower()
    if netloc in ("doi.org", "dx.doi.org") and port in (None, 443):
        ref = address.path.lstrip("/").lower()
        return "doi:" + ref if DOI.fullmatch(ref) else None
    if ":" in netloc:
        netloc = "[" + netloc + "]"
    if port not in (None, 443):
        netloc += ":" + str(port)
    return urlunsplit(("https", netloc, address.path or "/", address.query, ""))


def build_index(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.institute.citation-index-plan.v1", ("documents",))
    registration = {}
    cited = defaultdict(list)
    problems = []
    work = 0
    for row in items(plan["documents"], 240, 1):
        obj(row, ("id", "path", "sha256"))
        key = identifier(row["id"], "Dokumen")
        if key in registration:
            raise ResearchError("ID dokumen ganda.")
        registration[key] = row
        data = source_bytes(root, row["path"], row["sha256"], 300000)
        work += len(data)
        if work > 6_000_000:
            raise ResearchError("Anggaran dokumen sitasi terlampaui.")
        for number, line in enumerate(data.decode("utf-8").splitlines(), 1):
            for match in LOCATOR.finditer(line):
                normalized = canonical_citation(match[0])
                origin = {"document": key, "path": row["path"], "line": number, "column": match.start() + 1,
                          "document_sha256": row["sha256"]}
                if normalized:
                    cited[normalized].append(origin)
                else:
                    problems.append(origin)
    result = []
    for ref, evidence in sorted(cited.items()):
        result.append({"canonical": ref, "distinct_documents": len({row["document"] for row in evidence}),
                       "occurrences": sorted(evidence, key=lambda row: (row["document"], row["line"], row["column"]))})
    return {"schema": "ace.institute.citation-index.v1", "plan_sha256": expected,
            "documents": len(registration), "citations": result, "malformed": problems}


if __name__ == "__main__":
    raise SystemExit(cli(build_index, __doc__, rooted=True))
