#!/usr/bin/env python3
"""Sensus hasil layar/ukur JSONL ACE (berpasangan A/B dan sebaran pita skor).

Membaca satu atau lebih berkas JSONL hasil screening/ukur dengan field:
- ``id`` (wajib string tidak kosong)
- ``ratified`` (boolean) atau ``score`` (angka 0..100)
- ``task_kind`` (opsional; default ``unknown``)
- ``run`` (opsional, mis. ``A``/``B``)
- ``error`` (opsional; bila ada dan tidak kosong, baris dihitung invalid terpisah)

Baris yang rusak (JSON tidak sah), kekurangan field, memiliki ``error`` aktif,
atau nilai ``score`` di luar [0, 100] dipisahkan ke hitungan invalid dan tidak
pernah diikutkan sebagai hasil ukur.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import sys
from typing import Any

SCORE_BANDS = ("0-39", "40-44", "45-75", "76-100")


class CensusInputError(ValueError):
    """Kesalahan argumen CLI atau berkas masukan yang tidak dapat dibaca."""


def _is_valid_score(value: Any) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        numeric = float(value)
    except (OverflowError, TypeError, ValueError):
        return False
    if not math.isfinite(numeric):
        return False
    return 0.0 <= numeric <= 100.0


def _score_band(score: float) -> str:
    if score < 40.0:
        return "0-39"
    if score < 45.0:
        return "40-44"
    if score <= 75.0:
        return "45-75"
    return "76-100"


def _empty_bucket() -> dict[str, Any]:
    return {
        "valid_rows": 0,
        "invalid_rows": 0,
        "paired": {
            "total_episodes": 0,
            "always_pass": 0,
            "always_fail": 0,
            "split": 0,
            "single_observation": 0,
        },
        "score_bands": {band: 0 for band in SCORE_BANDS},
        "scored_rows": 0,
    }


def compute_census(paths: list[Path]) -> dict[str, Any]:
    """Hitung sensus hasil layar/ukur dari satu atau lebih berkas JSONL."""
    if not paths:
        raise CensusInputError("Minimal satu berkas JSONL harus diberikan.")

    per_kind: dict[str, dict[str, Any]] = defaultdict(_empty_bucket)
    overall = _empty_bucket()
    invalid_details: list[dict[str, Any]] = []

    # Kelompokkan baris ratified valid berdasarkan (task_kind, id) untuk analisis A/B.
    paired_obs: dict[tuple[str, str], list[bool]] = defaultdict(list)

    total_lines = 0
    for path in paths:
        if not path.is_file():
            raise CensusInputError(f"Berkas tidak ditemukan: {path}")
        try:
            raw_text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise CensusInputError(f"Gagal membaca berkas '{path}': {exc}") from exc

        for line_no, raw_line in enumerate(raw_text.splitlines(), start=1):
            total_lines += 1
            if not raw_line.strip():
                overall["invalid_rows"] += 1
                per_kind["unknown"]["invalid_rows"] += 1
                invalid_details.append(
                    {"file": str(path), "line": line_no, "id": "", "reason": "baris_kosong"}
                )
                continue

            try:
                obj = json.loads(raw_line)
            except (json.JSONDecodeError, ValueError) as exc:
                reason = exc.msg if isinstance(exc, json.JSONDecodeError) else str(exc)
                overall["invalid_rows"] += 1
                per_kind["unknown"]["invalid_rows"] += 1
                invalid_details.append(
                    {
                        "file": str(path),
                        "line": line_no,
                        "id": "",
                        "reason": f"json_tidak_sah: {reason}",
                    }
                )
                continue

            if not isinstance(obj, dict):
                overall["invalid_rows"] += 1
                per_kind["unknown"]["invalid_rows"] += 1
                invalid_details.append(
                    {"file": str(path), "line": line_no, "id": "", "reason": "bukan_objek_json"}
                )
                continue

            raw_tk = obj.get("task_kind")
            task_kind = raw_tk.strip() if isinstance(raw_tk, str) and raw_tk.strip() else "unknown"
            raw_id = obj.get("id")
            item_id = raw_id.strip() if isinstance(raw_id, str) and raw_id.strip() else ""

            def mark_invalid(reason: str) -> None:
                overall["invalid_rows"] += 1
                per_kind[task_kind]["invalid_rows"] += 1
                invalid_details.append(
                    {
                        "file": str(path),
                        "line": line_no,
                        "id": item_id,
                        "task_kind": task_kind,
                        "reason": reason,
                    }
                )

            if not item_id:
                mark_invalid("id_kosong_atau_tidak_sah")
                continue

            err_val = obj.get("error")
            if err_val is not None and str(err_val).strip() != "":
                mark_invalid(f"error_row: {err_val}")
                continue

            raw_score = obj.get("score")
            if raw_score is None and "judge_score" in obj:
                raw_score = obj.get("judge_score")
            has_ratified = "ratified" in obj and obj["ratified"] is not None
            has_score = raw_score is not None
            if not has_ratified and not has_score:
                mark_invalid("tanpa_ratified_atau_score")
                continue

            if has_ratified and not isinstance(obj["ratified"], bool):
                mark_invalid("ratified_bukan_boolean")
                continue

            if has_score and not _is_valid_score(raw_score):
                mark_invalid("score_di_luar_rentang_0_100")
                continue

            # Baris valid: catat ke metrik hasil ukur.
            overall["valid_rows"] += 1
            per_kind[task_kind]["valid_rows"] += 1

            if has_ratified:
                paired_obs[(task_kind, item_id)].append(bool(obj["ratified"]))

            if has_score:
                band = _score_band(float(raw_score))
                overall["score_bands"][band] += 1
                overall["scored_rows"] += 1
                per_kind[task_kind]["score_bands"][band] += 1
                per_kind[task_kind]["scored_rows"] += 1

    # Hitung agregasi A/B per (task_kind, id).
    split_ids: list[dict[str, Any]] = []
    for (task_kind, item_id), outcomes in sorted(paired_obs.items()):
        bucket = per_kind[task_kind]["paired"]
        bucket["total_episodes"] += 1
        overall["paired"]["total_episodes"] += 1
        if len(outcomes) < 2:
            bucket["single_observation"] += 1
            overall["paired"]["single_observation"] += 1
        elif all(outcomes):
            bucket["always_pass"] += 1
            overall["paired"]["always_pass"] += 1
        elif not any(outcomes):
            bucket["always_fail"] += 1
            overall["paired"]["always_fail"] += 1
        else:
            bucket["split"] += 1
            overall["paired"]["split"] += 1
            split_ids.append({"id": item_id, "task_kind": task_kind, "outcomes": outcomes})

    return {
        "files": [str(p) for p in paths],
        "total_lines": total_lines,
        "overall": overall,
        "by_task_kind": {k: per_kind[k] for k in sorted(per_kind)},
        "split_episodes": split_ids,
        "invalid_details": invalid_details,
    }


def format_text_table(census: dict[str, Any]) -> str:
    """Format sensus menjadi tabel teks ringkas yang mudah dibaca manusia."""
    lines: list[str] = []
    lines.append("=== SENSUS HASIL LAYAR/UKUR ACE ===")
    lines.append(f"Berkas     : {', '.join(census['files'])}")
    lines.append(
        f"Total baris: {census['total_lines']} "
        f"(valid={census['overall']['valid_rows']}, invalid={census['overall']['invalid_rows']})"
    )
    lines.append("")

    # Tabel pasangan A/B (ratified)
    lines.append("1) Sensus Pasangan A/B (ratified)")
    header_ab = f"{'task_kind':<12} {'episode':>7} {'lolos':>7} {'gagal':>7} {'belah':>7} {'tunggal':>7} {'invalid':>7}"
    lines.append(header_ab)
    lines.append("-" * len(header_ab))
    for tk, data in census["by_task_kind"].items():
        p = data["paired"]
        lines.append(
            f"{tk:<12} {p['total_episodes']:>7} {p['always_pass']:>7} "
            f"{p['always_fail']:>7} {p['split']:>7} {p['single_observation']:>7} {data['invalid_rows']:>7}"
        )
    po = census["overall"]["paired"]
    lines.append("-" * len(header_ab))
    lines.append(
        f"{'TOTAL':<12} {po['total_episodes']:>7} {po['always_pass']:>7} "
        f"{po['always_fail']:>7} {po['split']:>7} {po['single_observation']:>7} {census['overall']['invalid_rows']:>7}"
    )
    lines.append("")

    # Tabel sebaran pita skor
    lines.append("2) Sebaran Pita Skor (0-100)")
    header_sc = f"{'task_kind':<12} {'scored':>7} {'[0-39]':>7} {'[40-44]':>8} {'[45-75]':>8} {'[76-100]':>9}"
    lines.append(header_sc)
    lines.append("-" * len(header_sc))
    for tk, data in census["by_task_kind"].items():
        b = data["score_bands"]
        lines.append(
            f"{tk:<12} {data['scored_rows']:>7} {b['0-39']:>7} "
            f"{b['40-44']:>8} {b['45-75']:>8} {b['76-100']:>9}"
        )
    bo = census["overall"]["score_bands"]
    lines.append("-" * len(header_sc))
    lines.append(
        f"{'TOTAL':<12} {census['overall']['scored_rows']:>7} {bo['0-39']:>7} "
        f"{bo['40-44']:>8} {bo['45-75']:>8} {bo['76-100']:>9}"
    )
    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Sensus hasil layar/ukur JSONL ACE (pasangan A/B dan pita skor)."
    )
    parser.add_argument("files", nargs="+", type=Path, help="Satu atau lebih berkas JSONL hasil ukur")
    parser.add_argument(
        "--format",
        choices=("both", "text", "json"),
        default="both",
        help="Format keluaran: both (default), text, atau json",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Titik masuk CLI sensus layar/ukur."""
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
        census = compute_census(args.files)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 2
    except CensusInputError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if args.format in ("both", "text"):
        print(format_text_table(census))
    if args.format == "both":
        print("\n--- JSON ---")
    if args.format in ("both", "json"):
        print(json.dumps(census, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
