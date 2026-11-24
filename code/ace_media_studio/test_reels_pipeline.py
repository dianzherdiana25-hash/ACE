"""Tests for Real 9:16 Vertical Reels Video Pipeline (`ffmpeg` + `ffprobe` MP4 rendering)."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import unittest

from ace_media_studio._contracts import ContractError
from ace_media_studio.reels_pipeline import render_vertical_reels
from ace_operational.quality_gate_engine import evaluate_reels_quality


class ReelsPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
            self.skipTest("ffmpeg / ffprobe tidak tersedia")
        self._tmp = tempfile.TemporaryDirectory(prefix="ace-reels-")
        self.out_dir = Path(self._tmp.name) / "reels_out"

    def tearDown(self) -> None:
        if hasattr(self, "_tmp"):
            self._tmp.cleanup()

    def test_render_real_9_16_mp4_and_pass_high_bar_gate(self) -> None:
        package = {
            "title": "Rahasia Hook 3 Detik Reels",
            "promise_terms": ["hook", "detik", "reels"],
            "action_terms": ["lihat", "coba", "simpan"],
            "cta": "Simpan reels ini dan ikuti tips selanjutnya!",
            "source_ref": "riset/reels_01",
            "scenes": [
                {"id": "sc_hook", "source_ref": "riset/1", "narration": "Kenapa 3 detik pertama menentukan Reels? Lihat cara ini!", "duration_ms": 3500, "has_visual_action": True},
                {"id": "sc_body", "source_ref": "riset/2", "narration": "Coba tampilkan visual dinamis dengan teks besar terbaca.", "duration_ms": 4000, "has_visual_action": True},
                {"id": "sc_cta", "source_ref": "riset/3", "narration": "Simpan dan ikuti panduan lengkapnya sekarang!", "duration_ms": 3000, "has_visual_action": True, "cta": "IKUTI SEKARANG"},
            ],
            "facts": [
                {"id": "f1", "text": "Format 9:16 dengan teks kontras tinggi mempertahankan penonton mobile", "source_ref": "riset/1", "approved": True},
            ],
            "tags": ["reels", "ace"],
        }
        bundle = render_vertical_reels(package, self.out_dir, width=720, height=1280, fps=24)
        self.assertTrue(Path(bundle["video_path"]).is_file())
        self.assertTrue(Path(bundle["cover_path"]).is_file())
        self.assertTrue(Path(bundle["subtitle_path"]).is_file())
        probe = bundle["probe"]
        self.assertEqual((probe["width"], probe["height"]), (720, 1280))
        self.assertTrue(probe["portrait_9_16"])
        self.assertEqual(probe["audio_codec"], "aac")
        self.assertGreaterEqual(probe["duration_sec"], 5.5)

        meta = json.loads(Path(bundle["metadata_receipt_path"]).read_text(encoding="utf-8"))
        self.assertEqual(meta["status"], "ready")

        verdict = evaluate_reels_quality(
            {**package, "video_path": bundle["video_path"]},
            min_score_bp=8500,
            require_rendered_mp4=True,
        )
        self.assertTrue(verdict["passed"], verdict)
        self.assertTrue(verdict["checks"]["mp4_probe"]["portrait_9_16"])

    def test_rejects_landscape_or_out_of_window_duration(self) -> None:
        with self.assertRaises(ContractError):
            render_vertical_reels({"title": "Bad", "scenes": [{"narration": "x", "duration_ms": 3000}]}, self.out_dir, width=1280, height=720)
        with self.assertRaises(ContractError):
            render_vertical_reels({"title": "Too short", "scenes": [{"narration": "x", "duration_ms": 2000}]}, self.out_dir, width=720, height=1280)


if __name__ == "__main__":
    unittest.main()
