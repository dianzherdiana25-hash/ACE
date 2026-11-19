#!/usr/bin/env python3
"""Cocokkan klaim angka direktur dengan field JSON pada snapshot Git lokal."""
from __future__ import annotations

import argparse
from decimal import Decimal
from pathlib import Path
import re

if __package__:
    from ._director_sources import GitSnapshot, SourceError, parse_json, repo_path, write_json
else:
    from _director_sources import GitSnapshot, SourceError, parse_json, repo_path, write_json


class PointerMissing(LookupError):
    pass


def _at_pointer(document, pointer):
    if not isinstance(pointer, str) or (pointer and not pointer.startswith("/")):
        raise SourceError("Pointer harus berupa JSON Pointer.")
    parts = pointer.split("/")[1:]
    if any(re.search(r"~(?![01])", part) for part in parts):
        raise SourceError("Escape JSON Pointer tidak sah.")
    for encoded in parts:
        part = encoded.replace("~1", "/").replace("~0", "~")
        if isinstance(document, dict) and part in document:
            document = document[part]
            continue
        if isinstance(document, list) and re.fullmatch(r"0|[1-9][0-9]*", part):
            if len(part) <= len(str(len(document))) and int(part) < len(document):
                document = document[int(part)]
                continue
        raise PointerMissing
    return document


def _claims(text, json_product):
    if json_product:
        document = parse_json(text)
        if not isinstance(document, dict) or not isinstance(document.get("numeric_claims"), list):
            raise SourceError("Produk JSON perlu daftar numeric_claims.")
        for index, claim in enumerate(document["numeric_claims"]):
            yield f"/numeric_claims/{index}", claim
        return
    for index, line in enumerate(text.splitlines(), 1):
        match = re.fullmatch(r"\s*[-*]\s+claim:\s*(\{.*\})\s*", line)
        if match:
            yield f"L{index}", parse_json(match[1])


def _numeric(value):
    return type(value) is int or isinstance(value, Decimal) and value.is_finite()


def verify_values(repo, product_path):
    claims = _claims(repo.read_text(product_path), Path(product_path).suffix == ".json")
    rows = []
    sources = {}
    for location, claim in claims:
        if (not isinstance(claim, dict) or not isinstance(claim.get("label"), str)
                or not claim["label"].strip() or not _numeric(claim.get("value"))):
            raise SourceError(f"Klaim angka pada {location} harus memuat label dan angka berhingga.")
        path = repo_path(claim.get("source"))
        pointer = claim.get("pointer")
        row = {"location": location, "label": claim["label"], "claimed": str(claim["value"]),
               "source": path, "pointer": pointer}
        if path not in sources:
            try:
                sources[path] = repo.read_json(path), None
            except SourceError:
                reason = "source_not_found" if path not in repo.entries else "source_unreadable"
                sources[path] = None, reason
        data, reason = sources[path]
        try:
            observed = _at_pointer(data, pointer)
        except PointerMissing:
            observed = None
            reason = reason or "field_not_found"
        if reason:
            status = "not_found" if reason in {"source_not_found", "field_not_found"} else "ambiguous"
        elif not _numeric(observed):
            status, reason = "ambiguous", "source_not_numeric"
        elif observed == claim["value"]:
            status, reason = "verified", "exact_numeric_match"
        else:
            status, reason = "mismatch", "numeric_value_differs"
        rows.append({**row, "status": status, "reason": reason,
                     "observed": str(observed) if _numeric(observed) else None})
    return {"schema": "ace.director.value-check.v1", "commit": repo.commit,
            "product": product_path, "claims": rows}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("product", help="Path produk Markdown atau JSON dalam commit.")
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--revision", default="HEAD")
    args = parser.parse_args(argv)
    try:
        result = verify_values(GitSnapshot(args.repo, args.revision), args.product)
    except SourceError as exc:
        parser.exit(2, f"Error. {exc}\n")
    write_json(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
