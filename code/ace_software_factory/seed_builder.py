"""Bangun database seed baru dari model domain dan data berprovenance.

SQLite in-memory menegakkan tipe, kunci, dan foreign key pada satu
transaksi. Hanya snapshot yang seluruhnya valid diserialisasi. Seed
tidak membuka database target maupun menyimpan nilai di receipt.
"""
import argparse
from base64 import b64decode
from binascii import Error as Base64Error
from contextlib import closing
from hashlib import sha256
from pathlib import Path
import sqlite3
import sys

from ._contracts import ContractError, canonical, checked, decode, entries, identifier, identity, integer, obj, read, schema, text
from .schema_designer import Entity, _column_list, _quote, design


MAX_RECORDS = 2000
MAX_DB = 10_000_000


def _convert(column, value):
    if value is None:
        if column.nullable:
            return None
        raise ContractError("Kolom tidak nullable.")
    if column.kind == "boolean":
        if type(value) is not bool:
            raise ContractError("Boolean perlu true atau false.")
        return int(value)
    if column.kind == "integer":
        return integer(value, "Nilai integer", -2**63, 2**63 - 1)
    if column.kind == "text":
        if not isinstance(value, str) or len(value) > 12_000 or "\0" in value:
            raise ContractError("Nilai teks tidak sah atau melampaui batas.")
        value.encode("utf-8")
        return value
    if not isinstance(value, str) or not value.isascii() or len(value) > 16_000:
        raise ContractError("BLOB seed perlu literal base64 berbatas.")
    try:
        return b64decode(value, validate=True)
    except Base64Error as error:
        raise ContractError("BLOB seed bukan base64 sah.") from error


def _source_rows(manifest, tables):
    used = set()
    row_order = []
    for row in entries(manifest["rows"], MAX_RECORDS):
        obj(row, ("id", "table", "values", "source_ref"))
        key = identifier(row["id"], "ID seed")
        table = identifier(row["table"], "Tabel seed")
        pointer = text(row["source_ref"], "Sumber seed", 260)
        if key in used or table not in tables:
            raise ContractError("ID seed ganda atau tabel tidak dikenal.")
        used.add(key)
        source = row["values"]
        fields = tables[table].columns
        if not isinstance(source, dict) or not source or source.keys() - fields.keys():
            raise ContractError(f"Kolom seed tidak dikenal atau kosong pada {key}.")
        if set(tables[table].primary) - source.keys():
            raise ContractError(f"Primary key seed belum dinyatakan pada {key}.")
        names = tuple(sorted(source))
        try:
            values = tuple(_convert(fields[name], source[name]) for name in names)
        except (ValueError, UnicodeError) as error:
            raise ContractError(f"Tipe seed tidak sah pada {key}.") from error
        row_order.append((key, table, pointer, names, values, identity(row)))
    return row_order


def build(model, manifest, expected):
    checked(manifest, expected)
    schema(manifest, "ace.factory-seed-plan.v1", ("model_sha256", "source_ref", "rows"))
    source_ref = text(manifest["source_ref"], "Asal data seed", 200)
    ddl = design(model, manifest["model_sha256"])
    tables = {raw["name"]: Entity.parse(raw) for raw in model["entities"]}
    rows = _source_rows(manifest, tables)
    receipts = []
    counts = {key: 0 for key in sorted(tables)}
    with closing(sqlite3.connect(":memory:", isolation_level=None)) as connection:
        connection.executescript(ddl["sql"])
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("PRAGMA defer_foreign_keys=ON")
        for key, table, pointer, names, values, anchor in rows:
            placeholders = ", ".join("?" for _ in names)
            try:
                connection.execute(f"INSERT INTO {_quote(table)} ({_column_list(names)}) VALUES ({placeholders})", values)
            except sqlite3.IntegrityError as error:
                raise ContractError(f"Seed melanggar constraint pada {key}.") from error
            counts[table] += 1
            receipts.append({"id": key, "table": table, "source_ref": pointer, "row_sha256": anchor})
        violations = connection.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            broken = sorted({item[0] for item in violations})
            raise ContractError(f"Foreign key seed tidak lengkap pada {', '.join(broken)}.")
        connection.execute("COMMIT")
        if connection.execute("PRAGMA quick_check").fetchone() != ("ok",):
            raise ContractError("Integritas SQLite seed gagal.")
        pages = connection.execute("PRAGMA page_count").fetchone()[0]
        size = connection.execute("PRAGMA page_size").fetchone()[0]
        if pages * size > MAX_DB:
            raise ContractError("Snapshot seed melampaui batas.")
        payload = connection.serialize()
    return payload, {"schema": "ace.factory-seed-report.v1", "plan_sha256": expected, "source_ref": source_ref,
                     "model_sha256": manifest["model_sha256"], "sql_sha256": ddl["sql_sha256"],
                     "seed_sha256": sha256(payload).hexdigest(), "bytes": len(payload),
                     "counts": counts, "receipts": receipts}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", type=Path)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        payload, report = build(decode(read(args.model)), decode(read(args.plan)), args.expect_sha256)
        with args.output.open("xb") as stream:
            stream.write(payload)
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, RecursionError, sqlite3.Error) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
