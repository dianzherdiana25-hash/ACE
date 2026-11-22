"""Cetak label paket dan daftar isi dari tabel lokal dengan pengecekan alamat per paket."""
import argparse
import csv
from io import StringIO
from pathlib import Path
import sys
import unicodedata

from ._artifacts import evidence
from ._contracts import (ProductionError, anchor, canonical, decode, identifier,
                         identity, integer, obj, read, schema, source_bytes, text)
from .document_builder import make_document
from .tabular_engine import _read_csv


def create_labels(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.production.label-plan.v1", ("table", "title", "max_packages", "formats"))
    label = text(plan["title"], "Judul daftar", 140)
    maximum = integer(plan["max_packages"], "Batas paket", 1, 120)
    ref = obj(plan["table"], ("path", "sha256"))
    names, rows = _read_csv(source_bytes(root, ref["path"], ref["sha256"], 1_000_000), ref["sha256"], 3000)
    if names != ["parcel", "receiver", "destination", "item", "count"]:
        raise ProductionError("Header daftar kirim harus parcel,receiver,destination,item,count.")
    table = {}
    for (raw, receiver, destination, item, qty), proof in rows:
        key = identifier(raw, "ID paket")
        receiver = text(receiver, "Label penerima", 120)
        destination = text(destination, "Alamat atau kode zona", 220)
        item = identifier(item, "Item")
        if not qty.isascii() or not qty.isdigit() or len(qty) > 8 or not 0 < int(qty) <= 100000:
            raise ProductionError("Jumlah barang perlu integer positif dalam batas.")
        route = (unicodedata.normalize("NFC", receiver), unicodedata.normalize("NFC", destination))
        record = table.setdefault(key, {"route": route, "contents": {}})
        if record["route"] != route or item in record["contents"]:
            raise ProductionError("Satu paket memiliki alamat berkonflik atau barang ganda.")
        record["contents"][item] = (int(qty), proof[0][1])
        if len(table) > maximum:
            raise ProductionError("Jumlah paket melewati batas label.")
    if not table:
        raise ProductionError("Tidak ada paket untuk disusun.")
    sections = []
    pack_list = StringIO(newline="")
    writer = csv.writer(pack_list, lineterminator="\n")
    writer.writerow(["parcel", "item", "count", "source_line"])
    summary = []
    for parcel, row in sorted(table.items()):
        if sections:
            sections.append({"kind": "break"})
        sections.extend([{"kind": "heading", "level": 1, "body": parcel},
                         {"kind": "paragraph", "body": row["route"][0]},
                         {"kind": "paragraph", "body": row["route"][1]}])
        for key, (unit, line) in sorted(row["contents"].items()):
            writer.writerow([parcel, key, unit, line])
        summary.append({"parcel": parcel, "items": len(row["contents"]),
                        "source_lines": sorted(line for _, line in row["contents"].values())})
    doc = {"schema": "ace.production.document-plan.v1", "title": label, "formats": plan["formats"],
           "bindings": [], "blocks": sections}
    files, _ = make_document(doc, identity(doc))
    files["packing_list.csv"] = pack_list.getvalue().encode()
    return files, {"schema": "ace.production.labels-draft.v1", "plan_sha256": expected, "state": "local_draft",
                   "table": ref, "parcels": summary, "artifacts": evidence(files)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        files, proof = create_labels(decode(read(args.plan)), args.expect_sha256, args.root)
        args.output.mkdir()
        for key, raw in files.items():
            (args.output / key).write_bytes(raw)
        sys.stdout.buffer.write(canonical(proof) + b"\n")
    except (OSError, ValueError, KeyError, TypeError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
