"""Susun draf faktur dengan aritmetika desimal dan sumber per baris, tanpa koneksi pembayaran."""
import argparse
from decimal import Decimal, ROUND_HALF_UP, localcontext
from pathlib import Path
import re
import sys

from ._contracts import ProductionError, anchor, canonical, day, decode, identifier, identity, integer, items, number, obj, read, schema, text
from .document_builder import make_document


def build_invoice(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.production.invoice-plan.v1",
           ("id", "issued", "due", "currency", "minor_digits", "issuer_label", "recipient_label", "items", "formats"))
    invoice = identifier(plan["id"], "ID dokumen")
    issued, due = day(plan["issued"]), day(plan["due"])
    if due < issued:
        raise ProductionError("Tenggat dokumen mendahului tanggal terbit.")
    currency = text(plan["currency"], "Kode mata uang", 3)
    if re.fullmatch(r"[A-Z]{3}", currency) is None:
        raise ProductionError("Kode mata uang perlu tiga huruf kapital.")
    digits = integer(plan["minor_digits"], "Digit unit minor", 0, 4)
    size = Decimal(1).scaleb(-digits)
    issuer = text(plan["issuer_label"], "Label penerbit", 120)
    recipient = text(plan["recipient_label"], "Label penerima", 120)
    final = []
    seen = set()
    sub = taxes = Decimal(0)
    with localcontext() as context:
        context.prec = 40
        for row in items(plan["items"], 80, 1):
            obj(row, ("id", "description", "quantity", "price", "tax_bp", "source_ref"))
            key = identifier(row["id"], "ID baris")
            qty = number(row["quantity"], "Kuantitas")
            price = number(row["price"], "Harga unit")
            if key in seen or not 0 < qty <= 10**8 or not 0 <= price <= 10**12:
                raise ProductionError("Baris ganda atau kuantitas/harga di luar batas.")
            seen.add(key)
            rate = integer(row["tax_bp"], "Tarif pajak yang dinyatakan", 0, 10000)
            subtotal = (qty * price).quantize(size, rounding=ROUND_HALF_UP)
            tax = (subtotal * rate / 10000).quantize(size, rounding=ROUND_HALF_UP)
            sub += subtotal
            taxes += tax
            final.append({"id": key, "description": text(row["description"], "Uraian", 100),
                         "source_ref": text(row["source_ref"], "Pointer baris"), "quantity": format(qty, "f"),
                         "unit_price": format(price, "f"), "net": format(subtotal, "f"),
                         "tax": format(tax, "f"), "tax_rate_bp": rate})
        total = sub + taxes
    rec = {"net": format(sub.quantize(size), "f"), "tax": format(taxes.quantize(size), "f"),
           "total": format(total.quantize(size), "f")}
    layout = {"schema": "ace.production.document-plan.v1", "title": f"Draf faktur {invoice}", "formats": plan["formats"],
              "bindings": [], "blocks": [
                {"kind": "paragraph", "body": f"{issuer} · {recipient}"},
                {"kind": "paragraph", "body": f"Terbit {issued.isoformat()} · Tenggat {due.isoformat()}"},
                {"kind": "table", "columns": ["Uraian", "Jumlah", f"Unit {currency}", f"Neto {currency}", f"Pajak {currency}"],
                 "rows": [[row[column] for column in ("description", "quantity", "unit_price", "net", "tax")] for row in final]},
                {"kind": "paragraph", "body": f"Neto {currency} {rec['net']} · Pajak {currency} {rec['tax']}"},
                {"kind": "paragraph", "body": f"Total {currency} {rec['total']}"}]}
    artifacts, receipt = make_document(layout, identity(layout))
    return artifacts, {"schema": "ace.production.invoice-draft.v1", "plan_sha256": expected, "id": invoice,
                       "state": "document_only_draft", "currency": currency, "calculation": "line_half_up_then_tax_half_up",
                       "items": final, "totals": rec, "document": receipt}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        files, report = build_invoice(decode(read(args.plan)), args.expect_sha256)
        args.output.mkdir()
        for name, data in files.items():
            (args.output / name).write_bytes(data)
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, TypeError, ArithmeticError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
