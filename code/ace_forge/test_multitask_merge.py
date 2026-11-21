"""Verifier komposisi rank, bobot sumber, dan retensi probe."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from random import Random
from tempfile import TemporaryDirectory
import unittest

from ace_forge import multitask_merge as model
from ace_forge._forge_io import canonical, identity


BASE = "b" * 64


def adapter(a, b, alpha):
    return {"schema": "ace.lora-dense-adapter.v1", "base_sha256": BASE, "layer": "fixture/layer",
            "rank": len(a), "alpha": alpha, "a": a, "b": b}


def contributor(name, obj, weight):
    return {"task_kind": name, "adapter_sha256": identity(obj), "adapter_ref": f"fixture/adaptor/{name}",
            "weight_bp": weight}


def fixture():
    first = adapter([[1, 0]], [[2], [0]], 2)
    second = adapter([[0, 1]], [[0], [6]], 0.5)
    raw = {"recipe_ref": "fixture/merge", "maximum_rank": 3, "maximum_probe_delta": 7, "contributors": [
        contributor("a", first, 2500), contributor("b", second, 7500),
    ], "probes": [
        {"id": "alpha", "task_kind": "a", "input": [2, 3], "source_ref": "fixture/probe/a"},
        {"id": "beta", "task_kind": "b", "input": [0, 2], "source_ref": "fixture/probe/b"},
    ]}
    return raw, [first, second], identity(raw)


def merge(raw, snapshots):
    return model.merge(raw, snapshots, identity(raw))


class MultiMergeTests(unittest.TestCase):
    def test_merged_weights_and_independent_local_probe_match_manual_arithmetic(self):
        result = model.merge(*fixture())
        self.assertEqual(result["status"], "numeric_probes_within_limits")
        self.assertEqual(result["adapter"]["rank"], 2)
        self.assertEqual(result["adapter"]["alpha"], 2)
        self.assertEqual(result["adapter"]["a"], [[1, 0], [0, 1]])
        self.assertEqual(result["adapter"]["b"], [[1, 0], [0, 2.25]])
        self.assertEqual(result["adapter_sha256"], identity(result["adapter"]))
        probes = result["probes"]
        self.assertEqual(probes[0]["local_delta"], [8, 0])
        self.assertEqual(probes[0]["merged_delta"], [2, 6.75])
        self.assertEqual(probes[0]["max_absolute_delta"], 6.75)
        self.assertEqual(probes[1]["max_absolute_delta"], 1.5)
        self.assertEqual(probes[1]["source_ref"], "fixture/probe/b")

    def test_three_randomized_numeric_factors_reproduce_sum_of_weighted_outputs(self):
        random = Random(52)
        snapshots, contributions = [], []
        weights = [1000, 2000, 7000]
        for ix, rank in enumerate((1, 2, 3)):
            values = adapter([[random.uniform(-3, 3) for _ in range(4)] for _ in range(rank)],
                             [[random.uniform(-2, 2) for _ in range(rank)] for _ in range(3)], ix + 0.25)
            snapshots.append(values)
            contributions.append(contributor(f"t{ix}", values, weights[ix]))
        raw = {**fixture()[0], "maximum_rank": 6, "probes": [], "contributors": contributions}
        combined = model.Factor.read(merge(raw, snapshots)["adapter"])
        for _ in range(20):
            input_ = [random.uniform(-3, 3) for _ in range(4)]
            outputs = [model.Factor.read(row).delta(input_) for row in snapshots]
            expected = [sum(weight * row[index] / 10000 for weight, row in zip(weights, outputs, strict=True))
                        for index in range(3)]
            for actual, oracle in zip(combined.delta(input_), expected, strict=True):
                self.assertAlmostEqual(actual, oracle, places=12)

    def test_failing_probe_is_reported_and_missing_task_keeps_partial_status(self):
        raw, states, _ = fixture()
        raw["maximum_probe_delta"] = 2
        outcome = merge(raw, states)
        self.assertEqual(outcome["status"], "hold")
        self.assertEqual(outcome["failed_probes"], ["alpha"])
        raw["probes"] = raw["probes"][1:]
        report = merge(raw, states)
        self.assertEqual(report["status"], "partially_probed")
        self.assertEqual(report["untested_tasks"], ["a"])

    def test_unexpected_parameter_assets_and_probe_task_are_rejected(self):
        raw, snapshots, anchored = fixture()
        raw["maximum_rank"] = 1
        with self.assertRaisesRegex(model.InputError, "anchor"):
            model.merge(raw, snapshots, anchored)
        with self.assertRaisesRegex(model.InputError, "rank"):
            merge(raw, snapshots)
        raw["maximum_rank"] = 2
        for key, invalid in (("input", [4]), ("task_kind", "unknown")):
            raw["probes"][0][key] = invalid
            with self.subTest(key=key), self.assertRaises(model.InputError):
                merge(raw, snapshots)
            raw["probes"][0] = fixture()[0]["probes"][0]

    def test_duplicate_or_missing_contributor_cannot_inflate_parameter_counts(self):
        raw, states, _ = fixture()
        for adapters in ([states[0]], [states[0], states[0]], [*states, adapter([[1, 2]], [[0], [8]], 2)]):
            with self.subTest(snapshots=len(adapters)), self.assertRaises(model.InputError):
                merge(raw, adapters)
        raw["contributors"][1]["weight_bp"] = 7501
        with self.assertRaisesRegex(model.InputError, "10.000"):
            merge(raw, states)

    def test_wrong_base_and_shapes_fail_even_if_source_digest_is_current(self):
        for key, changed in (("base_sha256", "a" * 64), ("layer", "fixture/other"), ("a", [[1]]), ("b", [[1]])):
            raw, states, _ = fixture()
            states[1][key] = changed
            raw["contributors"][1] = contributor("b", states[1], 7500)
            with self.subTest(key=key), self.assertRaisesRegex(model.InputError, "dimensi"):
                merge(raw, states)

    def test_cli_merge_is_read_only_and_has_nonzero_status_for_failed_probe(self):
        raw, states, _ = fixture()
        raw["maximum_probe_delta"] = 2
        folder = Path(self.enterContext(TemporaryDirectory()))
        rp, sp = folder / "recipe.json", folder / "sources.json"
        rp.write_bytes(canonical(raw))
        sp.write_bytes(canonical(states))
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(model.main([str(rp), str(sp), "--expect-recipe-sha256", identity(raw)]), 1)
        self.assertEqual(json.loads(output.getvalue()), merge(raw, states))
        self.assertEqual(sp.read_bytes(), canonical(states))

    def test_source_array_permutation_preserves_reference_hash_and_numeric_result(self):
        raw, states, _ = fixture()
        self.assertEqual(merge(raw, states), merge(raw, states[::-1]))

    def test_probe_exact_boundary_and_no_probes_have_distinct_status(self):
        raw, snapshots, _ = fixture()
        raw["maximum_probe_delta"] = 6.75
        report = merge(raw, snapshots)
        self.assertEqual(report["status"], "numeric_probes_within_limits")
        self.assertEqual(report["failed_probes"], [])
        empty = merge({**raw, "probes": []}, snapshots)
        self.assertEqual(empty["untested_tasks"], ["a", "b"])
        self.assertEqual(empty["status"], "partially_probed")

    def test_scaling_keeps_original_source_factors_byte_identical(self):
        raw, snapshots, _ = fixture()
        before = canonical(snapshots)
        merge(raw, snapshots)
        self.assertEqual(canonical(snapshots), before)
        self.assertEqual(merge(raw, snapshots)["contributors"][0]["source_ref"], "fixture/adaptor/a")
