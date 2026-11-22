"""Verifier provenance dissent, garis waktu, ambang, dan skor berpasangan."""
from contextlib import redirect_stdout
from copy import deepcopy
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_deliberation import dissent_forecast_link as model
from ace_deliberation.debate_protocol import replay
from ace_deliberation.test_debate_protocol import fixture as debate_fixture


def q(n, d=1):
    return {"numerator": n, "denominator": d}


def at(day, hour=0):
    return f"2026-11-{day:02}T{hour:02}:00:00Z"


def alternative(key, estimate, turns, day=17):
    return {"forecast_at": at(day), "forecast_ref": f"forecast/{key}",
            "probability": estimate, "dissent_turns": turns}


def fixture():
    raw = debate_fixture()
    raw["turns"][1]["evidence_refs"] = ["fixture/contrary"]
    report = replay(raw)
    return {
        "question_id": "question/1", "as_of": at(20),
        "transcript": {"question_id": "question/1", "ref": "fixture/transcript",
                       "anchor_sha256": report["sha256"], "anchor_ref": "fixture/checkpoint",
                       "available_at": at(16), "report": report},
        "threshold": {"probability": q(1, 2), "ref": "fixture/threshold", "known_at": at(11)},
        "original": {"probability": q(3, 4), "forecast_ref": "forecast/base", "forecast_at": at(12)},
        "alternatives": [alternative("minority", q(1, 4), ["b1"])],
        "resolution": {"question_id": "question/1", "outcome": 0,
                       "resolution_ref": "fixture/resolution", "resolved_at": at(19)},
    }


