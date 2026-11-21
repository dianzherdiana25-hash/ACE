"""Periksa loss DPO, referensi beku, dan gradien pada pasangan fixture."""
from contextlib import redirect_stdout
from copy import deepcopy
from io import StringIO
import json
from math import log
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_forge import preference_trainer as model
from ace_forge._forge_io import canonical, identity


BASE, REFERENCE = "b" * 64, "c" * 64


def pair(key, features, offset=0):
    return {"id": key, "prompt_ref": f"fixture/prompt/{key}", "assessment_ref": f"fixture/assessment/{key}",
            "chosen": {"ref": f"fixture/chosen/{key}", "features": features,
                       "baseline_logp": -1 + offset, "reference_logp": -1},
            "rejected": {"ref": f"fixture/rejected/{key}", "features": [0, 0],
                         "baseline_logp": -1, "reference_logp": -1}}


def fixture():
    source = {"pairs_ref": "fixture/pairs", "feature_spec_ref": "fixture/extractor", "baseline_sha256": BASE,
              "reference_sha256": REFERENCE, "pairs": [pair("one", [1, -1]), pair("two", [2, -1])]}
    recipe = {"recipe_ref": "fixture/recipe", "feature_spec_ref": source["feature_spec_ref"],
              "baseline_sha256": BASE, "reference_sha256": REFERENCE, "pairs_sha256": identity(source),
              "width": 2, "epochs": 100, "beta": 1, "l2": 0.1, "learning_rate": 0.2}
    return recipe, source, recipe["pairs_sha256"]


class DPOTests(unittest.TestCase):
    def test_stable_terms_match_baseline_symmetry_and_extreme_margins(self):
        loss, derivative = model._logistic_terms(0)
        self.assertEqual(loss, log(2))
        self.assertEqual(derivative, 0.5)
        self.assertEqual(model._logistic_terms(10_000), (0, 0))
        self.assertEqual(model._logistic_terms(-10_000), (10_000, 1))
        positive, _ = model._logistic_terms(2)
        negative, _ = model._logistic_terms(-2)
        self.assertAlmostEqual(negative - positive, 2)

    def test_fit_learns_preference_under_shared_normalization(self):
        recipe, source, anchor = fixture()
        old = deepcopy(source)
        result = model.fit(recipe, source, anchor)
        x, y = result["adapter"]["weights"]
        self.assertGreater(x, 0)
        self.assertLess(y, 0)
        self.assertGreater(x - y, 0)
        self.assertGreater(2 * x - y, 0)
        self.assertEqual(result["trace"][0]["mean_dpo_loss"], log(2))
        self.assertLess(result["trace"][-1]["objective"], 0.35)
        self.assertEqual(result["adapter"]["reference_sha256"], REFERENCE)
        self.assertEqual(result["adapter_sha256"], identity(result["adapter"]))
        self.assertEqual(result["pairs"][0]["assessment_ref"], "fixture/assessment/one")
        self.assertEqual(source, old)

    def test_reference_ratio_subtracted_with_correct_sign(self):
        recipe, source, _ = fixture()
        row = source["pairs"][0]
        row["chosen"]["baseline_logp"] = -0.2
        row["chosen"]["reference_logp"] = -0.4
        row["rejected"]["baseline_logp"] = -2
        row["rejected"]["reference_logp"] = -2.4
        value = model.Pair.read(row, recipe["width"], set(), set())
        self.assertAlmostEqual(value.margin, -0.2)

    def test_gradient_including_reference_and_weight_penalty_matches_difference(self):
        recipe, source, _ = fixture()
        source["pairs"][0] = pair("one", [1, -1], offset=0.8)
        source["pairs"][1] = pair("two", [2, -1], offset=-0.5)
        opts = model.Recipe.read(recipe)
        pairs = [model.Pair.read(row, opts.width, set(), set()) for row in source["pairs"]]
        point = [0.2, -0.1]
        _, analytic = model._metrics(point, pairs, opts)
        delta = 1e-6
        for index, expected in enumerate(analytic):
            plus, minus = point[:], point[:]
            plus[index] += delta
            minus[index] -= delta
            above = model._metrics(plus, pairs, opts)[0]["objective"]
            below = model._metrics(minus, pairs, opts)[0]["objective"]
            self.assertAlmostEqual((above - below) / (2 * delta), expected, places=8)

    def test_opposing_pairs_can_leave_calibrated_zero_correction(self):
        recipe, source, _ = fixture()
        source["pairs"][1] = pair("two", [-1, 1])
        recipe["pairs_sha256"] = identity(source)
        result = model.fit(recipe, source, recipe["pairs_sha256"])
        self.assertEqual(result["adapter"]["weights"], [0, 0])
        self.assertEqual(result["trace"][0]["objective"], result["trace"][-1]["objective"])

    def test_tampered_snapshot_and_reference_identity_are_refused(self):
        recipe, source, anchor = fixture()
        source["reference_sha256"] = BASE
        with self.assertRaisesRegex(model.InputError, "anchor"):
            model.fit(recipe, source, anchor)
        recipe["pairs_sha256"] = identity(source)
        with self.assertRaisesRegex(model.InputError, "artefak"):
            model.fit(recipe, source, recipe["pairs_sha256"])

    def test_invalid_pair_and_unverified_aliases_fail_closed(self):
        for key, change in (("chosen", {"features": [0, 0]}), ("chosen", {"baseline_logp": 0.1}),
                            ("rejected", {"reference_logp": True}), ("rejected", {"ref": "fixture/chosen/one"}),
                            ("rejected", {"features": [-1]})):
            recipe, source, _ = fixture()
            source["pairs"][0][key].update(change)
            recipe["pairs_sha256"] = identity(source)
            with self.subTest(change=change), self.assertRaises(model.InputError):
                model.fit(recipe, source, recipe["pairs_sha256"])

    def test_cli_receipt_exact_replay_and_no_input_writes(self):
        recipe, source, anchor = fixture()
        root = Path(self.enterContext(TemporaryDirectory()))
        recipe_path, pairs_path = root / "recipe.json", root / "pairs.json"
        recipe_path.write_bytes(canonical(recipe))
        pairs_path.write_bytes(canonical(source))
        runs = []
        for _ in range(2):
            with redirect_stdout(StringIO()) as output:
                self.assertEqual(model.main([str(recipe_path), str(pairs_path), "--expect-pairs-sha256", anchor]), 0)
            runs.append(output.getvalue())
        self.assertEqual(*runs)
        self.assertEqual(json.loads(runs[0]), model.fit(recipe, source, anchor))
        self.assertEqual(pairs_path.read_bytes(), canonical(source))

    def test_recipe_rejects_negative_regularization_inverted_beta_and_bad_width(self):
        recipe, source, anchor = fixture()
        for change in ({"l2": -1}, {"beta": 0}, {"width": True}, {"epochs": 257}):
            with self.subTest(change=change), self.assertRaises(model.InputError):
                model.fit({**recipe, **change}, source, anchor)
