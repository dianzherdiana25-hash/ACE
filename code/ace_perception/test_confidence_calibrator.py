"""Verifier Brier, ECE dan coverage pada penilaian persepsi yang tertambat."""
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from ace_perception import confidence_calibrator as model


def grade(key, modality, confidence, correct, split):
    return {"id": key, "family": f"fixture/family/{key}", "modality": modality,
            "assessment_ref": f"fixture/grade/{key}", "split": split, "confidence_bp": confidence, "correct": correct}


def fixture():
    observations = [
        grade("a", "image", 1000, True, "train"), grade("b", "image", 4000, False, "train"),
        grade("c", "image", 5000, True, "train"), grade("d", "image", 10_000, True, "train"),
        grade("e", "image", 2000, True, "held_out"), grade("f", "image", 9000, False, "held_out"),
        grade("j", "audio", 5000, False, "train"), grade("k", "audio", 9000, False, "train"),
        grade("l", "audio", 4999, True, "held_out"), grade("m", "audio", 10_000, False, "held_out"),
    ]
    plan = {"plan_ref": "fixture/calibration", "receipt_snapshot_sha256": model._sha(observations),
            "edges_bp": [0, 5000, 10_000], "minimum_examples": 2, "alpha": 1, "beta": 1}
    return plan, observations


def q(numerator, denominator=1):
    return {"numerator": numerator, "denominator": denominator}


def assess(raw, rows):
    return model.assess(raw, rows, model._sha(raw))


def fresh(raw, rows):
    raw["receipt_snapshot_sha256"] = model._sha(rows)
    return assess(raw, rows)


class CalibrationTests(unittest.TestCase):
    def test_brier_ece_recomputed_on_same_heldout_and_rebucketed_after_calibration(self):
        audio, image = assess(*fixture())["modalities"]
        self.assertEqual(image["modality"], "image")
        self.assertEqual([row["confidence"] for row in image["fit"]], [q(1, 2), q(3, 4)])
        self.assertEqual(image["fit"][1]["fit_refs"], ["fixture/grade/c", "fixture/grade/d"])
        self.assertEqual(image["held_out_cases"], 2)
        self.assertEqual(image["paired"], 2)
        self.assertEqual(image["raw_metrics"]["brier"], q(29, 40))
        self.assertEqual(image["raw_metrics"]["ece"], q(17, 20))
        self.assertEqual(image["calibrated_metrics"]["brier"], q(13, 32))
        self.assertEqual(image["calibrated_metrics"]["ece"], q(1, 8))
        self.assertEqual(image["calibrated_metrics"]["bins"], [{
            "left_bp": 5000, "right_bp": 10_000, "cases": 2, "correct": 1, "mean_probability": q(5, 8),
        }])
        self.assertEqual(audio["calibrated_metrics"]["brier"], q(1, 16))

    def test_outside_fit_coverage_is_visible_and_not_counted_by_raw_metrics(self):
        result = assess(*fixture())["modalities"][0]
        self.assertEqual(result["modality"], "audio")
        self.assertEqual(result["held_out_cases"], 2)
        self.assertEqual(result["paired"], 1)
        self.assertEqual(result["held_out"][0]["status"], "unsupported_bin")
        self.assertIsNone(result["held_out"][0]["calibrated"])
        self.assertEqual(result["held_out"][1]["calibrated"], q(1, 4))
        self.assertEqual(result["raw_metrics"]["brier"], q(1))
        self.assertEqual(result["raw_metrics"]["ece"], q(1))

    def test_retains_negative_calibration_gain_when_observed(self):
        raw, rows = fixture()
        for row in rows:
            if row["id"] == "e":
                row["confidence_bp"], row["correct"] = 0, False
            if row["id"] == "f":
                row["confidence_bp"], row["correct"] = 10_000, True
        result = fresh(raw, rows)["modalities"][1]
        self.assertEqual(result["raw_metrics"]["brier"], q(0))
        self.assertEqual(result["calibrated_metrics"]["brier"], q(5, 32))

    def test_no_metric_when_minimum_support_not_met_anywhere(self):
        raw, rows = fixture()
        raw["minimum_examples"] = 3
        report = assess(raw, rows)
        for item in report["modalities"]:
            self.assertEqual(item["paired"], 0)
            self.assertEqual(item["calibrated_metrics"], {"brier": None, "ece": None, "bins": []})
            self.assertEqual(item["raw_metrics"], item["calibrated_metrics"])
            self.assertEqual(item["held_out_cases"], 2)

    def test_family_leakage_rejected_even_under_new_anchor_and_other_modality(self):
        raw, rows = fixture()
        rows[-1]["family"] = rows[0]["family"] + " "
        with self.assertRaisesRegex(ValueError, "tumpang tindih"):
            fresh(raw, rows)

    def test_both_anchors_distinguish_protocol_and_data_change(self):
        raw, rows = fixture()
        anchor = model._sha(raw)
        rows[0]["correct"] = False
        with self.assertRaisesRegex(ValueError, "komitmen"):
            model.assess(raw, rows, anchor)
        raw["receipt_snapshot_sha256"] = model._sha(rows)
        with self.assertRaisesRegex(ValueError, "anchor"):
            model.assess(raw, rows, anchor)

    def test_reject_non_probabilities_bad_receipts_and_malformed_edges(self):
        for key, value in (("correct", 1), ("confidence_bp", 10001), ("confidence_bp", False),
                           ("split", "test"), ("id", "f"), ("assessment_ref", "fixture/grade/f")):
            raw, rows = fixture()
            rows[0][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                fresh(raw, rows)
        for edges in ([0, 100], [1, 5000, 10_000], [0, 0, 10_000], [0, True, 10_000]):
            raw, rows = fixture()
            raw["edges_bp"] = edges
            with self.subTest(edges=edges), self.assertRaises(ValueError):
                assess(raw, rows)

    def test_cli_exact_canonical_report_and_input_immutability(self):
        plan, rows = fixture()
        root = Path(self.enterContext(TemporaryDirectory()))
        rp, ep = root/"protocol.json", root/"receipts.json"
        rp.write_bytes(model._canonical(plan))
        ep.write_bytes(model._canonical(rows))
        command = [sys.executable, "-m", "ace_perception.confidence_calibrator", str(rp), str(ep),
                   "--expect-sha256", model._sha(plan)]
        process = subprocess.run(command, capture_output=True, check=True)
        self.assertEqual(process.stdout, model._canonical(assess(plan, rows)) + b"\n")
        self.assertEqual(json.loads(process.stdout)["plan_ref"], "fixture/calibration")
        self.assertEqual(ep.read_bytes(), model._canonical(rows))
        self.assertEqual(subprocess.run(command, capture_output=True, check=True).stdout, process.stdout)

    def test_training_only_and_empty_corpora_distinguish_calibration_from_measurement(self):
        raw, grades = fixture()
        selected = [row for row in grades if row["split"] == "train"]
        trained = fresh(raw, selected)
        for row in trained["modalities"]:
            self.assertEqual(row["held_out_cases"], 0)
            self.assertEqual(row["paired"], 0)
            self.assertIsNone(row["raw_metrics"]["brier"])
            self.assertIsNone(row["calibrated_metrics"]["ece"])
            self.assertTrue(any(cell["confidence"] is not None for cell in row["fit"]))
        self.assertEqual(fresh(raw, [])["modalities"], [])
