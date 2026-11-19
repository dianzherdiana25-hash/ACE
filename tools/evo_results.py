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


def compare_metrics(
    before: Path,
    after: Path,
    metrics: list,
    *,
    scope_notes: dict | list | None = None,
) -> dict:
    """Hitung sesudah dikurangi sebelum beserta catatan cakupan & satuan per pasangan paket."""
    first, second = read_consolidation(before), read_consolidation(after)
    if not isinstance(metrics, list) or not metrics:
        raise ValueError("Peta perbandingan wajib berupa daftar metrik berisi.")
    required_keys = {"name", "unit", "before", "after"}
    optional_keys = {
        "before_unit",
        "after_unit",
        "scope_note",
        "before_population",
        "after_population",
        "comparable",
    }
    allowed_keys = required_keys | optional_keys
    rows = {}
    metric_scope_notes = []
    for entry in metrics:
        if not isinstance(entry, dict) or not required_keys.issubset(entry) or (set(entry) - allowed_keys):
            raise ValueError("Setiap metrik memerlukan name, unit, before, dan after.")
        name, unit = entry["name"], entry["unit"]
        if not all(isinstance(value, str) and value.strip() and value.isprintable() for value in (name, unit)):
            raise ValueError("Nama dan satuan metrik wajib berupa teks berisi.")
        if name in rows:
            raise ValueError("Nama metrik ganda.")

        before_unit = entry.get("before_unit", unit)
        after_unit = entry.get("after_unit", unit)
        for u_label in (before_unit, after_unit):
            if not isinstance(u_label, str) or not u_label.strip() or not u_label.isprintable():
                raise ValueError(f"Metrik '{name}': before_unit/after_unit wajib berupa teks berisi.")
        declared_comparable = entry.get("comparable", True)
        if type(declared_comparable) is not bool:
            raise ValueError(f"Metrik '{name}': comparable wajib bool.")
        units_match = before_unit.strip().casefold() == after_unit.strip().casefold()
        is_comparable = declared_comparable and units_match

        left = _read_metric(first, entry["before"])
        right = _read_metric(second, entry["after"])
        incomparable_reason = None
        if not units_match:
            incomparable_reason = f"unit_mismatch: {before_unit} != {after_unit}"
        elif not declared_comparable:
            incomparable_reason = "population_or_scope_mismatch"

        if left and right and is_comparable:
            with localcontext() as ctx:
                # Input dibatasi 64 karakter per angka, sehingga pengurangan tetap eksak.
                ctx.prec = 130
                delta = format(Decimal(right["value"]) - Decimal(left["value"]), "f")
        else:
            delta = None

        row = {
            "name": name,
            "unit": unit,
            "before_unit": before_unit,
            "after_unit": after_unit,
            "comparable": is_comparable,
            "before": left,
            "after": right,
            "delta": delta,
        }
        if incomparable_reason is not None:
            row["incomparable_reason"] = incomparable_reason
        if "scope_note" in entry:
            if not isinstance(entry["scope_note"], str) or not entry["scope_note"].strip():
                raise ValueError(f"Metrik '{name}': scope_note wajib teks non-kosong jika ada.")
            row["scope_note"] = entry["scope_note"].strip()
        if "before_population" in entry:
            row["before_population"] = entry["before_population"]
        if "after_population" in entry:
            row["after_population"] = entry["after_population"]
        rows[name] = row

        metric_scope_notes.append({
            "metric": name,
            "unit": unit,
            "before_unit": before_unit,
            "after_unit": after_unit,
            "comparable": is_comparable,
            "incomparable_reason": incomparable_reason,
            "scope_note": row.get("scope_note"),
            "before_population": row.get("before_population"),
            "after_population": row.get("after_population"),
        })

    pair_key = f"{first.package} -> {second.package}"
    return {
        "schema": "ace.evo-metric-diff.v1",
        "package_pair": pair_key,
        "before_package": first.package,
        "after_package": second.package,
        "metrics": [rows[name] for name in sorted(rows)],
        "scope_notes": {
            "package_pair": pair_key,
            "pair_notes": scope_notes if scope_notes is not None else {},
            "metric_notes": sorted(metric_scope_notes, key=lambda item: item["metric"]),
        },
    }


def compare_package_matrix(pairs: list[dict], *, base_dir: Path | None = None) -> dict:
    """Bandingkan beberapa pasangan paket EVO beserta catatan cakupan & satuan per pasangan."""
    if not isinstance(pairs, list) or not pairs:
        raise ValueError("Matriks perbandingan pasangan paket wajib tidak kosong.")
    comparisons = []
    scope_notes_by_pair = {}
    seen_pairs = set()
    for idx, spec in enumerate(pairs):
        if not isinstance(spec, dict):
            raise ValueError(f"Spesifikasi pasangan #{idx} wajib objek JSON.")
        before_raw = spec.get("before")
        after_raw = spec.get("after")
        metrics = spec.get("metrics")
        if not isinstance(before_raw, str) or not isinstance(after_raw, str):
            raise ValueError(f"Spesifikasi pasangan #{idx} wajib mencantumkan before dan after.")
        before_path = Path(before_raw)
        after_path = Path(after_raw)
        if base_dir is not None:
            if not before_path.is_absolute():
                before_path = base_dir / before_path
            if not after_path.is_absolute():
                after_path = base_dir / after_path
        diff = compare_metrics(
            before_path,
            after_path,
            metrics,
            scope_notes=spec.get("scope_notes"),
        )
        pair_key = diff["package_pair"]
        if pair_key in seen_pairs:
            raise ValueError(f"Pasangan paket ganda pada matriks: {pair_key}.")
        seen_pairs.add(pair_key)
        comparisons.append(diff)
        scope_notes_by_pair[pair_key] = diff["scope_notes"]
    comparisons.sort(key=lambda item: item["package_pair"])
    return {
        "schema": "ace.evo-metric-matrix.v1",
        "pair_count": len(comparisons),
        "scope_notes_by_pair": {k: scope_notes_by_pair[k] for k in sorted(scope_notes_by_pair)},
        "comparisons": comparisons,
    }


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
    matrix = modes.add_parser("compare-matrix", help="Bandingkan beberapa pasangan paket & simpan catatan cakupan.")
    matrix.add_argument("spec", type=Path, help="JSON daftar pasangan paket + metrik + scope_notes.")
    args = parser.parse_args(argv)
    try:
        if args.mode == "verdicts":
            result = tabulate_verdicts(args.files)
            if not args.json:
                print(verdict_markdown(result), end="")
                return 0
        elif args.mode == "compare":
            raw_spec = json.loads(args.metrics.read_text(encoding="utf-8"), object_pairs_hook=_unique_fields)
            if isinstance(raw_spec, dict):
                result = compare_metrics(
                    args.before,
                    args.after,
                    raw_spec.get("metrics"),
                    scope_notes=raw_spec.get("scope_notes"),
                )
            else:
                result = compare_metrics(args.before, args.after, raw_spec)
        else:
            raw_matrix = json.loads(args.spec.read_text(encoding="utf-8"), object_pairs_hook=_unique_fields)
            result = compare_package_matrix(raw_matrix, base_dir=args.spec.parent)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
