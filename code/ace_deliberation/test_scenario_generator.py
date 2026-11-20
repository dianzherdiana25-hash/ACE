"""Periksa peluang total, kondisi bersarang, dan ketidakmungkinan pengamatan."""
from contextlib import redirect_stdout
from fractions import Fraction
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_deliberation import scenario_generator as scenario


def rational(a, b=1):
    return {"numerator": a, "denominator": b}


def branch(identifier, paths):
    return {"id": identifier, "kind": "branch", "condition": identifier,
            "source_ref": f"fixture/condition/{identifier}", "outcomes": [
                {"label": label, "target": target, "probability": rational(*p),
                 "source_ref": f"fixture/{identifier}/{label}"}
                for label, target, p in paths
            ]}


def leaf(identifier, utility):
    return {"id": identifier, "kind": "leaf", "consequence": identifier,
            "source_ref": f"fixture/leaf/{identifier}", "utility": utility}


def fixture():
    return {"root": "top", "observations": {}, "nodes": [
        branch("top", [("clear", "sub", (1, 3)), ("rain", "later", (2, 3))]),
        branch("sub", [("light", "low", (1, 4)), ("bright", "high", (3, 4))]),
        leaf("low", -2), leaf("high", 6), leaf("later", 0),
    ]}


class ScenarioTests(unittest.TestCase):
    def test_joint_distribution_and_payoff_use_exact_fractions(self):
        report = scenario.generate(fixture())
        paths = {row["leaf"]["id"]: row for row in report["outcomes"]}
        self.assertEqual(paths["low"]["prior_probability"], rational(1, 12))
        self.assertEqual(paths["high"]["prior_probability"], rational(1, 4))
        self.assertEqual(paths["later"]["prior_probability"], rational(2, 3))
        self.assertEqual(report["expected_utility"], rational(4, 3))
        self.assertEqual([row["source_ref"] for row in paths["low"]["path"]],
                         ["fixture/top/clear", "fixture/sub/light"])

    def test_deep_observation_means_ancestor_path_was_visited(self):
        raw = {**fixture(), "observations": {"sub": "light"}}
        report = scenario.generate(raw)
        self.assertEqual(report["observation_mass"], rational(1, 12))
        self.assertEqual(report["expected_utility"], rational(-2))
        self.assertEqual(sum(Fraction(**row["posterior_probability"]) for row in report["outcomes"]), 1)

    def test_contradictory_observations_have_no_posterior(self):
        raw = {**fixture(), "observations": {"top": "rain", "sub": "light"}}
        gate = scenario.generate(raw)
        self.assertEqual(gate["status"], "impossible_observations")
        self.assertIsNone(gate["expected_utility"])
        self.assertTrue(all(item["posterior_probability"] is None for item in gate["outcomes"]))

    def test_rejects_non_normalized_branches_unreachable_nodes_and_shared_parents(self):
        for fault in ("probability", "unreachable", "shared"):
            raw = fixture()
            if fault == "probability":
                raw["nodes"][0]["outcomes"][0]["probability"] = rational(1, 4)
            elif fault == "unreachable":
                raw["nodes"].append(leaf("orphan", 1))
            else:
                raw["nodes"][1]["outcomes"][-1]["target"] = "later"
            with self.subTest(fault=fault), self.assertRaises(scenario.ScenarioError):
                scenario.generate(raw)

    def test_cli_report_is_stable_under_branch_and_node_reordering(self):
        raw = fixture()
        expected = scenario.generate(raw)
        raw["nodes"].reverse()
        for node in raw["nodes"]:
            if node["kind"] == "branch":
                node["outcomes"].reverse()
        path = Path(self.enterContext(TemporaryDirectory())) / "scenarios.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(scenario.main([str(path)]), 0)
        self.assertEqual(json.loads(output.getvalue()), expected)

    def test_zero_mass_branch_is_structural_but_not_observable(self):
        raw = fixture()
        raw["nodes"][0]["outcomes"][0]["probability"] = rational(0)
        raw["nodes"][0]["outcomes"][1]["probability"] = rational(1)
        raw["observations"] = {"top": "clear"}
        report = scenario.generate(raw)
        self.assertEqual(report["observation_mass"], rational(0))
        self.assertIsNone(report["expected_utility"])
        self.assertTrue(any(row["consistent_with_observations"] for row in report["outcomes"]))

    def test_distribution_merges_equal_utilities_and_omits_impossible_outcomes(self):
        raw = fixture()
        raw["nodes"][-1]["utility"] = 6
        report = scenario.generate(raw)
        self.assertEqual(report["utility_distribution"], [
            {"utility": -2, "probability": rational(1, 12)},
            {"utility": 6, "probability": rational(11, 12)},
        ])
        raw["observations"] = {"top": "rain"}
        self.assertEqual(scenario.generate(raw)["utility_distribution"],
                         [{"utility": 6, "probability": rational(1)}])

    def test_root_can_be_a_single_observed_leaf(self):
        raw = {"root": "fixed", "observations": {}, "nodes": [leaf("fixed", -7)]}
        report = scenario.generate(raw)
        self.assertEqual(report["expected_utility"], rational(-7))
        self.assertEqual(report["outcomes"][0]["path"], [])

    def test_refuses_unknown_observation_label_before_constructing_posterior(self):
        with self.assertRaises(scenario.ScenarioError):
            scenario.generate({**fixture(), "observations": {"sub": "absent"}})
