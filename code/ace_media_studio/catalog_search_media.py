"""Cari isi karya studio pada transkrip lokal dan cantumkan posisi sumber tiap hasil."""
import argparse
from collections import Counter
from hashlib import sha256
from math import log1p
from pathlib import Path
import re
import sys
import unicodedata

from ._assets import asset
from ._contracts import (ContractError, canonical, checked, decode, entries,
                         identifier, integer, obj, read, schema, text)


WORD = re.compile(r"[^\W_]+", re.UNICODE)


def _tokens(raw):
    return WORD.findall(unicodedata.normalize("NFKC", raw).casefold())


def build_index(plan, expected, root):
    checked(plan, expected)
    schema(plan, "ace.media.catalog-plan.v1", ("works",))
    documents = []
    seen = set()
    total = 0
    for row in entries(plan["works"], 220, 1):
        obj(row, ("id", "title", "path", "sha256", "source_ref", "series", "season"))
        key = identifier(row["id"], "Karya")
        if key in seen:
            raise ContractError("Karya duplikat.")
        seen.add(key)
        title = text(row["title"], "Judul karya")
        source = text(row["source_ref"], "Pointer karya")
        contents = asset(root, row["path"], row["sha256"], 200_000)
        total += len(contents)
        if total > 4_000_000:
            raise ContractError("Jumlah teks katalog melebihi batas.")
        lines = [line.strip() for line in contents.decode("utf-8").splitlines()]
        catalog = {}
        for index, line in enumerate(lines, 1):
            if not line:
                continue
            if len(line) > 1500 or not line.isprintable():
                raise ContractError("Baris transkrip tidak sah atau terlalu panjang.")
            catalog[index] = line
        tokens = [token for line in catalog.values() for token in _tokens(line)]
        if not tokens:
            raise ContractError(f"Karya {key} tidak memiliki isi untuk indeks.")
        documents.append({"id": key, "title": title, "source_ref": source,
                          "sha256": sha256(contents).hexdigest(), "series": identifier(row["series"], "Seri"),
                          "season": integer(row["season"], "Musim", 1, 999),
                          "lines": catalog, "terms": Counter(tokens), "length": len(tokens)})
    return sorted(documents, key=lambda row: row["id"])


def search(plan, expected, root, query, limit=10, series=None):
    terms = sorted(set(_tokens(text(query, "Query", 200))))
    cap = integer(limit, "Jumlah hasil", 1, 50)
    if not terms:
        raise ContractError("Query tidak memiliki token.")
    if series is not None:
        identifier(series, "Filter seri")
    indexed = [item for item in build_index(plan, expected, root) if series is None or series == item["series"]]
    found = []
    size = len(indexed)
    average = sum(row["length"] for row in indexed) / max(1, size)
    frequencies = {term: sum(term in item["terms"] for item in indexed) for term in terms}
    for item in indexed:
        present = {term for term in terms if term in item["terms"]}
        if not present:
            continue
        factor = 1.2 * (0.25 + 0.75 * item["length"] / average)
        score = 0
        for term in sorted(present):
            frequency = item["terms"][term]
            covered = frequencies[term]
            score += log1p((size - covered + 0.5) / (covered + 0.5)) * 2.2 * frequency / (frequency + factor)
        hits = [(len(set(_tokens(line)) & present), number, line)
                for number, line in item["lines"].items()]
        chosen = sorted((hit for hit in hits if hit[0]), key=lambda entry: (-entry[0], entry[1]))[:3]
        found.append({key: item[key] for key in ("id", "title", "source_ref", "sha256", "series", "season")} |
                     {"score_micros": round(score * 1_000_000), "matched_terms": sorted(present),
                      "excerpts": [{"line": number, "text": excerpt} for _, number, excerpt in chosen]})
    order = sorted(found, key=lambda item: (-item["score_micros"], item["id"]))
    return {"schema": "ace.media.catalog-search.v1", "plan_sha256": expected,
            "method": "local_bm25", "query_terms": terms, "indexed_works": size, "matched_works": len(found),
            "results": order[:cap]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("asset_root", type=Path)
    parser.add_argument("query")
    parser.add_argument("--series")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        reports = search(decode(read(args.plan)), args.expect_sha256, args.asset_root,
                         args.query, args.limit, args.series)
        sys.stdout.buffer.write(canonical(reports) + b"\n")
    except (OSError, ValueError, TypeError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
