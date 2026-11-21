"""Uji alokasi jumlah, batas mutu, pemecah seri, dan penahanan."""
from contextlib import redirect_stdout
from fractions import Fraction
from io import StringIO
import json
from pathlib import Path
from random import Random
from tempfile import TemporaryDirectory
import unittest

from ace_forge import mixture_planner as model
from ace_forge._forge_io import canonical, identity


def quota(kind, minimum, maximum, weight):
    return {"task_kind": kind, "minimum": minimum, "maximum": maximum, "weight": weight}


def row(kind, key, score=9000, *, split="train", status="ready"):
    return {"task_kind": kind, "example_id": key, "score_bp": score, "split": split,
            "status": status, "evidence_ref": f"fixture/source/{key}"}


def fixture():
    return {"policy_ref": "fixture/mix", "quality_report_ref": "fixture/quality", "target_examples": 7,
            "minimum_score_bp": 7000, "quotas": [quota("a", 1, 3, 2), quota("b", 1, 5, 3), quota("c", 0, 3, 1)],
            "candidates": [row(kind, f"{kind}-{index}", 9000 - 10 * index) for kind in "abc" for index in range(5)]}


def report(raw):
    return model.plan(raw, identity(raw))


def counts(report):
    return {row["task_kind"]: row["count"] for row in report["by_task"]}


