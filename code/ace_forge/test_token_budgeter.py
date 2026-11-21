"""Verifier perhitungan panjang batch, biaya eksak, dan batas reserve."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from ace_forge import token_budgeter as model
from ace_forge._forge_io import canonical, identity


def q(n, d=1):
    return {"numerator": n, "denominator": d}


def batch(key, mode, values):
    return {"id": key, "source_ref": f"fixture/batch/{key}", "padding": mode, "lengths": [
        {"input_tokens": prefix, "target_tokens": target} for prefix, target in values
    ]}


def stage(key, passes, rate, *batches):
    return {"id": key, "stage_ref": f"fixture/stage/{key}", "passes": passes, "rate_units_per_million": rate,
            "batches": list(batches)}


def fixture():
    return {"policy_ref": "fixture/budget", "unit": "kredit-lokal", "maximum_tokens": 58, "maximum_cost_units": 11,
            "reserve_bp": 1000, "context_limit_tokens": 30, "stages": [
                stage("train", 3, 200_000, batch("long", "longest", [(2, 1), (4, 1)]),
                      batch("packed", "packed", [(3, 2)])),
                stage("eval", 1, 125_000, batch("independent", "packed", [(5, 2)])),
            ]}


def estimate(raw):
    return model.estimate(raw, identity(raw))


class TokenBudgetTests(unittest.TestCase):
    def test_padding_reserve_and_prices_match_hand_calculation(self):
        value = estimate(fixture())
        self.assertEqual(value["status"], "within_budget")
        self.assertEqual(value["real_tokens"], 46)
        self.assertEqual(value["processed_tokens"], 52)
        self.assertEqual(value["padding_tokens"], 6)
        self.assertEqual(value["reserved_tokens_total"], 58)
        self.assertEqual(value["token_margin"], 0)
        self.assertEqual(value["cost_units"], q(79, 8))
        self.assertEqual(value["reserved_cost_units"], q(11))
        self.assertEqual(value["cost_margin_units"], q(0))
        evaluation, training = value["stages"]
        self.assertEqual(evaluation["reserved_tokens_total"], 8)
        self.assertEqual(training["reserved_tokens_total"], 50)
        self.assertEqual(training["batches"][0]["source_ref"], "fixture/batch/long")
        self.assertEqual(training["batches"][0]["padding_tokens"], 6)

    def test_separate_caps_allow_exact_boundary_and_identify_fractional_cost_overrun(self):
        raw = fixture()
        self.assertEqual(estimate({**raw, "maximum_tokens": 57})["blockers"], ["token_cap"])
        value = estimate({**raw, "maximum_cost_units": 10})
        self.assertEqual(value["blockers"], ["cost_cap"])
        self.assertEqual(value["cost_margin_units"], q(-1))
        self.assertEqual(estimate({**raw, "maximum_tokens": 57, "maximum_cost_units": 10})["blockers"],
                         ["token_cap", "cost_cap"])
        raw["stages"][1]["rate_units_per_million"] = 125_001
        self.assertEqual(estimate(raw)["cost_margin_units"], q(-1, 125_000))

    def test_zero_tariff_and_budget_are_explicit_and_preserve_resource_counts(self):
        raw = fixture()
        raw["maximum_cost_units"] = 0
        for job in raw["stages"]:
            job["rate_units_per_million"] = 0
        value = estimate(raw)
        self.assertEqual(value["status"], "within_budget")
        self.assertEqual(value["cost_units"], q(0))
        self.assertEqual(value["reserved_tokens_total"], 58)
        raw["maximum_tokens"] = 0
        self.assertEqual(estimate(raw)["blockers"], ["token_cap"])

    def test_context_cap_applies_to_sum_of_input_and_target(self):
        raw = fixture()
        raw["context_limit_tokens"] = 6
        with self.assertRaises(model.InputError):
            estimate(raw)
        raw["context_limit_tokens"] = 7
        self.assertEqual(estimate(raw)["status"], "within_budget")

    def test_longest_distinguishes_multi_example_padding_from_packing(self):
        raw = fixture()
        raw["stages"][0]["batches"][0]["padding"] = "packed"
        value = estimate(raw)
        self.assertEqual(value["padding_tokens"], 0)
        self.assertEqual(value["real_tokens"], 46)
        self.assertEqual(value["processed_tokens"], 46)
        self.assertEqual(value["token_margin"], 7)

    def test_zero_and_maximum_reserve_do_not_require_floating_rounding(self):
        raw = fixture()
        no = estimate({**raw, "reserve_bp": 0})
        max_ = estimate({**raw, "reserve_bp": 10_000})
        self.assertEqual((no["reserved_tokens_total"], max_["reserved_tokens_total"]), (52, 104))
        self.assertEqual(no["cost_units"], no["reserved_cost_units"])
        self.assertEqual(max_["reserved_cost_units"], q(79, 4))

    def test_aggregate_limits_are_applied_across_batch_and_stage_boundaries(self):
        with patch.object(model, "MAX_BATCHES", 2):
            with self.assertRaisesRegex(model.InputError, "jumlah batch"):
                estimate(fixture())
        with patch.object(model, "MAX_EXAMPLES", 3):
            with self.assertRaisesRegex(model.InputError, "Total contoh"):
                estimate(fixture())

    def test_invalid_and_duplicate_entries_cannot_become_costless_stages(self):
        bad = (
            [stage("s", 5, 0)],
            [stage("s", 1, 0, batch("b", "packed", []))],
            [stage("s", 0, 0, batch("b", "packed", [(1, 0)]))],
            [stage("s", 1, -3, batch("b", "packed", [(1, 0)]))],
            [stage("s", 1, 0, batch("b", "unknown", [(1, 0)]))],
            [stage("s", 1, 0, batch("b", "packed", [(0, 0)]))],
            [stage("s", 1, 0, batch("b", "packed", [(True, 0)]))],
            [stage("s", 1, 0, batch("b", "packed", [(1, 0)]))] * 2,
        )
        for stages in bad:
            with self.subTest(stages=stages), self.assertRaises(model.InputError):
                estimate({**fixture(), "stages": stages})

    def test_source_change_and_declared_reserve_tamper_are_separate_inputs(self):
        raw = fixture()
        expected = identity(raw)
        raw["stages"][0]["batches"][0]["lengths"][0]["target_tokens"] += 1
        with self.assertRaisesRegex(model.InputError, "anchor"):
            model.estimate(raw, expected)
        value = estimate(raw)
        self.assertEqual(value["real_tokens"], 49)
        self.assertEqual(value["processed_tokens"], 52)

    def test_cli_exits_one_for_held_and_zero_for_within_budget(self):
        path = Path(self.enterContext(TemporaryDirectory())) / "budget.json"
        for maximum, exit_code in ((57, 1), (58, 0)):
            with self.subTest(maximum=maximum):
                raw = {**fixture(), "maximum_tokens": maximum}
                path.write_bytes(canonical(raw))
                with redirect_stdout(StringIO()) as out:
                    self.assertEqual(model.main([str(path), "--expect-input-sha256", identity(raw)]), exit_code)
                self.assertEqual(json.loads(out.getvalue()), estimate(raw))
                self.assertEqual(path.read_bytes(), canonical(raw))

    def test_single_token_examples_are_counted_once_per_pass_and_reserve_ceils_per_stage(self):
        raw = fixture()
        raw["reserve_bp"] = 1
        raw["stages"] = [stage("first", 2, 1, batch("one", "packed", [(0, 1)])),
                         stage("second", 1, 1, batch("two", "packed", [(1, 0)]))]
        result = estimate(raw)
        self.assertEqual(result["real_tokens"], 3)
        self.assertEqual(result["reserved_tokens_total"], 5)
        self.assertEqual(result["reserved_cost_units"], q(1, 200_000))

    def test_zero_extra_padding_when_longest_batch_lengths_are_all_identical(self):
        raw = fixture()
        raw["stages"] = [stage("align", 3, 1, batch("items", "longest", [(1, 4), (3, 2), (4, 1)]))]
        result = estimate(raw)
        self.assertEqual(result["real_tokens"], 45)
        self.assertEqual(result["processed_tokens"], 45)
        self.assertEqual(result["padding_tokens"], 0)
