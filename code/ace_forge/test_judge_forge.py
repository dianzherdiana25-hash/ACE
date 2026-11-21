"""Verifier blok PAVA, interpolasi, dan evaluasi pasangan."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_forge import judge_forge as model
from ace_forge._forge_io import canonical, identity
from ace_forge.test_forgetting_guard import q


def row(key, raw, truth, *, split="train", domain="fixture", rubric="fixture/rubric"):
    return {"id": key, "family_id": f"family/{key}", "split": split, "domain": domain, "rubric_ref": rubric,
            "score_bp": raw, "assessor_bp": truth, "evaluation_ref": f"fixture/rating/{key}"}


def fixture():
    return {"recipe_ref": "fixture/judge", "minimum_train": 2, "records": [
        row("a", 1000, 2000), row("b", 2000, 8000), row("c", 2000, 6000), row("d", 9000, 4000),
        row("held-a", 1500, 5000, split="held_out"), row("held-b", 2500, 6000, split="held_out"),
        row("extreme", 9999, 200, split="held_out"), row("unseen", 2000, 9000, split="held_out", rubric="fixture/new"),
    ]}


def fit(raw):
    return model.forge(raw, identity(raw))


def rate(query, receipt):
    return model.calibrate(query, identity(query), receipt["adapter"], receipt["adapter_sha256"])


class JudgeTests(unittest.TestCase):
    def test_weighted_pooling_and_paired_errors_match_manual_arithmetic(self):
        result = fit(fixture())
        curve, = result["adapter"]["curves"]
        self.assertEqual(curve["blocks"], [
            {"lo": 1000, "hi": 1000, "count": 1, "value_bp": q(2000)},
            {"lo": 2000, "hi": 9000, "count": 3, "value_bp": q(6000)},
        ])
        scores = result["groups"][1]
        self.assertEqual(scores["mae_before_bp"], q(3500))
        self.assertEqual(scores["mae_after_bp"], q(500))
        self.assertEqual((scores["covered"], scores["held_out"]), (2, 3))
        self.assertEqual(scores["cases"][1]["evaluation_ref"], "fixture/rating/held-a")
        self.assertIsNone(scores["cases"][0]["calibrated_bp"])
        unknown = result["groups"][0]
        self.assertEqual(unknown["status"], "insufficient_training")
        self.assertIsNone(unknown["mae_before_bp"])

    def test_calibration_only_within_original_score_range_and_rubric(self):
        report = fit(fixture())
        query = {"domain": "fixture", "rubric_ref": "fixture/rubric", "score_bp": 1500}
        self.assertEqual(rate(query, report)["calibrated_bp"], q(4000))
        self.assertEqual(rate({**query, "score_bp": 1000}, report)["calibrated_bp"], q(2000))
        self.assertEqual(rate({**query, "score_bp": 9000}, report)["calibrated_bp"], q(6000))
        for modified in ({"score_bp": 999}, {"score_bp": 9001}, {"rubric_ref": "fixture/new"}, {"domain": "other"}):
            with self.subTest(modified=modified):
                self.assertEqual(rate({**query, **modified}, report)["status"], "uncovered")

    def test_equal_training_scores_keep_exact_fraction_at_single_point(self):
        raw = {"recipe_ref": "fixture/judge", "minimum_train": 2,
               "records": [row("a", 3000, 2), row("b", 3000, 3)]}
        report = fit(raw)
        query = {"domain": "fixture", "rubric_ref": "fixture/rubric", "score_bp": 3000}
        self.assertEqual(rate(query, report)["calibrated_bp"], q(5, 2))
        self.assertIsNone(rate({**query, "score_bp": 3001}, report)["calibrated_bp"])

    def test_heldout_labels_do_not_update_curve(self):
        original = fixture()
        report = fit(original)
        original["records"][-3]["assessor_bp"] = 0
        self.assertEqual(fit(original)["adapter_sha256"], report["adapter_sha256"])
        self.assertNotEqual(fit(original)["groups"][1]["mae_after_bp"], report["groups"][1]["mae_after_bp"])

    def test_ambiguous_snapshot_family_and_repeated_rating_are_blocked(self):
        raw = fixture()
        anchor = identity(raw)
        raw["records"][-1]["family_id"] = raw["records"][0]["family_id"]
        with self.assertRaisesRegex(model.InputError, "anchor"):
            model.forge(raw, anchor)
        with self.assertRaisesRegex(model.InputError, "partisi"):
            fit(raw)
        for row in ({"score_bp": True}, {"evaluation_ref": "fixture/rating/a"}):
            raw = fixture()
            raw["records"][1].update(row)
            with self.subTest(row=row), self.assertRaises(model.InputError):
                fit(raw)

    def test_anchored_but_nonmonotone_adapter_fails(self):
        report = fit(fixture())
        report["adapter"]["curves"][0]["blocks"][1]["value_bp"] = q(10)
        report["adapter_sha256"] = identity(report["adapter"])
        query = {"domain": "fixture", "rubric_ref": "fixture/rubric", "score_bp": 6000}
        with self.assertRaisesRegex(model.InputError, "monoton"):
            rate(query, report)

    def test_cli_fit_is_reproducible_and_apply_emits_only_calibrated_score(self):
        raw = fixture()
        expected = fit(raw)
        root = Path(self.enterContext(TemporaryDirectory()))
        p, model_path, query_path = (root / name for name in ("train.json", "model.json", "query.json"))
        p.write_bytes(canonical(raw))
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(model.main([str(p), "--expect-input-sha256", identity(raw)]), 0)
        self.assertEqual(json.loads(output.getvalue()), expected)
        model_path.write_bytes(canonical(expected["adapter"]))
        query = {"domain": "fixture", "rubric_ref": "fixture/rubric", "score_bp": 5000}
        query_path.write_bytes(canonical(query))
        cmd = [str(query_path), "--expect-input-sha256", identity(query), "--adapter", str(model_path),
               "--expect-adapter-sha256", expected["adapter_sha256"]]
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(model.main(cmd), 0)
        self.assertEqual(json.loads(output.getvalue()), rate(query, expected))
        self.assertEqual(p.read_bytes(), canonical(raw))

    def test_duplicate_curves_are_refused_even_with_matching_hash(self):
        report = fit(fixture())
        report["adapter"]["curves"] *= 2
        report["adapter_sha256"] = identity(report["adapter"])
        query = {"domain": "fixture", "rubric_ref": "fixture/rubric", "score_bp": 1000}
        with self.assertRaisesRegex(model.InputError, "ganda"):
            rate(query, report)

    def test_fit_of_ordered_labels_keeps_distinct_endpoint_blocks(self):
        items = [row("a", 0, 1), row("b", 10_000, 3)]
        curve = model._curve(items)
        self.assertEqual([block["count"] for block in curve], [1, 1])
        self.assertEqual(model._calibration(curve, 2500), 1.5)
