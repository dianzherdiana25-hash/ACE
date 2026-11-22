"""Gambar kemajuan per topik dari checkpoint belajar, dengan gap tanpa interpolasi palsu."""
import argparse
from pathlib import Path
import sys

from ._artifacts import evidence
from ._contracts import (ProductionError, anchor, canonical, day, decode, identifier,
                         identity, integer, items, obj, read, schema, source_bytes, text)
from .chart_builder import make_chart


def visualize(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.teaching.progress-plan.v1", ("readings", "topics", "chart_width"))
    fields = [identifier(value, "Topik") for value in items(plan["topics"], 25, 1)]
    if len(set(fields)) != len(fields):
        raise ProductionError("Topik visualisasi duplikat.")
    width = integer(plan["chart_width"], "Lebar grafik", 450, 1600)
    source = obj(plan["readings"], ("path", "sha256"))
    data = decode(source_bytes(root, source["path"], source["sha256"], 500000))
    schema(data, "ace.teaching.progress-readings.v1", ("checkpoints",))
    seen = set()
    by_topic = {key: [] for key in fields}
    for row in items(data["checkpoints"], 200, 1):
        obj(row, ("topic", "date", "score_bp", "source_ref"))
        topic = identifier(row["topic"], "Topik masukan")
        observed = day(row["date"])
        if (topic, observed) in seen:
            raise ProductionError("Topik dan tanggal checkpoint ganda.")
        seen.add((topic, observed))
        if topic in by_topic:
            score = None if row["score_bp"] is None else integer(row["score_bp"], "Skor kemajuan", 0, 10000)
            by_topic[topic].append((observed, score, text(row["source_ref"], "Pointer checkpoint")))
    assets = {}
    results = []
    for topic, rows in by_topic.items():
        rows.sort()
        intervals = []
        current = []
        skipped = []
        for stamp, score, ref in rows:
            if score is None:
                if current:
                    intervals.append(current)
                    current = []
                skipped.append({"date": stamp.isoformat(), "source_ref": ref})
            else:
                current.append((stamp, score, ref))
        if current:
            intervals.append(current)
        charts = []
        for number, run in enumerate(intervals, 1):
            if len(run) not in range(2, 13):
                charts.append({"first": run[0][0].isoformat(), "last": run[-1][0].isoformat(), "status": "invalid_run_size",
                               "points": len(run)})
                continue
            points = [{"label": stamp.isoformat(), "value": score, "source_ref": ref} for stamp, score, ref in run]
            chosen = {"schema": "ace.production.chart-plan.v1", "title": topic.replace("_", " ").title(), "kind": "line",
                      "width": max(width, 110 + 76 * len(points)), "height": 340, "y_label": "Skor basis point", "points": points,
                      "y_axis": {"min": "0", "max": "10000"}}
            raw, proof = make_chart(chosen, identity(chosen))
            name = f"{topic}_{number}.svg"
            assets[name] = raw
            charts.append({"status": "rendered", "file": name, "points": proof["points"]})
        results.append({"topic": topic, "missing_checkpoints": skipped, "charts": charts,
                        "finite_checkpoints": sum(score is not None for _, score, _ in rows)})
    return assets, {"schema": "ace.teaching.progress-visualization.v1", "plan_sha256": expected,
                    "basis": "ordinal_checkpoint_spacing", "topics": results, "source": source, "artifacts": evidence(assets)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        files, report = visualize(decode(read(args.plan)), args.expect_sha256, args.root)
        args.output.mkdir()
        for name, data in files.items():
            (args.output / name).write_bytes(data)
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, KeyError, TypeError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
