"""A/B/C v3 DI scorer tests (midday track (a)).

ALL numbers here are synthetic fixtures invented for
the test — they assert the scorer's arithmetic and
fail-closed behaviour, not any measured band. In
particular NO band-1 control B/C rate is claimed
anywhere: the census measured control A only.
"""
import unittest

from ace_operational.abc_v3_scorer import (
    CRITERIA_VERSION, assess_abc_v3, differentiation_index)


def _report(arms=(50.0, 60.0, 70.0), control=(100.0, 100.0, 100.0),
            gate=True, complete=True):
    return {
        "arms": {"A": arms[0], "B": arms[1], "C": arms[2]},
        "control": {"A": control[0], "B": control[1],
                    "C": control[2]},
        "calibration_gate_passed": gate,
        "complete": complete,
    }


class TestDifferentiationIndex(unittest.TestCase):

    def test_terms(self):
        terms = differentiation_index(
            arms={"A": 50.0, "B": 60.0, "C": 70.0},
            control={"A": 100.0, "B": 100.0, "C": 100.0})
        self.assertEqual(terms["c_minus_a_minus_15pp"], 5.0)
        self.assertEqual(terms["b_minus_a_minus_5pp"], 5.0)
        self.assertEqual(terms["control_margin_pp"], 0.0)
        # Control margin is 0 at best (arm A contributes 0),
        # so DI is 0 here — a shortfall index, not a surplus.
        self.assertEqual(terms["differentiation_index_pp"], 0.0)

    def test_control_margin_is_regression_relative(self):
        # A itself below 100 is not a regression: margin 0
        # when no arm falls below A.
        terms = differentiation_index(
            arms={"A": 50.0, "B": 60.0, "C": 70.0},
            control={"A": 96.97, "B": 96.97, "C": 96.97})
        self.assertEqual(terms["control_margin_pp"], 0.0)
        # One arm below A is a negative margin.
        terms = differentiation_index(
            arms={"A": 50.0, "B": 60.0, "C": 70.0},
            control={"A": 100.0, "B": 90.0, "C": 100.0})
        self.assertEqual(terms["control_margin_pp"], -10.0)


class TestAssessAbcV3(unittest.TestCase):

    def test_clear_pass(self):
        out = assess_abc_v3(report=_report())
        self.assertEqual(out["criteria_version"], CRITERIA_VERSION)
        # DI is a shortfall index: 0 = every margin met.
        self.assertEqual(out["differentiation_index_pp"], 0.0)
        self.assertEqual(out["overall"],
                         "DIFFERENTIATION_DEMONSTRATED")
        for clause in out["clauses"].values():
            self.assertEqual(clause["verdict"], "PASS")

    def test_di_exactly_zero_is_a_pass(self):
        out = assess_abc_v3(
            report=_report(arms=(50.0, 55.0, 65.0)))
        self.assertEqual(out["differentiation_index_pp"], 0.0)
        self.assertEqual(out["overall"],
                         "DIFFERENTIATION_DEMONSTRATED")

    def test_di_just_below_zero_fails(self):
        out = assess_abc_v3(
            report=_report(arms=(50.0, 54.9, 65.0)))
        self.assertAlmostEqual(out["differentiation_index_pp"], -0.1)
        self.assertEqual(out["overall"], "NOT_DEMONSTRATED")
        self.assertEqual(
            out["clauses"]["differentiation_index"]["verdict"],
            "FAIL")

    def test_c_term_binds_despite_huge_b_gain(self):
        # (C-A)-15 = -1 binds even though (B-A)-5 = +25.
        out = assess_abc_v3(
            report=_report(arms=(50.0, 80.0, 64.0)))
        self.assertEqual(out["differentiation_index_pp"], -1.0)
        self.assertEqual(out["overall"], "NOT_DEMONSTRATED")

    def test_control_regression_b_voids(self):
        out = assess_abc_v3(
            report=_report(control=(100.0, 90.0, 100.0)))
        self.assertEqual(out["differentiation_index_pp"], -10.0)
        self.assertEqual(out["overall"], "NOT_DEMONSTRATED")

    def test_control_regression_c_voids(self):
        out = assess_abc_v3(
            report=_report(control=(100.0, 100.0, 95.0)))
        self.assertEqual(out["differentiation_index_pp"], -5.0)
        self.assertEqual(out["overall"], "NOT_DEMONSTRATED")

    def test_a_below_100_control_does_not_void_by_itself(self):
        # Regression-relative reading (draft §4): A at 96.97
        # with B/C equal to A is margin 0, not a void.
        # Synthetic equal-rate scenario, not a band-1 claim.
        out = assess_abc_v3(
            report=_report(control=(96.97, 96.97, 96.97)))
        self.assertEqual(out["differentiation_index_pp"], 0.0)
        self.assertEqual(out["overall"],
                         "DIFFERENTIATION_DEMONSTRATED")

    def test_gate_failed_is_saturated_not_null(self):
        out = assess_abc_v3(report=_report(gate=False))
        self.assertEqual(out["overall"], "SATURATED_BY_DESIGN")
        # DI is still computed, as telemetry only (0 = margins met).
        self.assertEqual(out["differentiation_index_pp"], 0.0)
        self.assertEqual(
            out["clauses"]["calibration_gate"]["verdict"], "FAIL")

    def test_incomplete_is_inconclusive(self):
        out = assess_abc_v3(report=_report(complete=False))
        self.assertEqual(out["overall"], "INCONCLUSIVE")
        self.assertEqual(
            out["clauses"]["completeness"]["verdict"], "FAIL")

    def test_gate_failed_beats_incomplete(self):
        out = assess_abc_v3(report=_report(gate=False,
                                           complete=False))
        self.assertEqual(out["overall"], "SATURATED_BY_DESIGN")

    def test_missing_arm_field_is_named_fail(self):
        report = _report()
        del report["arms"]["C"]
        out = assess_abc_v3(report=report)
        self.assertEqual(out["overall"], "NOT_DEMONSTRATED")
        missing = out["clauses"]["report_validity"]["missing"]
        self.assertTrue(any("arms.C" in item for item in missing))
        self.assertIsNone(out["differentiation_index_pp"])

    def test_non_numeric_percent_is_named_fail(self):
        report = _report()
        report["arms"]["B"] = "60"
        out = assess_abc_v3(report=report)
        self.assertEqual(out["overall"], "NOT_DEMONSTRATED")
        missing = out["clauses"]["report_validity"]["missing"]
        self.assertTrue(any("arms.B" in item for item in missing))

    def test_out_of_range_percent_is_named_fail(self):
        report = _report()
        report["arms"]["A"] = 120.0
        out = assess_abc_v3(report=report)
        self.assertEqual(out["overall"], "NOT_DEMONSTRATED")
        missing = out["clauses"]["report_validity"]["missing"]
        self.assertTrue(any("arms.A" in item for item in missing))

    def test_non_boolean_flag_is_named_fail(self):
        report = _report()
        report["calibration_gate_passed"] = 1
        out = assess_abc_v3(report=report)
        self.assertEqual(out["overall"], "NOT_DEMONSTRATED")
        missing = out["clauses"]["report_validity"]["missing"]
        self.assertTrue(any("calibration_gate_passed" in item
                            for item in missing))

    def test_report_not_a_mapping_is_named_fail(self):
        out = assess_abc_v3(report=None)
        self.assertEqual(out["criteria_version"], CRITERIA_VERSION)
        self.assertEqual(out["overall"], "NOT_DEMONSTRATED")
        self.assertIn("not a mapping",
                      out["clauses"]["report_validity"]["missing"][0])


if __name__ == "__main__":
    unittest.main()
