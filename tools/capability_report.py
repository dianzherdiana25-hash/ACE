"""Laporan kapabilitas satu halaman dari papan gate dan statistik store.

Dibuat terpisah sebagai perkakas baca-saja atas JSON papan gate serta JSON
statistik OperationalStore. Ketentuan kejujuran mutlak: setiap gate, bukti
(evidence), hitungan gap, atau laju eksekusi yang datanya tidak tersedia
wajib dicetak sebagai ``"belum diketahui"`` dan tidak pernah dikarang atau
diisi angka default palsu.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


SCHEMA = "ace.capability-report.v1"
UNKNOWN = "belum diketahui"
DEFAULT_GATES: tuple[str, ...] = ("G1", "G2", "G3", "G4", "G5")


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _clean_text(value: Any) -> str:
    if value is None:
        return UNKNOWN
    if isinstance(value, str):
        stripped = value.strip()
        return stripped if stripped else UNKNOWN
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        parts = [str(item).strip() for item in value if str(item).strip()]
        return ", ".join(parts) if parts else UNKNOWN
    return str(value)


def _extract_gates_map(gate_board: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    raw_gates = gate_board.get("gates")
    mapping: dict[str, Mapping[str, Any]] = {}
    if isinstance(raw_gates, Mapping):
        for gate_id, payload in raw_gates.items():
            if isinstance(payload, Mapping):
                mapping[str(gate_id)] = payload
    elif isinstance(raw_gates, list):
        for item in raw_gates:
            if isinstance(item, Mapping):
                gate_id = item.get("gate") or item.get("id") or item.get("name")
                if gate_id:
                    mapping[str(gate_id)] = item
    else:
        for key, payload in gate_board.items():
            if isinstance(payload, Mapping) and str(key).upper().startswith("G"):
                mapping[str(key)] = payload
    return mapping


def _extract_gap_summary(store_stats: Mapping[str, Any]) -> dict[str, Any]:
    gaps_block = store_stats.get("gaps")
    src = gaps_block if isinstance(gaps_block, Mapping) else store_stats

    open_val = src.get("open", src.get("open_gaps"))
    closed_val = src.get("closed", src.get("closed_gaps"))
    total_val = src.get("total", src.get("total_gaps"))

    open_out: Any = int(open_val) if _is_number(open_val) else UNKNOWN
    closed_out: Any = int(closed_val) if _is_number(closed_val) else UNKNOWN
    if _is_number(total_val):
        total_out: Any = int(total_val)
    elif _is_number(open_val) and _is_number(closed_val):
        total_out = int(open_val) + int(closed_val)
    else:
        total_out = UNKNOWN

    return {
        "open": open_out,
        "closed": closed_out,
        "total": total_out,
    }


def _extract_execution_summary(store_stats: Mapping[str, Any]) -> dict[str, Any]:
    exec_block = store_stats.get("execution")
    if not isinstance(exec_block, Mapping):
        exec_block = store_stats.get("director")
    src = exec_block if isinstance(exec_block, Mapping) else store_stats

    executed = src.get("executed", src.get("total_attempts", src.get("attempts")))
    succeeded = src.get("succeeded", src.get("completed"))
    failed = src.get("failed")
    rate = src.get("execution_rate", src.get("success_rate"))

    executed_out: Any = int(executed) if _is_number(executed) else UNKNOWN
    succeeded_out: Any = int(succeeded) if _is_number(succeeded) else UNKNOWN
    failed_out: Any = int(failed) if _is_number(failed) else UNKNOWN

    if _is_number(rate):
        rate_out: Any = round(float(rate), 4)
    elif _is_number(executed) and int(executed) > 0 and _is_number(succeeded):
        rate_out = round(float(succeeded) / float(executed), 4)
    else:
        rate_out = UNKNOWN

    return {
        "executed": executed_out,
        "succeeded": succeeded_out,
        "failed": failed_out,
        "execution_rate": rate_out,
    }


def build_capability_report(
    gate_board: Mapping[str, Any],
    store_stats: Mapping[str, Any],
    *,
    expected_gates: Sequence[str] = DEFAULT_GATES,
) -> dict[str, Any]:
    """Bangun struktur laporan kapabilitas JSON dengan penanda ``belum diketahui``."""
    gate_map = _extract_gates_map(gate_board)
    ordered_gates: list[str] = list(expected_gates)
    for extra in sorted(gate_map):
        if extra not in ordered_gates:
            ordered_gates.append(extra)

    gates_out: list[dict[str, Any]] = []
    unknown_fields: list[str] = []

    for gate_id in ordered_gates:
        entry = gate_map.get(gate_id)
        if not isinstance(entry, Mapping):
            row = {
                "gate": gate_id,
                "status": UNKNOWN,
                "evidence": UNKNOWN,
                "measured_at": UNKNOWN,
            }
        else:
            evidence_raw = entry.get("evidence")
            if evidence_raw is None:
                evidence_raw = entry.get("evidence_ref")
            if evidence_raw is None:
                evidence_raw = entry.get("evidence_refs")
            row = {
                "gate": gate_id,
                "status": _clean_text(entry.get("status")),
                "evidence": _clean_text(evidence_raw),
                "measured_at": _clean_text(
                    entry.get("measured_at", entry.get("date", entry.get("updated_at")))
                ),
            }
        if row["status"] == UNKNOWN:
            unknown_fields.append(f"gates.{gate_id}.status")
        if row["evidence"] == UNKNOWN:
            unknown_fields.append(f"gates.{gate_id}.evidence")
        gates_out.append(row)

    gaps_out = _extract_gap_summary(store_stats)
    for field in ("open", "closed", "total"):
        if gaps_out[field] == UNKNOWN:
            unknown_fields.append(f"gaps.{field}")

    exec_out = _extract_execution_summary(store_stats)
    for field in ("executed", "succeeded", "failed", "execution_rate"):
        if exec_out[field] == UNKNOWN:
            unknown_fields.append(f"execution.{field}")

    subject = _clean_text(
        gate_board.get("subject")
        or store_stats.get("subject")
        or gate_board.get("release")
        or store_stats.get("home_id")
    )
    measured_at = _clean_text(
        gate_board.get("measured_at")
        or store_stats.get("measured_at")
        or gate_board.get("generated_at")
        or store_stats.get("generated_at")
    )

    total_checked = (len(ordered_gates) * 2) + 3 + 4
    known_count = total_checked - len(unknown_fields)

    return {
        "schema": SCHEMA,
        "subject": subject,
        "measured_at": measured_at,
        "gates": gates_out,
        "gaps": gaps_out,
        "execution": exec_out,
        "completeness": {
            "known_fields": known_count,
            "total_fields": total_checked,
            "unknown_count": len(unknown_fields),
            "all_known": len(unknown_fields) == 0,
        },
        "unknown_fields": unknown_fields,
    }


def _format_rate(value: Any) -> str:
    if value == UNKNOWN:
        return UNKNOWN
    if _is_number(value):
        return f"{float(value) * 100:.1f}% ({value})"
    return str(value)


def render_markdown(report: Mapping[str, Any]) -> str:
    """Render laporan kapabilitas ringkas satu halaman dalam Markdown."""
    lines: list[str] = [
        "# Laporan Kapabilitas ACE",
        "",
        f"- Subjek: `{report.get('subject', UNKNOWN)}`",
        f"- Tanggal ukur: `{report.get('measured_at', UNKNOWN)}`",
        f"- Skema: `{report.get('schema', SCHEMA)}`",
        "",
        "## Status Gate",
        "",
        "| Gate | Status | Bukti (Evidence) | Tanggal Ukur |",
        "| --- | --- | --- | --- |",
    ]

    for row in report.get("gates", []):
        lines.append(
            f"| {row['gate']} | {row['status']} | {row['evidence']} | {row['measured_at']} |"
        )

    gaps = report.get("gaps", {})
    execution = report.get("execution", {})
    completeness = report.get("completeness", {})

    lines.extend(
        [
            "",
            "## Ringkasan Store & Eksekusi",
            "",
            f"- Gap terbuka: {gaps.get('open', UNKNOWN)}",
            f"- Gap tertutup: {gaps.get('closed', UNKNOWN)}",
            f"- Total gap: {gaps.get('total', UNKNOWN)}",
            f"- Eksekusi dicoba: {execution.get('executed', UNKNOWN)}",
            f"- Eksekusi berhasil: {execution.get('succeeded', UNKNOWN)}",
            f"- Eksekusi gagal: {execution.get('failed', UNKNOWN)}",
            f"- Laju eksekusi: {_format_rate(execution.get('execution_rate', UNKNOWN))}",
            (
                "- Kelengkapan data: "
                f"{completeness.get('known_fields', 0)}/{completeness.get('total_fields', 0)} bidang terisi"
            ),
        ]
    )

    unknowns = report.get("unknown_fields", [])
    if unknowns:
        lines.extend(
            [
                "",
                "## Bidang Belum Diketahui",
                "",
                "- " + ", ".join(f"`{name}`" for name in unknowns),
            ]
        )

    return "\n".join(lines) + "\n"


def _load_json_object(path: Path, label: str) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{label} harus berupa objek JSON: {path}")
    return raw


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Render laporan kapabilitas 1 halaman dari papan gate dan statistik store."
    )
    parser.add_argument("--gate-board", required=True, help="Path JSON papan gate.")
    parser.add_argument("--store-stats", required=True, help="Path JSON statistik store.")
    parser.add_argument(
        "--gates",
        default=",".join(DEFAULT_GATES),
        help="Daftar gate terpisah koma (default: G1,G2,G3,G4,G5).",
    )
    parser.add_argument("--out-json", help="Tulis keluaran JSON ke path ini.")
    parser.add_argument("--out-md", help="Tulis keluaran Markdown ke path ini.")
    parser.add_argument(
        "--format",
        choices=("markdown", "json"),
        default="markdown",
        help="Format stdout saat --out-json / --out-md tidak dipakai (default: markdown).",
    )
    args = parser.parse_args(argv)

    try:
        gate_board = _load_json_object(Path(args.gate_board), "gate-board")
        store_stats = _load_json_object(Path(args.store_stats), "store-stats")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    expected_gates = tuple(g.strip() for g in args.gates.split(",") if g.strip())
    if not expected_gates:
        expected_gates = DEFAULT_GATES

    report = build_capability_report(
        gate_board,
        store_stats,
        expected_gates=expected_gates,
    )
    md_text = render_markdown(report)
    json_text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"

    if args.out_json:
        out_json = Path(args.out_json)
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json_text, encoding="utf-8")

    if args.out_md:
        out_md = Path(args.out_md)
        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_md.write_text(md_text, encoding="utf-8")

    if not args.out_json and not args.out_md:
        sys.stdout.write(json_text if args.format == "json" else md_text)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
