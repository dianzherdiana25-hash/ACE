#!/usr/bin/env python3
"""Perencana jadwal produksi dan rilis bab serial KBM deterministik (WS-C #10).

Membaca katalog serial JSON (`serials` list), target mingguan per serial atau global,
serta tanggal acuan (`--start-date` dan `--as-of`), lalu menyusun rencana produksi
JSON (`ace.kbm-schedule.v1`) lengkap dengan status tiap bab (`completed`, `overdue`,
atau `scheduled`) serta daftar rilis terdekat untuk konsumsi dashboard.
"""
from __future__ import annotations

import argparse
from datetime import date, timedelta
import json
import os
from pathlib import Path
import sys
from typing import Any

SCHEDULE_SCHEMA = "ace.kbm-schedule.v1"


class KbmScheduleError(ValueError):
    """Kesalahan berkas katalog JSON, tanggal ISO, atau parameter CLI jadwal KBM."""


def _parse_iso_date(raw: Any, field_name: str) -> date:
    if not isinstance(raw, str) or not raw.strip():
        raise KbmScheduleError(f"Field tanggal `{field_name}` wajib string ISO YYYY-MM-DD.")
    try:
        return date.fromisoformat(raw.strip())
    except ValueError as exc:
        raise KbmScheduleError(f"Tanggal `{field_name}` tidak sah ({raw!r}): {exc}") from exc


def _normalize_serial(raw: Any, idx: int, default_start: date, default_weekly_target: int) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise KbmScheduleError(f"Entri serial ke-{idx} wajib berupa objek JSON.")
    serial_id = raw.get("id")
    if not isinstance(serial_id, str) or not serial_id.strip():
        raise KbmScheduleError(f"Entri serial ke-{idx} wajib memiliki string 'id' tidak kosong.")
    title = str(raw.get("title") or serial_id).strip()

    total_ch = raw.get("total_chapters")
    if isinstance(total_ch, bool) or not isinstance(total_ch, int) or total_ch <= 0:
        raise KbmScheduleError(f"Serial '{serial_id}': `total_chapters` wajib bilangan bulat > 0.")

    weekly_target = raw.get("weekly_target", default_weekly_target)
    if isinstance(weekly_target, bool) or not isinstance(weekly_target, int) or weekly_target <= 0:
        raise KbmScheduleError(f"Serial '{serial_id}': `weekly_target` wajib bilangan bulat > 0.")

    start_date = (
        _parse_iso_date(raw["start_date"], f"{serial_id}.start_date")
        if raw.get("start_date") is not None
        else default_start
    )

    completed_set: set[int] = set()
    if raw.get("completed_chapters_list") is not None:
        clist = raw["completed_chapters_list"]
        if not isinstance(clist, list) or any(isinstance(x, bool) or not isinstance(x, int) for x in clist):
            raise KbmScheduleError(f"Serial '{serial_id}': `completed_chapters_list` wajib daftar integer.")
        for ch_no in clist:
            if not (1 <= ch_no <= total_ch):
                raise KbmScheduleError(f"Serial '{serial_id}': nomor bab selesai {ch_no} di luar 1..{total_ch}.")
            completed_set.add(ch_no)
    elif raw.get("completed_chapters") is not None:
        comp_n = raw["completed_chapters"]
        if isinstance(comp_n, bool) or not isinstance(comp_n, int) or not (0 <= comp_n <= total_ch):
            raise KbmScheduleError(
                f"Serial '{serial_id}': `completed_chapters` wajib integer pada rentang 0..{total_ch}."
            )
        completed_set = set(range(1, comp_n + 1))

    return {
        "id": serial_id.strip(),
        "title": title,
        "total_chapters": total_ch,
        "weekly_target": weekly_target,
        "start_date": start_date,
        "completed_set": completed_set,
    }


def _slot_date_for_chapter(start: date, chapter_num: int, weekly_target: int) -> date:
    """Hitung tanggal terdistribusi deterministik per minggu (offset hari merata 0..6)."""
    zero_idx = chapter_num - 1
    week_idx = zero_idx // weekly_target
    slot_in_week = zero_idx % weekly_target
    # Sebar merata dalam 7 hari minggu berjalan secara deterministik.
    day_offset_in_week = (slot_in_week * 7) // weekly_target
    return start + timedelta(days=week_idx * 7 + day_offset_in_week)


