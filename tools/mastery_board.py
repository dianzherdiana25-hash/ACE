"""Papan penguasaan domain dari penutupan gap, transfer, dan retensi (AG68).

Menghitung satu angka skor penguasaan per domain lengkap dengan rincian ketiga
komponennya (``closure``, ``transfer``, ``retention``). Sesuai aturan kejujuran:
apabila salah satu atau seluruh komponen hilang, angka domain wajib tampil
``"belum diketahui"``, bukan nol ataupun rata-rata parsial.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


SCHEMA = "ace.mastery-board.v1"
UNKNOWN = "belum diketahui"
DEFAULT_WEIGHTS: dict[str, float] = {
    "closure": 0.4,
    "transfer": 0.3,
    "retention": 0.3,
}


def _extract_component_score(raw: Any) -> float | str:
    if raw is None or isinstance(raw, bool):
        return UNKNOWN
    if isinstance(raw, (int, float)):
        val = float(raw)
        if 0.0 <= val <= 1.0:
            return round(val, 6)
        raise ValueError(f"Skor komponen wajib berada di rentang [0, 1], dapat: {val}")
    if isinstance(raw, Mapping):
        if "score" in raw or "rate" in raw:
            return _extract_component_score(raw.get("score", raw.get("rate")))
        if "passed" in raw and "total" in raw:
            total = raw.get("total")
            passed = raw.get("passed")
            if isinstance(total, (int, float)) and not isinstance(total, bool) and total > 0:
                if isinstance(passed, (int, float)) and not isinstance(passed, bool):
                    return round(float(passed) / float(total), 6)
        if "closed" in raw and "total" in raw:
            total = raw.get("total")
            closed = raw.get("closed")
            if isinstance(total, (int, float)) and not isinstance(total, bool) and total > 0:
                if isinstance(closed, (int, float)) and not isinstance(closed, bool):
                    return round(float(closed) / float(total), 6)
    return UNKNOWN


def build_mastery_board(
    domain_inputs: Mapping[str, Mapping[str, Any]],
    *,
    weights: Mapping[str, float] = DEFAULT_WEIGHTS,
) -> dict[str, Any]:
    """Hitung papan penguasaan per domain dari data penutupan, transfer, dan retensi."""
    w_c = float(weights.get("closure", DEFAULT_WEIGHTS["closure"]))
    w_t = float(weights.get("transfer", DEFAULT_WEIGHTS["transfer"]))
    w_r = float(weights.get("retention", DEFAULT_WEIGHTS["retention"]))
    if abs((w_c + w_t + w_r) - 1.0) > 1e-6 or min(w_c, w_t, w_r) < 0:
        raise ValueError("Bobot komponen mastery wajib nonnegatif dan berjumlah 1.0")

    src = (
        domain_inputs["domains"]
        if isinstance(domain_inputs.get("domains"), Mapping)
        else domain_inputs
    )
    if not src:
        raise ValueError("Daftar domain masukan tidak boleh kosong")

    rows: list[dict[str, Any]] = []
    known_scores: list[float] = []
    complete_domains: list[str] = []
    partial_domains: list[str] = []
    empty_domains: list[str] = []

    for domain in sorted(src):
        payload = src[domain] if isinstance(src[domain], Mapping) else {}
        closure = _extract_component_score(payload.get("closure"))
        transfer = _extract_component_score(payload.get("transfer"))
        retention = _extract_component_score(payload.get("retention"))

        present_cnt = sum(val != UNKNOWN for val in (closure, transfer, retention))
        if present_cnt == 3:
            mastery: float | str = round(
                w_c * float(closure) + w_t * float(transfer) + w_r * float(retention), 6
            )
            status = "complete"
            complete_domains.append(domain)
            known_scores.append(float(mastery))
        elif present_cnt == 0:
            mastery = UNKNOWN
            status = "empty"
            empty_domains.append(domain)
        else:
            mastery = UNKNOWN
            status = "partial"
            partial_domains.append(domain)

        rows.append(
            {
                "domain": domain,
                "status": status,
                "mastery_score": mastery,
                "components": {
                    "closure": closure,
                    "transfer": transfer,
                    "retention": retention,
                },
                "missing_components": [
                    k
                    for k, v in (
                        ("closure", closure),
                        ("transfer", transfer),
                        ("retention", retention),
                    )
                    if v == UNKNOWN
                ],
            }
        )

    aggregate_mastery: float | str = (
        round(sum(known_scores) / len(known_scores), 6)
        if len(known_scores) == len(rows) and rows
        else UNKNOWN
    )

    return {
        "schema": SCHEMA,
        "weights": {"closure": w_c, "transfer": w_t, "retention": w_r},
        "summary": {
            "total_domains": len(rows),
            "complete_count": len(complete_domains),
            "partial_count": len(partial_domains),
            "empty_count": len(empty_domains),
            "complete_domains": complete_domains,
            "partial_domains": partial_domains,
            "empty_domains": empty_domains,
            "aggregate_mastery": aggregate_mastery,
        },
        "domains": rows,
    }


def render_markdown(board: Mapping[str, Any]) -> str:
    """Render papan penguasaan domain menjadi tabel Markdown."""
    lines = [
        "# Papan Penguasaan Domain",
        "",
        "| Domain | Status | Penguasaan | Penutupan | Transfer | Retensi |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in board["domains"]:
        comp = row["components"]
        lines.append(
            f"| {row['domain']} | {row['status']} | {row['mastery_score']} | "
            f"{comp['closure']} | {comp['transfer']} | {comp['retention']} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Hitung skor penguasaan domain (closure + transfer + retention)."
    )
    parser.add_argument("--input", required=True, help="Path JSON data penutupan/transfer/retensi per domain.")
    parser.add_argument("--out-json", help="Tulis laporan JSON ke path ini.")
    parser.add_argument("--out-md", help="Tulis tabel Markdown ke path ini.")
    args = parser.parse_args(argv)

    try:
        raw = json.loads(Path(args.input).read_text(encoding="utf-8"))
        if not isinstance(raw, Mapping):
            raise ValueError("Berkas input wajib berupa objek JSON")
        board = build_mastery_board(raw)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    json_text = json.dumps(board, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    md_text = render_markdown(board)
    if args.out_json:
        p = Path(args.out_json)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json_text, encoding="utf-8")
    if args.out_md:
        p = Path(args.out_md)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(md_text, encoding="utf-8")
    if not args.out_json and not args.out_md:
        sys.stdout.write(json_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