class MixtureTests(unittest.TestCase):
    def test_minimum_then_weighted_extras_with_finite_capacity(self):
        value = report(fixture())
        self.assertEqual(value["status"], "ready")
        self.assertEqual(counts(value), {"a": 3, "b": 4, "c": 0})
        self.assertEqual(value["planned_examples"], 7)
        rows = value["by_task"]
        self.assertEqual(rows[0]["share"], {"numerator": 3, "denominator": 7})
        self.assertTrue(all(row["evidence_ref"].startswith("fixture/source/") for row in rows[1]["examples"]))
        self.assertEqual(sum(Fraction(**group["share"]) for group in rows), 1)

    def test_selection_tie_prefers_stable_id_and_best_evidence_score(self):
        raw = {**fixture(), "target_examples": 2, "quotas": [quota("a", 2, 3, 1)],
               "candidates": [row("a", "z", 9000), row("a", "j", 9000), row("a", "a", 7000),
                              row("a", "q", 9500)]}
        picked = report(raw)["by_task"][0]["examples"]
        self.assertEqual([example["example_id"] for example in picked], ["q", "j"])

    def test_partitions_and_quality_filters_keep_reasons_and_ref(self):
        raw = fixture()
        raw["candidates"] += [row("a", "held", 10000, split="held_out"),
                              row("a", "pending", 8000, status="hold"),
                              row("a", "no-score", None, status="unscored"),
                              row("a", "low", 6999), row("new", "unplanned")]
        result = report(raw)
        self.assertEqual({row["example_id"]: row["reason"] for row in result["excluded"]}, {
            "held": "held_out", "pending": "quality_hold", "no-score": "quality_unscored",
            "low": "below_mixture_floor", "unplanned": "task_not_requested",
        })
        self.assertEqual(result["excluded"][0]["evidence_ref"], "fixture/source/held")
        self.assertEqual(result["capacity"], 11)
        self.assertEqual(result["planned_examples"], 7)

    def test_unmet_minimum_does_not_choose_a_partial_plan(self):
        raw = fixture()
        raw["candidates"] = [row for row in raw["candidates"] if row["task_kind"] != "a"]
        result = report(raw)
        self.assertEqual(result["status"], "hold")
        self.assertEqual(result["blockers"], ["unmet_minimum"])
        self.assertEqual(result["minimum_shortfalls"], [{"task_kind": "a", "required": 1, "available": 0}])
        self.assertEqual(result["planned_examples"], 0)
        self.assertTrue(all(row["count"] is None and not row["examples"] for row in result["by_task"]))

    def test_oversized_target_or_sum_of_minimums_each_items_report_blocker(self):
        self.assertEqual(report({**fixture(), "target_examples": 12})["blockers"], ["insufficient_capacity"])
        self.assertEqual(report({**fixture(), "target_examples": 1})["blockers"], ["sum_minimum_above_target"])

    def test_equal_priority_favors_earlier_id_and_empty_quota_is_skipped(self):
        raw = {**fixture(), "target_examples": 1, "quotas": [quota("b", 0, 2, 1), quota("a", 0, 2, 1),
                                                            quota("c", 0, 0, 1000)]}
        self.assertEqual(counts(report(raw)), {"a": 1, "b": 0, "c": 0})

    def test_tampering_candidate_proof_is_refused_before_planning(self):
        raw = fixture()
        anchor = identity(raw)
        raw["candidates"][0]["evidence_ref"] = "fixture/another"
        with self.assertRaisesRegex(model.InputError, "anchor"):
            model.plan(raw, anchor)

    def test_malformed_duplicate_and_invalid_status_are_fail_closed(self):
        raw = fixture()
        for changed in ({"quotas": []}, {"target_examples": True}, {"quotas": [quota("b", 4, 2, 1)]},
                        {"quotas": [quota("b", 0, 8, 0)]}, {"quotas": raw["quotas"] * 2},
                        {"candidates": [row("a", "one", 0, status="unscored")]},
                        {"candidates": [row("a", "one", split="all")]},
                        {"candidates": raw["candidates"][:1] * 2}):
            with self.subTest(changed=changed), self.assertRaises(model.InputError):
                report({**raw, **changed})

    def test_row_permutations_preserve_decisions_with_distinct_snapshot_anchors(self):
        raw = fixture()
        expected = report(raw)
        raw["candidates"].reverse()
        raw["quotas"].reverse()
        actual = report(raw)
        self.assertNotEqual(actual.pop("input_sha256"), expected.pop("input_sha256"))
        self.assertEqual(actual, expected)

    def test_cli_exit_code_reflects_complete_or_held_plan(self):
        path = Path(self.enterContext(TemporaryDirectory())) / "mix.json"
        for count, status_code in ((7, 0), (1, 1)):
            raw = {**fixture(), "target_examples": count}
            before = canonical(raw)
            path.write_bytes(before)
            with redirect_stdout(StringIO()) as output:
                self.assertEqual(model.main([str(path), "--expect-input-sha256", identity(raw)]), status_code)
            self.assertEqual(json.loads(output.getvalue()), report(raw))
            self.assertEqual(path.read_bytes(), before)

    def test_observed_capacity_obeys_task_maximum_even_if_stock_is_large(self):
        raw = fixture()
        raw["quotas"][0] = quota("a", 1, 1, 1000)
        stats = report(raw)["by_task"][0]
        self.assertEqual((stats["capacity"], stats["eligible"], stats["count"]), (1, 5, 1))

    def test_heap_apportionment_matches_independent_exact_ranking(self):
        rng = Random(52)
        for _ in range(25):
            raw = fixture()
            quotas = []
            cap = 0
            for key in "abc":
                maximum = rng.randint(1, 5)
                cap += maximum
                quotas.append(quota(key, 1, maximum, rng.randint(1, 10)))
            raw.update(quotas=quotas, target_examples=rng.randint(3, cap))
            votes = {item["task_kind"]: item["weight"] for item in quotas}
            limits = {item["task_kind"]: item["maximum"] for item in quotas}
            expected = dict.fromkeys(votes, 1)
            for _ in range(raw["target_examples"] - 3):
                viable = [key for key, assigned in expected.items() if assigned < limits[key]]
                winner = min(viable, key=lambda key: (-Fraction(votes[key], expected[key]), key))
                expected[winner] += 1
            self.assertEqual(counts(report(raw)), expected)

    def test_required_slots_remain_protected_under_an_extreme_weight_ratio(self):
        raw = fixture()
        raw["quotas"] = [quota("a", 2, 5, 1), quota("b", 1, 5, 1000), quota("c", 1, 5, 1)]
        self.assertEqual(counts(report(raw)), {"a": 2, "b": 4, "c": 1})
