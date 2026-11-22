"""Buat turunan CSV yang bersih dengan peta baris, transformasi, dan karantina."""
import argparse
import csv
from hashlib import sha256
from io import StringIO
from pathlib import Path
import sys

from ._contracts import (ResearchError, anchor, canonical, decode, identifier, items,
                         obj, read, schema, source_bytes)
from ._tabular import load, serialize


def clean(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.institute.clean-plan.v1", ("data", "format", "unique_by"))
    link = obj(plan["data"], ("path", "sha256"))
    raw = source_bytes(root, link["path"], link["sha256"], 3_000_000)
    table = load(raw, link["sha256"], plan["format"])
    dedup = [identifier(value, "Kunci dedup") for value in items(plan["unique_by"], 20)]
    if len(set(dedup)) != len(dedup) or any(key not in table.columns for key in dedup):
        raise ResearchError("Kunci dedup ganda atau tak terdaftar.")
    stream = StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(table.columns)
    seen = {}
    rejected = list(table.rejected)
    written = []
    for row in table.rows:
        values = row["cells"]
        if dedup:
            keys = tuple(values[field] for field in dedup)
            if None in keys:
                rejected.append({"line": row["line"], "end_line": row["end_line"],
                                 "issues": [{"column": None, "reason": "missing_dedup_key"}]})
                continue
            if keys in seen:
                rejected.append({"line": row["line"], "end_line": row["end_line"], "issues": [
                    {"column": None, "reason": "duplicate_key", "first_line": seen[keys]}]})
                continue
            seen[keys] = row["line"]
        alignment = [serialize(values[key], spec) for key, spec in table.columns.items()]
        writer.writerow(alignment)
        written.append({"from_line": row["line"], "through_line": row["end_line"],
                        "output_record": len(written) + 2, "changed_fields": row["normalized"]})
    result = stream.getvalue().encode("utf-8")
    return result, {"schema": "ace.institute.clean-receipt.v1", "plan_sha256": expected, "source": link,
                    "csv_sha256": sha256(result).hexdigest(), "records_written": len(written), "lineage": written,
                    "quarantine": sorted(rejected, key=lambda row: row["line"])}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        payload, report = clean(decode(read(args.plan)), args.expect_sha256, args.root)
        with args.output.open("xb") as stream:
            stream.write(payload)
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, KeyError, TypeError, ArithmeticError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
