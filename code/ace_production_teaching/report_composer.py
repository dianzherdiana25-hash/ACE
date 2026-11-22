"""Rakit laporan dengan kamus angka tunggal dan provenance untuk setiap turunan."""
import argparse
from decimal import Decimal, localcontext
from pathlib import Path
import re
import sys

from ._contracts import (ProductionError, anchor, canonical, decode, fmt, identifier, identity,
                         items, number, obj, read, schema, source_bytes, text)
from .document_builder import make_document


NUMERAL = re.compile(r"(?<!\w)[+-]?[0-9]+(?:[.,][0-9]+)?(?!\w)")


def compose_report(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.production.report-plan.v1", ("source", "metrics", "document"))
    reference = obj(plan["source"], ("path", "sha256"))
    data = decode(source_bytes(root, reference["path"], reference["sha256"], 1_500_000))
    schema(data, "ace.production.measurement-series.v1", ("items",))
    observation = {}
    for index, row in enumerate(items(data["items"], 1500, 1), 1):
        obj(row, ("id", "value", "unit", "source_ref"))
        key = identifier(row["id"], "Pengukuran")
        if key in observation:
            raise ProductionError("Observasi ID ganda.")
        observation[key] = (number(row["value"], "Ukuran"), text(row["unit"], "Satuan", 60),
                            {"source_ref": text(row["source_ref"], "Pointer observasi"), "record": index})
    results = {}
    with localcontext() as context:
        context.prec = 28
        for row in items(plan["metrics"], 100, 1):
            obj(row, ("id", "operation", "members", "unit"))
            key = identifier(row["id"], "Angka laporan")
            method = row["operation"]
            members = [identifier(key, "ID pengukuran") for key in items(row["members"], 500, 1)]
            unit = text(row["unit"], "Satuan laporan", 60)
            if key in results or len(set(members)) != len(members) or any(name not in observation for name in members):
                raise ProductionError("Metrik atau anggotanya duplikat atau belum tersedia.")
            if any(observation[name][1] != unit for name in members):
                raise ProductionError("Satuan observasi tidak sesuai metrik laporan.")
            values = [observation[name][0] for name in members]
            if method == "sum":
                measurement = sum(values, Decimal(0))
            elif method == "mean":
                measurement = sum(values, Decimal(0)) / len(values)
            elif method == "difference" and len(values) == 2:
                measurement = values[1] - values[0]
            elif method == "identity" and len(values) == 1:
                measurement = values[0]
            else:
                raise ProductionError("Operasi metrik atau jumlah input tidak sah.")
            results[key] = {"value": fmt(measurement), "unit": unit, "operation": method,
                            "evidence": [observation[name][2] | {"id": name} for name in members]}
    outline = obj(plan["document"], ("title", "formats", "blocks"))
    # Ask callers to bind each quantitative result so all occurrences share the same value.
    def numbers(value):
        if isinstance(value, str):
            return bool(NUMERAL.search(value))
        if isinstance(value, dict):
            return any(numbers(item) for key, item in value.items() if key != "level")
        if isinstance(value, list):
            return any(numbers(item) for item in value)
        return False
    if numbers(outline):
        raise ProductionError("Angka teks laporan perlu binding metrik.")
    recipe = {"schema": "ace.production.document-plan.v1", **outline,
              "bindings": [{"id": key, "value": row["value"] + " " + row["unit"],
                            "source_ref": reference["path"] + "#" + key} for key, row in sorted(results.items())]}
    bundle, draft = make_document(recipe, identity(recipe))
    return bundle, {"schema": "ace.production.report-receipt.v1", "plan_sha256": expected,
                    "source": reference, "metrics": results, "document": draft}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        outputs, receipt = compose_report(decode(read(args.plan)), args.expect_sha256, args.root)
        args.output.mkdir()
        for name, raw in outputs.items():
            (args.output / name).write_bytes(raw)
        sys.stdout.buffer.write(canonical(receipt) + b"\n")
    except (OSError, ValueError, KeyError, TypeError, ArithmeticError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
