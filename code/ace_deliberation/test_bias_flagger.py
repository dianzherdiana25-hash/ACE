"""Uji pembanding sezaman dan pembobotan per pertanyaan."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_deliberation import bias_flagger as model


def q(n, d=1):
    return {"numerator": n, "denominator": d}


def rec(question, round_id, who, direction, chance):
    return {
        "question_id": question, "round_id": round_id, "forecaster": who,
        "direction": direction, "probability": chance, "forecast_ref": f"p/{question}/{round_id}/{who}",
        "disclosure_ref": f"stake/{question}/{who}" if direction != "unknown" else None,
    }


def compared(question, round_id, yes, no, neutral):
    return [rec(question, round_id, person, direction, chance)
            for person, direction, chance in (("y", "yes", yes),
                                               ("n", "no", no), ("c", "neutral", neutral))]


def fixture(records=None):
    return {"protocol_ref": "fixture/protocol", "threshold": q(1, 4),
            "min_per_direction": 1, "min_questions": 2,
            "records": records if records is not None else [
                *compared("a", "1", q(3, 4), q(1, 4), q(1, 2)),
                *compared("b", "1", q(2, 3), q(1, 3), q(1, 2)),
            ]}


class BiasTests(unittest.TestCase):
    def test_both_directions_align_to_declared_interest(self):
        report = model.analyze(fixture())
        self.assertEqual(report["questions"], 2)
        yes, no = report["comparisons"][:2]
        self.assertEqual((yes["directional_shift"], no["directional_shift"]), (q(1, 4), q(1, 4)))
        self.assertEqual(yes["declared_mean"], q(3, 4))
        self.assertEqual(no["declared_mean"], q(1, 4))
        self.assertEqual(no["neutral_mean"], q(1, 2))
        for direction in ("yes", "no"):
            self.assertEqual(report["summary"][direction]["mean_directional_shift"], q(5, 24))
            self.assertEqual(report["summary"][direction]["status"], "within_threshold")

    def test_threshold_is_inclusive_at_round_and_aggregate(self):
        raw = fixture(compared("a", "1", q(3, 4), q(1, 4), q(1, 2)))
        raw["min_questions"] = 1
        report = model.analyze(raw)
        self.assertEqual(report["summary"]["yes"]["status"], "review")
        self.assertEqual([row["status"] for row in report["comparisons"]], ["review", "review"])
        self.assertEqual(report["threshold"], q(1, 4))

    def test_extended_rounds_do_not_overweight_question_in_summary(self):
        raw = fixture([*compared("a", "1", q(1), q(0), q(0)),
                       *compared("b", "1", q(0), q(0), q(0)),
                       *compared("a", "2", q(1), q(0), q(0)),
                       *compared("a", "3", q(0), q(0), q(0))])
        report = model.analyze(raw)
        self.assertEqual(report["summary"]["yes"]["mean_directional_shift"], q(1, 3))
        self.assertEqual(report["summary"]["yes"]["questions"], [
            {"question_id": "a", "directional_shift": q(2, 3)},
            {"question_id": "b", "directional_shift": q(0)},
        ])
        self.assertEqual(report["summary"]["no"]["status"], "within_threshold")

    def test_neutral_from_other_round_or_question_does_not_make_a_pair(self):
        report = model.analyze(fixture([
            rec("a", "1", "y", "yes", q(1)),
            rec("a", "2", "c", "neutral", q(0)),
            rec("b", "1", "c", "neutral", q(0)),
        ]))
        row, = report["comparisons"]
        self.assertEqual(row["status"], "insufficient_comparison")
        self.assertIsNone(row["directional_shift"])
        self.assertFalse(row["neutral"])

    def test_unknown_has_provenance_but_is_not_used_as_neutral(self):
        report = model.analyze(fixture([
            rec("a", "1", "u", "unknown", q(0)),
            rec("a", "1", "y", "yes", q(1)),
        ]))
        unknown, = report["unknown_disclosures"]
        self.assertEqual(unknown["forecast_ref"], "p/a/1/u")
        self.assertIsNone(unknown["disclosure_ref"])
        self.assertEqual(report["comparisons"][0]["status"], "insufficient_comparison")

    def test_smaller_sample_does_not_hide_round_level_result_or_create_mean(self):
        raw = {**fixture(), "min_questions": 3}
        report = model.analyze(raw)
        self.assertEqual(report["comparisons"][0]["status"], "review")
        self.assertIsNone(report["summary"]["yes"]["mean_directional_shift"])
        self.assertEqual(len(report["summary"]["yes"]["questions"]), 2)

    def test_multiple_forecasters_enter_only_their_own_group_mean(self):
        raw = fixture([*compared("a", "1", q(1), q(0), q(1, 2)),
                       rec("a", "1", "y2", "yes", q(1, 2)),
                       rec("a", "1", "c2", "neutral", q(0))])
        raw.update(min_per_direction=2, min_questions=1)
        yes, no = model.analyze(raw)["comparisons"]
        self.assertEqual(yes["directional_shift"], q(1, 2))
        self.assertEqual(no["status"], "insufficient_comparison")
        self.assertEqual([row["disclosure_ref"] for row in yes["declared"]], ["stake/a/y", "stake/a/y2"])

    def test_forecast_against_interest_is_negative_for_either_direction(self):
        raw = fixture(compared("a", "1", q(1, 4), q(3, 4), q(1, 2)))
        raw["min_questions"] = 1
        report = model.analyze(raw)
        self.assertTrue(all(row["directional_shift"] == q(-1, 4) for row in report["comparisons"]))
        self.assertTrue(all(row["status"] == "within_threshold" for row in report["comparisons"]))

    def test_undeclared_direction_or_recycled_provenance_are_invalid(self):
        original = rec("a", "1", "y", "yes", q(1))
        for changes in ({"direction": "guessed"}, {"disclosure_ref": None},
                        {"direction": "unknown"}, {"disclosure_ref": original["forecast_ref"]}):
            with self.subTest(changes=changes), self.assertRaises(model.InputError):
                model.analyze(fixture([{**original, **changes}]))

    def test_duplicate_person_round_or_forecast_ref_are_not_counted_twice(self):
        original = rec("a", "1", "y", "yes", q(1))
        for changed in ({**original, "forecast_ref": "different"},
                        {**original, "forecaster": "different"}):
            with self.subTest(changed=changed), self.assertRaisesRegex(model.InputError, "ganda"):
                model.analyze(fixture([original, changed]))

    def test_empty_input_and_strict_positive_threshold(self):
        report = model.analyze(fixture([]))
        self.assertEqual(report["questions"], 0)
        self.assertEqual(report["comparisons"], [])
        for row in report["summary"].values():
            self.assertEqual(row["status"], "insufficient_questions")
        with self.assertRaises(model.InputError):
            model.analyze({**fixture([]), "threshold": q(0)})

    def test_cli_report_is_reproducible_for_reversed_records(self):
        raw = fixture()
        path = Path(self.enterContext(TemporaryDirectory())) / "bias.json"
        content = []
        for _ in range(2):
            path.write_text(json.dumps(raw), encoding="utf-8")
            with redirect_stdout(StringIO()) as output:
                self.assertEqual(model.main([str(path)]), 0)
            content.append(output.getvalue())
            raw["records"].reverse()
        self.assertEqual(content[0], content[1])

    def test_pairing_uses_only_neutral_reference_within_same_context(self):
        report = model.analyze(fixture())
        self.assertEqual({row["neutral"][0]["forecast_ref"] for row in report["comparisons"]},
                         {"p/a/1/c", "p/b/1/c"})
        for row in report["comparisons"]:
            self.assertTrue(row["declared"][0]["forecast_ref"].startswith(f"p/{row['question_id']}/1/"))

    def test_one_direction_does_not_borrow_support_from_the_other(self):
        raw = fixture([
            rec("a", "1", "y", "yes", q(1)), rec("a", "1", "a", "neutral", q(0)),
            rec("b", "1", "n", "no", q(0)), rec("b", "1", "b", "neutral", q(1)),
        ])
        report = model.analyze(raw)
        self.assertEqual([row["status"] for row in report["comparisons"]], ["review", "review"])
        for direction, key in (("yes", "a"), ("no", "b")):
            self.assertEqual(report["summary"][direction]["status"], "insufficient_questions")
            self.assertEqual(report["summary"][direction]["questions"], [
                {"question_id": key, "directional_shift": q(1)},
            ])
