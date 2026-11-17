#!/usr/bin/env python3
"""Scaffold paket eksperimen EVO baru (WS-F #16).

Menghasilkan kerangka awal untuk eksperimen EVO baru di direktori target:
1. Draf preregistrasi Markdown mengikuti templat rumah ACE (`§0`–`§5`).
2. Manifest stage kosong (`manifest.json`) yang kompatibel dengan `tools/stage_verify.py`.
3. Konfigurasi hook census JSON (`census_hook.json`) dengan default fail-closed.

Tidak menyentuh instrumen pengukuran, korpus beku, ataupun state program lama.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


SCHEMA_VERSION = "ace.evo-scaffold.v1"
STAGE_SCHEMA = "ace.stage-verify.v1"
CENSUS_HOOK_SCHEMA = "ace.evo-census-hook.v1"

_EVO_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{1,63}$")


class EvoScaffoldError(ValueError):
    """Kesalahan parameter atau penulisan scaffold EVO."""


def normalize_evo_id(raw: str) -> str:
    if not isinstance(raw, str):
        raise EvoScaffoldError("evo_id harus berupa string.")
    cleaned = raw.strip()
    if not _EVO_ID_RE.match(cleaned):
        raise EvoScaffoldError(
            f"evo_id tidak sah ({raw!r}); gunakan huruf/angka/'_'/'-' panjang 2..64."
        )
    return cleaned


def render_preregistration_md(
    *,
    evo_id: str,
    title: str,
    author: str,
    date_str: str,
    claim: str,
    min_score: int,
    max_score: int,
    arms: Sequence[str],
    delivery_gate: float,
) -> str:
    arms_label = " vs ".join(arms)
    return f"""# PREREGISTRASI {evo_id} — DRAF ({author}, {date_str})
## {title}

> **Status:** DRAF — belum diratifikasi hub dan belum dijalankan.

## §0 Konteks & alasan paket baru

- ID eksperimen: `{evo_id}`
- Tanggal penyusunan draf: {date_str}
- Ringkasan konteks: [isi alasan eksperimen ini dibuka dan relasinya terhadap hasil EVO sebelumnya]

## §1 Klaim yang diuji

{claim}

## §2 Prasyarat instrumen & bangun

- Instrumen penilaian dan jalur keputusan tetap dipegang engineer utama; scaffold ini tidak mengubah scorer/judge.
- Catat hash commit basis (`main`) dan prasyarat PR yang wajib ter-ratifikasi sebelum lari dimulai.

## §3 Kalibrasi pita & korpus beku

- Pita sensitivitas target: rata-rata skor kalibrasi dalam rentang `[{min_score}, {max_score}]`.
- Korpus kandidat wajib dibekukan bersama SHA-256 sebelum tahap screening/probe berjalan.
- Aturan henti keras: hentikan gelombang sesuai batas preregistrasi; jika ukuran probe set di bawah ambang minimum, catat `INSTRUMEN_TIDAK_CUKUP`.

## §4 Lengan & gerbang pengukuran

- Lengan uji: `{arms_label}`
- Gerbang pengantaran minimum: `{delivery_gate:.2f}`
- Write-back memori selama fase probe: **NONAKTIF** (`false`).

## §5 Ikatan tetap

