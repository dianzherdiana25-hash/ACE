"""Tulis panduan produk hanya dari antarmuka tersurat dan contoh teruji.

Contoh menaut ke kriteria spesifikasi dan receipt yang sudah diikat
pembaca dengan SHA-256. Ketika belum ada receipt, antarmuka tetap
tercatat dengan kekurangan buktinya.
"""
import argparse
import html
from pathlib import Path
import re
import sys

from ._contracts import ContractError, canonical, checked, decode, digest, entries, identifier, obj, read, schema, text


def escape(value):
    return re.sub(r"([\\`*_{}\[\]()!|#])", r"\\\1", html.escape(value, quote=False))


def _index(items, column):
    records = {}
    for row in entries(items, 512):
        ref = text(row[column], "ID atau rujukan", 200)
        if ref in records:
            raise ContractError("ID atau rujukan muncul lebih dari sekali.")
        records[ref] = row
    return records


def _verified_evidence(raw, spec, arch):
    schema(raw, "ace.factory-doc-examples.v1", ("spec_sha256", "architecture_sha256", "examples"))
    checked(spec, raw["spec_sha256"])
    checked(arch, raw["architecture_sha256"])
    by_interface = _index(arch["interfaces"], "id")
    by_requirement = _index(spec["requirements"], "id")
    examples = {}
    for row in entries(raw["examples"], 512):
        obj(row, ("id", "interface", "acceptance_ref", "command", "observed_output", "receipt"))
        key = identifier(row["id"], "ID contoh")
        interface = identifier(row["interface"], "ID antarmuka")
        pointer = text(row["acceptance_ref"], "Rujukan acceptance", 200)
        if key in examples or interface not in by_interface:
            raise ContractError("Contoh ganda atau merujuk antarmuka tak dikenal.")
        need = by_interface[interface]["use_case"]
        criteria = _index(by_requirement[need]["acceptance"], "source_ref")
        if pointer not in criteria:
            raise ContractError("Contoh dan acceptance berasal dari kebutuhan berbeda.")
        receipt = obj(row["receipt"], ("status", "path", "sha256"))
        if receipt["status"] != "passed":
            raise ContractError("Dokumentasi contoh membutuhkan verifier yang lulus.")
        examples[key] = {"id": key, "interface": interface, "acceptance_ref": pointer,
                         "command": text(row["command"], "Contoh perintah", 400),
                         "observed_output": text(row["observed_output"], "Keluaran teramati", 500),
                         "receipt": {"path": text(receipt["path"], "Path receipt", 300),
                                     "sha256": digest(receipt["sha256"])}}
    return by_interface, by_requirement, examples


def build(spec, architecture, examples, expected):
    checked(examples, expected)
    if spec.get("status") != "ready" or architecture.get("status") != "ready":
        raise ContractError("Kontrak produk belum siap.")
    checked(spec, architecture["spec_sha256"])
    if spec["product_id"] != architecture["product_id"]:
        raise ContractError("Spesifikasi dan arsitektur memiliki produk berbeda.")
    interfaces, requirements, evidence = _verified_evidence(examples, spec, architecture)
    groups = []
    missing = []
    lines = [f"# {escape(text(spec['name'], 'Nama produk', 120))}", "", escape(spec["objective"]),
             "", f"Sumber tujuan {escape(spec['objective_ref'])}.", "", "## Antarmuka"]
    for key, row in sorted(interfaces.items()):
        need = requirements[row["use_case"]]
        available = [item for _, item in sorted(evidence.items()) if item["interface"] == key]
        if not available:
            missing.append(key)
        groups.append({"id": key, "source_ref": row["source_ref"], "requirement_ref": need["source_ref"],
                       "examples": available})
        lines.extend(["", f"### {escape(key)}", "", escape(need["statement"]), "",
                      f"- Masukan {escape(row['input_shape'])}.",
                      f"- Keluaran {escape(row['output_shape'])}.",
                      f"- Sumber {escape(row['source_ref'])} dan {escape(need['source_ref'])}."])
        if not available:
            lines.append("- Contoh penggunaan menunggu receipt verifier.")
        for example in available:
            ref = example["receipt"]
            lines.extend(["", f"#### {escape(example['id'])}", "", "```text", example["command"], "```",
                          "", f"Keluaran teramati **{escape(example['observed_output'])}**.",
                          f"Sumber acceptance {escape(example['acceptance_ref'])}.",
                          f"Bukti {escape(ref['path'])} · SHA-256 `{ref['sha256']}`."])
    lines.extend(["", "## Batas"])
    for item in [*spec["constraints"], *spec["non_goals"]]:
        lines.append(f"- {escape(item['statement'])} ({escape(item['source_ref'])}).")
    if not spec["constraints"] and not spec["non_goals"]:
        lines.append("- Spesifikasi tidak mencantumkan batas tambahan.")
    return "\n".join(lines) + "\n", {
        "schema": "ace.factory-doc-report.v1", "examples_sha256": expected, "interfaces": groups,
        "missing_examples": missing, "status": "partial" if missing else "documented",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path)
    parser.add_argument("architecture", type=Path)
    parser.add_argument("examples", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    parser.add_argument("--index", action="store_true")
    args = parser.parse_args(argv)
    try:
        document, report = build(decode(read(args.spec)), decode(read(args.architecture)),
                                 decode(read(args.examples)), args.expect_sha256)
        output = canonical(report) + b"\n" if args.index else document.encode()
        sys.stdout.buffer.write(output)
    except (OSError, KeyError, ValueError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return int(report["status"] == "partial")


if __name__ == "__main__":
    raise SystemExit(main())
