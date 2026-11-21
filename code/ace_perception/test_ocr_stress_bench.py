"""Verifier CER dengan font, transformasi, dan seed yang tertambat."""
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_perception import ocr_stress_bench as model
from ace_perception.test_ocr_engine import canvas, font, raster


class StressTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(TemporaryDirectory()))
        self.samples = font()
        self.asset = raster(canvas(["HAT"]))
        (self.root/"sample.pgm").write_bytes(self.asset)
        self.plan = {"schema": "ace.perception-ocr-stress.v1", "plan_ref": "fixture/stress", "seed": 19,
                     "light_ink": False, "word_gap": 4, "limit_bp": 0, "font_sha256": sha256(self.samples).hexdigest(),
                     "cases": [{"id": "page", "image_path": "sample.pgm", "bytes": len(self.asset), "sha256": sha256(self.asset).hexdigest(),
                                "gold": "HAT", "gold_ref": "fixture/gold"}],
                     "variants": [{"id": "blank", "kind": "horizontal_occlusion", "severity_bp": 10000},
                                  {"id": "salt", "kind": "salt_pepper", "severity_bp": 1000}]}

    def run_bench(self):
        return model.assess(self.root, model._canonical(self.plan), self.samples, model._sha(self.plan))

    def test_clean_measured_zero_and_blank_distortion_measured_full_loss(self):
        result = self.run_bench()
        clean, blank, salt = result["summary"]
        self.assertEqual(clean["cer"], {"numerator": 0, "denominator": 1})
        self.assertEqual(blank["cer_delta"], {"numerator": 1, "denominator": 1})
        self.assertEqual(blank["edits"], 3)
        self.assertEqual(result["cases"][0]["scores"][1]["ocr_status"], "empty")
        self.assertEqual(result["cases"][0]["gold_ref"], "fixture/gold")
        self.assertEqual(salt["gold_chars"], 3)

    def test_seed_repeat_and_source_tampering(self):
        initial = self.run_bench()
        self.assertEqual(initial, self.run_bench())
        self.plan["seed"] += 1
        self.assertNotEqual(initial["cases"][0]["scores"][-1]["image_sha256"],
                            self.run_bench()["cases"][0]["scores"][-1]["image_sha256"])
        (self.root/"sample.pgm").write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "Hash"):
            self.run_bench()
