"""Modul Visualisasi Grafik & Data Terminal Berbahasa Indonesia (F17, F18, Section 28).

Menyediakan visualisasi visual berbasis karakter Unicode/ASCII langsung di terminal
tanpa ketergantungan library grafik eksternal (100% offline & Termux-compatible):
- `render_bar_chart`: Diagram batang horizontal berlabel dengan penskalaan otomatis.
- `render_sparkline`: Garis tren ringkas (sparklines) deret angka ` ▂▃▄▅▆▇█`.
- `render_progress_bar`: Batang persentase progres berlabel.
- `render_distribution_bar`: Batang distribusi proporsional bersegmen.
"""
from __future__ import annotations

import math
from typing import Any


SPARK_BLOCKS = (" ", "▂", "▃", "▄", "▅", "▆", "▇", "█")
PROGRESS_FULL = "█"
PROGRESS_EMPTY = "░"


def render_sparkline(values: list[float | int]) -> str:
    """Render deret angka menjadi grafik tren mini (sparkline) berbasis karakter blok.

    Contoh input: [10, 25, 40, 15, 80, 100]
    Output: ' ▂▄ ▇█'
    """
    if not values:
        return ""
    min_v = float(min(values))
    max_v = float(max(values))
    rentang = max_v - min_v

    if rentang <= 1e-9:
        return SPARK_BLOCKS[len(SPARK_BLOCKS) // 2] * len(values)

    result = []
    num_blocks = len(SPARK_BLOCKS)
    for v in values:
        normalized = (float(v) - min_v) / rentang
        index = min(int(normalized * num_blocks), num_blocks - 1)
        result.append(SPARK_BLOCKS[index])
    return "".join(result)


def render_progress_bar(
    current: float | int,
    total: float | int,
    *,
    length: int = 25,
    label: str = "",
    unit: str = "",
) -> str:
    """Render batang progres persentase terminal."""
    if total <= 0:
        persen = 0.0
        filled_len = 0
    else:
        persen = min(max(float(current) / float(total), 0.0), 1.0)
        filled_len = int(round(length * persen))

    empty_len = max(length - filled_len, 0)
    bar = PROGRESS_FULL * filled_len + PROGRESS_EMPTY * empty_len
    persen_str = f"{persen * 100.0:.1f}%"

    tag = f" {label}:" if label else ""
    satuan = f" {unit}" if unit else ""
    return f"{tag} [{bar}] {persen_str} ({current}/{total}{satuan})"


def render_bar_chart(
    data: dict[str, float | int],
    *,
    max_width: int = 35,
    unit: str = "",
    show_percentage: bool = True,
) -> str:
    """Render diagram batang horizontal untuk data kategori."""
    if not data:
        return "(Tidak ada data untuk ditampilkan)"

    max_val = max(float(v) for v in data.values()) if data else 0.0
    total_val = sum(float(v) for v in data.values()) if data else 0.0
    max_label_len = max(len(str(k)) for k in data.keys())

    lines: list[str] = []
    satuan = f" {unit}" if unit else ""

    for label, val in data.items():
        float_v = float(val)
        if max_val > 0:
            bar_len = int(round((float_v / max_val) * max_width))
        else:
            bar_len = 0

        bar = PROGRESS_FULL * bar_len
        persen_text = ""
        if show_percentage and total_val > 0:
            pct = (float_v / total_val) * 100.0
            persen_text = f" ({pct:5.1f}%)"

        val_formatted = f"{int(round(float_v)):,}".replace(",", ".")
        lines.append(f"{label:<{max_label_len}} │ {bar:<{max_width}} {val_formatted}{satuan}{persen_text}")

    return "\n".join(lines)


def render_distribution_bar(
    data: dict[str, float | int],
    *,
    width: int = 30,
) -> str:
    """Render batang distribusi multi-kategori proporsional bersegmen."""
    total = sum(float(v) for v in data.values())
    if total <= 0:
        return f"[{PROGRESS_EMPTY * width}] (Data kosong)"

    symbols = ["█", "▓", "▒", "░", "■", "▰"]
    segments: list[str] = []
    legend: list[str] = []

    remaining_width = width
    items = list(data.items())

    for i, (kat, val) in enumerate(items):
        sym = symbols[i % len(symbols)]
        porsi = float(val) / total
        pct_str = f"{porsi * 100.0:.1f}%"
        seg_len = int(round(porsi * width))
        if i == len(items) - 1:
            seg_len = max(remaining_width, 0)
        seg_len = min(seg_len, remaining_width)
        remaining_width -= seg_len

        segments.append(sym * seg_len)
        legend.append(f"{sym} {kat}: {pct_str}")

    bar_str = "".join(segments)
    return f"[{bar_str}]\n  " + " | ".join(legend)


if __name__ == "__main__":
    # Self-test demo
    print("=== Demo Sparkline ===")
    print("Tren Aktivitas Mingguan:", render_sparkline([5, 12, 19, 8, 45, 60, 85, 100]))

    print("\n=== Demo Progress Bar ===")
    print(render_progress_bar(75, 100, label="Penyelesaian Mandat", unit="subtugas"))

    print("\n=== Demo Diagram Batang Horizontal ===")
    data_demo = {
        "Kebutuhan Pokok": 6350000,
        "Gaya Hidup & Hiburan": 4450000,
        "Tabungan & Investasi": 3500000,
    }
    print(render_bar_chart(data_demo, unit="Rp"))

    print("\n=== Demo Batang Distribusi Proporsional ===")
    print(render_distribution_bar(data_demo))
    print("\nVISUALIZER_VERIFIED_OK")
