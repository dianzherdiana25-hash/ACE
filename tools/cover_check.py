#!/usr/bin/env python3
"""Validator gambar sampul KBM berbasis dekoder biner stdlib murni (WS-C #8).

Membaca header dan dimensi piksel langsung dari berkas biner PNG (`IHDR`) atau
JPEG (`SOF*`) tanpa dependensi eksternal, lalu memvalidasi format, dimensi
(lebar/tinggi), rasio aspek, dan ukuran byte terhadap berkas `--rules`.

Exit code:
- 0: sampul memenuhi seluruh aturan
- 1: ditemukan pelanggaran aturan atau format gambar korup/tidak didukung
- 2: masukan CLI atau berkas aturan tidak valid / tidak ditemukan
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct
import sys
from typing import Any

COVER_CHECK_SCHEMA = "ace.cover-check.v1"

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
JPEG_SOI = b"\xff\xd8"

DEFAULT_RULES: dict[str, Any] = {
    "allowed_formats": ["png", "jpeg"],
    "min_width": 600,
    "min_height": 800,
    "max_width": 4096,
    "max_height": 6144,
    "min_aspect_ratio": 0.5,
    "max_aspect_ratio": 0.85,
    "min_bytes": 1024,
    "max_bytes": 10 * 1024 * 1024,
}


class CoverCheckInputError(ValueError):
    """Kesalahan berkas masukan CLI atau berkas `--rules` tidak sah."""


class CoverDecodeError(ValueError):
    """Gambar tidak valid, terpotong, atau format biner tidak dikenali."""


def decode_image_dimensions(data: bytes) -> dict[str, Any]:
    """Dekode format, lebar, dan tinggi piksel dari byte biner PNG atau JPEG."""
    if len(data) < 4:
        raise CoverDecodeError("Berkas gambar terlalu pendek untuk header biner.")

    if data.startswith(PNG_SIGNATURE):
        if len(data) < 24:
            raise CoverDecodeError("Header PNG terpotong (kurang dari 24 byte).")
        chunk_len = struct.unpack(">I", data[8:12])[0]
        chunk_type = data[12:16]
        if chunk_type != b"IHDR" or chunk_len < 13:
            raise CoverDecodeError(f"Chunk pertama PNG bukan IHDR sah (chunk={chunk_type!r}, len={chunk_len}).")
        width, height = struct.unpack(">II", data[16:24])
        if width <= 0 or height <= 0:
            raise CoverDecodeError(f"Dimensi PNG tidak sah: {width}x{height}.")
        return {
            "format": "png",
            "width": width,
            "height": height,
            "aspect_ratio": round(width / height, 6),
        }

    if data.startswith(JPEG_SOI):
        idx = 2
        n = len(data)
        while idx < n:
            while idx < n and data[idx] == 0xFF:
                idx += 1
            if idx >= n:
                break
            marker = data[idx]
            idx += 1
            if marker == 0x00:
                continue
            # Marker tanpa panjang segmen: RST0..RST7 (D0..D7), SOI (D8), EOI (D9), TEM (01).
            if marker in (0x01, 0xD8) or (0xD0 <= marker <= 0xD7):
                continue
            if marker == 0xD9 or marker == 0xDA:
                # EOI atau Start of Scan sebelum SOF ditemukan.
                break
            if idx + 2 > n:
                raise CoverDecodeError("Segmen JPEG terpotong saat membaca panjang blok.")
            seg_len = struct.unpack(">H", data[idx : idx + 2])[0]
            if seg_len < 2 or idx + seg_len > n:
                raise CoverDecodeError(f"Panjang segmen JPEG tidak sah: {seg_len}.")
            # SOF markers: C0..CF kecuali DHT(C4), JPG(C8), DAC(CC).
            if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                if seg_len < 7 or idx + 7 > n:
                    raise CoverDecodeError("Segmen SOF JPEG terpotong.")
                height, width = struct.unpack(">HH", data[idx + 3 : idx + 7])
                if width <= 0 or height <= 0:
                    raise CoverDecodeError(f"Dimensi JPEG tidak sah: {width}x{height}.")
                return {
                    "format": "jpeg",
                    "width": width,
                    "height": height,
                    "aspect_ratio": round(width / height, 6),
                }
            idx += seg_len
        raise CoverDecodeError("Marker SOF dimensi JPEG tidak ditemukan pada aliran biner.")

    raise CoverDecodeError("Format gambar tidak dikenali (hanya mendukung PNG dan JPEG).")


def load_rules(rules_path: Path | None) -> dict[str, Any]:
    """Muat aturan validasi sampul dari JSON atau pakai aturan bawaan."""
    if rules_path is None:
        return dict(DEFAULT_RULES)
    if not rules_path.is_file():
        raise CoverCheckInputError(f"Berkas rules tidak ditemukan: {rules_path}")
    try:
        raw = json.loads(rules_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CoverCheckInputError(f"Gagal membaca rules JSON '{rules_path}': {exc}") from exc
    if not isinstance(raw, dict):
        raise CoverCheckInputError("Berkas rules wajib berupa objek JSON.")

    merged = dict(DEFAULT_RULES)
    for key, val in raw.items():
        merged[key] = val

    allowed = merged.get("allowed_formats")
    if not isinstance(allowed, list) or not allowed or not all(isinstance(x, str) and x.strip() for x in allowed):
        raise CoverCheckInputError("`allowed_formats` pada rules wajib daftar string tidak kosong.")
    merged["allowed_formats"] = [x.strip().lower() for x in allowed]
    return merged


def check_cover(image_path: Path, rules: dict[str, Any] | None = None) -> dict[str, Any]:
    """Validasi berkas gambar sampul terhadap aturan format, dimensi, rasio, dan byte."""
    if not image_path.is_file():
        raise CoverCheckInputError(f"Berkas gambar sampul tidak ditemukan: {image_path}")
    try:
        data = image_path.read_bytes()
    except OSError as exc:
        raise CoverCheckInputError(f"Gagal membaca berkas gambar '{image_path}': {exc}") from exc

    active_rules = dict(DEFAULT_RULES)
    if rules is not None:
        active_rules.update(rules)

    size_bytes = len(data)
    checks: list[dict[str, Any]] = []

    def record(rule_name: str, passed: bool, actual: Any, expected: Any, message: str) -> None:
        checks.append(
            {
                "rule": rule_name,
                "passed": bool(passed),
                "actual": actual,
                "expected": expected,
                "message": message,
            }
        )

    min_bytes = active_rules.get("min_bytes")
    if min_bytes is not None:
        ok = size_bytes >= int(min_bytes)
        record(
            "min_bytes",
            ok,
            size_bytes,
            f">= {min_bytes}",
            "Ukuran berkas memenuhi batas minimum." if ok else f"Ukuran berkas {size_bytes} byte < {min_bytes} byte.",
        )

    max_bytes = active_rules.get("max_bytes")
    if max_bytes is not None:
        ok = size_bytes <= int(max_bytes)
        record(
            "max_bytes",
            ok,
            size_bytes,
            f"<= {max_bytes}",
            "Ukuran berkas memenuhi batas maksimum." if ok else f"Ukuran berkas {size_bytes} byte > {max_bytes} byte.",
        )

    decoded: dict[str, Any] | None = None
    decode_error: str | None = None
    try:
        decoded = decode_image_dimensions(data)
    except CoverDecodeError as exc:
        decode_error = str(exc)

    if decoded is None:
        record("image_header", False, None, "valid PNG or JPEG header", decode_error or "Decode gagal.")
        return {
            "schema": COVER_CHECK_SCHEMA,
            "file": str(image_path),
            "size_bytes": size_bytes,
            "decoded": None,
            "valid": False,
            "failed_rules": [c["rule"] for c in checks if not c["passed"]],
            "checks": checks,
        }

    record("image_header", True, decoded["format"], "valid header", "Header biner gambar sah.")
    allowed_formats = [str(f).lower() for f in active_rules.get("allowed_formats", ["png", "jpeg"])]
    fmt_ok = decoded["format"] in allowed_formats
    record(
        "allowed_formats",
        fmt_ok,
        decoded["format"],
        allowed_formats,
        "Format gambar diizinkan." if fmt_ok else f"Format '{decoded['format']}' tidak ada di {allowed_formats}.",
    )

    w = decoded["width"]
    h = decoded["height"]
    ar = decoded["aspect_ratio"]

    if active_rules.get("min_width") is not None:
        mw = int(active_rules["min_width"])
        ok = w >= mw
        record("min_width", ok, w, f">= {mw}", "Lebar memenuhi minimum." if ok else f"Lebar {w}px < {mw}px.")
    if active_rules.get("max_width") is not None:
        xw = int(active_rules["max_width"])
        ok = w <= xw
        record("max_width", ok, w, f"<= {xw}", "Lebar memenuhi maksimum." if ok else f"Lebar {w}px > {xw}px.")
    if active_rules.get("min_height") is not None:
        mh = int(active_rules["min_height"])
        ok = h >= mh
        record("min_height", ok, h, f">= {mh}", "Tinggi memenuhi minimum." if ok else f"Tinggi {h}px < {mh}px.")
    if active_rules.get("max_height") is not None:
        xh = int(active_rules["max_height"])
        ok = h <= xh
        record("max_height", ok, h, f"<= {xh}", "Tinggi memenuhi maksimum." if ok else f"Tinggi {h}px > {xh}px.")

    if active_rules.get("min_aspect_ratio") is not None:
        mar = float(active_rules["min_aspect_ratio"])
        ok = ar >= mar
        record(
            "min_aspect_ratio",
            ok,
            ar,
            f">= {mar}",
            "Rasio aspek memenuhi batas minimum." if ok else f"Rasio aspek {ar} < {mar}.",
        )
    if active_rules.get("max_aspect_ratio") is not None:
        xar = float(active_rules["max_aspect_ratio"])
        ok = ar <= xar
        record(
            "max_aspect_ratio",
            ok,
            ar,
            f"<= {xar}",
            "Rasio aspek memenuhi batas maksimum." if ok else f"Rasio aspek {ar} > {xar}.",
        )

    if active_rules.get("target_aspect_ratio") is not None:
        tar = float(active_rules["target_aspect_ratio"])
        tol = float(active_rules.get("aspect_tolerance", 0.05))
        ok = abs(ar - tar) <= tol
        record(
            "target_aspect_ratio",
            ok,
            ar,
            f"{tar} +/- {tol}",
            "Rasio aspek sesuai target." if ok else f"Rasio aspek {ar} menyimpang dari {tar} +/- {tol}.",
        )

    failed_rules = [c["rule"] for c in checks if not c["passed"]]
    return {
        "schema": COVER_CHECK_SCHEMA,
        "file": str(image_path),
        "size_bytes": size_bytes,
        "decoded": decoded,
        "valid": len(failed_rules) == 0,
        "failed_rules": failed_rules,
        "checks": checks,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validator format, dimensi piksel, rasio aspek, dan ukuran sampul KBM."
    )
    parser.add_argument("image", type=Path, help="Path berkas gambar sampul (.png atau .jpg/.jpeg).")
    parser.add_argument("--rules", type=Path, default=None, help="Path berkas JSON aturan sampul.")
    args = parser.parse_args(argv)

    try:
        rules = load_rules(args.rules)
        report = check_cover(args.image, rules=rules)
    except CoverCheckInputError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
