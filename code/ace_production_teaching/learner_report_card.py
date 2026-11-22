"""Buat rapor periode dari percobaan aktual, dengan status belum diukur tetap terlihat."""
import argparse
from pathlib import Path
import sys

from ._contracts import (ProductionError, anchor, canonical, day, decode, identity,
                         read, schema, text)
from .document_builder import make_document
from .learner_model import posterior


def report_card(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.teaching.report-card-plan.v1", ("profile", "start", "title", "formats"))
    report = posterior(plan["profile"], identity(plan["profile"]), root)
    first, last = day(plan["start"]), day(report["as_of"])
    if first > last:
        raise ProductionError("Awal periode rapor melewati tanggal profil.")
    title = text(plan["title"], "Judul rapor", 130)
    topics = []
    for name, row in report["topic_posteriors"].items():
        sources = [item for item in row["evidence"] if day(item["date"]) >= first]
        awarded = sum(item["earned"] for item in sources)
        available = sum(item["possible"] for item in sources)
        topics.append({"topic": name, "attempts": len(sources), "points": [awarded, available],
                       "period_score_bp": awarded * 10000 // available if available else None,
                       "source": report["attempts_ref"], "attempt_refs": [{"line": item["line"],
                                                                            "source_ref": item["source_ref"]} for item in sources]})
    template = {"schema": "ace.production.document-plan.v1", "title": title, "formats": plan["formats"], "bindings": [],
                "blocks": [{"kind": "paragraph", "body": f"Periode {plan['start']} sampai {report['as_of']}"},
                           {"kind": "table", "columns": ["Topik", "Percobaan", "Skor basis point"], "rows": [
                               [row["topic"], str(row["attempts"]), str(row["period_score_bp"]) if row["period_score_bp"] is not None else "Belum diukur"]
                               for row in topics]}]}
    outputs, receipt = make_document(template, identity(template))
    return outputs, {"schema": "ace.teaching.report-card.v1", "plan_sha256": expected, "scope": "local_period_report",
                     "learner": report["learner"], "range": [plan["start"], report["as_of"]],
                     "topics": topics, "document": receipt}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        files, report = report_card(decode(read(args.plan)), args.expect_sha256, args.root)
        args.output.mkdir()
        for key, data in files.items():
            (args.output / key).write_bytes(data)
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, TypeError, KeyError, ArithmeticError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
