#!/usr/bin/env python3
"""Cetak laporan Markdown dari keluaran revenue_verify, dengan total per rel."""
from __future__ import annotations

import argparse
from collections import Counter
from html import escape
import json
from pathlib import Path

if __package__:
    from .revenue_verify import RAILS, RESULT_SCHEMA, STATUSES, _unique_fields
else:
    from revenue_verify import RAILS, RESULT_SCHEMA, STATUSES, _unique_fields


_MARKDOWN = str.maketrans({char: f"&#{ord(char)};" for char in r"\`*_[]~!|"})


def _text(value):
    return isinstance(value, str) and bool(value.strip()) and value.isprintable()


def _cell(text):
    return escape(text).translate(_MARKDOWN)


def _rupiah(amount):
    return "—" if amount is None else f"Rp{amount:,}".replace(",", ".")


def _validated_events(result):
    if not isinstance(result, dict) or result.get("schema") != RESULT_SCHEMA:
        raise ValueError("Skema hasil verifikasi tidak dikenali.")
    lag = result.get("max_lag_days")
    if type(lag) is not int or lag < 0:
        raise ValueError("max_lag_days wajib bilangan bulat nonnegatif.")
    events = result.get("events")
    if not isinstance(events, list):
        raise ValueError("events wajib berupa daftar.")
    seen = set()
    for index, event in enumerate(events, 1):
        if not isinstance(event, dict) or not all(
            _text(event.get(field)) for field in ("id", "rail", "status")
        ):
            raise ValueError(f"Identitas atau status peristiwa ke-{index} tidak sah.")
        if event["id"] in seen:
            raise ValueError(f"ID peristiwa ke-{index} ganda.")
        seen.add(event["id"])
        status, rail = event["status"], event["rail"]
        is_unregistered = rail not in RAILS
        if status not in STATUSES or is_unregistered != (status == "REL TAK TERDAFTAR"):
            raise ValueError(f"Status dan rel peristiwa ke-{index} tidak konsisten.")
        issues = event.get("issues")
        if not isinstance(issues, list) or not all(_text(issue) for issue in issues):
            raise ValueError(f"issues peristiwa ke-{index} wajib berupa daftar teks.")
        if bool(issues) == (status == "COCOK PENUH"):
            raise ValueError(f"Temuan peristiwa ke-{index} tidak konsisten dengan status.")
        amount = event.get("verified_rupiah")
        if status == "COCOK PENUH":
            if type(amount) is not int or amount <= 0:
                raise ValueError(f"Nominal terverifikasi peristiwa ke-{index} tidak sah.")
        elif "verified_rupiah" not in event or amount is not None:
            raise ValueError(f"Nominal peristiwa ke-{index} wajib null untuk status {status}.")
    return events


def render_report(result: dict) -> str:
    """Tampilkan peristiwa menurut rel dan ID, serta jumlah dari baris COCOK PENUH."""
    events = _validated_events(result)
    counts = Counter(event["status"] for event in events)
    totals = Counter()
    for event in events:
        if event["status"] == "COCOK PENUH":
            totals[event["rail"]] += event["verified_rupiah"]

    verified_total = sum(totals.values()) if totals else None
    lines = [
        "# Laporan verifikasi pendapatan",
        "",
        f"- Jendela penarikan ke mutasi — {result['max_lag_days']} hari",
        f"- Total terverifikasi — {_rupiah(verified_total)}",
        *[f"- {status} — {counts[status]}" for status in sorted(STATUSES)],
        "",
        "## Total terverifikasi per rel",
        "",
    ]
    lines.extend(f"- {_cell(rail)} — {_rupiah(totals[rail])}" for rail in sorted(totals))
    if not totals:
        lines.append("Belum ada peristiwa berstatus COCOK PENUH.")
    lines.extend([
        "",
        "## Peristiwa",
        "",
        "| Rel | ID | Status | Rupiah terverifikasi | Temuan |",
        "| --- | --- | --- | ---: | --- |",
    ])
    for event in sorted(events, key=lambda item: (item["rail"], item["id"])):
        issues = ", ".join(_cell(issue) for issue in event["issues"]) or "—"
        lines.append(
            f"| {_cell(event['rail'])} | {_cell(event['id'])} | {event['status']} | "
            f"{_rupiah(event['verified_rupiah'])} | {issues} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("verification", type=Path, help="JSON keluaran verifikator.")
    args = parser.parse_args(argv)
    try:
        result = json.loads(
            args.verification.read_text(encoding="utf-8"), object_pairs_hook=_unique_fields,
        )
        report = render_report(result)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    print(report, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
