#!/usr/bin/env python3
"""Satukan pemeriksaan produksi KBM agar kegagalan menghentikan tahap berikutnya.

Bahan riset berupa teks UTF-8 dengan baris `Pola: <label>` (boleh diawali
tanda daftar Markdown). Laporan menunjuk baris sumber setiap pola. Target
bawaan naskah adalah 30 bab dan 1.000 kata isi per bab. Ambang dapat disetel
untuk paket latihan. Bundel lokal harus menuju direktori baru dalam induk
yang sudah ada. Ringkasan royalti dibaca dari CSV melalui royalty_track.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import csv
import json
from pathlib import Path
import re
import sys
from tempfile import TemporaryDirectory
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools.cover_check import check_cover
from tools.kbm_pack_check import DEFAULT_MIN_BYTES
from tools.kbm_pipeline import run_pipeline
from tools.kbm_qc import audit_manuscript as qc_audit_manuscript
from tools.kbm_split import split_manuscript
from tools.royalty_track import RoyaltyTrackError, load_column_map, summarize_royalties

PRODUCE_SCHEMA = "ace.kbm-produce.v1"
_PATTERN_LINE = re.compile(r"^\s*(?:[-*+]\s+)?Pola:\s*(\S.*)$", re.IGNORECASE)


def _research(materials: Path) -> dict[str, Any]:
    references: dict[str, list[int]] = defaultdict(list)
    labels = {}
    for number, line in enumerate(materials.read_text(encoding="utf-8").splitlines(), start=1):
        match = _PATTERN_LINE.match(line)
        if match:
            label = " ".join(match.group(1).split())
            key = label.casefold()
            labels.setdefault(key, label)
            references[key].append(number)
    report = {
        "valid": bool(references),
        "source": str(materials),
        "patterns": [
            {"label": labels[key], "count": len(lines), "lines": lines}
            for key, lines in sorted(references.items())
        ],
    }
    if not references:
        report["error"] = "Tidak ditemukan baris bahan berlabel Pola."
    return report


def _chapter_report(split: dict[str, Any], expected_chapters: int) -> dict[str, Any]:
    chapters = split["chapters"]
    numbers = [chapter["chapter_number"] for chapter in chapters]
    sequence_ok = len(numbers) == expected_chapters and all(
        number == index for index, number in enumerate(numbers, start=1)
    )
    below = [chapter["chapter_number"] for chapter in chapters if chapter["below_threshold"]]
    return {
        "valid": sequence_ok and not below,
        "expected_chapters": expected_chapters,
        "chapter_count": len(chapters),
        "min_words": split["min_words"],
        "sequence_ok": sequence_ok,
        "below_threshold_chapters": below,
        "chapters": [
            {"chapter_number": ch["chapter_number"], "word_count": ch["word_count"]}
            for ch in chapters
        ],
    }


def _manuscript_check(manuscript: Path, *, expected_chapters: int, min_words: int) -> dict[str, Any]:
    if expected_chapters <= 0 or min_words <= 0:
        raise ValueError("Jumlah bab dan jumlah minimum kata wajib positif.")
    with TemporaryDirectory(prefix="kbm-manuscript-") as temporary:
        split = split_manuscript(manuscript, Path(temporary), min_words=min_words)
    return _chapter_report(split, expected_chapters)


def _assemble(
    manuscript: Path,
    cover: Path,
    bundle_dir: Path,
    *,
    expected_chapters: int,
    min_words: int,
    min_bytes: int,
) -> dict[str, Any]:
    if bundle_dir.exists() or bundle_dir.is_symlink():
        raise ValueError("Direktori tujuan paket sudah ada.")
    with TemporaryDirectory(prefix="kbm-package-", dir=bundle_dir.parent) as temporary:
        scratch = Path(temporary)
        bundle = scratch / "upload"
        pipeline = run_pipeline(
            manuscript, scratch / "split", min_words=min_words, min_bytes=min_bytes,
            cover_source=cover, bundle_dir=bundle, strict_cover=True,
        )
        if not pipeline["passed"]:
            return {
                "valid": False,
                "pipeline_stage": pipeline["failed_stage"],
                "errors": pipeline["pack_check"]["errors"],
                "short_chapters": pipeline["short_chapters"],
            }
        # Periksa hasil split yang benar-benar dirakit jika naskah berubah sejak pemeriksaan awal.
        chapters = _chapter_report(pipeline["split"], expected_chapters)
        if not chapters["valid"]:
            return {"valid": False, "pipeline_stage": "manuscript", "chapter_check": chapters}
        manifest = pipeline["bundle"]["manifest"]
        if bundle_dir.exists() or bundle_dir.is_symlink():
            raise ValueError("Direktori tujuan paket sudah ada.")
        bundle.rename(bundle_dir)
    return {
        "valid": True,
        "bundle_dir": str(bundle_dir),
        "manifest_file": str(bundle_dir / "upload_manifest.json"),
        "chapter_count": manifest["chapter_count"],
        "total_words": manifest["total_words"],
    }


def _royalties(paths: list[Path], column_map: Path | None) -> dict[str, Any]:
    if len({path.resolve() for path in paths}) != len(paths):
        raise ValueError("Berkas CSV royalti yang sama diberikan lebih dari sekali.")
    try:
        totals = summarize_royalties(paths, column_map=load_column_map(column_map))
    except (RoyaltyTrackError, csv.Error, TypeError):
        # Kutipan mentah dari CSV dapat memuat informasi akun.
        raise ValueError("Catatan royalti tidak dapat dibaca. Periksa header CSV dan pemetaan kolom.") from None
    return {
        "valid": totals["invalid_rows"] == 0,
        "valid_rows": totals["valid_rows"],
        "invalid_rows": totals["invalid_rows"],
        "invalid_locations": [
            {"file": error["file"], "line": error["line"]} for error in totals["errors"]
        ],
        "totals_by_currency": totals["totals_by_currency"],
        "monthly_totals": totals["monthly_totals"],
    }


def run_production(
    *,
    materials: Path,
    manuscript: Path,
    cover: Path,
    bundle_dir: Path,
    royalty_paths: list[Path],
    royalty_map: Path | None = None,
    title_config: Path | None = None,
    expected_chapters: int = 30,
    min_words: int = 1000,
    min_bytes: int = DEFAULT_MIN_BYTES,
) -> dict[str, Any]:
    """Jalankan tahap yang diperlukan untuk menyiapkan satu paket lokal."""
    checks: list[tuple[str, Any]] = [
        ("research", lambda: _research(materials)),
        ("chapter_check", lambda: _manuscript_check(
            manuscript, expected_chapters=expected_chapters, min_words=min_words,
        )),
    ]
    if title_config is not None:
        checks.append(
            ("editorial_qc", lambda: qc_audit_manuscript(
                manuscript, title_config, min_words=min_words,
            ))
        )
    checks.extend(
        [
            ("cover_check", lambda: check_cover(cover)),
            ("package", lambda: _assemble(
                manuscript, cover, bundle_dir, expected_chapters=expected_chapters,
                min_words=min_words, min_bytes=min_bytes,
            )),
            ("royalty", lambda: _royalties(royalty_paths, royalty_map)),
        ]
    )
    stages: dict[str, Any] = {}
    failed_stage = None
    for name, check in checks:
        try:
            result = check()
        except (OSError, ValueError) as exc:
            # Galat input dari splitter, pemeriksa sampul, dan pipeline turunan ValueError.
            result = {"valid": False, "error": str(exc)}
        stages[name] = result
        if not result["valid"]:
            failed_stage = name
            break
    return {
        "schema": PRODUCE_SCHEMA,
        "passed": failed_stage is None,
        "failed_stage": failed_stage,
        "stages": stages,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--materials", type=Path, required=True, help="Bahan riset dengan baris Pola.")
    parser.add_argument("--manuscript", type=Path, required=True)
    parser.add_argument("--cover", type=Path, required=True)
    parser.add_argument("--bundle-dir", type=Path, required=True)
    parser.add_argument("--royalty-csv", type=Path, required=True, action="append",
                        help="Catatan CSV royalti. Ulangi argumen untuk beberapa berkas.")
    parser.add_argument("--royalty-map", type=Path, help="Pemetaan kolom untuk royalty_track.")
    parser.add_argument("--title-config", type=Path, default=None,
                        help="Konfigurasi judul JSON untuk gerbang QC editorial kbm_qc.")
    parser.add_argument("--chapter-count", type=int, default=30)
    parser.add_argument("--min-words", type=int, default=1000)
    parser.add_argument("--min-bytes", type=int, default=DEFAULT_MIN_BYTES)
    args = parser.parse_args(argv)
    report = run_production(
        materials=args.materials, manuscript=args.manuscript, cover=args.cover,
        bundle_dir=args.bundle_dir, royalty_paths=args.royalty_csv, royalty_map=args.royalty_map,
        title_config=args.title_config, expected_chapters=args.chapter_count,
        min_words=args.min_words, min_bytes=args.min_bytes,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
