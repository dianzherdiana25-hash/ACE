"""Verifier drift rasional dan kecocokan frame yang diverifikasi."""
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_perception import _vision, audio_pipeline, media_sync as model
from ace_perception.test_audio_pipeline import fixture, receipt


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(TemporaryDirectory()))
        self.wave = fixture()
        self.receipt = model._canonical(receipt(audio_pipeline.segment(self.wave)))
        rows = []
        for n, stamp in enumerate((1025000, 1080000, 1230000)):
            data = _vision.encode(2, 2, bytes([n, n, 200, 255]))
            path = self.root/f"frame-{n}.pgm"
            path.write_bytes(data)
            rows.append({"time_us": stamp, "file": path.name, "sha256": sha256(data).hexdigest(), "bytes": len(data)})
        self.manifest = model._canonical({"schema": "ace.perception-video-keyframes.v1", "frames": rows})
        self.settings = {"schema": "ace.perception-media-sync.v1", "manifest_sha256": sha256(self.manifest).hexdigest(),
                         "anchors": [{"audio_us": 0, "visual_us": 1000000, "ref": "fixture/a"},
                                     {"audio_us": 100000, "visual_us": 1100000, "ref": "fixture/b"},
                                     {"audio_us": 300000, "visual_us": 1300000, "ref": "fixture/c"}],
                         "maximum_residual_us": 10, "maximum_drift_ppm": 1000, "maximum_frame_gap_us": 30000}

    def sync(self):
        return model.sync(self.wave, self.receipt, self.root, self.manifest, model._canonical(self.settings))

    def test_projects_midpoints_with_offset_and_attached_file_hash(self):
        report = self.sync()
        first, second, third = report["words"]
        self.assertEqual(report["scale"], {"numerator": 1, "denominator": 1})
        self.assertEqual(first["visual_us_rounded"], 1030000)
        self.assertEqual(first["frame"]["file"], "frame-0.pgm")
        self.assertEqual(second["frame"]["file"], "frame-1.pgm")
        self.assertEqual(third["frame"]["time_us"], 1230000)
        self.assertEqual(third["receipt_ref"], "fixture/receipt/2")
        self.assertEqual(len(report["anchors"]), 3)

    def test_outside_anchors_and_no_frame_gap_remain_separate(self):
        self.settings["anchors"].pop()
        self.settings["maximum_frame_gap_us"] = 200
        report = self.sync()
        self.assertEqual([row["status"] for row in report["words"]], ["frame_gap", "frame_gap", "outside_anchors"])
        self.assertTrue(all(row["frame"] is None for row in report["words"]))

    def test_residual_and_hash_tamper_rejected(self):
        self.settings["anchors"][1]["visual_us"] += 11
        with self.assertRaisesRegex(ValueError, "residual"):
            self.sync()
        self.settings["anchors"][1]["visual_us"] -= 11
        (self.root/"frame-0.pgm").write_bytes(b"broken")
        with self.assertRaises(ValueError):
            self.sync()
