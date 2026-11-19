#!/usr/bin/env python3
"""Tabulasi vonis dan bandingkan metrik eksplisit dari konsolidasi EVO Markdown."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from decimal import Decimal, localcontext
from html import escape
import hashlib
import json
from pathlib import Path
import re

if __package__:
    from .evo_prereg_draft import _headings
else:
    from evo_prereg_draft import _headings


PACKAGE = re.compile(r"^# (?:KONSOLIDASI )?EVO[ _]([0-9]{4})(?:\s|$)", re.IGNORECASE)
GATE = re.compile(r"^(?:GATE\s+([A-Z][A-Z0-9_-]*)|(BLOK\s+[A-Z0-9]+)|([BT]\d+))\b", re.IGNORECASE)
VERDICT = re.compile(
    r"\b(?i:vonis|verdict)\s*:\s*"
    r"(TIDAK LOLOS|TIDAK TERDUKUNG|LOLOS GERBANG|[A-Z][A-Z_0-9]*)"
    r"(?=\s*(?:[,()—]|$))"
)
HEADLINE_VERDICT = re.compile(
    r"(?:\(|:\s*)(TIDAK TERDUKUNG|TERDUKUNG|PASS|FAIL|TIDAK LOLOS|LOLOS|ERROR)"
    r"(?=[,)]|\s*\(|\s*$)"
)
TERMINAL_VERDICT = re.compile(r"(?:—\s+|\b\d+/\d+\s+)(TIDAK TERDUKUNG|TERDUKUNG|LOLOS GERBANG)\s*$")
NUMBER = re.compile(r"[+-]?[0-9]+(?:\.[0-9]+)?")
MARKDOWN = str.maketrans({char: f"&#{ord(char)};" for char in "`*_[]~!|\\"})


@dataclass(frozen=True)
class Consolidation:
    path: Path
    package: str
    lines: list[str]
    headings: list[tuple[int, str]]


def read_consolidation(path: Path) -> Consolidation:
    lines = path.read_text(encoding="utf-8").splitlines()
    headings = _headings(lines)
    titles = [match for index, _ in headings if (match := PACKAGE.match(lines[index]))]
    if len(titles) != 1:
        raise ValueError(f"{path.name}: judul konsolidasi EVO harus tunggal.")
    return Consolidation(path, "EVO " + titles[0].group(1), lines, headings)


def tabulate_verdicts(paths: list[Path]) -> dict:
    """Baca vonis eksplisit dan beri lokasi bagian yang belum terbaca."""
    packages = set()
    verdicts = []
    unknown = []
    for path in paths:
        doc = read_consolidation(path)
        if doc.package in packages:
            raise ValueError(f"Konsolidasi paket ganda: {doc.package}.")
        packages.add(doc.package)
        unclassified = {}
        gates = set()
        for index, heading in doc.headings:
            if doc.lines[index].startswith("# "):
                continue
            gate = GATE.match(heading)
            explicit = VERDICT.search(heading) if gate else VERDICT.match(heading)
            fallback = (HEADLINE_VERDICT.search(heading) or TERMINAL_VERDICT.search(heading)) if gate else None
            gate_name = (
                " ".join(next(group for group in gate.groups() if group).upper().split())
                if gate else "PAKET"
            )
            source = {"file": path.as_posix(), "line": index + 1}
            if not (explicit or fallback):
                if gate and gate_name not in unclassified:
                    unclassified[gate_name] = source
                continue
            if gate_name in gates:
                raise ValueError(f"{doc.package}: vonis ganda untuk {gate_name}.")
            gates.add(gate_name)
            verdicts.append({"gate": gate_name, "package": doc.package,
                             "verdict": (explicit or fallback).group(1),
                             "source": source})
        unknown.extend({"gate": gate, "package": doc.package, "source": source}
                       for gate, source in unclassified.items() if gate not in gates)
        if not (gates or unclassified):
            unknown.append({"gate": "PAKET", "package": doc.package,
                            "source": {"file": path.as_posix(), "line": None}})
    return {"schema": "ace.evo-verdicts.v1",
            "rows": sorted(verdicts, key=lambda row: (row["gate"], row["package"])),
            "unknown": sorted(unknown, key=lambda row: (row["gate"], row["package"]))}


def _md_cell(text: str) -> str:
    return escape(text).translate(MARKDOWN)


def verdict_markdown(summary: dict) -> str:
    lines = ["# Vonis lintas paket EVO", "", "| Gate | Paket | Hasil | Sumber |",
             "| --- | --- | --- | --- |"]
    for row in sorted(summary["rows"] + summary["unknown"], key=lambda row: (row["gate"], row["package"])):
        source = row["source"]
        location = source["file"] if source["line"] is None else f"{source['file']}:{source['line']}"
        values = (row["gate"], row["package"], row.get("verdict", "TIDAK TAHU"), location)
        lines.append("| " + " | ".join(_md_cell(value) for value in values) + " |")
    return "\n".join(lines) + "\n"


def _read_metric(doc: Consolidation, selector: dict | None) -> dict | None:
    if selector is None:
        return None
    if not isinstance(selector, dict) or selector.keys() - {"line", "column", "format", "line_sha256"}:
        raise ValueError("Field selector metrik tidak dikenali.")
    line, column = selector.get("line"), selector.get("column")
    style = selector.get("format", "decimal")
    if type(line) is not int or not 1 <= line <= len(doc.lines):
        raise ValueError(f"{doc.package}: nomor baris selector di luar dokumen.")
    source_line = doc.lines[line - 1]
    digest = hashlib.sha256(source_line.encode("utf-8")).hexdigest()
    if "line_sha256" in selector and selector["line_sha256"] != digest:
        raise ValueError(f"{doc.package} baris {line}: SHA-256 baris berubah.")
    token = source_line.strip()
    if column is not None:
        if type(column) is not int or column < 1 or not token.startswith("|") or not token.endswith("|"):
            raise ValueError(f"{doc.package} baris {line}: selector kolom memerlukan baris tabel.")
        cells = token[1:-1].split("|")
        if column > len(cells) or r"\|" in token:
            raise ValueError(f"{doc.package} baris {line}: kolom tidak ada atau ambigu.")
        token = cells[column - 1].strip()
    if token.startswith("**") and token.endswith("**"):
        token = token[2:-2].strip()
    if style == "equals_decimal":
        left, separator, right = token.partition("=")
        if not separator or not re.fullmatch(r"[0-9]+\s*/\s*[1-9][0-9]*", left.strip()):
            raise ValueError(f"{doc.package} baris {line}: diharapkan pecahan = desimal.")
        token = right.strip()
    elif style == "decimal_comma":
        if "." in token:
            raise ValueError(f"{doc.package} baris {line}: format hanya menerima koma desimal.")
        token = token.replace(",", ".")
    elif style != "decimal":
        raise ValueError("Format selector tidak dikenali.")
    if len(token) > 64 or not NUMBER.fullmatch(token):
        raise ValueError(f"{doc.package} baris {line}: angka desimal eksplisit tidak ditemukan.")
    return {"value": format(Decimal(token), "f"),
            "source": {"file": doc.path.as_posix(), "line": line, "column": column, "line_sha256": digest}}


def compare_metrics(before: Path, after: Path, metrics: list) -> dict:
    """Hitung sesudah dikurangi sebelum berdasarkan selector eksplisit per dokumen."""
    first, second = read_consolidation(before), read_consolidation(after)
    if not isinstance(metrics, list) or not metrics:
        raise ValueError("Peta perbandingan wajib berupa daftar metrik berisi.")
    rows = {}
    for entry in metrics:
        if not isinstance(entry, dict) or set(entry) != {"name", "unit", "before", "after"}:
            raise ValueError("Setiap metrik memerlukan name, unit, before, dan after.")
        name, unit = entry["name"], entry["unit"]
        if not all(isinstance(value, str) and value.strip() and value.isprintable() for value in (name, unit)):
            raise ValueError("Nama dan satuan metrik wajib berupa teks berisi.")
        if name in rows:
            raise ValueError("Nama metrik ganda.")
        left = _read_metric(first, entry["before"])
        right = _read_metric(second, entry["after"])
        with localcontext() as ctx:
            # Input dibatasi 64 karakter per angka, sehingga pengurangan tetap eksak.
            ctx.prec = 130
            delta = format(Decimal(right["value"]) - Decimal(left["value"]), "f") if left and right else None
        rows[name] = {"name": name, "unit": unit, "before": left, "after": right, "delta": delta}
    return {"schema": "ace.evo-metric-diff.v1", "before_package": first.package,
            "after_package": second.package, "metrics": [rows[name] for name in sorted(rows)]}


def _unique_fields(pairs):
    data = dict(pairs)
    if len(data) != len(pairs):
        raise ValueError("Field JSON peta metrik ganda.")
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    verdicts = modes.add_parser("verdicts", help="Tabel gate × paket dengan lokasi vonis.")
    verdicts.add_argument("files", nargs="+", type=Path)
    verdicts.add_argument("--json", action="store_true", help="Keluarkan JSON.")
    compare = modes.add_parser("compare", help="Bandingkan metrik bernama dengan selector eksplisit.")
    compare.add_argument("before", type=Path)
    compare.add_argument("after", type=Path)
    compare.add_argument("--metrics", type=Path, required=True, help="Peta selector metrik JSON.")
    args = parser.parse_args(argv)
    try:
        if args.mode == "verdicts":
            result = tabulate_verdicts(args.files)
            if not args.json:
                print(verdict_markdown(result), end="")
                return 0
        else:
            metrics = json.loads(args.metrics.read_text(encoding="utf-8"), object_pairs_hook=_unique_fields)
            result = compare_metrics(args.before, args.after, metrics)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
