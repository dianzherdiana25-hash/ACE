#!/usr/bin/env python3
"""Baca rancangan Markdown dan cetak templat praregistrasi EVO ke stdout."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import re


TITLE = re.compile(r"^# RANCANGAN (EVO[ _][0-9]{4})(?:\s|$)", re.IGNORECASE)
SECTIONS = (
    ("Konteks & alasan paket baru", ("konteks", "latar belakang")),
    ("Klaim yang diuji", ("hipotesis", "klaim yang diuji")),
    ("Prasyarat instrumen & bangun", ("prasyarat", "instrumen")),
    ("Kalibrasi pita & korpus beku", ("kalibrasi", "korpus beku")),
    ("Lengan & gerbang pengukuran", ("sketsa lengan", "lengan", "gerbang pengukuran")),
    ("Ikatan tetap", ("ikatan tetap", "yang belum diputuskan")),
)
HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*$")
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")


def _headings(lines: list[str]) -> list[tuple[int, str]]:
    headings = []
    open_fence = ""
    for index, line in enumerate(lines):
        fence = FENCE.match(line)
        if fence:
            marks, rest = fence.groups()
            if not open_fence:
                open_fence = marks
            elif marks.startswith(open_fence) and not rest.strip():
                open_fence = ""
            continue
        heading = HEADING.match(line)
        if not open_fence and heading:
            headings.append((index, heading.group(1)))
    return headings


def render_draft(design: Path) -> str:
    """Salin bagian yang dikenali sebagai kutipan, dengan isian untuk review."""
    raw = design.read_bytes()
    lines = raw.decode("utf-8").splitlines()
    headings = _headings(lines)
    titles = [m for index, _ in headings if (m := TITLE.match(lines[index]))]
    if len(titles) != 1:
        raise ValueError("Rancangan harus memuat satu judul '# RANCANGAN EVO NNNN'.")
    evo_id = titles[0].group(1).upper().replace("_", " ")
    digest = hashlib.sha256(raw).hexdigest()
    output = [
        f"# PREREGISTRASI {evo_id} — DRAF",
        "",
        "Status penyusunan: DRAF. Konfirmasi isian dan ratifikasi melalui review.",
        "",
        f"SHA-256 sumber rancangan: `{digest}`",
    ]
    for number, (label, keywords) in enumerate(SECTIONS):
        output.extend(("", f"## §{number} {label}", ""))
        for position, (index, header) in enumerate(headings):
            if not lines[index].startswith("## "):
                continue
            key = re.sub(r"^(?:§\s*)?\d+[.)]?\s+", "", header.casefold())
            if not any(key == name or key.startswith((name + " ", name + ":")) for name in keywords):
                continue
            # H3 and deeper headings are part of the source H2 section.
            end = next((later for later, _ in headings[position + 1:]
                        if lines[later].startswith(("# ", "## "))), len(lines))
            output.extend((f"Kutipan rancangan, baris {index + 1}–{end}.", ""))
            output.extend(f"    {line}" for line in lines[index:end])
            output.append("")
        output.append("[Isi keputusan dan bukti pendukung.]")
    return "\n".join(output) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("design", type=Path, help="Rancangan Markdown lokal.")
    args = parser.parse_args(argv)
    try:
        draft = render_draft(args.design)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    print(draft, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
