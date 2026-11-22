"""Rakit kontrak draf dari klausul berizin dan utuh, tanpa tanda tangan atau pengiriman."""
import argparse
from pathlib import Path
import sys

from ._contracts import (ProductionError, anchor, canonical, decode, identifier,
                         identity, items, obj, read, schema, source_bytes, text)
from .document_builder import make_document


def draft_contract(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.production.contract-plan.v1", ("title", "required_topics", "clauses", "bindings", "formats"))
    title = text(plan["title"], "Judul draf", 150)
    required = {identifier(label, "Topik wajib") for label in items(plan["required_topics"], 60, 1)}
    seen = set()
    sources = []
    covered = set()
    body = [{"kind": "paragraph", "body": "Draf untuk telaah."}]
    for row in items(plan["clauses"], 65, 1):
        obj(row, ("id", "topic", "heading", "path", "sha256", "approval_ref"))
        key = identifier(row["id"], "Klausul")
        topic = identifier(row["topic"], "Topik klausul")
        if key in seen:
            raise ProductionError("Klausul ganda.")
        seen.add(key)
        covered.add(topic)
        pointer = text(row["approval_ref"], "Pointer persetujuan klausul")
        raw = source_bytes(root, row["path"], row["sha256"], 18000)
        clause = raw.decode("utf-8").splitlines()
        lines = [text(line.strip(), "Paragraf klausul", 1400) for line in clause if line.strip()]
        if not lines or len(lines) > 8:
            raise ProductionError("Klausul perlu satu sampai delapan paragraf.")
        body.append({"kind": "heading", "level": 1, "body": text(row["heading"], "Heading klausul", 90)})
        body.extend({"kind": "paragraph", "body": line} for line in lines)
        sources.append({"id": key, "topic": topic, "path": row["path"], "clause_sha256": row["sha256"], "approval_ref": pointer})
    if not required <= covered:
        raise ProductionError("Topik wajib belum dicakup oleh klausul.")
    layout = {"schema": "ace.production.document-plan.v1", "title": title, "formats": plan["formats"],
              "bindings": plan["bindings"], "blocks": body}
    outputs, document = make_document(layout, identity(layout))
    return outputs, {"schema": "ace.production.contract-draft.v1", "plan_sha256": expected, "state": "draft_unsigned",
                     "required_topics": sorted(required), "clauses": sources, "document": document}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        files, report = draft_contract(decode(read(args.plan)), args.expect_sha256, args.root)
        args.output.mkdir()
        for key, raw in files.items():
            (args.output / key).write_bytes(raw)
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, KeyError, TypeError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
