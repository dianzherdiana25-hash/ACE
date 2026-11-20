"""Uji median, bobot, kriteria kritis, dan sumber seperti dinyatakan penilai."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_deliberation import argument_scorer as scorer


def review(criterion, reviewer, points):
    return {"argument": "proposal", "criterion": criterion, "reviewer": reviewer,
            "points": points, "source_ref": f"fixture/{criterion}/{reviewer}"}


def fixture():
    return {"minimum_reviewers": 2, "max_spread_percent": 30,
            "rubric": [
                {"id": "source", "source_ref": "fixture/criterion/source", "max_points": 10,
                 "weight": 2, "critical_min": 4},
                {"id": "logic", "source_ref": "fixture/criterion/logic", "max_points": 8,
                 "weight": 1, "critical_min": None},
            ],
            "arguments": [{"id": "proposal", "source_ref": "fixture/proposal"}],
            "reviews": [review("source", "a", 7), review("source", "b", 8),
                        review("logic", "a", 6), review("logic", "b", 6)]}


def q(a, b=1):
    return {"numerator": a, "denominator": b}


class ScorerTests(unittest.TestCase):
    def test_weight_normalization_uses_medial_fraction_and_keeps_sources(self):
        row, = scorer.score(fixture())["arguments"]
        self.assertEqual(row["status"], "scored")
        self.assertEqual(row["weighted_score"], q(3, 4))
        criterion = row["grades"][1]
        self.assertEqual(criterion["median"], q(15, 2))
        self.assertEqual(criterion["criterion_ref"], "fixture/criterion/source")
        self.assertEqual(criterion["reviews"][0]["source_ref"], "fixture/source/a")

    def test_high_noncritical_score_cannot_bypass_critical_minimum(self):
        raw = fixture()
        raw["reviews"][0]["points"] = 2
        raw["reviews"][1]["points"] = 3
        raw["reviews"][2]["points"] = raw["reviews"][3]["points"] = 8
        report = scorer.score(raw)["arguments"][0]
        self.assertEqual(report["weighted_score"], q(1, 2))
        self.assertEqual(report["status"], "critical_floor_missed")

    def test_missing_review_holds_score_instead_of_zero_filling(self):
        raw = fixture()
        raw["reviews"].pop(0)
        row = scorer.score(raw)["arguments"][0]
        self.assertEqual(row["status"], "review_required")
        self.assertIsNone(row["weighted_score"])
        self.assertIsNone(row["grades"][1]["median"])
        self.assertEqual(row["grades"][1]["reasons"], ["too_few_reviewers"])

    def test_at_spread_limit_reviewer_disagreement_is_still_allowed(self):
        raw = fixture()
        raw["reviews"][0]["points"] = 5
        self.assertEqual(scorer.score(raw)["arguments"][0]["status"], "scored")
        raw["reviews"][0]["points"] = 4
        self.assertEqual(scorer.score(raw)["arguments"][0]["grades"][1]["reasons"], ["reviewer_disagreement"])

    def test_reviews_cannot_reuse_source_or_voter_to_fill_quorum(self):
        raw = fixture()
        for changes in ({"source_ref": raw["reviews"][0]["source_ref"]}, {"reviewer": "a"}, {"points": True}):
            with self.subTest(changes=changes), self.assertRaises(scorer.RubricError):
                scorer.score({**raw, "reviews": [raw["reviews"][0], {**raw["reviews"][1], **changes},
                                                 *raw["reviews"][2:]]})

    def test_shuffling_sources_and_votes_preserves_cli_report(self):
        raw = fixture()
        initial = scorer.score(raw)
        for key in ("rubric", "arguments", "reviews"):
            raw[key].reverse()
        path = Path(self.enterContext(TemporaryDirectory())) / "argument.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(scorer.main([str(path)]), 0)
        self.assertEqual(json.loads(output.getvalue()), initial)

    def test_possible_weighted_range_preserves_reviewer_disagreement(self):
        raw = fixture()
        raw["reviews"][0]["points"] = 4
        row, = scorer.score(raw)["arguments"]
        self.assertEqual(row["status"], "review_required")
        self.assertEqual(row["grades"][1]["observed_range"], {"minimum": 4, "maximum": 8})
        self.assertEqual(row["weighted_range"], {"minimum": q(31, 60), "maximum": q(47, 60)})
        self.assertEqual(row["weighted_score"], q(13, 20))

    def test_insufficient_review_holds_score_bounds_for_whole_argument(self):
        raw = {**fixture(), "minimum_reviewers": 3}
        row, = scorer.score(raw)["arguments"]
        self.assertIsNone(row["weighted_score"])
        self.assertIsNone(row["weighted_range"])
        self.assertTrue(all(item["observed_range"] is None for item in row["grades"]))

    def test_odd_median_resists_one_extreme_score_but_surfaces_conflict(self):
        raw = fixture()
        raw["reviews"].append(review("source", "c", 0))
        row, = scorer.score(raw)["arguments"]
        self.assertEqual(row["grades"][1]["median"], q(7))
        self.assertEqual(row["grades"][1]["spread"], q(4, 5))
        self.assertEqual(row["status"], "review_required")

    def test_scores_for_other_argument_cannot_fill_missing_criterion_coverage(self):
        raw = fixture()
        raw["arguments"].append({"id": "other", "source_ref": "fixture/other"})
        other, first = scorer.score(raw)["arguments"]
        self.assertEqual(other["status"], "review_required")
        self.assertEqual(first["status"], "scored")

    def test_incompatible_criterion_scale_cannot_inflate_normalized_score(self):
        raw = fixture()
        raw["rubric"][0]["max_points"] = 4
        with self.assertRaises(scorer.RubricError):
            scorer.score(raw)

    def test_exact_critical_floor_is_permitted_and_does_not_move_rubric(self):
        raw = fixture()
        before = json.dumps(raw["rubric"], sort_keys=True)
        raw["reviews"][0]["points"] = raw["reviews"][1]["points"] = 4
        self.assertEqual(scorer.score(raw)["arguments"][0]["status"], "scored")
        self.assertEqual(json.dumps(raw["rubric"], sort_keys=True), before)

    def test_source_ref_of_argument_and_rubric_must_be_distinct(self):
        raw = fixture()
        raw["arguments"][0]["source_ref"] = raw["rubric"][0]["source_ref"]
        with self.assertRaisesRegex(scorer.RubricError, "telah digunakan"):
            scorer.score(raw)
