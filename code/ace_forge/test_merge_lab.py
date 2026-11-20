"""Periksa operasi tensor, kompatibilitas dan provenance tanpa menjalankan organ."""
from contextlib import redirect_stdout
from copy import deepcopy
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_forge import merge_lab as model
from ace_forge._forge_io import canonical, identity


def snapshot(key, dense, bias=0):
    return {"weights_ref": f"fixture/{key}", "architecture_ref": "fixture/architecture",
            "tensors": [{"name": "dense", "shape": [2, 2], "values": dense},
                        {"name": "bias", "shape": [], "values": [bias]}]}


def proportional(row, value):
    return {"snapshot_sha256": identity(row), "weight_bp": value}


def fixture():
    left = snapshot("left", [0, 4, 0, 4], bias=2)
    right = snapshot("right", [4, 0, 4, 0], bias=-2)
    recipe = {"recipe_ref": "fixture/recipe", "output_ref": "fixture/merged",
              "mode": "interpolate", "base_sha256": None,
              "weights": [proportional(left, 7500), proportional(right, 2500)]}
    return recipe, [left, right], identity(recipe)


def output_values(result):
    return {row["name"]: row["values"] for row in result["output"]["tensors"]}


class MergeTests(unittest.TestCase):
    def test_interpolation_matches_manual_values_shapes_and_distance(self):
        report = model.merge(*fixture())
        self.assertEqual(output_values(report), {"bias": [1], "dense": [1, 3, 1, 3]})
        self.assertEqual(report["tensor_count"], 2)
        self.assertEqual(report["elements"], 5)
        self.assertEqual(report["output_sha256"], identity(report["output"]))
        cards = {row["snapshot_ref"]: row for row in report["snapshots"]}
        self.assertEqual(cards["fixture/left"]["mean_squared_distance"], 1)
        self.assertEqual(cards["fixture/right"]["mean_squared_distance"], 9)
        self.assertEqual(cards["fixture/right"]["weight_bp"], 2500)

    def test_signed_deltas_use_base_exactly_once(self):
        recipe, sources, _ = fixture()
        base = snapshot("base", [2, 2, 2, 2], bias=1)
        recipe.update(mode="task_delta", base_sha256=identity(base),
                      weights=[proportional(sources[0], 5000), proportional(sources[1], -5000)])
        report = model.merge(recipe, [*sources, base], identity(recipe))
        self.assertEqual(output_values(report), {"bias": [3], "dense": [0, 4, 0, 4]})
        row = next(row for row in report["snapshots"] if row["snapshot_ref"] == "fixture/base")
        self.assertIsNone(row["weight_bp"])
        self.assertEqual(row["mean_squared_distance"], 4)

    def test_equal_weight_sources_produce_identical_result_after_array_reorder(self):
        recipe, sources, anchor = fixture()
        previous = deepcopy(sources)
        one = model.merge(recipe, sources, anchor)
        another = model.merge(recipe, sources[::-1], anchor)
        self.assertEqual(one, another)
        self.assertEqual(sources, previous)
        self.assertEqual([tensor["name"] for tensor in one["output"]["tensors"]], ["bias", "dense"])

    def test_unchanged_value_has_zero_distance_even_when_refs_differ(self):
        recipe, sources, _ = fixture()
        sources[1]["tensors"] = deepcopy(sources[0]["tensors"])
        recipe["weights"][1] = proportional(sources[1], 2500)
        self.assertTrue(all(row["mean_squared_distance"] == 0
                            for row in model.merge(recipe, sources, identity(recipe))["snapshots"]))

    def test_changed_snapshot_or_coefficient_is_rejected_against_anchor(self):
        recipe, sources, anchor = fixture()
        sources[1]["tensors"][0]["values"][0] = 9
        with self.assertRaisesRegex(model.InputError, "hilang"):
            model.merge(recipe, sources, anchor)
        recipe["weights"][0]["weight_bp"] = 6666
        with self.assertRaisesRegex(model.InputError, "anchor"):
            model.merge(recipe, sources, anchor)

    def test_reshaping_equal_sized_tensor_or_switching_architecture_is_invalid(self):
        for change in ("shape", "architecture", "name"):
            recipe, sources, _ = fixture()
            matrix = sources[1]["tensors"][0]
            if change == "shape":
                matrix["shape"] = [4]
            elif change == "architecture":
                sources[1]["architecture_ref"] = "fixture/other"
            else:
                matrix["name"] = "attention"
            recipe["weights"][1] = proportional(sources[1], 2500)
            with self.subTest(change=change), self.assertRaisesRegex(model.InputError, "kompatibel"):
                model.merge(recipe, sources, identity(recipe))

    def test_unknown_and_duplicate_weights_and_extra_snapshots_are_refused(self):
        recipe, sources, _ = fixture()
        for weights in ([recipe["weights"][0]] * 2,
                        [recipe["weights"][0], {**recipe["weights"][1], "weight_bp": 1000}],
                        [recipe["weights"][0], {**recipe["weights"][1], "weight_bp": 0}]):
            altered = {**recipe, "weights": weights}
            with self.subTest(weights=weights), self.assertRaises(model.InputError):
                model.merge(altered, sources, identity(altered))
        with self.assertRaisesRegex(model.InputError, "Daftar"):
            model.merge(recipe, [*sources, snapshot("unregistered", [0] * 4)], identity(recipe))

    def test_invalid_tensor_and_overflowing_delta_fail_before_exporting_weights(self):
        for numbers in ([1, 2, 3], [True, 2, 3, 4], [1, 2, 3, model.MAX_VALUE + 1]):
            recipe, sources, _ = fixture()
            sources[0]["tensors"][0]["values"] = numbers
            recipe["weights"][0] = proportional(sources[0], 7500)
            with self.subTest(numbers=numbers), self.assertRaises(model.InputError):
                model.merge(recipe, sources, identity(recipe))
        recipe, sources, _ = fixture()
        base = snapshot("base", [model.MAX_VALUE] * 4)
        contrast = snapshot("contrast", [-model.MAX_VALUE] * 4)
        recipe.update(mode="task_delta", base_sha256=identity(base),
                      weights=[proportional(sources[0], -10000), proportional(contrast, -10000)])
        with self.assertRaisesRegex(model.InputError, "keluar"):
            model.merge(recipe, [sources[0], contrast, base], identity(recipe))

    def test_recipe_without_base_cannot_claim_delta_and_base_must_not_be_contributor(self):
        recipe, sources, _ = fixture()
        recipe["mode"] = "task_delta"
        with self.assertRaisesRegex(model.InputError, "Mode"):
            model.merge(recipe, sources, identity(recipe))
        recipe["base_sha256"] = identity(sources[0])
        with self.assertRaisesRegex(model.InputError, "basis"):
            model.merge(recipe, sources, identity(recipe))

    def test_cli_outputs_exact_replay_from_canonical_snapshot_input(self):
        recipe, sources, anchor = fixture()
        root = Path(self.enterContext(TemporaryDirectory()))
        recipe_path, source_path = root / "recipe.json", root / "snapshots.json"
        recipe_path.write_bytes(canonical(recipe))
        source_path.write_bytes(canonical(sources))
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(model.main([str(recipe_path), str(source_path), "--expect-recipe-sha256", anchor]), 0)
        self.assertEqual(json.loads(output.getvalue()), model.merge(recipe, sources, anchor))
        self.assertEqual(source_path.read_bytes(), canonical(sources))

    def test_architecture_checks_all_inputs_including_delta_base(self):
        recipe, sources, _ = fixture()
        base = snapshot("base", [2] * 4)
        base["architecture_ref"] = "fixture/base-only"
        recipe.update(mode="task_delta", base_sha256=identity(base))
        with self.assertRaisesRegex(model.InputError, "kompatibel"):
            model.merge(recipe, [*sources, base], identity(recipe))
