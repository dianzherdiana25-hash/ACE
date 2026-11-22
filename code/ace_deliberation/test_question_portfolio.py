"""Uji optimasi eksak, batas kategori tumpang tindih, dan provenance."""
from collections import Counter
from contextlib import redirect_stdout
from io import StringIO
from itertools import combinations
import json
from pathlib import Path
import random
from tempfile import TemporaryDirectory
import unittest

from ace_deliberation import question_portfolio as model


def question(key, value, cost, *groups):
    return {"id": key, "value_units": value, "cost_units": cost, "groups": list(groups), "source_ref": f"q/{key}"}


def fixture():
    return {
        "protocol_ref": "fixture/p", "budget": 10, "max_questions": 3,
        "category_limits": [{"id": "infra", "max": 2}, {"id": "risk", "max": 1}, {"id": "science", "max": 2}],
        "questions": [
            question("headline", 12, 9, "infra", "risk"),
            question("latency", 9, 5, "infra"),
            question("outage", 8, 4, "infra", "risk"),
            question("measure", 7, 4, "science"),
            question("learn", 5, 1, "science"),
        ],
    }


def oracle(raw):
    """Sensus subset secara independen untuk memeriksa semua ukuran."""
    records = raw["questions"]
    caps = {row["id"]: row["max"] for row in raw["category_limits"]}
    result = []
    for size in range(raw["max_questions"] + 1):
        feasible = []
        for subset in combinations(records, size):
            cost = sum(row["cost_units"] for row in subset)
            counts = Counter(key for row in subset for key in row["groups"])
            if cost > raw["budget"] or any(counts[key] > cap for key, cap in caps.items()):
                continue
            value = sum(row["value_units"] for row in subset)
            feasible.append((-value, cost, sorted(row["id"] for row in subset)))
        if feasible:
            value, cost, ids = min(feasible)
            result.append((size, -value, cost, ids))
    return result


