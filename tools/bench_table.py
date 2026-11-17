#!/usr/bin/env python3
"""Tabulator hasil benchmark JSONL menjadi tabel Markdown `mean ± stdev` per label.

Membaca berkas JSONL dengan field bebas per baris (minimal memiliki kunci
label dan metrik numerik), lalu menghitung jumlah sampel, rata-rata, dan
simpangan baku sampel per label untuk setiap metrik numerik.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import statistics
import sys
from typing import Any

BENCH_SCHEMA = "ace.bench-table.v1"


class BenchTableError(ValueError):
    """Kesalahan berkas masukan, format JSONL, atau field label benchmark."""


def _is_number(value: Any) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return math.isfinite(float(value))


def summarize_bench(
    jsonl_path: Path,
    *,
    label_key: str = "label",
) -> dict[str, Any]:
    """Muat JSONL benchmark dan hitung ringkasan `mean`, `stdev`, dan `n` per label."""
    if not jsonl_path.is_file():
        raise BenchTableError(f"Berkas benchmark tidak ditemukan: {jsonl_path}")

    try:
        raw_text = jsonl_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise BenchTableError(f"Gagal membaca '{jsonl_path}': {exc}") from exc

    grouped: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    row_counts: dict[str, int] = defaultdict(int)
    metrics_seen: set[str] = set()
    total_rows = 0

    for line_no, raw_line in enumerate(raw_text.splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped:
            continue
        try:
            obj = json.loads(stripped)
        except (json.JSONDecodeError, ValueError) as exc:
            detail = exc.msg if isinstance(exc, json.JSONDecodeError) else str(exc)
            raise BenchTableError(f"JSON tidak sah pada baris {line_no}: {detail}") from exc
        if not isinstance(obj, dict):
            raise BenchTableError(f"Baris {line_no} wajib berupa objek JSON.")

        raw_label = obj.get(label_key)
        if not isinstance(raw_label, str) or not raw_label.strip():
            raise BenchTableError(
                f"Baris {line_no} wajib memiliki field '{label_key}' berupa string non-kosong."
            )
        label = raw_label.strip()
        row_counts[label] += 1
        total_rows += 1

        for key, value in obj.items():
            if key == label_key:
                continue
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                try:
                    numeric = float(value)
                except OverflowError as exc:
                    raise BenchTableError(
                        f"Nilai metrik terlalu besar (overflow) pada baris {line_no} metrik '{key}'."
                    ) from exc
                if not math.isfinite(numeric):
                    raise BenchTableError(
                        f"Nilai non-finit pada baris {line_no} metrik '{key}': {value!r}"
                    )
                metrics_seen.add(key)
                grouped[label][key].append(numeric)

    if total_rows == 0:
        raise BenchTableError(f"Berkas benchmark kosong: {jsonl_path}")

    metric_names = sorted(metrics_seen)
    labels = sorted(row_counts)
    rows: list[dict[str, Any]] = []
    for label in labels:
        metric_stats: dict[str, dict[str, float | int]] = {}
        for metric in metric_names:
            vals = grouped[label].get(metric, [])
            if not vals:
                continue
            try:
                mean_val = statistics.fmean(vals)
                stdev_val = statistics.stdev(vals) if len(vals) >= 2 else 0.0
            except (OverflowError, ValueError) as exc:
                raise BenchTableError(
                    f"Overflow statistik pada label '{label}' metrik '{metric}': {exc}"
                ) from exc
            if not (math.isfinite(mean_val) and math.isfinite(stdev_val)):
                raise BenchTableError(
                    f"Statistik non-finit pada label '{label}' metrik '{metric}'."
                )
            metric_stats[metric] = {
                "n": len(vals),
                "mean": mean_val,
                "stdev": stdev_val,
            }
        rows.append(
            {
                "label": label,
                "n": row_counts[label],
                "metrics": metric_stats,
            }
        )

    return {
        "schema": BENCH_SCHEMA,
        "source": str(jsonl_path),
        "label_key": label_key,
        "total_rows": total_rows,
        "metrics": metric_names,
        "rows": rows,
    }


def render_markdown_table(summary: dict[str, Any], *, precision: int = 2) -> str:
    """Render ringkasan benchmark menjadi tabel Markdown `mean ± stdev`."""
    if precision < 0:
        raise BenchTableError("Precision tidak boleh negatif.")

    metrics: list[str] = summary["metrics"]
    headers = [summary["label_key"], "n", *metrics]
    sep = ["---", "---:", *("---:" for _ in metrics)]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(sep) + " |",
    ]
    fmt = f"{{:.{precision}f}}"
    for row in summary["rows"]:
        cells = [str(row["label"]), str(row["n"])]
        for metric in metrics:
            stat = row["metrics"].get(metric)
            if stat is None:
                cells.append("-")
            elif stat["n"] == 1:
                cells.append(f"{fmt.format(stat['mean'])} (n=1)")
            else:
                cells.append(f"{fmt.format(stat['mean'])} ± {fmt.format(stat['stdev'])}")
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Tabulator hasil benchmark JSONL menjadi tabel Markdown mean ± stdev."
    )
    parser.add_argument("jsonl_path", type=Path, help="Path berkas benchmark JSONL.")
    parser.add_argument(
        "--label-key",
        default="label",
        help="Nama field pengelompokan label (default: label).",
    )
    parser.add_argument(
        "--precision",
        type=int,
        default=2,
        help="Jumlah angka di belakang koma pada tabel Markdown (default: 2).",
    )
    parser.add_argument(
        "--format",
        choices=("markdown", "json"),
        default="markdown",
        help="Format keluaran: markdown atau json (default: markdown).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Tulis hasil ke berkas alih-alih hanya stdout.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Titik masuk CLI bench tabulator."""
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
        summary = summarize_bench(args.jsonl_path, label_key=args.label_key)
        if args.format == "json":
            rendered = json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
        else:
            rendered = render_markdown_table(summary, precision=args.precision)
        if args.output is not None:
            args.output.write_text(rendered, encoding="utf-8")
        print(rendered, end="")
        return 0
    except SystemExit as exc:
        return 0 if exc.code == 0 else 2
    except (OSError, BenchTableError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
