"""Tests for the explicit extension boundary and public state witnesses."""

import json
import unittest

from .contract import ContractError, canonical_json
from .dsl import Fuel, compile_ast, predict
from .evaluator.boundary import boundary_report


class BoundaryTests(unittest.TestCase):
    def test_two_families_each_have_all_ten_distinguishing_pairs(self):
        report = boundary_report()
        self.assertEqual([family["family"] for family in report["families"]], ["S", "G"])
        for family in report["families"]:
            pairs = {tuple(w["prefix_counts"]) for w in family["witnesses"]}
            self.assertEqual(len(pairs), 10)
            self.assertEqual(len({value for pair in pairs for value in pair}), 5)
            self.assertGreater(family["distinct_live_prefixes"], family["closed_state_cap"])

    def test_extension_requires_opt_in_and_replays_from_bytes(self):
        for family in boundary_report()["families"]:
            raw = canonical_json(family["ast"])
            example = family["witnesses"][0]
            value = canonical_json(example["inputs"][1])
            with self.assertRaisesRegex(ContractError, "extension is disabled"):
                predict(raw, value, Fuel(2_000))
            reloaded = compile_ast(bytes(raw), allow_extension=True)
            self.assertEqual(reloaded.sha256, family["ast_sha256"])
            self.assertEqual(predict(reloaded.ast, value, Fuel(2_000), allow_extension=True),
                             example["expected"][1])

    def test_extension_size_bounds_hold_even_when_enabled(self):
        report = boundary_report()
        for family in report["families"]:
            for size in (4, 9):
                ast = json.loads(json.dumps(family["ast"]))
                root = ast["ast"]
                if family["family"] == "S":
                    root["table"] = [[[0, 0]] * 3] * size
                else:
                    root["table"] = [[0, 0, 0]] * size
                    root["accept"] = [1] * size
                with self.assertRaises(ContractError):
                    compile_ast(canonical_json(ast), allow_extension=True)
