"""Buat DOCX/PDF dari templat terikat hash dan lampirkan asal seluruh binding."""
import argparse
from pathlib import Path
import sys

from ._artifacts import evidence
from ._contracts import ProductionError, anchor, canonical, decode, items, read, schema
from ._docmodel import prepare_document
from ._docx import build_docx
from ._pdf import build_pdf


def make_document(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.production.document-plan.v1", ("title", "bindings", "blocks", "formats"))
    formats = items(plan["formats"], 2, 1)
    if any(tag not in ("docx", "pdf") for tag in formats) or len(set(formats)) != len(formats):
        raise ProductionError("Format dibuat sekali dari docx atau pdf.")
    title, blocks, origins = prepare_document(plan)
    output = {}
    page_count = None
    if "docx" in formats:
        output["document.docx"] = build_docx(title, blocks)
    if "pdf" in formats:
        output["document.pdf"], page_count = build_pdf(title, blocks)
    return output, {"schema": "ace.production.document-receipt.v1", "plan_sha256": expected,
                    "title": title, "output": evidence(output), "binding_sources": origins,
                    "blocks": len(blocks), "headings": [item["body"] for item in blocks if item["kind"] == "heading"],
                    "tables": sum(item["kind"] == "table" for item in blocks), "pdf_pages": page_count}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        artifacts, report = make_document(decode(read(args.plan)), args.expect_sha256)
        args.output.mkdir()
        for name, data in artifacts.items():
            (args.output / name).write_bytes(data)
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, KeyError, TypeError, ArithmeticError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
