"""Susun spesifikasi dari kutipan kebutuhan yang memiliki rujukan.

Transkrip deklaratif mengenali penanda perlu/uji/batas/luar.
Kutipan yang ambigu tetap muncul di daftar klarifikasi. Syarat
ditautkan ke acceptance criterion dengan ID dan rujukan berbeda.
Status dapat dibangun membutuhkan konten dan acceptance yang lengkap.
"""
import argparse
from collections import defaultdict
from pathlib import Path
import re
import sys

from ._contracts import ContractError, canonical, checked, decode, entries, identifier, identity, obj, read, schema, text


SURFACES = {"web", "cli", "service"}
MODES = re.compile(r"^(perlu|uji|batas|luar)\s+([a-z][a-z0-9_]{0,63})\s*:\s*(.+)$", re.IGNORECASE)


def _escape(value):
    return value.replace("\\", "\\\\").replace("**", "\\*\\*").replace("<", "&lt;").replace(">", "&gt;")


def write(raw, expected=None):
    schema(raw, "ace.factory-product-brief.v1", ("id", "name", "surface", "objective", "objective_ref", "utterances"))
    if expected is not None:
        checked(raw, expected)
    product = identifier(raw["id"], "ID produk")
    title = text(raw["name"], "Nama produk", 120)
    objective = text(raw["objective"], "Tujuan produk")
    objective_ref = text(raw["objective_ref"], "Rujukan tujuan", 200)
    surface = raw["surface"]
    if not isinstance(surface, str) or surface not in SURFACES:
        raise ContractError("Permukaan produk belum didukung.")
    requirements, constraints, excluded = {}, {}, {}
    acceptance = defaultdict(list)
    pending = []
    known, references = set(), {objective_ref}
    for row in entries(raw["utterances"], 512):
        obj(row, ("id", "ref", "text"))
        key = identifier(row["id"], "ID ujaran")
        pointer = text(row["ref"], "Rujukan ujaran", 200)
        quote = text(row["text"], "Kutipan ujaran")
        if key in known or pointer in references:
            raise ContractError("Ujaran atau rujukan ganda.")
        known.add(key)
        references.add(pointer)
        match = MODES.fullmatch(quote.strip())
        if not match:
            pending.append({"utterance_id": key, "source_ref": pointer, "quote": quote, "reason": "unrecognized_statement"})
            continue
        mode, subject, statement = match.groups()
        identifier(subject, "ID klausa")
        value = {"statement": text(statement.strip(), "Isi klausa"), "source_ref": pointer}
        mode = mode.casefold()
        if mode == "uji":
            if any(item["statement"] == value["statement"] for item in acceptance[subject]):
                raise ContractError("Kriteria acceptance ganda.")
            acceptance[subject].append(value)
            continue
        destination = {"perlu": requirements, "batas": constraints, "luar": excluded}[mode]
        if subject in destination or (mode == "luar" and subject in requirements) or (mode == "perlu" and subject in excluded):
            raise ContractError("Klausa ganda atau bertentangan dengan batas produk.")
        destination[subject] = value
    unknown = sorted(acceptance.keys()-requirements.keys())
    for key in unknown:
        pending.append({"requirement_id": key, "reason": "acceptance_without_requirement",
                        "source_refs": [item["source_ref"] for item in acceptance[key]]})
    if not requirements:
        pending.append({"reason": "no_requirements", "source_ref": objective_ref})
    for key in sorted(requirements):
        if not acceptance[key]:
            pending.append({"requirement_id": key, "reason": "missing_acceptance",
                            "source_ref": requirements[key]["source_ref"]})
    output = {"schema": "ace.factory-product-spec.v1", "brief_sha256": identity(raw), "product_id": product,
              "name": title, "surface": surface, "objective": objective, "objective_ref": objective_ref,
              "requirements": [{"id": key, **value, "acceptance": acceptance[key]} for key,value in sorted(requirements.items())],
              "constraints": [{"id": key, **value} for key,value in sorted(constraints.items())],
              "non_goals": [{"id": key, **value} for key,value in sorted(excluded.items())],
              "pending": pending, "status": "ready" if not pending else "needs_clarification"}
    return output


def markdown(report):
    lines = ["# "+_escape(report["name"]), "", _escape(report["objective"]), "",
             "## Kebutuhan", ""]
    for item in report["requirements"]:
        lines.append(f"- **{item['id']}** {_escape(item['statement'])} ({_escape(item['source_ref'])})")
        for check in item["acceptance"]:
            lines.append(f"  - {_escape(check['statement'])} ({_escape(check['source_ref'])})")
    for key, title in (("constraints","Batas"),("non_goals","Di luar cakupan")):
        lines += ["", f"## {title}", ""]
        lines += [f"- {row['id']} · {_escape(row['statement'])} ({_escape(row['source_ref'])})" for row in report[key]]
    lines += ["", "## Pertanyaan terbuka", ""]
    lines += [f"- `{item['reason']}` · {item.get('requirement_id', item.get('utterance_id', 'product'))}"
              for item in report["pending"]]
    return "\n".join(lines)+"\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("brief", type=Path)
    parser.add_argument("--expect-sha256")
    parser.add_argument("--markdown", action="store_true")
    args = parser.parse_args(argv)
    try:
        product = write(decode(read(args.brief)),args.expect_sha256)
        sys.stdout.buffer.write(markdown(product).encode() if args.markdown else canonical(product)+b"\n")
    except (OSError, OverflowError, ValueError, RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return int(product["status"] != "ready")


if __name__ == "__main__":
    raise SystemExit(main())
