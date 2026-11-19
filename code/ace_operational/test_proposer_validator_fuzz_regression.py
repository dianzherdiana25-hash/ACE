"""Regression and fuzz tests for D6 non-finite float bypass & audience TypeError crash in proposer_validator."""
from __future__ import annotations

import copy
import random
import unittest

from ace_operational.proposer_episodes import load_episodes
from ace_operational.proposer_validator import validate_package
from ace_operational.test_proposer_engine import valid_package


class ProposerValidatorFuzzRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.base_pkg = valid_package(load_episodes()[0])

    def test_nan_and_inf_cost_estimate_rejected(self) -> None:
        for bad_val in (float("nan"), float("inf"), float("-inf")):
            for field in ("calls", "wall_seconds", "cost_units"):
                with self.subTest(field=field, val=bad_val):
                    pkg = copy.deepcopy(self.base_pkg)
                    pkg["cost_estimate"][field] = bad_val
                    ok, reasons = validate_package(pkg)
                    self.assertFalse(ok)
                    self.assertTrue(any(f"cost_estimate.{field}" in r for r in reasons), reasons)

    def test_nan_and_inf_cost_ceiling_rejected(self) -> None:
        for bad_val in (float("nan"), float("inf"), float("-inf")):
            for field in ("max_calls", "max_wall_seconds", "max_cost_units"):
                with self.subTest(field=field, val=bad_val):
                    pkg = copy.deepcopy(self.base_pkg)
                    pkg["cost_ceiling"][field] = bad_val
                    ok, reasons = validate_package(pkg)
                    self.assertFalse(ok)
                    self.assertTrue(any(f"cost_ceiling.{field}" in r for r in reasons), reasons)

    def test_non_iterable_or_mixed_ratification_audience_rejected_without_typeerror(self) -> None:
        for bad_aud in (123, None, {"a": 1}, "internal_operator", [1, "a"], [None]):
            with self.subTest(audience=bad_aud):
                pkg = copy.deepcopy(self.base_pkg)
                pkg["ratification"]["audience"] = bad_aud
                ok, reasons = validate_package(pkg)
                self.assertFalse(ok)
                self.assertTrue(any("ratification.audience" in r for r in reasons), reasons)

    def test_exact_cost_ceiling_boundary_accepted_and_bool_rejected(self) -> None:
        pkg = copy.deepcopy(self.base_pkg)
        pkg["cost_estimate"]["calls"] = pkg["cost_ceiling"]["max_calls"]
        pkg["cost_estimate"]["wall_seconds"] = pkg["cost_ceiling"]["max_wall_seconds"]
        pkg["cost_estimate"]["cost_units"] = pkg["cost_ceiling"]["max_cost_units"]
        ok, reasons = validate_package(pkg)
        self.assertTrue(ok, reasons)

        pkg_bool = copy.deepcopy(self.base_pkg)
        pkg_bool["cost_estimate"]["calls"] = False
        pkg_bool["cost_ceiling"]["max_calls"] = True
        ok_b, reasons_b = validate_package(pkg_bool)
        self.assertFalse(ok_b)
        self.assertGreaterEqual(len(reasons_b), 2)

    def test_deterministic_fuzz_300_mutated_packages_fail_closed(self) -> None:
        rng = random.Random(20261119)
        weird_values = [
            None, True, False, 0, -1, float("nan"), float("inf"), float("-inf"),
            "", "x", 123, [1, "a"], {"k": "v"}, ["owner_approval"],
        ]
        top_keys = list(self.base_pkg.keys())
        for i in range(300):
            if i % 15 == 0:
                candidate = rng.choice(weird_values)
            else:
                candidate = copy.deepcopy(self.base_pkg)
                for _ in range(rng.randint(1, 3)):
                    k = rng.choice(top_keys)
                    if k not in candidate:
                        continue
                    v = rng.choice(weird_values)
                    if isinstance(candidate[k], dict) and rng.random() < 0.7 and candidate[k]:
                        subk = rng.choice(list(candidate[k].keys()))
                        candidate[k][subk] = v
                    elif rng.random() < 0.2:
                        del candidate[k]
                    else:
                        candidate[k] = v
            ok, reasons = validate_package(candidate)
            self.assertIsInstance(ok, bool)
            self.assertIsInstance(reasons, list)
            if ok:
                self.assertEqual(reasons, [])
                for f in candidate["cost_estimate"].values():
                    self.assertTrue(isinstance(f, (int, float)) and f == f and abs(f) != float("inf"))


if __name__ == "__main__":
    unittest.main()
