"""Hitung laporan keuangan baca-saja dari tabel eksplisit dengan rekonsiliasi per kelompok."""
import argparse
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP, localcontext
from pathlib import Path
import re
import sys

from ._contracts import (ProductionError, anchor, canonical, day, decode, identifier,
                         identity, integer, number, obj, read, schema, source_bytes, text)
from .document_builder import make_document
from .tabular_engine import _read_csv


def build_finance_report(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.production.finance-report-plan.v1",
           ("table", "title", "from", "through", "currency", "minor_digits", "formats"))
    ref = obj(plan["table"], ("path", "sha256"))
    title = text(plan["title"], "Judul laporan", 150)
    begin, end = day(plan["from"]), day(plan["through"])
    currency = text(plan["currency"], "Mata uang", 3)
    if not re.fullmatch(r"[A-Z]{3}", currency) or end < begin:
        raise ProductionError("Kode mata uang atau rentang tanggal tidak sah.")
    digits = integer(plan["minor_digits"], "Digit minor", 0, 4)
    rounding = Decimal(1).scaleb(-digits)
    names, rows = _read_csv(source_bytes(root, ref["path"], ref["sha256"], 3_000_000), ref["sha256"], 30000)
    if names != ["id", "date", "kind", "category", "amount", "currency"]:
        raise ProductionError("Kolom laporan wajib id,date,kind,category,amount,currency.")
    groups = defaultdict(list)
    skipped = []
    known = set()
    with localcontext() as ctx:
        ctx.prec = 42
        for (key, stamp, kind, label, value, unit), proof in rows:
            identity_key = identifier(key, "Catatan")
            category = identifier(label, "Kategori")
            when = day(stamp)
            if identity_key in known or kind not in ("income", "cost") or unit != currency:
                raise ProductionError("ID catatan ganda atau mata uang/jenis tak sepadan.")
            known.add(identity_key)
            amount = number(value, "Nominal")
            if amount < 0:
                raise ProductionError("Nominal harus nonnegatif dan jenis arus dinyatakan terpisah.")
            if begin <= when <= end:
                groups[kind, category].append((amount.quantize(rounding, rounding=ROUND_HALF_UP), proof[0][1]))
            else:
                skipped.append(proof[0][1])
        rendered = []
        totals = {"income": Decimal(0), "cost": Decimal(0)}
        for (kind, category), evidence in sorted(groups.items()):
            value = sum(amount for amount, _ in evidence)
            totals[kind] += value
            rendered.append({"kind": kind, "category": category, "amount": format(value, "f"),
                             "source_lines": [line for _, line in evidence]})
        balance = totals["income"] - totals["cost"]
        summary = {**{key: format(value.quantize(rounding), "f") for key, value in totals.items()},
                   "net": format(balance.quantize(rounding), "f")}
    if len(rendered) > 80:
        raise ProductionError("Kategori melebihi anggaran tampilan laporan.")
    doc = {"schema": "ace.production.document-plan.v1", "title": title, "formats": plan["formats"], "bindings": [], "blocks": [
        {"kind": "paragraph", "body": f"{begin.isoformat()} s.d. {end.isoformat()}"},
        {"kind": "table", "columns": ["Jenis", "Kategori", currency],
         "rows": [[row["kind"], row["category"], row["amount"]] for row in rendered]},
        {"kind": "paragraph", "body": f"Pemasukan {summary['income']} · Biaya {summary['cost']} · Neto {summary['net']} {currency}"}]}
    payloads, generated = make_document(doc, identity(doc))
    return payloads, {"schema": "ace.production.finance-report.v1", "plan_sha256": expected, "state": "read_only_report",
                      "source": ref, "currency": currency, "totals": summary, "categories": rendered,
                      "ignored_lines_outside_period": skipped, "document": generated}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        files, report = build_finance_report(decode(read(args.plan)), args.expect_sha256, args.root)
        args.output.mkdir()
        for key, raw in files.items():
            (args.output / key).write_bytes(raw)
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, KeyError, TypeError, ArithmeticError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
