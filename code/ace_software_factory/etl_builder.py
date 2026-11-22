"""Bangun ETL lokal dengan pemetaan kolom yang dapat diperiksa ulang.

CSV berheader tepat dikonversi ke JSONL. Setiap transform memiliki
tipe, sumber, dan aturan nilai kosong sendiri. Record gagal dicatat
dengan indeks dan alasan tanpa menyalin isinya ke laporan.
"""
import argparse
from hashlib import sha256
import keyword
from pathlib import Path
import sys

from ._contracts import ContractError, canonical, checked, decode, entries, identifier, integer, obj, read, schema, text
from .repo_scaffolder import materialize


KINDS = {"text", "integer", "boolean", "date"}
RUNTIME = '''"""Jalur ETL CSV menuju JSONL yang dibatasi kontrak."""
import argparse
import csv
from datetime import date
from hashlib import sha256
import io
import json
import re
import sys


class Invalid(ValueError):
    pass


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def convert(value, field):
    value = value.strip() if field["trim"] else value
    if not value:
        if field["nullable"]:
            return None
        raise Invalid("required")
    if len(value) > field["max_chars"]:
        raise Invalid("too_long")
    kind = field["type"]
    if kind == "text":
        return value
    if kind == "integer":
        if not re.fullmatch(r"-?(0|[1-9][0-9]{0,18})", value) or abs(int(value)) > 2**63 - 1:
            raise Invalid("invalid_integer")
        return int(value)
    if kind == "boolean":
        if value not in {"true", "false"}:
            raise Invalid("invalid_boolean")
        return value == "true"
    try:
        result = date.fromisoformat(value)
        if result.isoformat() != value:
            raise Invalid("invalid_date")
        return result.isoformat()
    except ValueError as error:
        raise Invalid("invalid_date") from error


def process(data):
    source = data.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(source, newline=""), delimiter=CONFIG["delimiter"], strict=True)
    header = next(reader, [])
    if not header or set(header) != set(CONFIG["columns"]) or len(header) != len(CONFIG["columns"]):
        raise Invalid("invalid_header")
    indices = {column: index for index, column in enumerate(header)}
    valid = []
    rejected = []
    total = 0
    for row_index, row in enumerate(reader, 1):
        total = row_index
        if total > CONFIG["max_rows"]:
            raise Invalid("too_many_rows")
        if len(row) != len(header):
            rejected.append({"record": row_index, "issues": [{"column": None, "reason": "width"}]})
            continue
        output = {}
        issues = []
        for field in CONFIG["mapping"]:
            try:
                output[field["target"]] = convert(row[indices[field["source"]]], field)
            except Invalid as error:
                issues.append({"column": field["target"], "reason": str(error)})
        if issues:
            rejected.append({"record": row_index, "issues": issues})
        else:
            valid.append(encoded(output) + b"\\n")
    permitted = not rejected or not CONFIG["strict"]
    result = b"".join(valid) if permitted else None
    return result, {"schema": "ace.factory-etl-run.v1", "plan_sha256": CONFIG["plan_sha256"],
                    "input_sha256": sha256(data).hexdigest(), "records": total, "valid": len(valid),
                    "written": len(valid) if permitted else 0, "rejected": rejected,
                    "output_sha256": sha256(result).hexdigest() if result is not None else None,
                    "status": ("partial" if rejected else "success") if permitted else "held"}


def main(argv=None):
    parser = argparse.ArgumentParser(prog=CONFIG["id"])
    parser.add_argument("--report", action="store_true", help="Tulis laporan JSON ke stderr.")
    args = parser.parse_args(argv)
    try:
        data = sys.stdin.buffer.read(CONFIG["max_bytes"] + 1)
        if len(data) > CONFIG["max_bytes"]:
            raise Invalid("input_too_large")
        payload, report = process(data)
        if args.report or report["rejected"]:
            sys.stderr.buffer.write(encoded(report) + b"\\n")
        if payload is not None:
            sys.stdout.buffer.write(payload)
        return int(payload is None)
    except (Invalid, UnicodeError, csv.Error) as error:
        sys.stderr.buffer.write(encoded({"status": "rejected", "category": type(error).__name__,
                                         "reason": str(error) if isinstance(error, Invalid) else "invalid_csv"}) + b"\\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
'''


def build(plan, expected):
    checked(plan, expected)
    schema(plan, "ace.factory-etl-plan.v1", ("id", "delimiter", "strict", "max_rows", "max_bytes", "columns", "mapping"))
    product = identifier(plan["id"], "ID ETL")
    if keyword.iskeyword(product) or product in sys.stdlib_module_names:
        raise ContractError("Nama ETL bertabrakan dengan Python.")
    if plan["delimiter"] not in (",", ";", "\t") or type(plan["strict"]) is not bool:
        raise ContractError("Delimiter atau mode strict tidak sah.")
    columns = [text(column, "Kolom sumber", 160) for column in entries(plan["columns"], 120, minimum=1)]
    if len(columns) != len(set(columns)):
        raise ContractError("Kolom sumber ganda.")
    fields = {}
    for raw in entries(plan["mapping"], 120, minimum=1):
        obj(raw, ("source", "target", "type", "nullable", "trim", "max_chars", "source_ref"))
        label = text(raw["source"], "Kolom sumber", 160)
        target = identifier(raw["target"], "Kolom tujuan")
        kind = raw["type"]
        if target in fields or label not in columns or not isinstance(kind, str) or kind not in KINDS:
            raise ContractError("Kolom tujuan ganda atau tipe dan sumber tidak dikenal.")
        if type(raw["nullable"]) is not bool or type(raw["trim"]) is not bool:
            raise ContractError("Flag pemetaan perlu boolean.")
        size = integer(raw["max_chars"], "Panjang maksimum", 1, 3000)
        fields[target] = {"source": label, "target": target, "type": kind, "nullable": raw["nullable"],
                          "trim": raw["trim"], "max_chars": size, "source_ref": text(raw["source_ref"], "Sumber aturan")}
    config = {"id": product, "delimiter": plan["delimiter"], "strict": plan["strict"], "plan_sha256": expected,
              "max_rows": integer(plan["max_rows"], "Batas record", 1, 50_000),
              "max_bytes": integer(plan["max_bytes"], "Batas byte", 64, 2_000_000),
              "columns": columns, "mapping": [fields[key] for key in sorted(fields)]}
    name = f"{product}.py"
    runtime = RUNTIME.replace("import sys\n\n", f"import sys\n\nCONFIG = {config!r}\n", 1).encode()
    report = {"schema": "ace.factory-etl-build.v1", "plan_sha256": expected, "product_id": product,
              "runtime": {"path": name, "sha256": sha256(runtime).hexdigest()}, "mapping": config["mapping"]}
    return {name: runtime, "etl_manifest.json": canonical(report) + b"\n"}, report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        files, report = build(decode(read(args.plan)), args.expect_sha256)
        materialize(args.output, files)
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