- Fail-closed pada baris error pertama; baris outage disimpan terpisah sebagai bukti audit.
- Korpus tidak ditambal di tengah gelombang aktif.
- Tidak ada merge otomatis maupun perubahan model/venue tanpa ratifikasi ulang.
"""


def build_stage_manifest(evo_id: str, date_str: str) -> Dict[str, Any]:
    return {
        "schema": STAGE_SCHEMA,
        "evo_id": evo_id,
        "created_date": date_str,
        "status": "empty_scaffold",
        "files": [],
    }


def build_census_hook(
    *,
    evo_id: str,
    date_str: str,
    min_score: int,
    max_score: int,
    arms: Sequence[str],
    delivery_gate: float,
    min_probe_episodes: int,
    max_waves: int,
) -> Dict[str, Any]:
    return {
        "schema": CENSUS_HOOK_SCHEMA,
        "evo_id": evo_id,
        "created_date": date_str,
        "enabled": False,
        "fail_closed": True,
        "writeback_during_probe": False,
        "corpus": {
            "manifest_path": "manifest.json",
            "expected_sha256": None,
            "frozen": False,
        },
        "calibration": {
            "band_min_score": min_score,
            "band_max_score": max_score,
            "min_probe_episodes": min_probe_episodes,
            "max_waves": max_waves,
        },
        "arms": list(arms),
        "delivery_gate": delivery_gate,
    }


def scaffold_evo(
    *,
    evo_id: str,
    out_dir: Path,
    title: str = "Rancangan eksperimen baru",
    author: str = "Ian",
    date_str: Optional[str] = None,
    claim: str = "[Isi hipotesis utama dan metrik perbandingan antar lengan.]",
    min_score: int = 45,
    max_score: int = 75,
    arms: Sequence[str] = ("SEEDED", "KOSONG"),
    delivery_gate: float = 0.75,
    min_probe_episodes: int = 8,
    max_waves: int = 2,
    force: bool = False,
) -> Dict[str, Any]:
    """Tulis berkas scaffold EVO ke `out_dir` secara deterministik."""
    norm_id = normalize_evo_id(evo_id)
    if min_score < 0 or max_score > 100 or min_score > max_score:
        raise EvoScaffoldError(f"Rentang skor pita tidak sah: [{min_score}, {max_score}]")
    if not (0.0 <= delivery_gate <= 1.0):
        raise EvoScaffoldError(f"delivery_gate harus dalam [0.0, 1.0]: {delivery_gate}")
    if min_probe_episodes < 1 or max_waves < 1:
        raise EvoScaffoldError("min_probe_episodes dan max_waves harus >= 1")
    clean_arms = [a.strip() for a in arms if isinstance(a, str) and a.strip()]
    if len(clean_arms) < 2:
        raise EvoScaffoldError("Minimal harus ada 2 lengan uji yang tidak kosong.")

    resolved_date = date_str or _dt.date.today().isoformat()
    slug = norm_id.upper()

    target_dir = Path(out_dir)
    prereg_path = target_dir / f"PREREGISTRASI_{slug}_DRAF.md"
    manifest_path = target_dir / "manifest.json"
    hook_path = target_dir / "census_hook.json"
    planned_paths = [prereg_path, manifest_path, hook_path]

    if not force:
        collisions = [str(p) for p in planned_paths if p.exists()]
        if collisions:
            raise EvoScaffoldError(
                "Berkas tujuan sudah ada (gunakan --force untuk menimpa): "
                + ", ".join(collisions)
            )

    target_dir.mkdir(parents=True, exist_ok=True)

    prereg_text = render_preregistration_md(
        evo_id=norm_id,
        title=title,
        author=author,
        date_str=resolved_date,
        claim=claim,
        min_score=min_score,
        max_score=max_score,
        arms=clean_arms,
        delivery_gate=delivery_gate,
    )
    manifest_obj = build_stage_manifest(norm_id, resolved_date)
    hook_obj = build_census_hook(
        evo_id=norm_id,
        date_str=resolved_date,
        min_score=min_score,
        max_score=max_score,
        arms=clean_arms,
        delivery_gate=delivery_gate,
        min_probe_episodes=min_probe_episodes,
        max_waves=max_waves,
    )

    prereg_path.write_text(prereg_text, encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest_obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    hook_path.write_text(json.dumps(hook_obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    return {
        "schema": SCHEMA_VERSION,
        "evo_id": norm_id,
        "created_date": resolved_date,
        "out_dir": str(target_dir),
        "files": {
            "preregistration_md": str(prereg_path),
            "stage_manifest_json": str(manifest_path),
            "census_hook_json": str(hook_path),
        },
        "summary": {
            "arms": clean_arms,
            "band": [min_score, max_score],
            "delivery_gate": delivery_gate,
            "stage_manifest_files_count": 0,
            "hook_enabled": False,
        },
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Scaffold paket eksperimen EVO baru (draf preregistrasi, manifest stage kosong, hook census)."
    )
    parser.add_argument("--evo-id", required=True, help="ID EVO target (mis. EVO_0008)")
    parser.add_argument("--out-dir", required=True, help="Direktori output scaffold")
    parser.add_argument("--title", default="Rancangan eksperimen baru", help="Subjudul preregistrasi")
    parser.add_argument("--author", default="Ian", help="Nama penyusun draf")
    parser.add_argument("--date", default=None, help="Tanggal YYYY-MM-DD (default: hari ini)")
    parser.add_argument(
        "--claim",
        default="[Isi hipotesis utama dan metrik perbandingan antar lengan.]",
        help="Teks klaim §1",
    )
    parser.add_argument("--min-score", type=int, default=45, help="Batas bawah pita kalibrasi (default: 45)")
    parser.add_argument("--max-score", type=int, default=75, help="Batas atas pita kalibrasi (default: 75)")
    parser.add_argument("--arms", nargs="+", default=["SEEDED", "KOSONG"], help="Daftar nama lengan uji")
    parser.add_argument("--delivery-gate", type=float, default=0.75, help="Gerbang pengantaran (default: 0.75)")
    parser.add_argument("--min-probe-episodes", type=int, default=8, help="Minimum episode probe set (default: 8)")
    parser.add_argument("--max-waves", type=int, default=2, help="Batas gelombang kalibrasi (default: 2)")
    parser.add_argument("--force", action="store_true", help="Izinkan menimpa berkas yang sudah ada")

    args = parser.parse_args(argv)
    try:
        report = scaffold_evo(
            evo_id=args.evo_id,
            out_dir=Path(args.out_dir),
            title=args.title,
            author=args.author,
            date_str=args.date,
            claim=args.claim,
            min_score=args.min_score,
            max_score=args.max_score,
            arms=args.arms,
            delivery_gate=args.delivery_gate,
            min_probe_episodes=args.min_probe_episodes,
            max_waves=args.max_waves,
            force=args.force,
        )
    except EvoScaffoldError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
