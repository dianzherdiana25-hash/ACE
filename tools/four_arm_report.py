#!/usr/bin/env python3
"""Pengemas analisis empat-lengan EVO 0007 (pattern / receipt / sham / tanpa-konteks).

Membaca hasil keempat lengan dari satu atau lebih berkas JSONL/JSON, menghitung
accept-rate, skor rata-rata, dan pemeriksaan gerbang delivery per lengan
(lengan berkonteks dengan delivery < 75% berstatus `TIDAK_TERANTAR`, bukan nol).
Keluaran bersifat ringkasan deskriptif komparatif, BUKAN putusan ilmiah.
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

FOUR_ARM_SCHEMA = "ace.four-arm-report.v1"
DELIVERY_THRESHOLD = 0.75
REQUIRED_ARMS = ("pattern", "receipt", "sham", "no_context")
CONTEXT_ARMS = frozenset({"pattern", "receipt", "sham"})

_ARM_ALIASES = {
    "pattern": "pattern",
    "pola": "pattern",
    "distilled": "pattern",
    "pattern_distilled": "pattern",
    "receipt": "receipt",
    "kuitansi": "receipt",
    "sham": "sham",
    "no_context": "no_context",
    "no-context": "no_context",
    "tanpa_konteks": "no_context",
    "tanpa-konteks": "no_context",
    "none": "no_context",
    "baseline": "no_context",
}


class FourArmReportError(ValueError):
    """Kesalahan berkas masukan, nama lengan, atau format JSON hasil empat lengan."""


def _normalize_arm_name(raw: Any) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise FourArmReportError(f"Nama lengan tidak sah: {raw!r}")
    key = raw.strip().lower().replace(" ", "_")
    if key not in _ARM_ALIASES:
        raise FourArmReportError(
            f"Lengan '{raw}' tidak dikenal; wajib salah satu dari {list(REQUIRED_ARMS)}."
        )
    return _ARM_ALIASES[key]


def _is_delivered(row: dict[str, Any]) -> bool:
    for key in ("context_delivered", "delivered", "recall_delivered"):
        val = row.get(key)
        if isinstance(val, bool):
            return val
    recall_hits = row.get("recall_hits")
    if isinstance(recall_hits, int) and not isinstance(recall_hits, bool):
        return recall_hits > 0
    ctx = row.get("context") or row.get("injected_context")
    if isinstance(ctx, str):
        return bool(ctx.strip())
    return False


def _is_accepted(row: dict[str, Any]) -> bool:
    for key in ("accepted", "ratified", "passed"):
        val = row.get(key)
        if isinstance(val, bool):
            return val
    for key in ("status", "verdict", "decision"):
        val = row.get(key)
        if isinstance(val, str) and val.strip().upper() in {"ACCEPTED", "RATIFIED", "PASS", "PASSED"}:
            return True
    return False


def _finite_float(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        f = float(value)
    except OverflowError:
        return None
    return f if math.isfinite(f) else None


def _load_rows(paths: list[Path], *, arm_override: str | None = None) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for path in paths:
        if not path.is_file():
            raise FourArmReportError(f"Berkas hasil lengan tidak ditemukan: {path}")
        try:
            raw_text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise FourArmReportError(f"Gagal membaca '{path}': {exc}") from exc

        stripped = raw_text.strip()
        if not stripped:
            raise FourArmReportError(f"Berkas hasil lengan kosong: {path}")

        rows: list[dict[str, Any]] = []
        parsed_single = None
        if not path.name.endswith(".jsonl"):
            try:
                parsed_single = json.loads(stripped)
            except (json.JSONDecodeError, ValueError):
                parsed_single = None

        if isinstance(parsed_single, list):
            for idx, item in enumerate(parsed_single, start=1):
                if not isinstance(item, dict):
                    raise FourArmReportError(f"Entri #{idx} pada '{path}' bukan objek JSON.")
                rows.append(item)
        elif isinstance(parsed_single, dict) and any(k in parsed_single for k in ("episodes", "records", "results")):
            seq = next(parsed_single[k] for k in ("episodes", "records", "results") if isinstance(parsed_single.get(k), list))
            for idx, item in enumerate(seq, start=1):
                if not isinstance(item, dict):
                    raise FourArmReportError(f"Entri #{idx} pada '{path}' bukan objek JSON.")
                rows.append(item)
        else:
            for line_no, raw_line in enumerate(raw_text.splitlines(), start=1):
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except (json.JSONDecodeError, ValueError) as exc:
                    raise FourArmReportError(f"JSONL rusak pada '{path}' baris {line_no}: {exc}") from exc
                if not isinstance(obj, dict):
                    raise FourArmReportError(f"Baris {line_no} '{path}' wajib berupa objek JSON.")
                rows.append(obj)

        for row in rows:
            raw_arm = arm_override if arm_override is not None else row.get("arm")
            arm = _normalize_arm_name(raw_arm)
            grouped[arm].append(row)
    return grouped


def analyze_four_arms(
    arm_inputs: dict[str, list[Path]] | list[Path],
    *,
    delivery_threshold: float = DELIVERY_THRESHOLD,
) -> dict[str, Any]:
    """Analisis hasil empat lengan beserta pemeriksaan gerbang delivery >= 75%."""
    if not 0.0 < delivery_threshold <= 1.0:
        raise FourArmReportError("delivery_threshold harus di rentang (0, 1].")

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    if isinstance(arm_inputs, dict):
        for raw_arm, paths in arm_inputs.items():
            arm = _normalize_arm_name(raw_arm)
            loaded = _load_rows(paths, arm_override=arm)
            grouped[arm].extend(loaded[arm])
    else:
        grouped = _load_rows(arm_inputs)

    missing_arms = [arm for arm in REQUIRED_ARMS if not grouped.get(arm)]
    if missing_arms:
        raise FourArmReportError(f"Hasil empat lengan belum lengkap; lengan kosong/hilang: {missing_arms}")

    arms_summary: dict[str, dict[str, Any]] = {}
    blocked_arms: list[str] = []

    for arm in REQUIRED_ARMS:
        rows = grouped[arm]
        total = len(rows)
        errors = 0
        valid_rows: list[dict[str, Any]] = []
        for row in rows:
            err = row.get("error")
            if err is not None and str(err).strip() != "":
                errors += 1
            else:
                valid_rows.append(row)

        valid_count = len(valid_rows)
        accepted = sum(1 for r in valid_rows if _is_accepted(r))
        delivered = sum(1 for r in valid_rows if _is_delivered(r))
        accepted_when_delivered = sum(
            1 for r in valid_rows if _is_delivered(r) and _is_accepted(r)
        )
        scores = [s for s in (_finite_float(r.get("score")) for r in valid_rows) if s is not None]

        accept_rate = round(accepted / valid_count, 4) if valid_count else 0.0
        delivery_rate = round(delivered / valid_count, 4) if valid_count else 0.0
        accept_when_delivered_rate = round(accepted_when_delivered / delivered, 4) if delivered else None

        if arm in CONTEXT_ARMS:
            if valid_count == 0 or delivery_rate < delivery_threshold:
                gate_status = "TIDAK_TERANTAR"
                blocked_arms.append(arm)
            else:
                gate_status = "TERANTAR"
        else:
            gate_status = "TANPA_KONTEKS"

        arms_summary[arm] = {
            "total_rows": total,
            "valid_rows": valid_count,
            "error_rows": errors,
            "accepted_count": accepted,
            "accept_rate": accept_rate,
            "delivered_count": delivered,
            "delivery_rate": delivery_rate,
            "delivery_gate_status": gate_status,
            "accepted_when_delivered_count": accepted_when_delivered,
            "accept_rate_when_delivered": accept_when_delivered_rate,
            "mean_score": round(statistics.fmean(scores), 4) if scores else None,
        }

    def _pair_delta(a: str, b: str) -> dict[str, Any]:
        sa = arms_summary[a]
        sb = arms_summary[b]
        blocked = [x for x in (a, b) if arms_summary[x]["delivery_gate_status"] == "TIDAK_TERANTAR"]
        return {
            "lhs": a,
            "rhs": b,
            "accept_rate_delta": round(sa["accept_rate"] - sb["accept_rate"], 4),
            "comparable": len(blocked) == 0,
            "blocked_reason": (
                f"TIDAK_TERANTAR_BUKAN_NOL: lengan {blocked} di bawah ambang delivery {delivery_threshold:.0%}"
                if blocked
                else None
            ),
        }

    return {
        "schema": FOUR_ARM_SCHEMA,
        "delivery_threshold": delivery_threshold,
        "all_context_arms_delivered": len(blocked_arms) == 0,
        "undelivered_arms": blocked_arms,
        "arms": arms_summary,
        "comparisons": {
            "pattern_vs_no_context": _pair_delta("pattern", "no_context"),
            "pattern_vs_receipt": _pair_delta("pattern", "receipt"),
            "pattern_vs_sham": _pair_delta("pattern", "sham"),
            "receipt_vs_no_context": _pair_delta("receipt", "no_context"),
            "sham_vs_no_context": _pair_delta("sham", "no_context"),
        },
        "scientific_verdict": "NOT_ASSESSED",
        "note": "Ringkasan deskriptif empat-lengan; lengan <75% delivery ditandai TIDAK_TERANTAR (bukan nol).",
    }


def render_markdown_report(report: dict[str, Any]) -> str:
    """Format laporan empat-lengan menjadi ringkasan Markdown."""
    lines = [
        "# Laporan Perbandingan Empat-Lengan EVO 0007",
        "",
        f"- Ambang gerbang delivery: `{report['delivery_threshold']:.0%}`",
        f"- Status gerbang konteks: `{'LULUS_SEMUA' if report['all_context_arms_delivered'] else 'TIDAK_TERANTAR: ' + ', '.join(report['undelivered_arms'])}`",
        f"- Putusan ilmiah: `{report['scientific_verdict']}`",
        "",
        "| Lengan | Valid | Accept Rate | Delivered | Delivery Rate | Gate Delivery | Mean Score |",
        "| --- | ---: | ---: | ---: | ---: | --- | ---: |",
    ]
    for arm in REQUIRED_ARMS:
        s = report["arms"][arm]
        score_str = f"{s['mean_score']:.2f}" if s["mean_score"] is not None else "-"
        lines.append(
            f"| `{arm}` | {s['valid_rows']} | {s['accept_rate']:.2%} | {s['delivered_count']} | "
            f"{s['delivery_rate']:.2%} | `{s['delivery_gate_status']}` | {score_str} |"
        )
    lines.extend(["", "## Perbandingan Pasangan", ""])
    for name, cmp_info in report["comparisons"].items():
        status = "sah" if cmp_info["comparable"] else f"TERBLOKIR ({cmp_info['blocked_reason']})"
        lines.append(
            f"- `{name}`: delta accept-rate `{cmp_info['accept_rate_delta']:+.2%}` — {status}"
        )
    return "\n".join(lines) + "\n"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Pengemas analisis empat-lengan EVO 0007 beserta pemeriksaan gerbang delivery."
    )
    parser.add_argument("inputs", nargs="*", type=Path, help="Berkas JSON/JSONL gabungan yang memiliki field 'arm'.")
    parser.add_argument("--pattern", type=Path, action="append", default=[], help="Berkas hasil lengan pattern.")
    parser.add_argument("--receipt", type=Path, action="append", default=[], help="Berkas hasil lengan receipt.")
    parser.add_argument("--sham", type=Path, action="append", default=[], help="Berkas hasil lengan sham.")
    parser.add_argument("--no-context", type=Path, action="append", default=[], help="Berkas hasil lengan tanpa-konteks.")
    parser.add_argument("--delivery-threshold", type=float, default=DELIVERY_THRESHOLD, help="Ambang gerbang delivery (default: 0.75).")
    parser.add_argument("--format", choices=("json", "markdown", "both"), default="both", help="Format keluaran.")
    parser.add_argument("--strict-delivery", action="store_true", help="Keluar dengan kode 1 bila ada lengan berkonteks TIDAK_TERANTAR.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
        explicit = {
            "pattern": args.pattern,
            "receipt": args.receipt,
            "sham": args.sham,
            "no_context": args.no_context,
        }
        has_explicit = any(explicit.values())
        if has_explicit and args.inputs:
            raise FourArmReportError("Gunakan salah satu: argumen posisi gabungan ATAU flag per lengan (--pattern/--receipt/--sham/--no-context).")
        if has_explicit:
            report = analyze_four_arms(explicit, delivery_threshold=args.delivery_threshold)
        elif args.inputs:
            report = analyze_four_arms(args.inputs, delivery_threshold=args.delivery_threshold)
        else:
            raise FourArmReportError("Berikan berkas hasil empat lengan sebagai masukan.")

        if args.format in ("both", "markdown"):
            print(render_markdown_report(report), end="")
        if args.format == "both":
            print("\n--- JSON ---")
        if args.format in ("both", "json"):
            print(json.dumps(report, ensure_ascii=False, indent=2))

        if args.strict_delivery and not report["all_context_arms_delivered"]:
            return 1
        return 0
    except SystemExit as exc:
        return 0 if exc.code == 0 else 2
    except (OSError, FourArmReportError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