class PortfolioTests(unittest.TestCase):
    def test_headline_loses_to_feasible_combination_and_keeps_pointer(self):
        result = model.optimize(fixture())
        choice = result["chosen"]
        self.assertEqual(choice["ids"], ["latency", "learn", "outage"])
        self.assertEqual(choice["value_units"], 22)
        self.assertEqual(choice["unspent_budget"], 0)
        self.assertEqual(choice["category_counts"], {"infra": 2, "risk": 1, "science": 1})
        self.assertEqual([item["source_ref"] for item in result["selected_questions"]],
                         ["q/latency", "q/learn", "q/outage"])

    def test_frontier_preserves_best_for_each_feasible_size(self):
        result = model.optimize(fixture())
        self.assertEqual([(row["size"], row["ids"]) for row in result["frontier"]], [
            (0, []), (1, ["headline"]), (2, ["latency", "outage"]), (3, ["latency", "learn", "outage"]),
        ])

    def test_limit_per_category_applies_to_all_groups_of_same_item(self):
        raw = fixture()
        raw["category_limits"][0]["max"] = 1
        result = model.optimize(raw)
        self.assertEqual(result["chosen"]["ids"], ["latency", "learn", "measure"])
        headline = next(row for row in result["not_selected"] if row["id"] == "headline")
        self.assertIn("category:infra", headline["addition_blockers"])
        self.assertNotIn("category:risk", headline["addition_blockers"])

    def test_reports_every_constraint_against_current_selection(self):
        result = model.optimize(fixture())
        self.assertEqual(result["not_selected"][0], {
            "id": "headline", "source_ref": "q/headline",
            "addition_blockers": ["slots", "budget", "category:infra", "category:risk"],
        })

    def test_tie_breaks_by_cost_then_ids_without_preferring_larger_size(self):
        raw = fixture()
        raw.update(max_questions=1, questions=[
            question("aaa", 12, 5, "science"), question("c", 12, 4, "science"),
            question("b", 12, 4, "infra"),
        ])
        result = model.optimize(raw)
        self.assertEqual(result["chosen"]["ids"], ["b"])
        raw["questions"] = [question("zero", 0, 0, "infra")]
        self.assertEqual(model.optimize(raw)["chosen"]["ids"], [])

    def test_zero_budget_allows_zero_cost_action_but_slots_zero_does_not(self):
        raw = fixture()
        raw.update(budget=0, questions=[question("free", 3, 0, "risk"), question("paid", 10, 1, "infra")])
        self.assertEqual(model.optimize(raw)["chosen"]["ids"], ["free"])
        self.assertEqual(model.optimize({**raw, "max_questions": 0})["chosen"]["ids"], [])

    def test_zero_category_quota_blocks_inclusion_without_blocking_rest(self):
        raw = fixture()
        raw["category_limits"][1]["max"] = 0
        result = model.optimize(raw)
        self.assertEqual(result["chosen"]["ids"], ["latency", "learn", "measure"])
        self.assertTrue(all("category:risk" in row["addition_blockers"] for row in result["not_selected"]))

    def test_measured_frontier_matches_separate_powerset_model(self):
        rng = random.Random(542)
        for _ in range(30):
            raw = fixture()
            raw.update(max_questions=rng.randrange(7), budget=rng.randrange(12))
            raw["questions"] = [question(f"case-{i}", rng.randrange(15), rng.randrange(6),
                                         *rng.sample(["risk", "science", "infra"], rng.randrange(1, 4)))
                                for i in range(rng.randrange(8))]
            for row in raw["category_limits"]:
                row["max"] = rng.randrange(4)
            actual = model.optimize(raw)
            self.assertEqual([(row["size"], row["value_units"], row["cost_units"], row["ids"])
                              for row in actual["frontier"]], oracle(raw))

    def test_invalid_category_unit_or_duplicate_id_fails_closed(self):
        raw = fixture()
        for change in (
            {"budget": True}, {"budget": -1}, {"max_questions": 21},
            {"category_limits": [raw["category_limits"][0]] * 2},
            {"questions": [question("new", 7, 0, "missing")]},
            {"questions": [question("repeat", 3, 1, "science")] * 2},
            {"questions": [question("twice", 3, 1, "science", "science")]},
            {"questions": [question("negative", -1, 1, "science")]},
        ):
            with self.subTest(change=change), self.assertRaises(model.InputError):
                model.optimize({**raw, **change})

    def test_provenance_may_not_be_reused_for_separate_questions(self):
        raw = fixture()
        raw["questions"][1]["source_ref"] = raw["questions"][0]["source_ref"]
        with self.assertRaisesRegex(model.InputError, "ganda"):
            model.optimize(raw)

    def test_cli_is_order_invariant(self):
        raw = fixture()
        path = Path(self.enterContext(TemporaryDirectory())) / "portfolio.json"
        outputs = []
        for _ in range(2):
            path.write_text(json.dumps(raw), encoding="utf-8")
            with redirect_stdout(StringIO()) as stdout:
                self.assertEqual(model.main([str(path)]), 0)
            outputs.append(stdout.getvalue())
            raw["questions"].reverse()
            raw["category_limits"].reverse()
        self.assertEqual(outputs[0], outputs[1])

    def test_empty_candidate_set_has_valid_zero_plan(self):
        result = model.optimize({**fixture(), "questions": []})
        self.assertEqual(result["chosen"], {
            "ids": [], "cost_units": 0, "value_units": 0, "category_counts": {}, "unspent_budget": 10,
        })
        self.assertEqual(len(result["frontier"]), 1)
        self.assertEqual(result["not_selected"], [])

    def test_omission_without_blockers_distinguishes_tie_from_unavailability(self):
        raw = {**fixture(), "questions": [question("optional", 0, 0, "infra")]}
        result = model.optimize(raw)
        self.assertEqual(result["chosen"]["ids"], [])
        self.assertEqual(result["not_selected"], [
            {"id": "optional", "source_ref": "q/optional", "addition_blockers": []},
        ])
