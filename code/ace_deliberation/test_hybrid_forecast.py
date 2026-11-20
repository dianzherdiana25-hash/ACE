"""Uji penggabungan Brier, holdout dan batas informasi."""
from contextlib import redirect_stdout
from fractions import Fraction
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_deliberation import hybrid_forecast as model


def q(n, d=1):
    return {"numerator": n, "denominator": d}


def forecast(ref, value, when="2026-11-10T12:00:00Z"):
    return {"probability": value, "at": when, "ref": f"fixture/{ref}"}


def pair(key, outcome, human=None, machine=None):
    return {
        "question_id": key, "human": forecast(f"{key}/human", human or q(1)),
        "machine": forecast(f"{key}/machine", machine or q(0)),
        "outcome": outcome, "resolved_at": "2026-11-15T00:00:00Z", "resolution_ref": f"fixture/{key}/resolution",
    }


def fixture():
    return {
        "target": {"question_id": "new", "forecast_at": "2026-11-20T00:00:00Z", "forecast_ref": "fixture/hybrid",
                   "human": forecast("new/human", q(3, 4)), "machine": forecast("new/machine", q(1, 4))},
        "history": [pair("a", 1), pair("b", 0), pair("c", 1)],
        "minimum_pairs": 2, "protocol_ref": "fixture/protocol",
    }


class HybridTests(unittest.TestCase):
    def test_weight_and_forecast_match_manual_optimum(self):
        report = model.fit(fixture())
        self.assertEqual(report["status"], "forecasted")
        self.assertEqual(report["fit"]["human_weight"], q(2, 3))
        self.assertEqual(report["fit"]["machine_weight"], q(1, 3))
        self.assertEqual(report["forecast"], {
            "question_id": "new", "forecast_ref": "fixture/hybrid",
            "forecast_at": "2026-11-20T00:00:00+00:00", "probability": "0.583333333333333333",
        })
        self.assertEqual(report["fit"]["training_brier"], {
            "human": q(1, 3), "machine": q(2, 3), "hybrid": q(2, 9),
        })

    def test_leave_one_out_uses_weights_refit_without_each_case(self):
        report = model.fit(fixture())
        self.assertEqual(report["fit"]["leave_one_out_brier"], {
            "human": q(1, 3), "machine": q(2, 3), "hybrid": q(1, 2),
        })
        at_minimum = model.fit({**fixture(), "minimum_pairs": 3})
        self.assertIsNone(at_minimum["fit"]["leave_one_out_brier"])

    def test_weight_is_clipped_to_convex_mix_in_both_directions(self):
        for outcome, expected in ((0, q(0)), (1, q(1))):
            with self.subTest(outcome=outcome):
                raw = {**fixture(), "history": [pair(key, outcome, q(3, 4), q(1, 4)) for key in "abc"]}
                self.assertEqual(model.fit(raw)["fit"]["human_weight"], expected)

    def test_solver_matches_grid_for_asymmetric_predictions(self):
        history = [pair("a", 1, q(4, 5), q(1, 8)), pair("b", 0, q(1, 3), q(3, 5)),
                   pair("c", 1, q(1, 9), q(3, 4))]
        report = model.fit({**fixture(), "history": history})
        optimum = Fraction(**report["fit"]["training_brier"]["hybrid"])
        for numerator in range(21):
            weight = Fraction(numerator, 20)
            loss = sum(
                (weight * Fraction(**row["human"]["probability"])
                 + (1 - weight) * Fraction(**row["machine"]["probability"]) - row["outcome"])**2
                for row in history
            ) / len(history)
            self.assertLessEqual(optimum, loss)

    def test_identical_historical_predictions_expose_unidentified_weight(self):
        raw = {**fixture(), "history": [pair(key, 1, q(1, 3), q(1, 3)) for key in "abc"]}
        result = model.fit(raw)
        self.assertTrue(result["fit"]["unidentified_weight"])
        self.assertEqual(result["fit"]["human_weight"], q(1, 2))
        self.assertEqual(result["fit"]["training_brier"]["hybrid"], q(4, 9))

    def test_target_and_lookahead_are_excluded_with_reasons(self):
        raw = fixture()
        future = pair("future", 0)
        future["resolved_at"] = raw["target"]["forecast_at"]
        late = pair("late", 0)
        late["human"]["at"] = late["resolved_at"]
        leaked = pair("target-copy", 0)
        leaked["question_id"] = raw["target"]["question_id"]
        raw["history"].extend((late, future, leaked))
        report = model.fit(raw)
        self.assertEqual(report["fit"]["human_weight"], q(2, 3))
        self.assertEqual({item["question_id"]: item["reason"] for item in report["excluded"]}, {
            "late": "late_forecast", "future": "unresolved_at_target_cutoff", "new": "target_question",
        })

    def test_insufficient_history_withholds_fit(self):
        raw = {**fixture(), "history": [pair("a", 1)]}
        result = model.fit(raw)
        self.assertEqual(result["status"], "insufficient_pairs")
        self.assertIsNone(result["forecast"])
        self.assertIsNone(result["fit"])
        self.assertEqual(len(result["pairs"]), 1)

    def test_target_input_at_cutoff_allowed_and_later_rejected(self):
        raw = fixture()
        raw["target"]["machine"]["at"] = "2026-11-20T07:00:00+07:00"
        self.assertEqual(model.fit(raw)["status"], "forecasted")
        raw["target"]["machine"]["at"] = "2026-11-20T07:00:00.000001+07:00"
        with self.assertRaisesRegex(model.InputError, "sesudah cutoff"):
            model.fit(raw)

    def test_duplicate_history_ids_and_reused_forecast_evidence_fail(self):
        raw = fixture()
        for change in (
            raw["history"][0],
            {**pair("other", 0), "machine": raw["target"]["machine"]},
            {**pair("other", 0), "resolution_ref": raw["protocol_ref"]},
        ):
            with self.subTest(change=change), self.assertRaisesRegex(model.InputError, "ganda"):
                model.fit({**raw, "history": [*raw["history"], change]})

    def test_invalid_subfields_do_not_fall_back_to_a_default(self):
        for key, value in (("outcome", "yes"), ("resolved_at", "2026-11-20T00:00:00"),
                           ("human", forecast("bad", q(2, 1)))):
            raw = fixture()
            raw["history"][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                model.fit(raw)

    def test_cli_is_deterministic_after_reordering_history(self):
        path = Path(self.enterContext(TemporaryDirectory())) / "pair.json"
        raw = fixture()
        logs = []
        for _ in range(2):
            path.write_text(json.dumps(raw), encoding="utf-8")
            with redirect_stdout(StringIO()) as output:
                self.assertEqual(model.main([str(path)]), 0)
            logs.append(output.getvalue())
            raw["history"].reverse()
        self.assertEqual(logs[0], logs[1])

    def test_recorded_components_keep_authoritative_refs_and_normalized_times(self):
        result = model.fit(fixture())
        self.assertEqual(result["pairs"][0]["human"]["ref"], "fixture/a/human")
        self.assertEqual(result["pairs"][0]["resolution_ref"], "fixture/a/resolution")
        self.assertEqual(result["pairs"][0]["resolved_at"], "2026-11-15T00:00:00+00:00")
        self.assertEqual(result["components"]["machine"]["probability"], q(1, 4))

    def test_all_history_excluded_keeps_distinct_component_forecasts(self):
        report = model.fit({**fixture(), "history": []})
        self.assertEqual(report["components"]["human"]["probability"], q(3, 4))
        self.assertEqual(report["components"]["machine"]["probability"], q(1, 4))
        self.assertIsNone(report["forecast"])
