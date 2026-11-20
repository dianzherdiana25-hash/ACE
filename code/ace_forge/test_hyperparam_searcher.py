"""Uji rencana successive halving, sumber skor, dan reservasi kredit."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_forge import hyperparam_searcher as model
from ace_forge._forge_io import canonical, identity


def config(key):
    return {"id": key, "recipe_sha256": identity({"learning_rate": key}), "recipe_ref": f"fixture/recipe/{key}"}


def fixture():
    return {"policy_ref": "fixture/hyper", "direction": "maximize", "metric": "held_out_score_bp",
            "limit_units": 12, "reduction": 2, "rung_units": [1, 2, 4],
            "configurations": [config(key) for key in "abcd"]}


def evaluate(policy, rows=()):
    return model.plan(policy, list(rows), identity(policy))


def result(job, score):
    return {key: job[key] for key in ("id", "rung", "units", "recipe_sha256", "metric", "policy_sha256")} | {
        "score": score, "trial_ref": f"fixture/trial/{job['id']}/{job['rung']}"}


def complete(policy, earlier, scores):
    jobs = evaluate(policy, earlier)["pending"]
    return [*earlier, *(result(job, scores[job["id"]]) for job in jobs)]


class SearchTests(unittest.TestCase):
    def test_all_trials_are_budgeted_and_each_rung_reduces_eligibility(self):
        policy = fixture()
        first = complete(policy, [], dict(a=70, b=40, c=67, d=40))
        after_first = evaluate(policy, first)
        second_jobs = after_first["pending"]
        self.assertEqual([row["id"] for row in second_jobs], ["a", "c"])
        self.assertEqual(after_first["budget"], {
            "limit_units": 12, "used_units": 4, "reserved_units": 4, "unassigned_units": 4})
        self.assertEqual(after_first["rungs"][0]["ranking"], ["a", "c", "b", "d"])
        second = complete(policy, first, dict(a=30, c=50))
        third_jobs = evaluate(policy, second)["pending"]
        self.assertEqual([row["id"] for row in third_jobs], ["c"])
        all_rows = complete(policy, second, dict(c=99))
        final = evaluate(policy, all_rows)
        self.assertEqual(final["winner"]["trial_ref"], "fixture/trial/c/2")
        self.assertEqual(final["winner"]["score"], 99)
        self.assertEqual(final["status"], "complete")
        self.assertEqual(final["budget"]["used_units"], 12)

    def test_partial_results_do_not_eliminate_and_usage_counts_only_observations(self):
        policy = fixture()
        job = evaluate(policy)["pending"][2]
        incomplete = evaluate(policy, [result(job, 100)])
        self.assertEqual(incomplete["status"], "awaiting_trials")
        self.assertEqual(incomplete["budget"]["used_units"], 1)
        self.assertEqual(incomplete["budget"]["reserved_units"], 3)
        self.assertEqual([row["id"] for row in incomplete["pending"]], ["a", "b", "d"])
        self.assertIsNone(incomplete["rungs"][0]["ranking"])
        self.assertIsNone(incomplete["winner"])

    def test_budget_exhausted_separates_diagnostic_ranking_from_winner(self):
        policy = {**fixture(), "limit_units": 7}
        after = evaluate(policy, complete(policy, [], dict(a=1, b=2, c=3, d=4)))
        self.assertEqual(after["status"], "budget_exhausted")
        self.assertEqual(after["rungs"][0]["advanced"], ["d", "c"])
        self.assertEqual(after["budget"]["unassigned_units"], 3)
        self.assertIsNone(after["winner"])
        self.assertEqual(after["pending"], [])
        initial = evaluate({**fixture(), "limit_units": 3})
        self.assertEqual(initial["rungs"], [])
        self.assertEqual(initial["budget"]["used_units"], 0)

    def test_minimization_respects_negative_scores_and_ties(self):
        policy = {**fixture(), "direction": "minimize", "rung_units": [1]}
        after = evaluate(policy, complete(policy, [], dict(a=0, b=-3, c=-3, d=100)))
        self.assertEqual(after["winner"]["id"], "b")
        self.assertEqual(after["rungs"][0]["ranking"], ["b", "c", "a", "d"])

    def test_observations_are_anchored_to_budget_configs_and_metric(self):
        policy = fixture()
        receipt = result(evaluate(policy)["pending"][0], 7)
        for key, changed in (("recipe_sha256", "0" * 64), ("units", 2), ("metric", "another"),
                             ("policy_sha256", "1" * 64), ("score", True)):
            with self.subTest(key=key), self.assertRaises(model.InputError):
                evaluate(policy, [{**receipt, key: changed}])

    def test_receipt_for_eliminated_or_future_configuration_is_rejected(self):
        policy = fixture()
        jobs = evaluate(policy)["pending"]
        future = result({**jobs[-1], "rung": 1, "units": 2}, 99)
        with self.assertRaisesRegex(model.InputError, "sebelum"):
            evaluate(policy, [future])
        complete_first = complete(policy, [], dict(a=6, b=5, c=4, d=3))
        with self.assertRaisesRegex(model.InputError, "eliminasi"):
            evaluate(policy, [*complete_first, future])

    def test_empty_or_nonincreasing_limits_and_duplicate_configuration_fail(self):
        policy = fixture()
        for changed in ({"rung_units": []}, {"rung_units": [2, 2]}, {"reduction": 1},
                        {"configurations": [config("a"), config("a")]}, {"direction": "sideways"}):
            with self.subTest(changed=changed), self.assertRaises(model.InputError):
                evaluate({**policy, **changed})

    def test_cli_canonical_order_for_observation_permutations(self):
        policy = fixture()
        receipts = complete(policy, [], dict(a=1, b=2, c=3, d=4))
        root = Path(self.enterContext(TemporaryDirectory()))
        policy_file, data_file = root / "policy.json", root / "results.json"
        policy_file.write_bytes(canonical(policy))
        outputs = []
        for _ in range(2):
            data_file.write_bytes(canonical(receipts))
            with redirect_stdout(StringIO()) as output:
                self.assertEqual(model.main([str(policy_file), str(data_file), "--expect-policy-sha256", identity(policy)]), 0)
            outputs.append(output.getvalue())
            receipts.reverse()
        self.assertEqual(*outputs)
        self.assertEqual(json.loads(outputs[0])["status"], "awaiting_trials")

    def test_policy_anchor_fails_before_reserving_any_trials(self):
        policy = fixture()
        old = identity(policy)
        policy["limit_units"] = 100
        with self.assertRaisesRegex(model.InputError, "anchor"):
            model.plan(policy, [], old)

    def test_large_reduction_preserves_one_survivor_across_remaining_rungs(self):
        policy = {**fixture(), "reduction": 20}
        first = complete(policy, [], dict(a=1, b=2, c=3, d=4))
        jobs = evaluate(policy, first)["pending"]
        self.assertEqual([(row["id"], row["units"]) for row in jobs], [("d", 2)])
        second = complete(policy, first, dict(d=5))
        final = evaluate(policy, complete(policy, second, dict(d=6)))
        self.assertEqual(final["winner"]["id"], "d")
        self.assertEqual(final["budget"]["used_units"], 10)
        self.assertEqual(final["budget"]["unassigned_units"], 2)

    def test_receipt_alias_with_different_configuration_never_reuses_evidence(self):
        policy = fixture()
        first, second, *_ = evaluate(policy)["pending"]
        evidence = result(first, 5)
        other = {**result(second, 6), "trial_ref": evidence["trial_ref"]}
        with self.assertRaisesRegex(model.InputError, "ganda"):
            evaluate(policy, [evidence, other])

    def test_single_stage_perfect_tie_keeps_exact_deterministic_winner(self):
        policy = {**fixture(), "rung_units": [1]}
        receipts = complete(policy, [], dict(a=15, b=15, c=15, d=15))
        self.assertEqual(evaluate(policy, receipts)["winner"]["id"], "a")
