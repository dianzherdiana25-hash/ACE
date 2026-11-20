"""Verifikasi turnamen pada penilaian berpasangan, kosong, dan seri."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_deliberation import method_tournament as tournament


def card(method, case, points, *, cost=1, elapsed=100):
    return {"method": method, "case": case, "points": points, "cost_units": cost, "elapsed_ms": elapsed,
            "decision_ref": f"fixture/decisions/{method}/{case}", "score_ref": f"fixture/scoring/{method}/{case}"}


def fixture():
    return {"methods": ["gamma", "alpha", "beta"], "cases": ["q", "p", "r"], "rubric_ref": "fixture/rubric",
            "scorecards": [
                card(method, case, points)
                for method, scores in (("alpha", (90, 60, 80)), ("beta", (85, 70, 75)), ("gamma", (60, 90, 70)))
                for case, points in zip(("p", "q", "r"), scores)
            ]}


class TournamentTests(unittest.TestCase):
    def test_round_robin_and_paired_reference_trace(self):
        report = tournament.run_tournament(fixture())
        self.assertEqual(len(report["matches"]), 3)
        match = report["matches"][0]
        self.assertEqual((match["left"], match["right"], match["winner"]), ("alpha", "beta", "alpha"))
        self.assertEqual((match["left_wins"], match["right_wins"], match["ties"]), (2, 1, 0))
        self.assertEqual(match["mean_point_delta"], {"numerator": 0, "denominator": 1})
        self.assertEqual(match["trials"][0]["right_score_ref"], "fixture/scoring/beta/p")
        self.assertEqual(report["leading_methods"], ["alpha"])
        self.assertEqual([row["match_points"] for row in report["standings"]], [4, 2, 0])

    def test_absent_card_does_not_turn_into_zero_or_partial_ranking(self):
        raw = fixture()
        absent = raw["scorecards"].pop()
        result = tournament.run_tournament(raw)
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual(result["missing_scorecards"], [{"method": absent["method"], "case": absent["case"]}])
        self.assertEqual(result["standings"], [])
        self.assertEqual(result["leading_methods"], [])

    def test_divergent_costs_and_elapsed_times_do_not_break_quality_tie(self):
        raw = fixture()
        for index, row in enumerate(raw["scorecards"]):
            row.update(points=50, cost_units=index, elapsed_ms=(index + 1) * 200)
        report = tournament.run_tournament(raw)
        self.assertEqual(report["status"], "tied")
        self.assertEqual(report["leading_methods"], ["alpha", "beta", "gamma"])
        self.assertEqual([row["rank"] for row in report["standings"]], [1, 1, 1])
        self.assertEqual([row["total_cost_units"] for row in report["standings"]], [3, 12, 21])

    def test_tied_pair_contributes_one_standing_point_to_each(self):
        raw = {**fixture(), "methods": ["alpha", "beta"], "cases": ["x", "y"],
               "scorecards": [card("alpha", "x", 80), card("beta", "x", 90),
                              card("alpha", "y", 60), card("beta", "y", 40)]}
        result = tournament.run_tournament(raw)
        self.assertIsNone(result["matches"][0]["winner"])
        self.assertEqual([row["match_points"] for row in result["standings"]], [1, 1])
        self.assertEqual(result["leading_methods"], ["alpha"])

    def test_scorecard_indexes_and_refs_cannot_be_reused(self):
        for edits in ({"score_ref": "fixture/scoring/alpha/p"}, {"case": "unregistered"}, {"points": True}):
            raw = fixture()
            raw["scorecards"][1].update(edits)
            with self.subTest(edits=edits), self.assertRaises(tournament.InputError):
                tournament.run_tournament(raw)

    def test_cli_reports_same_standings_after_reordering(self):
        raw = fixture()
        expected = tournament.run_tournament(raw)
        for key in ("methods", "cases", "scorecards"):
            raw[key].reverse()
        path = Path(self.enterContext(TemporaryDirectory())) / "tournament.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(tournament.main([str(path)]), 0)
        self.assertEqual(json.loads(output.getvalue()), expected)

    def test_competition_rank_skips_places_occupied_by_tied_methods(self):
        raw = fixture()
        raw["scorecards"] = [card(method, case, 90 if method != "gamma" else 1)
                             for method in raw["methods"] for case in raw["cases"]]
        total = tournament.run_tournament(raw)
        self.assertEqual([row["rank"] for row in total["standings"]], [1, 1, 3])
        self.assertEqual(total["leading_methods"], ["alpha", "beta"])

    def test_single_case_and_zero_quality_are_measured_not_missing(self):
        raw = {"methods": ["x", "y"], "cases": ["p"], "rubric_ref": "fixture/r",
               "scorecards": [card("x", "p", 0, cost=0, elapsed=0), card("y", "p", 0)]}
        result = tournament.run_tournament(raw)
        self.assertEqual(result["missing_scorecards"], [])
        self.assertEqual(result["matches"][0]["ties"], 1)
        self.assertEqual(result["standings"][0]["mean_quality"], {"numerator": 0, "denominator": 1})

    def test_case_influence_agrees_with_recomputed_standings(self):
        raw = fixture()
        report = tournament.run_tournament(raw)
        for row in report["case_influence"]:
            target = row["case_removed"]
            recomputed = {**raw, "cases": [case for case in raw["cases"] if case != target],
                          "scorecards": [card for card in raw["scorecards"] if card["case"] != target]}
            expected = tournament.run_tournament(recomputed)["leading_methods"]
            self.assertEqual(row["leading_methods"], expected)
            self.assertEqual(row["leader_set_changed"], expected != report["leading_methods"])

    def test_no_sensitivity_calculation_without_a_remaining_case(self):
        raw = {**fixture(), "cases": ["p"],
               "scorecards": [row for row in fixture()["scorecards"] if row["case"] == "p"]}
        self.assertEqual(tournament.run_tournament(raw)["case_influence"], [])

    def test_compared_costs_stay_visible_with_quality_ranking(self):
        raw = fixture()
        raw["scorecards"][0].update(cost_units=55, elapsed_ms=450)
        first = tournament.run_tournament(raw)["standings"][0]
        self.assertEqual((first["method"], first["total_cost_units"], first["total_elapsed_ms"]),
                         ("alpha", 57, 650))

    def test_no_registered_result_does_not_fabricate_a_standing(self):
        raw = {**fixture(), "scorecards": []}
        report = tournament.run_tournament(raw)
        self.assertEqual(len(report["missing_scorecards"]), 9)
        self.assertEqual(report["case_influence"], [])

    def test_provenance_reuse_from_rubric_inside_result_is_invalid(self):
        raw = fixture()
        raw["scorecards"][0]["decision_ref"] = raw["rubric_ref"]
        with self.assertRaisesRegex(tournament.InputError, "ganda"):
            tournament.run_tournament(raw)

    def test_identical_quality_both_before_and_after_each_removal(self):
        raw = fixture()
        for item in raw["scorecards"]:
            item["points"] = 20
        report = tournament.run_tournament(raw)
        self.assertTrue(all(not entry["leader_set_changed"] for entry in report["case_influence"]))

    def test_incomplete_input_keeps_existing_provenance(self):
        raw = fixture()
        raw["scorecards"].pop()
        report = tournament.run_tournament(raw)
        self.assertEqual(report["rubric_ref"], raw["rubric_ref"])
        self.assertFalse(report["standings"])
