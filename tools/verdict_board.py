"""Perakit papan vonis Markdown dari JSON bukti per-gate G1–G5 (AG56).

Mengumpulkan berkas JSON bukti tiap gate (``G1`` s.d. ``G5``) secara read-only
dan merakit tabel papan vonis Markdown serta struktur JSON ringkasan.
Ketentuan kejujuran mutlak: gate yang berkas atau penunjuk buktinya hilang
WAJIB menampilkan ``"belum diketahui"`` dan tidak pernah dinyatakan ``PASS``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


SCHEMA = "ace.verdict-board.v1"
UNKNOWN = "belum diketahui"
DEFAULT_GATES: tuple[str, ...] = ("G1", "G2", "G3", "G4", "G5")


def _clean_field(value: Any) -> str:
    if value is None:
        return UNKNOWN
    if isinstance(value, str):
        s = value.strip()
        return s if s else UNKNOWN
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        parts = [str(item).strip() for item in value if str(item).strip()]
        return ", ".join(parts) if parts else UNKNOWN
    return str(value)


def discover_gate_files(evidence_dir: Path) -> dict[str, Path]:
    """Temukan berkas JSON per-gate (G1..G5) di dalam direktori bukti."""
    root = Path(evidence_dir)
    if not root.is_dir():
        raise FileNotFoundError(f"Direktori bukti tidak ditemukan: {root}")
    found: dict[str, Path] = {}
    for gate in DEFAULT_GATES:
        for candidate_name in (f"{gate}.json", f"{gate.lower()}.json"):
            cand = root / candidate_name
            if cand.is_file():
                found[gate] = cand
                break
        if gate in found:
            continue
        prefixed = sorted(
            p
            for p in root.iterdir()
            if p.is_file()
            and p.suffix == ".json"
            and p.stem.upper().startswith(f"{gate}_")
        )
        if prefixed:
            found[gate] = prefixed[0]
    return found


def assemble_verdict_board(
    gate_paths: Mapping[str, Path],
    *,
    gates: Sequence[str] = DEFAULT_GATES,
    title: str = "Papan Vonis Gate G1–G5",
) -> dict[str, Any]:
    """Rakit papan vonis G1–G5 dari path JSON tiap gate."""
    rows: list[dict[str, Any]] = []
    missing_gates: list[str] = []
    pass_count = 0
    known_count = 0

    for gate in gates:
        path = gate_paths.get(gate)
        if path is None or not Path(path).is_file():
            missing_gates.append(gate)
            rows.append(
                {
                    "gate": gate,
                    "status": UNKNOWN,
                    "evidence_pointer": UNKNOWN,
                    "measured_date": UNKNOWN,
                    "source_file": None,
                    "present": False,
                }
            )
            continue

        resolved = Path(path)
        try:
            payload = json.loads(resolved.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = None

        if not isinstance(payload, Mapping):
            missing_gates.append(gate)
            rows.append(
                {
                    "gate": gate,
                    "status": UNKNOWN,
                    "evidence_pointer": UNKNOWN,
                    "measured_date": UNKNOWN,
                    "source_file": str(resolved),
                    "present": False,
                }
            )
            continue

        ev_raw = (
            payload.get("evidence_pointer")
            or payload.get("evidence")
            or payload.get("evidence_ref")
            or payload.get("evidence_refs")
        )
        evidence_pointer = _clean_field(ev_raw)
        measured_date = _clean_field(
            payload.get("measured_date") or payload.get("measured_at") or payload.get("date")
        )
        raw_status = _clean_field(payload.get("status") or payload.get("verdict"))

        # Larang status PASS bila evidence_pointer tidak tersedia (fail-closed).
        if evidence_pointer == UNKNOWN:
            status = UNKNOWN
            missing_gates.append(gate)
        else:
            status = raw_status
            if status == UNKNOWN:
                missing_gates.append(gate)
            else:
                known_count += 1
                if status.upper() == "PASS":
                    pass_count += 1

        rows.append(
            {
                "gate": gate,
                "status": status,
                "evidence_pointer": evidence_pointer,
                "measured_date": measured_date,
                "source_file": str(resolved),
                "present": True,
            }
        )

    all_known = len(missing_gates) == 0 and known_count == len(gates)
    if not all_known:
        board_verdict = "INCOMPLETE"
    elif pass_count == len(gates):
        board_verdict = "PASS"
    elif any(r["status"].upper() == "FAIL" for r in rows):
        board_verdict = "FAIL"
    else:
        board_verdict = "HOLD"

    return {
        "schema": SCHEMA,
        "title": title,
        "summary": {
            "total_gates": len(gates),
            "known_gates": known_count,
            "pass_gates": pass_count,
            "missing_gates": missing_gates,
            "all_gates_measured": all_known,
            "board_verdict": board_verdict,
        },
        "gates": rows,
    }


def render_verdict_board_markdown(board: Mapping[str, Any]) -> str:
    """Render papan vonis G1–G5 dalam format Markdown."""
    summary = board["summary"]
    lines = [
        f"# {board.get('title', 'Papan Vonis Gate G1–G5')}",
        "",
        f"- Vonis papan: `{summary['board_verdict']}`",
        f"- Gate terukur: {summary['known_gates']}/{summary['total_gates']}",
        (
            "- Gate tak lengkap: "
            + (", ".join(summary["missing_gates"]) if summary["missing_gates"] else "-")
        ),
        "",
        "| Gate | Status | Evidence Pointer | Measured Date |",
        "| --- | --- | --- | --- |",
    ]
    for row in board["gates"]:
        lines.append(
            f"| {row['gate']} | {row['status']} | {row['evidence_pointer']} | {row['measured_date']} |"
        )
    return "\n".join(lines) + "\n"


def _parse_gate_overrides(items: Sequence[str]) -> dict[str, Path]:
    mapping: dict[str, Path] = {}
    for raw in items:
        if "=" not in raw:
            raise ValueError(f"Format --gate harus GATE=PATH, diterima: {raw!r}")
        gate, path_str = raw.split("=", 1)
        gate_key = gate.strip().upper()
        if gate_key not in DEFAULT_GATES:
            raise ValueError(f"Gate tidak dikenal: {gate_key!r}")
        mapping[gate_key] = Path(path_str.strip())
    return mapping


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Rakit papan vonis Markdown dari berkas JSON bukti per-gate G1–G5."
    )
    parser.add_argument("--evidence-dir", help="Direktori berisi berkas G1.json..G5.json.")
    parser.add_argument(
        "--gate",
        action="append",
        default=[],
        help="Override/berikan path per gate eksplisit dengan format G1=path/to/g1.json.",
    )
    parser.add_argument("--title", default="Papan Vonis Gate G1–G5")
    parser.add_argument("--out-md", help="Tulis output Markdown ke path ini.")
    parser.add_argument("--out-json", help="Tulis output JSON ke path ini.")
    args = parser.parse_args(argv)

    if not args.evidence_dir and not args.gate:
        print("error: berikan --evidence-dir atau minimal satu --gate", file=sys.stderr)
        return 2

    try:
        gate_paths: dict[str, Path] = {}
        if args.evidence_dir:
            gate_paths.update(discover_gate_files(Path(args.evidence_dir)))
        if args.gate:
            gate_paths.update(_parse_gate_overrides(args.gate))
        board = assemble_verdict_board(gate_paths, title=args.title)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    md_text = render_verdict_board_markdown(board)
    json_text = json.dumps(board, ensure_ascii=False, indent=2, sort_keys=True) + "\n"

    if args.out_md:
        p = Path(args.out_md)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(md_text, encoding="utf-8")
    if args.out_json:
        p = Path(args.out_json)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json_text, encoding="utf-8")
    if not args.out_md and not args.out_json:
        sys.stdout.write(md_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
