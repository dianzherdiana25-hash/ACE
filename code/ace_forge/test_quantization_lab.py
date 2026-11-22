"""Verifier bitpacking, skala per baris, dan error probe aritmetika."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_forge import quantization_lab as model
from ace_forge._forge_io import canonical, identity
from ace_forge.merge_lab import Tensor


def fixture():
    weights = {"weights_ref": "fixture/weights", "architecture_ref": "fixture/architecture",
               "tensors": [{"name": "dense", "shape": [2, 3], "values": [0, 1, 2, -5, 0.5, 1.5]}]}
    recipe = {"recipe_ref": "fixture/quant", "source_sha256": identity(weights), "bits": 4, "mode": "tensor",
              "maximum_weight_error": 0.5, "maximum_probe_error": 0.5, "probes": [
                  {"id": "direction", "tensor": "dense", "input": [0, 1, 0], "source_ref": "fixture/probe"},
              ]}
    return recipe, weights, identity(recipe)


def calculate(recipe, weights):
    return model.quantify(recipe, weights, identity(recipe))


class QuantizationTests(unittest.TestCase):
    def test_4_bit_signed_codes_roundtrip_and_error_uses_reconstruction(self):
        recipe, weights, anchor = fixture()
        result = model.quantify(recipe, weights, anchor)
        packed, = result["artifact"]["tensors"]
        self.assertEqual(packed["payload_hex"], "109321")
        self.assertEqual(result["payload_bytes_total"], 3)
        self.assertEqual(result["artifact_sha256"], identity(result["artifact"]))
        restored = model.reconstruct(packed)
        for actual, expected in zip(restored, (0, 5/7, 15/7, -5, 5/7, 10/7), strict=True):
            self.assertAlmostEqual(actual, expected)
        metrics, = result["tensor_errors"]
        self.assertAlmostEqual(metrics["max_absolute_error"], 2/7)
        self.assertAlmostEqual(result["probes"][0]["max_absolute_output_error"], 2/7)
        self.assertEqual(result["status"], "numeric_probes_within_limits")

    def test_first_axis_divides_matrix_by_row_scale(self):
        recipe, weights, _ = fixture()
        whole = calculate(recipe, weights)
        recipe["mode"] = "first_axis"
        separated = calculate(recipe, weights)
        self.assertEqual(separated["artifact"]["tensors"][0]["scales"], [2/7, 5/7])
        self.assertLess(separated["tensor_errors"][0]["max_absolute_error"], whole["tensor_errors"][0]["max_absolute_error"])

    def test_8_bit_expands_payload_reduces_error_on_fixture(self):
        recipe, weights, _ = fixture()
        low = calculate(recipe, weights)
        high = calculate({**recipe, "bits": 8}, weights)
        self.assertEqual(high["payload_bytes_total"], 6)
        self.assertLess(high["tensor_errors"][0]["mean_squared_error"], low["tensor_errors"][0]["mean_squared_error"])
        self.assertLess(high["probes"][0]["max_absolute_output_error"], low["probes"][0]["max_absolute_output_error"])

    def test_hold_when_weight_or_probe_error_exceeds_limit_and_partial_if_unseen(self):
        recipe, weights, _ = fixture()
        for option, field in (("maximum_weight_error", "failed_tensors"), ("maximum_probe_error", "failed_probes")):
            result = calculate({**recipe, option: 0.05}, weights)
            self.assertEqual(result["status"], "hold")
            self.assertTrue(result[field])
        result = calculate({**recipe, "probes": []}, weights)
        self.assertEqual(result["status"], "partially_probed")
        self.assertEqual(result["unprobed_tensors"], ["dense"])

    def test_odd_nibble_padding_and_restricted_codes_are_validated(self):
        packed = model._quantize(Tensor("tiny", (3,), (-1.0, 1.0, 0.0)), 4, "first_axis")
        self.assertEqual(packed["payload_hex"], "7900")
        self.assertEqual(model.reconstruct(packed), [-1, 1, 0])
        for bad, reason in (("7910", "padding"), ("7800", "simetri"), ("790", "Payload"), ("79  ", "Payload")):
            with self.subTest(bad=bad), self.assertRaisesRegex(model.InputError, reason):
                model.reconstruct({**packed, "payload_hex": bad})

    def test_zero_tensor_scalar_and_smallest_subnormal_never_divide_by_zero(self):
        for shape, values in (((), (0.0,)), ((2,), (0.0, 0.0)), ((1,), (5e-324,))):
            with self.subTest(shape=shape, values=values):
                for bits in (4, 8):
                    encoded = model._quantize(Tensor("small", shape, values), bits, "first_axis")
                    self.assertEqual(model.reconstruct(encoded), list(values))

    def test_source_and_recipe_anchors_reject_tampering(self):
        recipe, weights, anchor = fixture()
        weights["tensors"][0]["values"][0] += 1
        with self.assertRaisesRegex(model.InputError, "Snapshot"):
            model.quantify(recipe, weights, anchor)
        with self.assertRaisesRegex(model.InputError, "anchor"):
            model.quantify({**recipe, "bits": 8}, weights, anchor)

    def test_scale_vector_and_unsupported_modes_fail_closed(self):
        recipe, weights, _ = fixture()
        for change in ({"bits": 6}, {"mode": "second_axis"}, {"maximum_weight_error": -1},
                       {"probes": [{**recipe["probes"][0], "input": [1, 2]}]},
                       {"probes": [{**recipe["probes"][0], "tensor": "missing"}]}):
            with self.subTest(change=change), self.assertRaises(model.InputError):
                calculate({**recipe, **change}, weights)
        packed = model._quantize(Tensor("tiny", (1,), (4.0,)), 8, "tensor")
        for scales in ([], [0], [True], [1, 2]):
            with self.subTest(scales=scales), self.assertRaises(model.InputError):
                model.reconstruct({**packed, "scales": scales})

    def test_cli_verifies_snapshot_and_emits_artifact_plus_measurement(self):
        recipe, weights, anchor = fixture()
        root = Path(self.enterContext(TemporaryDirectory()))
        r, s = root / "recipe.json", root / "snapshot.json"
        r.write_bytes(canonical(recipe))
        s.write_bytes(canonical(weights))
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(model.main([str(r), str(s), "--expect-recipe-sha256", anchor]), 0)
        self.assertEqual(json.loads(output.getvalue()), model.quantify(recipe, weights, anchor))
        self.assertEqual(s.read_bytes(), canonical(weights))

    def test_all_tensor_provenance_survives_partial_probe_report(self):
        recipe, weights, _ = fixture()
        weights["tensors"].append({"name": "scalar", "shape": [], "values": [2]})
        recipe["source_sha256"] = identity(weights)
        value = calculate(recipe, weights)
        self.assertEqual(value["status"], "partially_probed")
        self.assertEqual(value["unprobed_tensors"], ["scalar"])
        scalar = value["artifact"]["tensors"][1]
        self.assertEqual(model.reconstruct(scalar), [2])
        self.assertEqual(value["source_ref"], "fixture/weights")

    def test_reconstruction_rejects_forbidden_negative_8_bit_code(self):
        tensor = model._quantize(Tensor("tiny", (1,), (-2.0,)), 8, "tensor")
        self.assertEqual(tensor["payload_hex"], "81")
        with self.assertRaisesRegex(model.InputError, "simetri"):
            model.reconstruct({**tensor, "payload_hex": "80"})
