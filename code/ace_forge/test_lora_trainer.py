"""Periksa gradien dan rekonstruksi adaptor pada matriks numerik fixture."""
from contextlib import redirect_stdout
from copy import deepcopy
from dataclasses import replace
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_forge import lora_trainer as model
from ace_forge._forge_io import canonical, identity


BASE = "a" * 64


def row(key, features):
    frozen = [1, -2]
    shift = features[0] + 2 * features[1]
    return {"id": key, "source_ref": f"fixture/activation/{key}", "input": features,
            "base_output": frozen, "target": [frozen[0] + shift, frozen[1] - 2 * shift]}


def fixture():
    source = {"dataset_ref": "fixture/activation", "base_sha256": BASE, "layer": "fixture.dense",
              "samples": [row(key, sample) for key, sample in
                          zip(("x", "y", "z", "w"), ([1, 0], [0, 1], [-1, 0], [0, -1]), strict=True)]}
    recipe = {"recipe_ref": "fixture/recipe", "layer": source["layer"], "base_sha256": BASE,
              "dataset_sha256": identity(source), "input_width": 2, "output_width": 2,
              "rank": 1, "alpha": 2, "learning_rate": 0.08, "gradient_cap": 10, "epochs": 100, "seed": 52}
    return recipe, source, recipe["dataset_sha256"]


class LoRATests(unittest.TestCase):
    def test_reconstructs_rank_one_delta_without_loading_base_weights(self):
        recipe, source, anchor = fixture()
        frozen_copy = deepcopy(source)
        out = model.fit(recipe, source, anchor)
        a, b = out["adapter"]["a"], out["adapter"]["b"]
        delta = [[2 * left[0] * right for right in a[0]] for left in b]
        for actual, expected in zip(delta[0] + delta[1], [1, 2, -2, -4], strict=True):
            self.assertAlmostEqual(actual, expected, places=6)
        self.assertEqual(out["sample_refs"][0], {"id": "w", "source_ref": "fixture/activation/w"})
        self.assertEqual(out["adapter"]["base_sha256"], BASE)
        self.assertEqual(out["dataset_sha256"], anchor)
        self.assertEqual(out["adapter_sha256"], identity(out["adapter"]))
        self.assertEqual(source, frozen_copy)
        self.assertAlmostEqual(out["trace"][0]["train_mse"], 6.25)
        self.assertLess(out["trace"][-1]["train_mse"], 1e-12)

    def test_analytic_gradients_match_finite_difference_for_both_factors(self):
        recipe, source, _ = fixture()
        options = model.Recipe.read(recipe)
        samples = [model.Sample.read(row, options, set(), set()) for row in source["samples"]]
        a, b = [[0.3, -0.5]], [[-0.7], [0.4]]
        scale = 1.9
        _, ga, gb = model._loss_gradient(a, b, samples, scale, gradient=True)
        delta = 1e-6
        for matrix, gradient in ((a, ga), (b, gb)):
            for i, grad_row in enumerate(gradient):
                for j, expected in enumerate(grad_row):
                    prior = matrix[i][j]
                    matrix[i][j] = prior + delta
                    above = model._loss_gradient(a, b, samples, scale, gradient=False)[0]
                    matrix[i][j] = prior - delta
                    below = model._loss_gradient(a, b, samples, scale, gradient=False)[0]
                    matrix[i][j] = prior
                    self.assertAlmostEqual((above - below) / (2 * delta), expected, places=7)

    def test_clipping_bounds_actual_update_norm(self):
        recipe, _, _ = fixture()
        options = replace(model.Recipe.read(recipe), gradient_cap=2, learning_rate=0.1)
        a, b = [[0.0]], [[0.0]]
        self.assertTrue(model._update(a, b, [[3.0]], [[4.0]], options))
        self.assertAlmostEqual(a[0][0], -0.12)
        self.assertAlmostEqual(b[0][0], -0.16)

    def test_identity_tied_to_source_before_optimizer_starts(self):
        recipe, source, anchor = fixture()
        source["samples"][0]["target"][0] += 1
        with self.assertRaisesRegex(model.InputError, "anchor"):
            model.fit(recipe, source, anchor)
        for difference in ({"base_sha256": "b" * 64}, {"layer": "wrong"}):
            recipe, source, _ = fixture()
            source.update(difference)
            recipe["dataset_sha256"] = identity(source)
            with self.assertRaisesRegex(model.InputError, "lapisan berbeda"):
                model.fit(recipe, source, recipe["dataset_sha256"])

    def test_shape_duplicate_provenance_and_limits_are_explicit(self):
        for changed in ({"id": "y"}, {"source_ref": "fixture/activation/y"}, {"input": [0]},
                        {"base_output": [True, False]}, {"target": [100_001, 0]}):
            recipe, source, _ = fixture()
            source["samples"][0].update(changed)
            recipe["dataset_sha256"] = identity(source)
            with self.subTest(changed=changed), self.assertRaises(model.InputError):
                model.fit(recipe, source, recipe["dataset_sha256"])
        recipe, source, anchor = fixture()
        for changed in ({"rank": 3}, {"seed": True}, {"epochs": 0}, {"alpha": 0}):
            with self.subTest(changed=changed), self.assertRaises(model.InputError):
                model.fit({**recipe, **changed}, source, anchor)

    def test_deterministic_tensor_shape_float_trace_and_cli(self):
        recipe, source, anchor = fixture()
        result = model.fit(recipe, source, anchor)
        self.assertEqual(result, model.fit(recipe, source, anchor))
        self.assertEqual(len(result["adapter"]["a"]), 1)
        self.assertEqual(len(result["adapter"]["b"]), 2)
        self.assertEqual(len(result["trace"]), recipe["epochs"] + 1)
        root = Path(self.enterContext(TemporaryDirectory()))
        recipe_path, source_path = root / "recipe.json", root / "activation.json"
        recipe_path.write_bytes(canonical(recipe))
        source_path.write_bytes(canonical(source))
        with redirect_stdout(StringIO()) as out:
            self.assertEqual(model.main([str(recipe_path), str(source_path), "--expect-dataset-sha256", anchor]), 0)
        self.assertEqual(json.loads(out.getvalue()), result)
        self.assertEqual(source_path.read_bytes(), canonical(source))

    def test_zero_residual_leaves_adapter_delta_zero(self):
        recipe, source, _ = fixture()
        for item in source["samples"]:
            item["target"] = item["base_output"][:]
        recipe["dataset_sha256"] = identity(source)
        result = model.fit(recipe, source, recipe["dataset_sha256"])
        self.assertEqual(result["adapter"]["b"], [[0], [0]])
        self.assertTrue(all(row["train_mse"] == 0 for row in result["trace"]))

    def test_empty_dataset_has_no_receipt_with_fabricated_zero_mse(self):
        recipe, source, _ = fixture()
        source["samples"].clear()
        recipe["dataset_sha256"] = identity(source)
        with self.assertRaisesRegex(model.InputError, "memerlukan contoh"):
            model.fit(recipe, source, recipe["dataset_sha256"])

    def test_large_fit_rejected_before_parameters_are_initialized(self):
        recipe, source, _ = fixture()
        large = {**recipe, "input_width": 128, "output_width": 128, "rank": 16, "epochs": 256}
        source["samples"] *= 8
        large["dataset_sha256"] = identity(source)
        with self.assertRaisesRegex(model.InputError, "anggaran operasi"):
            model.fit(large, source, large["dataset_sha256"])
