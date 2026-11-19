#!/usr/bin/env python3
"""Perencana jendela RAM deterministik berbasis berkas untuk menjadwalkan beban organ ACE.

Kenapa modul ini ada:
Mesin lokal ACE memiliki batas RAM fisik yang ketat; menyalakan beberapa beban
(model, pengujian, atau indeks) secara serentak tanpa margin keamanan dapat
memicu OOM-killer dan memutus jalannya eksperimen. Kalkulator murni berbasis
berkas ini memakai aritmetika `Decimal` agar perhitungan GiB bebas galat
floating-point, menentukan kombinasi beban serentak yang muat di bawah margin
keamanan, serta menyusun urutan eksekusi yang menjamin puncak penggunaan RAM
tidak pernah melampaui batas aman.

Exit code:
- 0: seluruh beban muat dalam margin dan jadwal aman berhasil disusun
- 1: terdapat satu atau lebih beban yang sendirian sudah melebihi batas aman RAM
- 2: berkas masukan atau argumen CLI tidak sah
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from itertools import combinations
import json
from pathlib import Path
import sys
from typing import Any

RAM_WINDOW_SCHEMA = "ace.ram-window.v1"
MAX_EXACT_SUBSET_WORKLOADS = 16


class RamWindowError(ValueError):
    """Kesalahan spesifikasi beban, nilai RAM/margin, atau berkas masukan CLI."""


@dataclass(frozen=True)
class Workload:
    """Satu beban bernama dengan kebutuhan RAM (GiB) dan durasi positif."""

    name: str
    gib: Decimal
    duration: Decimal


def _to_decimal(value: Any, field_name: str) -> Decimal:
    if isinstance(value, bool):
        raise RamWindowError(f"Field '{field_name}' tidak boleh boolean.")
    if isinstance(value, Decimal):
        dec = value
    elif isinstance(value, (int, float, str)):
        raw = str(value).strip()
        if not raw:
            raise RamWindowError(f"Field '{field_name}' kosong.")
        try:
            dec = Decimal(raw)
        except InvalidOperation as exc:
            raise RamWindowError(f"Nilai '{field_name}' bukan angka sah: {value!r}") from exc
    else:
        raise RamWindowError(f"Tipe '{field_name}' tidak sah: {type(value).__name__}")
    if not dec.is_finite():
        raise RamWindowError(f"Nilai '{field_name}' harus berhingga: {value!r}")
    return dec


def _dec_str(value: Decimal) -> str:
    norm = value.normalize()
    s = format(norm, "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s or "0"


def parse_workloads(raw_items: Any) -> list[Workload]:
    """Validasi daftar beban bernama dari JSON (`list` atau `{"workloads": [...]}`)."""
    if isinstance(raw_items, dict) and "workloads" in raw_items:
        items = raw_items["workloads"]
    else:
        items = raw_items

    if not isinstance(items, list) or not items:
        raise RamWindowError("Daftar beban wajib berupa array JSON tidak kosong.")

    workloads: list[Workload] = []
    seen_names: set[str] = set()
    for idx, entry in enumerate(items):
        if not isinstance(entry, dict):
            raise RamWindowError(f"Beban pada indeks {idx} wajib berupa objek JSON.")
        name = entry.get("name")
        if not isinstance(name, str) or not name.strip():
            raise RamWindowError(f"Beban pada indeks {idx} wajib memiliki 'name' string tidak kosong.")
        clean_name = name.strip()
        if clean_name in seen_names:
            raise RamWindowError(f"Nama beban ganda ditemukan: '{clean_name}'.")
        seen_names.add(clean_name)

        gib_raw = entry.get("gib", entry.get("ram_gib"))
        if gib_raw is None:
            raise RamWindowError(f"Beban '{clean_name}' wajib memiliki field 'gib' (atau 'ram_gib').")
        gib = _to_decimal(gib_raw, f"{clean_name}.gib")
        if gib <= 0:
            raise RamWindowError(f"Ukuran GiB beban '{clean_name}' wajib > 0.")

        dur_raw = entry.get("duration", entry.get("duration_min", entry.get("duration_s")))
        if dur_raw is None:
            raise RamWindowError(f"Beban '{clean_name}' wajib memiliki field 'duration'.")
        duration = _to_decimal(dur_raw, f"{clean_name}.duration")
        if duration <= 0:
            raise RamWindowError(f"Durasi beban '{clean_name}' wajib > 0.")

        workloads.append(Workload(name=clean_name, gib=gib, duration=duration))

    return workloads


def load_workloads_file(path: Path) -> list[Workload]:
    """Muat daftar beban dari berkas JSON secara baca-saja."""
    if not path.is_file():
        raise RamWindowError(f"Berkas daftar beban tidak ditemukan: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RamWindowError(f"Gagal membaca JSON '{path}': {exc}") from exc
    return parse_workloads(data)


def _compute_safe_combinations(
    feasible: list[Workload],
    safe_ceiling_gib: Decimal,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], bool]:
    """Hitung kombinasi serentak yang muat beserta himpunan maksimalnya."""
    if len(feasible) > MAX_EXACT_SUBSET_WORKLOADS:
        # Untuk jumlah beban besar, kembalikan pasangan & singleton agar tidak meledak 2^N.
        subsets: list[tuple[Workload, ...]] = []
        for r in (1, 2):
            for combo in combinations(feasible, r):
                if sum((w.gib for w in combo), Decimal("0")) <= safe_ceiling_gib:
                    subsets.append(combo)
        truncated = True
    else:
        subsets = []
        for r in range(1, len(feasible) + 1):
            for combo in combinations(feasible, r):
                if sum((w.gib for w in combo), Decimal("0")) <= safe_ceiling_gib:
                    subsets.append(combo)
        truncated = False

    subset_sets = [frozenset(w.name for w in combo) for combo in subsets]
    maximal_combos: list[tuple[Workload, ...]] = []
    for combo, name_set in zip(subsets, subset_sets):
        total = sum((w.gib for w in combo), Decimal("0"))
        if truncated:
            # Pada mode terpotong, maksimal bila tidak ada beban lain yang bisa ditambahkan.
            can_extend = any(w.name not in name_set and total + w.gib <= safe_ceiling_gib for w in feasible)
            if not can_extend:
                maximal_combos.append(combo)
        else:
            if not any(name_set < other for other in subset_sets):
                maximal_combos.append(combo)

    def _serialize(combo: tuple[Workload, ...]) -> dict[str, Any]:
        total = sum((w.gib for w in combo), Decimal("0"))
        names = sorted(w.name for w in combo)
        return {
            "workloads": names,
            "count": len(names),
            "total_gib": _dec_str(total),
            "headroom_gib": _dec_str(safe_ceiling_gib - total),
        }

    def _sort_key(item: dict[str, Any]) -> tuple[Decimal, int, list[str]]:
        return (-Decimal(item["total_gib"]), -item["count"], item["workloads"])

    all_serialized = sorted((_serialize(c) for c in subsets), key=_sort_key)
    max_serialized = sorted((_serialize(c) for c in maximal_combos), key=_sort_key)
    return all_serialized, max_serialized, truncated


def _schedule_workloads(
    feasible: list[Workload],
    safe_ceiling_gib: Decimal,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], Decimal, Decimal]:
    """Susun urutan jalan deterministik (First-Fit Decreasing by RAM) di bawah plafon aman."""
    # Urutkan beban terbesar RAM lebih dulu, lalu durasi terlama, lalu nama alfabetis.
    ordered = sorted(feasible, key=lambda w: (-w.gib, -w.duration, w.name))
    placed: list[tuple[Workload, Decimal, Decimal]] = []

    def _usage_during(start: Decimal, end: Decimal) -> Decimal:
        # Periksa puncak penggunaan di setiap titik transisi dalam [start, end).
        points = {start}
        for _, ps, pe in placed:
            if start < ps < end:
                points.add(ps)
            if start < pe < end:
                points.add(pe)
        peak = Decimal("0")
        for pt in sorted(points):
            active_sum = sum(
                (pw.gib for pw, ps, pe in placed if ps <= pt < pe),
                Decimal("0"),
            )
            if active_sum > peak:
                peak = active_sum
        return peak

    for w in ordered:
        candidates = sorted({Decimal("0"), *(pe for _, _, pe in placed)})
        chosen_start: Decimal | None = None
        for t in candidates:
            if _usage_during(t, t + w.duration) + w.gib <= safe_ceiling_gib:
                chosen_start = t
                break
        if chosen_start is None:
            # Fallback teoretis: setelah seluruh jadwal sebelumnya selesai.
            chosen_start = max((pe for _, _, pe in placed), default=Decimal("0"))
        placed.append((w, chosen_start, chosen_start + w.duration))

    # Urutkan jadwal berdasarkan waktu mulai, lalu selesai, lalu nama.
    placed.sort(key=lambda item: (item[1], item[2], item[0].name))
    schedule_rows = [
        {
            "order": idx,
            "name": w.name,
            "gib": _dec_str(w.gib),
            "duration": _dec_str(w.duration),
            "start": _dec_str(start),
            "end": _dec_str(end),
        }
        for idx, (w, start, end) in enumerate(placed, start=1)
    ]

    # Bangun jendela timeline terpisah untuk verifikasi invarian RAM setiap detik.
    boundaries = sorted({pt for _, s, e in placed for pt in (s, e)})
    windows: list[dict[str, Any]] = []
    peak_ram = Decimal("0")
    for i in range(len(boundaries) - 1):
        w_start, w_end = boundaries[i], boundaries[i + 1]
        active = sorted(w.name for w, s, e in placed if s <= w_start and e >= w_end)
        used = sum((w.gib for w, s, e in placed if s <= w_start and e >= w_end), Decimal("0"))
        if used > peak_ram:
            peak_ram = used
        windows.append(
            {
                "start": _dec_str(w_start),
                "end": _dec_str(w_end),
                "duration": _dec_str(w_end - w_start),
                "active_workloads": active,
                "used_gib": _dec_str(used),
                "headroom_gib": _dec_str(safe_ceiling_gib - used),
            }
        )

    makespan = max((e for _, _, e in placed), default=Decimal("0"))
    return schedule_rows, windows, makespan, peak_ram


def plan_ram_windows(
    workloads: list[Workload],
    *,
    total_ram_gib: Decimal | float | int | str,
    margin_gib: Decimal | float | int | str = Decimal("2"),
    duration_unit: str = "min",
) -> dict[str, Any]:
    """Hitung jendela aman, kombinasi yang muat, dan urutan jalan tanpa melewati margin."""
    total_dec = _to_decimal(total_ram_gib, "total_ram_gib")
    margin_dec = _to_decimal(margin_gib, "margin_gib")
    if total_dec <= 0:
        raise RamWindowError("total_ram_gib wajib > 0.")
    if margin_dec < 0:
        raise RamWindowError("margin_gib tidak boleh negatif.")
    safe_ceiling = total_dec - margin_dec
    if safe_ceiling <= 0:
        raise RamWindowError("Plafon aman (total_ram_gib - margin_gib) wajib > 0.")

    feasible = [w for w in workloads if w.gib <= safe_ceiling]
    oversized = [w for w in workloads if w.gib > safe_ceiling]

    safe_combos, maximal_combos, combos_truncated = _compute_safe_combinations(feasible, safe_ceiling)
    schedule_rows, windows, makespan, peak_ram = _schedule_workloads(feasible, safe_ceiling)

    invariant_safe = peak_ram <= safe_ceiling
    all_fit = len(oversized) == 0

    return {
        "schema": RAM_WINDOW_SCHEMA,
        "total_ram_gib": _dec_str(total_dec),
        "margin_gib": _dec_str(margin_dec),
        "safe_ceiling_gib": _dec_str(safe_ceiling),
        "duration_unit": duration_unit,
        "workload_count": len(workloads),
        "feasible_count": len(feasible),
        "oversized_count": len(oversized),
        "oversized_workloads": [
            {
                "name": w.name,
                "gib": _dec_str(w.gib),
                "excess_gib": _dec_str(w.gib - safe_ceiling),
            }
            for w in sorted(oversized, key=lambda x: x.name)
        ],
        "all_fit": all_fit,
        "invariant_never_exceeds_margin": invariant_safe,
        "peak_ram_gib": _dec_str(peak_ram),
        "min_headroom_gib": _dec_str(safe_ceiling - peak_ram),
        "makespan": _dec_str(makespan),
        "combinations_truncated": combos_truncated,
        "safe_combinations": safe_combos,
        "maximal_safe_combinations": maximal_combos,
        "schedule": schedule_rows,
        "windows": windows,
    }


def render_markdown(plan: dict[str, Any]) -> str:
    """Render rencana jendela RAM sebagai ringkasan Markdown deterministik."""
    unit = plan["duration_unit"]
    lines = [
        "# Perencanaan Jendela Aman RAM ACE",
        "",
        f"> Dihasilkan deterministik oleh `tools/ram_window.py` (`{plan['schema']}`).",
        "",
        "## Parameter & Ringkasan",
        "",
        f"- **Total RAM:** {plan['total_ram_gib']} GiB",
        f"- **Margin keamanan:** {plan['margin_gib']} GiB",
        f"- **Plafon aman:** {plan['safe_ceiling_gib']} GiB",
        f"- **Beban muat / melebihi plafon:** {plan['feasible_count']} / {plan['oversized_count']}",
        f"- **Puncak RAM jadwal:** {plan['peak_ram_gib']} GiB (sisa headroom minimum: {plan['min_headroom_gib']} GiB)",
        f"- **Total durasi (makespan):** {plan['makespan']} {unit}",
        f"- **Invarian aman terpenuhi:** `{plan['invariant_never_exceeds_margin']}`",
        "",
        "## Kombinasi Serentak Maksimal yang Muat",
        "",
        "| Kombinasi Beban | Total GiB | Headroom GiB |",
        "| --- | ---: | ---: |",
    ]
    for combo in plan["maximal_safe_combinations"]:
        lines.append(
            f"| {', '.join(combo['workloads'])} | {combo['total_gib']} | {combo['headroom_gib']} |"
        )
    if not plan["maximal_safe_combinations"]:
        lines.append("| (tidak ada beban yang muat) | 0 | - |")

    lines.extend(
        [
            "",
            "## Urutan Jalan Aman",
            "",
            f"| # | Beban | RAM (GiB) | Mulai ({unit}) | Selesai ({unit}) |",
            "| ---: | --- | ---: | ---: | ---: |",
        ]
    )
    for row in plan["schedule"]:
        lines.append(
            f"| {row['order']} | `{row['name']}` | {row['gib']} | {row['start']} | {row['end']} |"
        )

    lines.extend(
        [
            "",
            "## Jendela Waktu & Penggunaan RAM",
            "",
            f"| Rentang ({unit}) | Beban Aktif | RAM Terpakai (GiB) | Headroom (GiB) |",
            "| --- | --- | ---: | ---: |",
        ]
    )
    for w in plan["windows"]:
        lines.append(
            f"| [{w['start']}, {w['end']}) | {', '.join(w['active_workloads'])} | {w['used_gib']} | {w['headroom_gib']} |"
        )

    if plan["oversized_workloads"]:
        lines.extend(["", "## Beban Melebihi Plafon Aman (Tidak Dijadwalkan)", ""])
        for ov in plan["oversized_workloads"]:
            lines.append(f"- `{ov['name']}`: {ov['gib']} GiB (kelebihan {ov['excess_gib']} GiB)")

    lines.append("")
    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Hitung kombinasi aman dan urutan eksekusi beban RAM tanpa melewati margin keamanan."
    )
    parser.add_argument("workloads_file", help="Berkas JSON berisi daftar beban (name, gib, duration).")
    parser.add_argument("--total-ram-gib", required=True, help="Total RAM fisik mesin dalam GiB.")
    parser.add_argument("--margin-gib", default="2", help="Margin keamanan RAM dalam GiB (default: 2).")
    parser.add_argument("--duration-unit", default="min", help="Label satuan durasi (default: min).")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--json-out", help="Simpan hasil JSON ke berkas ini.")
    parser.add_argument("--markdown-out", help="Simpan hasil Markdown ke berkas ini.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        workloads = load_workloads_file(Path(args.workloads_file))
        plan = plan_ram_windows(
            workloads,
            total_ram_gib=args.total_ram_gib,
            margin_gib=args.margin_gib,
            duration_unit=args.duration_unit,
        )
    except RamWindowError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    json_text = json.dumps(plan, ensure_ascii=False, indent=2) + "\n"
    md_text = render_markdown(plan)
    if args.json_out:
        out_p = Path(args.json_out)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(json_text, encoding="utf-8")
    if args.markdown_out:
        md_p = Path(args.markdown_out)
        md_p.parent.mkdir(parents=True, exist_ok=True)
        md_p.write_text(md_text, encoding="utf-8")

    sys.stdout.write(md_text if args.format == "markdown" else json_text)
    return 0 if plan["all_fit"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