def build_schedule(
    catalog_path: Path,
    *,
    default_start_date: str | None = None,
    as_of_date: str | None = None,
    default_weekly_target: int = 3,
) -> dict[str, Any]:
    """Bangun rencana produksi serial KBM JSON dari berkas katalog."""
    if isinstance(default_weekly_target, bool) or not isinstance(default_weekly_target, int) or default_weekly_target <= 0:
        raise KbmScheduleError("`--weekly-target` wajib bilangan bulat > 0.")
    if not catalog_path.is_file():
        raise KbmScheduleError(f"Berkas katalog serial tidak ditemukan: {catalog_path}")
    try:
        loaded = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise KbmScheduleError(f"Gagal membaca katalog '{catalog_path}': {exc}") from exc

    if isinstance(loaded, dict):
        raw_serials = loaded.get("serials")
        file_start = loaded.get("default_start_date")
        file_as_of = loaded.get("as_of")
    elif isinstance(loaded, list):
        raw_serials = loaded
        file_start = None
        file_as_of = None
    else:
        raise KbmScheduleError("Katalog JSON wajib berupa objek dengan field `serials` atau daftar serial.")

    if not isinstance(raw_serials, list) or not raw_serials:
        raise KbmScheduleError("Daftar `serials` pada katalog tidak boleh kosong.")

    as_of = _parse_iso_date(as_of_date or file_as_of or date.today().isoformat(), "as_of")
    default_start = _parse_iso_date(default_start_date or file_start or as_of.isoformat(), "start_date")

    serial_entries: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for idx, raw in enumerate(raw_serials, start=1):
        norm = _normalize_serial(raw, idx, default_start, default_weekly_target)
        if norm["id"] in seen_ids:
            raise KbmScheduleError(f"ID serial duplikat dalam katalog: {norm['id']!r}")
        seen_ids.add(norm["id"])
        serial_entries.append(norm)

    total_chapters = 0
    total_completed = 0
    total_overdue = 0
    total_scheduled = 0
    upcoming_items: list[dict[str, Any]] = []
    serial_reports: list[dict[str, Any]] = []

    for entry in serial_entries:
        slots: list[dict[str, Any]] = []
        s_completed = 0
        s_overdue = 0
        s_scheduled = 0
        for ch_no in range(1, entry["total_chapters"] + 1):
            sched = _slot_date_for_chapter(entry["start_date"], ch_no, entry["weekly_target"])
            if ch_no in entry["completed_set"]:
                status = "completed"
                s_completed += 1
            elif sched < as_of:
                status = "overdue"
                s_overdue += 1
            else:
                status = "scheduled"
                s_scheduled += 1
                upcoming_items.append(
                    {
                        "serial_id": entry["id"],
                        "title": entry["title"],
                        "chapter": ch_no,
                        "scheduled_date": sched.isoformat(),
                    }
                )
            slots.append(
                {
                    "chapter": ch_no,
                    "scheduled_date": sched.isoformat(),
                    "status": status,
                }
            )

        total_chapters += entry["total_chapters"]
        total_completed += s_completed
        total_overdue += s_overdue
        total_scheduled += s_scheduled

        last_date = slots[-1]["scheduled_date"]
        serial_reports.append(
            {
                "id": entry["id"],
                "title": entry["title"],
                "start_date": entry["start_date"].isoformat(),
                "weekly_target": entry["weekly_target"],
                "total_chapters": entry["total_chapters"],
                "completed_count": s_completed,
                "overdue_count": s_overdue,
                "scheduled_count": s_scheduled,
                "projected_completion_date": last_date,
                "slots": slots,
            }
        )

    upcoming_items.sort(key=lambda item: (item["scheduled_date"], item["serial_id"], item["chapter"]))
    return {
        "schema": SCHEDULE_SCHEMA,
        "catalog": str(catalog_path),
        "as_of": as_of.isoformat(),
        "default_start_date": default_start.isoformat(),
        "default_weekly_target": default_weekly_target,
        "summary": {
            "total_serials": len(serial_reports),
            "total_chapters": total_chapters,
            "completed": total_completed,
            "overdue": total_overdue,
            "scheduled": total_scheduled,
            "next_upcoming": upcoming_items[:10],
        },
        "serials": serial_reports,
    }


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    tmp_path.write_text(text, encoding="utf-8")
    os.replace(tmp_path, path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generator jadwal produksi bab serial KBM deterministik."
    )
    parser.add_argument("catalog", type=Path, help="Path berkas JSON katalog serial KBM.")
    parser.add_argument("--start-date", default=None, help="Tanggal mulai default YYYY-MM-DD.")
    parser.add_argument("--as-of", default=None, help="Tanggal acuan evaluasi status YYYY-MM-DD.")
    parser.add_argument("--weekly-target", type=int, default=3, help="Target bab per minggu default (default: 3).")
    parser.add_argument("--out", type=Path, default=None, help="Path opsional berkas JSON rencana jadwal keluaran.")
    args = parser.parse_args(argv)

    try:
        report = build_schedule(
            args.catalog,
            default_start_date=args.start_date,
            as_of_date=args.as_of,
            default_weekly_target=args.weekly_target,
        )
    except KbmScheduleError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.out is not None:
        _atomic_write_text(args.out, rendered)
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
