#!/usr/bin/env python3
"""Unit tests untuk tools/cover_check.py (WS-C #8)."""
from __future__ import annotations

import json
from pathlib import Path
import struct
import tempfile
import unittest

from tools.cover_check import (
    COVER_CHECK_SCHEMA,
    CoverDecodeError,
    PNG_SIGNATURE,
    check_cover,
    decode_image_dimensions,
    main,
)


def _make_png(width: int, height: int, total_size: int = 2048) -> bytes:
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    ihdr_chunk = struct.pack(">I", len(ihdr_data)) + b"IHDR" + ihdr_data + b"\x00\x00\x00\x00"
    payload = PNG_SIGNATURE + ihdr_chunk
    if len(payload) < total_size:
        payload += b"\x00" * (total_size - len(payload))
    return payload


def _make_jpeg(width: int, height: int, *, sof_marker: int = 0xC0, total_size: int = 2048) -> bytes:
    # SOI + APP0 (length=16) + SOF0/SOF2 (length=11) + EOI
    app0 = b"\xff\xe0" + struct.pack(">H", 16) + b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    sof = bytes([0xFF, sof_marker]) + struct.pack(">HBHHB", 11, 8, height, width, 3) + b"\x00" * 3
    payload = b"\xff\xd8" + app0 + sof + b"\xff\xd9"
    if len(payload) < total_size:
        # Sisipkan padding APP1 sebelum SOF agar panjang total tepat.
        extra_len = max(2, total_size - len(payload) - 2)
        app1 = b"\xff\xe1" + struct.pack(">H", extra_len) + b"\x00" * (extra_len - 2)
        payload = b"\xff\xd8" + app0 + app1 + sof + b"\xff\xd9"
    return payload


class TestCoverCheck(unittest.TestCase):
    def test_valid_png_and_jpeg_pass_default_and_custom_rules(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            png_path = tmp / "cover.png"
            png_path.write_bytes(_make_png(800, 1200, total_size=4096))
            rep_png = check_cover(png_path)
            self.assertEqual(rep_png["schema"], COVER_CHECK_SCHEMA)
            self.assertTrue(rep_png["valid"])
            self.assertEqual(rep_png["decoded"]["format"], "png")
            self.assertEqual(rep_png["decoded"]["width"], 800)
            self.assertEqual(rep_png["decoded"]["height"], 1200)

            jpg_path = tmp / "cover_prog.jpg"
            jpg_path.write_bytes(_make_jpeg(900, 1200, sof_marker=0xC2, total_size=4096))
            rep_jpg = check_cover(jpg_path)
            self.assertTrue(rep_jpg["valid"])
            self.assertEqual(rep_jpg["decoded"]["format"], "jpeg")
            self.assertEqual(rep_jpg["decoded"]["width"], 900)
            self.assertEqual(rep_jpg["decoded"]["height"], 1200)

    def test_rule_violations_dimension_aspect_format_and_size(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            small_png = tmp / "small.png"
            small_png.write_bytes(_make_png(400, 400, total_size=500))
            rules_file = tmp / "rules.json"
            rules_file.write_text(
                json.dumps(
                    {
                        "allowed_formats": ["jpeg"],
                        "min_width": 600,
                        "min_height": 800,
                        "min_bytes": 1024,
                        "target_aspect_ratio": 0.6667,
                        "aspect_tolerance": 0.05,
                    }
                ),
                encoding="utf-8",
            )

            rc = main([str(small_png), "--rules", str(rules_file)])
            self.assertEqual(rc, 1)

            rep = check_cover(small_png, rules=json.loads(rules_file.read_text(encoding="utf-8")))
            self.assertFalse(rep["valid"])
            self.assertIn("min_bytes", rep["failed_rules"])
            self.assertIn("allowed_formats", rep["failed_rules"])
            self.assertIn("min_width", rep["failed_rules"])
            self.assertIn("min_height", rep["failed_rules"])
            self.assertIn("target_aspect_ratio", rep["failed_rules"])

    def test_malformed_and_missing_inputs(self) -> None:
        with self.assertRaises(CoverDecodeError):
            decode_image_dimensions(b"GIF89a\x01\x00\x01\x00")
        with self.assertRaises(CoverDecodeError):
            decode_image_dimensions(PNG_SIGNATURE + b"\x00\x00\x00\x04TEXT")
        with self.assertRaises(CoverDecodeError):
            # JPEG terpotong dengan segmen panjang 0 (invalid).
            decode_image_dimensions(b"\xff\xd8\xff\xe0\x00\x01")
        with self.assertRaises(CoverDecodeError):
            decode_image_dimensions(b"\xff\xd8\xff\xd9")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            corrupt = tmp / "corrupt.jpg"
            corrupt.write_bytes(b"NOT_AN_IMAGE_BYTES" * 100)
            self.assertEqual(main([str(corrupt)]), 1)
            self.assertEqual(main([str(tmp / "missing.png")]), 2)
            valid_png = tmp / "ok.png"
            valid_png.write_bytes(_make_png(700, 1000, total_size=2048))
            self.assertEqual(main([str(valid_png)]), 0)


if __name__ == "__main__":
    unittest.main()
