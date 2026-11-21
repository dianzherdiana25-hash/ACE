"""Rakit migrasi SQLite aditif tanpa menulis database sumber.

Schema lama diperiksa terhadap model yang di-anchor, lalu setiap row
disalin ke skema baru dalam transaksi. Tabel maupun nilai lama harus
bertahan byte-for-byte pada bentuk record kanonis sebelum total dihitung.
"""
import argparse
from base64 import b64encode
from contextlib import closing
from hashlib import sha256
from pathlib import Path
import sqlite3
import sys

from ._contracts import ContractError, canonical, checked, decode, digest, read, schema, text
from .schema_designer import Entity, _column_list, _quote, design


MAX_DATABASE = 8_000_000
MAX_ROWS = 40_000


def _tables(model):
    return {entry["name"]: Entity.parse(entry) for entry in model["entities"]}


def _changes(old, new):
    if old.keys() - new.keys():
        raise ContractError("Migrasi tidak boleh menghapus tabel.")
    added = {}
    for name, before in sorted(old.items()):
        after = new[name]
        if (before.primary != after.primary or set(before.unique) != set(after.unique)
                or before.foreign_raw != after.foreign_raw or set(before.indexes)-set(after.indexes)):
            raise ContractError(f"Constraint lama berbeda pada {name}.")
        if before.columns.keys() - after.columns.keys() or any(
                column != after.columns[key] for key, column in before.columns.items()):
            raise ContractError(f"Definisi kolom lama berbeda pada {name}.")
        extra = sorted(after.columns.keys()-before.columns.keys())
        if any(not after.columns[key].nullable and (after.columns[key].default_sql in (None, "NULL")) for key in extra):
            raise ContractError(f"Kolom baru wajib default atau nullable pada {name}.")
        added[name] = {"columns": extra, "new_indexes": [list(row) for row in sorted(set(after.indexes)-set(before.indexes))]}
    return {"tables": sorted(new.keys()-old.keys()), "existing_tables": added}


def _database_layout(connection):
    return connection.execute("SELECT type,name,tbl_name,sql FROM sqlite_schema "
                              "WHERE name NOT LIKE 'sqlite_stat%' ORDER BY type,name").fetchall()


def _reader(connection, entity, columns):
    fields = _column_list(columns)
    order = _column_list(entity.primary)
    return connection.execute(f"SELECT {fields} FROM {_quote(entity.name)} ORDER BY {order}")


def _encode_row(raw):
    return canonical([{"b64": b64encode(value).decode("ascii")} if isinstance(value, bytes) else value for value in raw])


def _digest_rows(incoming):
    anchor = sha256()
    count = 0
    for item in incoming:
        count += 1
        if count > MAX_ROWS:
            raise ContractError("Jumlah baris tabel melebihi anggaran migrasi.")
        anchor.update(_encode_row(item))
        anchor.update(b"\n")
    return count, anchor.hexdigest()


def migrate(source, old_model, new_model, plan, expected):
    checked(plan, expected)
    schema(plan, "ace.factory-additive-migration.v1", ("source_ref", "source_sha256", "old_model_sha256", "new_model_sha256"))
    pointer = text(plan["source_ref"], "Sumber migrasi", 250)
    original = digest(plan["source_sha256"])
    if not isinstance(source, bytes) or len(source) > MAX_DATABASE or sha256(source).hexdigest() != original:
        raise ContractError("Database sumber melampaui batas atau gagal anchor.")
    old_definition = design(old_model, plan["old_model_sha256"])
    new_definition = design(new_model, plan["new_model_sha256"])
    old, new = _tables(old_model), _tables(new_model)
    changes = _changes(old, new)
    with closing(sqlite3.connect(":memory:")) as expected_old, closing(sqlite3.connect(":memory:")) as snapshot:
        expected_old.executescript(old_definition["sql"])
        snapshot.deserialize(source)
        snapshot.execute("PRAGMA trusted_schema=OFF")
        snapshot.execute("PRAGMA query_only=ON")
        if _database_layout(expected_old) != _database_layout(snapshot):
            raise ContractError("Layout SQLite tidak sama dengan model sumber.")
        if snapshot.execute("PRAGMA quick_check").fetchone() != ("ok",):
            raise ContractError("Pemeriksaan integritas snapshot lama gagal.")
        with closing(sqlite3.connect(":memory:", isolation_level=None)) as target:
            target.executescript(new_definition["sql"])
            target.execute("BEGIN IMMEDIATE")
            target.execute("PRAGMA defer_foreign_keys=ON")
            receipts = []
            for _, entity in sorted(old.items()):
                columns = sorted(entity.columns)
                inserts = ", ".join("?" for _ in columns)
                put = f"INSERT INTO {_quote(entity.name)} ({_column_list(columns)}) VALUES ({inserts})"
                count, before = _digest_rows(_reader(snapshot, entity, columns))
                target.executemany(put, _reader(snapshot, entity, columns))
                migrated, after = _digest_rows(_reader(target, entity, columns))
                if (count, before) != (migrated, after):
                    raise ContractError(f"Baris sumber berbeda sesudah migrasi pada {entity.name}.")
                receipts.append({"table": entity.name, "rows": count, "old_sha256": before, "new_sha256": after})
            if target.execute("PRAGMA foreign_key_check").fetchone() is not None:
                raise ContractError("Validasi foreign key migrasi gagal.")
            target.execute("COMMIT")
            if target.execute("PRAGMA quick_check").fetchone() != ("ok",):
                raise ContractError("Pemeriksaan integritas hasil migrasi gagal.")
            page_count = target.execute("PRAGMA page_count").fetchone()[0]
            page_size = target.execute("PRAGMA page_size").fetchone()[0]
            if page_count * page_size > MAX_DATABASE:
                raise ContractError("Database hasil melampaui batas.")
            result = target.serialize()
    return result, {"schema": "ace.factory-migration-report.v1", "status": "verified", "plan_sha256": expected,
                    "source_ref": pointer, "source_sha256": original, "output_sha256": sha256(result).hexdigest(),
                    "old_schema_sha256": old_definition["sql_sha256"], "new_schema_sha256": new_definition["sql_sha256"],
                    "changes": changes, "row_checks": receipts}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "old_model", "new_model", "plan", "output"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        patch, report = migrate(read(args.source, MAX_DATABASE), decode(read(args.old_model)), decode(read(args.new_model)),
                                decode(read(args.plan)), args.expect_sha256)
        with args.output.open("xb") as output:
            output.write(patch)
        sys.stdout.buffer.write(canonical(report)+b"\n")
    except (OSError, ValueError, RecursionError, sqlite3.Error) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
