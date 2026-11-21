"""Bangun CLI mandiri untuk memproyeksikan, menjumlahkan dan memvalidasi JSON.

Kontrak nama, operasi, bentuk record dan batas masukan direkam pada
source hasil. Kode hasil hanya memakai pustaka standar. Operand
dibaca dari stdin dengan parser yang menolak kunci ganda dan NaN.
"""
import argparse
from hashlib import sha256
import keyword
from pathlib import Path
import sys

from ._contracts import ContractError, canonical, checked, decode, entries, identifier, integer, obj, read, schema, text
from .repo_scaffolder import materialize


KINDS = {"text", "integer", "boolean"}
OPERATIONS = {"project", "sum", "validate"}
RUNTIME = '''"""CLI produk dari kontrak yang telah diperiksa."""
import argparse
import json
import sys


class InvalidData(ValueError):
    pass


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InvalidData("Kunci JSON ganda.")
        result[key] = value
    return result


def nonfinite(value):
    raise InvalidData("Konstanta JSON nonfinite.")


def load_input(stream, limit):
    data = stream.read(limit + 1)
    if len(data) > limit:
        raise InvalidData("Masukan melewati batas.")
    parsed = json.loads(data.decode("utf-8"), object_pairs_hook=unique, parse_constant=nonfinite)
    if not isinstance(parsed, list):
        raise InvalidData("Masukan harus berupa array record.")
    return parsed


def validate(record, types):
    if not isinstance(record, dict) or set(record) != types.keys():
        return False
    expected = {"text": str, "integer": int, "boolean": bool}
    for key, kind in types.items():
        value = record[key]
        if type(value) is not expected[kind]:
            return False
        if kind == "integer" and abs(value) > 2 ** 63 - 1:
            return False
        if kind == "text" and (len(value) > 2000 or any(0xd800 <= ord(item) <= 0xdfff for item in value)):
            return False
    return True


def process(command, records):
    if len(records) > 5000:
        raise InvalidData("Jumlah record melampaui batas.")
    rejected = [index for index, row in enumerate(records) if not validate(row, command["fields"])]
    op = command["operation"]
    if op == "validate":
        return {"records": len(records), "valid": len(records) - len(rejected), "rejected_indices": rejected}, int(bool(rejected))
    if rejected:
        raise InvalidData(f"Record tidak sah pada indeks {rejected[0]}.")
    if op == "project":
        return [{key: row[key] for key in command["select"]} for row in records], 0
    return {"total": sum(row[command["select"][0]] for row in records), "records": len(records)}, 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog=PRODUCT["id"], description=PRODUCT["description"])
    commands = parser.add_subparsers(dest="command", required=True)
    for key, row in sorted(PRODUCT["commands"].items()):
        commands.add_parser(key, help=row["help"])
    args = parser.parse_args(argv)
    try:
        data = load_input(sys.stdin.buffer, PRODUCT["max_input_bytes"])
        result, status = process(PRODUCT["commands"][args.command], data)
        print(json.dumps(result, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False))
    except (UnicodeError, ValueError, RecursionError) as error:
        print(f"Masukan ditolak: {error}", file=sys.stderr)
        return 2
    return status


if __name__ == "__main__":
    raise SystemExit(main())
'''


def _commands(raw):
    commands = {}
    for row in entries(raw, 30, minimum=1):
        obj(row, ("id", "help", "operation", "fields", "select", "source_ref"))
        key = identifier(row["id"], "ID subcommand")
        operation = row["operation"]
        if key in commands or not isinstance(operation, str) or operation not in OPERATIONS:
            raise ContractError("Subcommand ganda atau operasi belum didukung.")
        description = text(row["help"], "Bantuan", 150)
        reference = text(row["source_ref"], "Rujukan subcommand", 220)
        fields = {}
        for field in entries(row["fields"], 40, minimum=1):
            obj(field, ("name", "type"))
            name = identifier(field["name"], "Nama kolom")
            kind = field["type"]
            if name in fields or not isinstance(kind, str) or kind not in KINDS:
                raise ContractError("Kolom input ganda atau tipe belum didukung.")
            fields[name] = kind
        select = [identifier(value, "Kolom pilihan") for value in entries(row["select"], 40)]
        if len(select) != len(set(select)) or set(select) - fields.keys():
            raise ContractError("Pilihan kolom ganda atau tidak dikenal.")
        valid = (operation == "project" and bool(select)) or (
            operation == "sum" and len(select) == 1 and fields[select[0]] == "integer") or (
            operation == "validate" and not select)
        if not valid:
            raise ContractError("Pilihan kolom tidak sesuai operasi.")
        commands[key] = {"help": description, "operation": operation, "fields": dict(sorted(fields.items())),
                         "select": select, "source_ref": reference}
    return dict(sorted(commands.items()))


def build(plan, expected):
    checked(plan, expected)
    schema(plan, "ace.factory-cli-plan.v1", ("id", "description", "max_input_bytes", "commands"))
    product = identifier(plan["id"], "ID produk")
    if keyword.iskeyword(product) or product in sys.stdlib_module_names:
        raise ContractError("Nama paket bertabrakan dengan Python.")
    config = {"id": product, "description": text(plan["description"], "Deskripsi CLI", 180),
              "max_input_bytes": integer(plan["max_input_bytes"], "Ukuran maksimum", 64, 2_000_000),
              "commands": _commands(plan["commands"])}
    module = f"{product}/__main__.py"
    content = RUNTIME.replace("import sys\n\n", f"import sys\n\nPRODUCT = {config!r}\n", 1).encode("utf-8")
    report = {"schema": "ace.factory-cli-build.v1", "plan_sha256": expected, "product_id": product,
              "entrypoint": ["python3", "-m", product],
              "commands": [{"id": key, "operation": row["operation"], "source_ref": row["source_ref"]}
                           for key, row in config["commands"].items()],
              "runtime": {"path": module, "sha256": sha256(content).hexdigest()}}
    return {f"{product}/__init__.py": b"", module: content, "cli_manifest.json": canonical(report) + b"\n"}, report


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