class DissentForecastTests(unittest.TestCase):
    def test_result_retains_both_probabilities_and_links_actual_objections(self):
        raw = fixture()
        snapshot = deepcopy(raw)
        report = model.link(raw)
        self.assertEqual(report["original"]["probability"], q(3, 4))
        alt, = report["alternatives"]
        self.assertEqual(alt["probability"], q(1, 4))
        self.assertEqual(alt["delta_probability"], q(-1, 2))
        self.assertTrue(alt["crosses_threshold"])
        self.assertEqual(alt["dissent"], [
            {"turn_id": "b1", "participant": "b", "evidence_refs": ["fixture/contrary"]},
        ])
        self.assertEqual(report["transcript"]["anchor_ref"], "fixture/checkpoint")
        self.assertEqual(report["transcript"]["debate_id"], "d1")
        self.assertEqual(raw, snapshot)

    def test_resolved_pair_gets_exact_loss_and_improvement(self):
        report = model.link(fixture())
        self.assertEqual(report["original"]["brier"], q(9, 16))
        self.assertEqual(report["alternatives"][0]["brier"], q(1, 16))
        self.assertEqual(report["alternatives"][0]["brier_improvement_from_original"], q(1, 2))
        self.assertEqual(report["resolution"]["resolution_ref"], "fixture/resolution")

    def test_future_resolution_is_withheld_until_audit_timestamp(self):
        raw = fixture()
        raw["as_of"] = at(18)
        early = model.link(raw)
        self.assertIsNone(early["resolution"])
        self.assertIsNone(early["original"]["brier"])
        self.assertIsNone(early["alternatives"][0]["brier_improvement_from_original"])
        self.assertTrue(early["alternatives"][0]["crosses_threshold"])
        raw["as_of"] = at(19)
        self.assertEqual(model.link(raw)["resolution"]["outcome"], 0)

    def test_null_resolution_yields_same_comparison_as_not_yet_available_resolution(self):
        raw = fixture()
        raw["as_of"] = at(18)
        self.assertEqual(model.link(raw), model.link({**raw, "resolution": None}))

    def test_regressive_alternative_score_remains_negative(self):
        raw = fixture()
        raw["resolution"]["outcome"] = 1
        result = model.link(raw)
        self.assertEqual(result["original"]["brier"], q(1, 16))
        self.assertEqual(result["alternatives"][0]["brier_improvement_from_original"], q(-1, 2))

    def test_threshold_includes_equality_and_can_be_crossed_upwards(self):
        raw = fixture()
        raw["original"]["probability"] = q(1, 4)
        raw["alternatives"][0]["probability"] = q(1, 2)
        result = model.link(raw)["alternatives"][0]
        self.assertTrue(result["crosses_threshold"])
        raw["original"]["probability"] = q(1, 2)
        self.assertFalse(model.link(raw)["alternatives"][0]["crosses_threshold"])

    def test_replayed_debate_and_external_hash_are_checked_separately(self):
        raw = fixture()
        raw["transcript"]["report"]["turns"][1]["statement"] = "versi berubah"
        with self.assertRaisesRegex(model.InputError, "replay"):
            model.link(raw)
        raw = fixture()
        raw["transcript"]["anchor_sha256"] = "a" * 64
        with self.assertRaisesRegex(model.InputError, "hash"):
            model.link(raw)

    def test_transcript_for_another_question_is_rejected_even_with_valid_hash(self):
        raw = fixture()
        raw["transcript"]["question_id"] = "question/other"
        with self.assertRaisesRegex(model.InputError, "berbeda"):
            model.link(raw)

    def test_non_dissent_unknown_and_repeated_turns_fail_closed(self):
        for turned in (["a1"], ["made-up"], ["b1", "b1"], []):
            raw = fixture()
            raw["alternatives"][0]["dissent_turns"] = turned
            with self.subTest(turned=turned), self.assertRaises(model.InputError):
                model.link(raw)

    def test_forecast_before_transcript_or_on_resolution_date_is_invalid(self):
        for day in (13, 15, 19, 20, 21):
            raw = fixture()
            raw["alternatives"][0]["forecast_at"] = at(day)
            with self.subTest(day=day), self.assertRaises(model.InputError):
                model.link(raw)
        raw = fixture()
        raw["alternatives"][0]["forecast_at"] = at(16)
        self.assertEqual(model.link(raw)["alternatives"][0]["forecast_at"], "2026-11-16T00:00:00+00:00")

    def test_threshold_cannot_be_selected_after_original_forecast(self):
        raw = fixture()
        raw["threshold"]["known_at"] = at(13)
        with self.assertRaisesRegex(model.InputError, "Ambang"):
            model.link(raw)

    def test_early_or_wrong_question_resolution_fails_even_before_calculating_score(self):
        for changed in ({"resolved_at": at(12)}, {"question_id": "question/other"}):
            raw = fixture()
            raw["resolution"].update(changed)
            with self.subTest(changed=changed), self.assertRaisesRegex(model.InputError, "Resolusi"):
                model.link(raw)

    def test_cli_and_canonical_outputs_preserve_unresolved_empty_alternatives(self):
        data = {**fixture(), "alternatives": [], "resolution": None}
        path = Path(self.enterContext(TemporaryDirectory())) / "forecast.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(model.main([str(path)]), 0)
        report = json.loads(output.getvalue())
        self.assertEqual(report["alternatives"], [])
        self.assertEqual(report["original"]["forecast_ref"], "forecast/base")
        self.assertIsNone(report["resolution"])

    def test_one_forecast_per_dissent_set_and_distinct_provenance(self):
        for added in (alternative("other", q(1), ["b1"]), alternative("base", q(1), ["b1"])):
            raw = fixture()
            raw["alternatives"].append(added)
            with self.subTest(added=added), self.assertRaisesRegex(model.InputError, "ganda"):
                model.link(raw)

    def test_in_progress_replay_cannot_anchor_an_alternative(self):
        raw = fixture()
        debate_input = debate_fixture()
        debate_input["turns"].pop()
        debate_input.pop("decision")
        report = replay(debate_input)
        raw["transcript"].update(report=report, anchor_sha256=report["sha256"])
        with self.assertRaisesRegex(model.InputError, "masih"):
            model.link(raw)

    def test_missing_transcript_by_cutoff_cannot_be_hidden_by_no_alternatives(self):
        raw = fixture()
        raw["transcript"]["available_at"] = at(21)
        raw["alternatives"].clear()
        with self.assertRaisesRegex(model.InputError, "jendela"):
            model.link(raw)
