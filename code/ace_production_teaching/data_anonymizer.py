"""Proyeksikan data dengan redaksi dan pseudonim keyed tanpa menyimpan nilai asal."""
import argparse
import csv
from hashlib import sha256
import hmac
from io import StringIO
import os
from pathlib import Path
import sys
import unicodedata

from ._contracts import (ProductionError, anchor, canonical, decode, identifier,
                         integer, items, obj, read, schema, source_bytes)
from .tabular_engine import _read_csv


def anonymize(plan, expected, root, *, key=None):
    anchor(plan, expected)
    schema(plan, "ace.production.anonymization-plan.v1", ("data", "scope", "columns", "max_records"))
    scope = identifier(plan["scope"], "Lingkup pseudonim")
    cap = integer(plan["max_records"], "Batas record", 1, 30000)
    link = obj(plan["data"], ("path", "sha256"))
    headers, rows = _read_csv(source_bytes(root, link["path"], link["sha256"], 3_000_000), link["sha256"], cap)
    rules = {}
    for item in items(plan["columns"], 80, 1):
        obj(item, ("column", "operation"))
        column = identifier(item["column"], "Kolom")
        if column in rules or column not in headers or item["operation"] not in ("drop", "mask", "keep", "pseudonym"):
            raise ProductionError("Kolom redaksi ganda atau jenis operasi belum didukung.")
        rules[column] = item["operation"]
    if rules.keys() != set(headers) or all(rule == "drop" for rule in rules.values()):
        raise ProductionError("Semua kolom perlu kebijakan dan setidaknya satu kolom keluaran.")
    keyed = "pseudonym" in rules.values()
    if keyed and (not isinstance(key, bytes) or not 32 <= len(key) <= 128):
        raise ProductionError("Kunci pseudonim harus disediakan secara lokal dan memenuhi panjang.")
    published = [name for name in headers if rules[name] != "drop"]
    word_count = dict.fromkeys(published, 0)
    output = StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(published)
    for values, _ in rows:
        final = []
        for name, raw in zip(headers, values, strict=True):
            operation = rules[name]
            if operation == "drop":
                continue
            value = raw
            if raw and operation == "mask":
                value = "[REDACTED]"
            if raw and operation == "pseudonym":
                normalized = unicodedata.normalize("NFC", raw.strip()).casefold()
                if not normalized:
                    value = ""
                else:
                    content = b"\0".join((scope.encode(), name.encode(), normalized.encode()))
                    value = "p_" + hmac.new(key, content, sha256).hexdigest()
            word_count[name] += value != raw
            final.append(value)
        writer.writerow(final)
    data = output.getvalue().encode("utf-8")
    return data, {"schema": "ace.production.anonymization-receipt.v1", "plan_sha256": expected,
                  "input_sha256": link["sha256"], "output_sha256": sha256(data).hexdigest(),
                  "basis": "operator_declared_column_roles", "scope": scope, "rows": len(rows),
                  "rules": rules, "changed_cells": word_count, "pseudonymized": keyed}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--expect-sha256", required=True)
    parser.add_argument("--key-env", default="ACE_PRODUCTION_PSEUDONYM_KEY_HEX")
    args = parser.parse_args(argv)
    try:
        raw_key = os.environ.get(args.key_env)
        try:
            key = None if raw_key is None else bytes.fromhex(raw_key)
        except ValueError as error:
            raise ProductionError("Kunci pseudonim lokal bukan bentuk heksadesimal.") from error
        data, report = anonymize(decode(read(args.plan)), args.expect_sha256, args.root, key=key)
        with args.output.open("xb") as stream:
            stream.write(data)
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, KeyError, TypeError, ArithmeticError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
