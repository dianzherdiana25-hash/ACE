"""Uji jadwal tanpa mendahulukan urgency dengan mengorbankan tenggat."""
from contextlib import redirect_stdout
from io import StringIO
from itertools import combinations
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_deliberation import deliberation_scheduler as scheduler


def request(identifier, duration, due, cost, urgency):
    return {"id": identifier, "duration_minutes": duration, "due_minute": due, "cost_units": cost,
            "urgency": urgency, "source_ref": f"fixture/{identifier}"}


def fixture():
    return {"opens_at": "2026-11-20T07:00:00+07:00", "window_minutes": 8, "budget_units": 6,
            "requests": [request("A", 6, 8, 6, 10), request("B", 4, 4, 2, 6),
                         request("C", 4, 8, 4, 7), request("D", 5, 4, 7, 30)]}


class SchedulingTests(unittest.TestCase):
    def test_two_jobs_beat_greedy_and_both_deadlines_hold(self):
        report = scheduler.schedule(fixture())
        self.assertEqual([row["id"] for row in report["schedule"]], ["B", "C"])
        self.assertEqual((report["urgency_total"], report["cost_units"], report["used_minutes"]), (13, 6, 8))
        self.assertEqual(report["schedule"][0]["starts_at"], "2026-11-20T00:00:00+00:00")
        self.assertEqual(report["schedule"][1]["ends_at"], "2026-11-20T00:08:00+00:00")
        skipped = {row["id"]: row["reasons"] for row in report["unscheduled"]}
        self.assertEqual(skipped["A"], ["excluded_by_optimum"])
        self.assertEqual(skipped["D"],
                         ["duration_exceeds_window_or_deadline", "cost_exceeds_budget"])

    def test_edf_order_is_necessary_for_feasible_earlier_deadline(self):
        early, late = request("early", 3, 3, 0, 2), request("late", 3, 6, 0, 25)
        raw = {**fixture(), "budget_units": 0, "requests": [late, early]}
        report = scheduler.schedule(raw)
        self.assertEqual([row["id"] for row in report["schedule"]], ["early", "late"])
        self.assertEqual(report["cost_units"], 0)

    def test_optimality_matches_enumerated_subsets_over_multiple_limits(self):
        fixture_data = fixture()
        rows = fixture_data["requests"] + [request("E", 1, 6, 0, 3),
                                          request("F", 3, 9, 1, 4), request("G", 1, 1, 2, 5)]
        for budget in range(7):
            with self.subTest(budget=budget):
                feasible = []
                for count in range(len(rows) + 1):
                    for subset in combinations(rows, count):
                        order = sorted(subset, key=lambda item: (item["due_minute"], item["id"]))
                        minute = 0
                        for entry in order:
                            minute += entry["duration_minutes"]
                            if minute > min(8, entry["due_minute"]):
                                break
                        else:
                            cost = sum(entry["cost_units"] for entry in order)
                            if cost <= budget:
                                feasible.append((-sum(entry["urgency"] for entry in order), cost, minute,
                                                 tuple(entry["id"] for entry in order)))
                result = scheduler.schedule({**fixture_data, "budget_units": budget, "requests": rows})
                self.assertEqual((-result["urgency_total"], result["cost_units"], result["used_minutes"],
                                  tuple(entry["id"] for entry in result["schedule"])), min(feasible))

    def test_tie_breaks_by_cost_then_finish_then_id(self):
        raw = {**fixture(), "window_minutes": 4, "requests": [
            request("cheaper", 4, 4, 3, 5), request("X", 4, 4, 1, 5),
            request("a", 3, 4, 1, 5), request("b", 3, 4, 1, 5),
        ]}
        result = scheduler.schedule(raw)
        self.assertEqual([row["id"] for row in result["schedule"]], ["a"])
        self.assertEqual(result, scheduler.schedule({**raw, "requests": raw["requests"][::-1]}))

    def test_blank_calendar_is_valid_and_malformed_budget_or_date_refused(self):
        self.assertEqual(scheduler.schedule({**fixture(), "requests": []})["schedule"], [])
        for updates in ({"budget_units": True}, {"opens_at": "2026-11-20T11:05:00"},
                        {"requests": [fixture()["requests"][0]] * 2}):
            with self.subTest(updates=updates), self.assertRaises(scheduler.ScheduleError):
                scheduler.schedule({**fixture(), **updates})

    def test_cli_cites_selected_request_sources(self):
        path = Path(self.enterContext(TemporaryDirectory())) / "planning.json"
        path.write_text(json.dumps(fixture()), encoding="utf-8")
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(scheduler.main([str(path)]), 0)
        self.assertEqual(json.loads(output.getvalue())["schedule"][1]["source_ref"], "fixture/C")

    def test_explains_urgency_loss_of_requiring_a_displaced_request(self):
        raw = {**fixture(), "explain_ids": ["C", "D", "A"]}
        explanations = scheduler.schedule(raw)["explanations"]
        self.assertEqual(explanations, [
            {"id": "A", "status": "feasible_if_required", "urgency_loss": 3, "candidate_schedule_ids": ["A"]},
            {"id": "C", "status": "already_selected", "urgency_loss": 0, "candidate_schedule_ids": ["B", "C"]},
            {"id": "D", "status": "infeasible_even_alone", "urgency_loss": None, "candidate_schedule_ids": []},
        ])

    def test_explanation_does_not_replace_base_schedule_and_rejects_unknown_subject(self):
        raw = fixture()
        base = scheduler.schedule(raw)
        explained = scheduler.schedule({**raw, "explain_ids": ["A"]})
        self.assertEqual(explained["schedule"], base["schedule"])
        with self.assertRaises(scheduler.ScheduleError):
            scheduler.schedule({**raw, "explain_ids": ["absent"]})

    def test_forcing_middle_task_cannot_reinsert_a_cheaper_path_that_omits_it(self):
        raw = {**fixture(), "requests": [request("early", 3, 3, 3, 10),
                                         request("middle", 2, 5, 2, 1), request("later", 3, 8, 3, 10)],
               "explain_ids": ["middle"]}
        report = scheduler.schedule(raw)
        self.assertEqual([row["id"] for row in report["schedule"]], ["early", "later"])
        middle, = report["explanations"]
        self.assertEqual(middle["candidate_schedule_ids"], ["early", "middle"])
        self.assertEqual(middle["urgency_loss"], 9)

    def test_counterfactual_order_is_canonical(self):
        first = scheduler.schedule({**fixture(), "explain_ids": ["A", "D"]})
        self.assertEqual(first, scheduler.schedule({**fixture(), "explain_ids": ["D", "A"]}))
