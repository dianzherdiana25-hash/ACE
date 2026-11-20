"""Uji putaran buntu, perubahan bukti, dan jendela pendinginan."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_deliberation import deadlock_breaker as breaker


def debate_round(cycle, votes=None, evidence=None):
    return {"cycle": cycle, "votes": votes or {"x": "a", "y": "b", "z": "b"},
            "evidence_refs": evidence or [], "source_ref": f"fixture/round/{cycle}"}


def fixture():
    return {"rounds": [debate_round(cycle) for cycle in (1, 2, 3)],
            "choices": ["a", "b"], "as_of_cycle": 3,
            "policy": {"repetitions": 3, "cooldown_cycles": 4,
                       "consensus": {"numerator": 1, "denominator": 1}}}


class BreakerTests(unittest.TestCase):
    def test_fixed_distribution_starts_non_sliding_cooldown(self):
        raw = fixture()
        result = breaker.recommend(raw)
        self.assertEqual(result["status"], "cooldown")
        self.assertEqual(result["deadlock"], {"kind": "unchanged", "detected_at_cycle": 3, "resume_at_cycle": 7,
                                              "source_refs": ["fixture/round/1", "fixture/round/2", "fixture/round/3"]})
        raw["rounds"].append(debate_round(4))
        raw["as_of_cycle"] = 7
        self.assertEqual(breaker.recommend(raw)["status"], "cooldown_elapsed")

    def test_evidence_change_resets_repetition_and_repeated_reference_does_not(self):
        raw = fixture()
        raw["rounds"][2]["evidence_refs"] = ["fixture/evidence"]
        self.assertEqual(breaker.recommend(raw)["status"], "continue")
        raw["rounds"].extend([debate_round(4, evidence=["fixture/evidence"]), debate_round(5)])
        raw["as_of_cycle"] = 5
        result = breaker.recommend(raw)
        self.assertEqual(result["deadlock"]["detected_at_cycle"], 5)
        self.assertEqual(result["observation_rounds"][3]["new_evidence_refs"], [])

    def test_alternating_polls_trigger_independent_pattern(self):
        raw = fixture()
        raw["policy"]["repetitions"] = 2
        raw["rounds"].append(debate_round(4))
        b = {"x": "a", "y": "a", "z": "b"}
        raw["rounds"][1]["votes"] = b
        raw["rounds"][3]["votes"] = b
        raw["as_of_cycle"] = 4
        result = breaker.recommend(raw)
        self.assertEqual(result["deadlock"]["kind"], "alternating")
        self.assertEqual(len(result["deadlock"]["source_refs"]), 4)

    def test_roster_change_prevents_commensurability(self):
        raw = fixture()
        raw["rounds"][2]["votes"]["new"] = raw["rounds"][2]["votes"].pop("z")
        self.assertEqual(breaker.recommend(raw)["status"], "continue")

    def test_consensus_after_deadlock_moves_to_recorded_state(self):
        raw = fixture()
        raw["rounds"].append(debate_round(4, votes={"x": "a", "y": "a", "z": "a"}))
        raw["as_of_cycle"] = 4
        result = breaker.recommend(raw)
        self.assertEqual(result["status"], "consensus_recorded")
        self.assertIsNone(result["deadlock"])

    def test_invalid_deadline_reordered_round_or_unknown_voter_choice_refused(self):
        raw = fixture()
        for update in ({"as_of_cycle": 2}, {"rounds": raw["rounds"][::-1]},
                       {"rounds": [debate_round(1, votes={"x": "unknown", "y": "a"})]}):
            with self.subTest(update=update), self.assertRaises(breaker.DeadlockError):
                breaker.recommend({**raw, **update})

    def test_cli_agrees_with_replay_and_preserves_source_order(self):
        raw = fixture()
        expected = breaker.recommend(raw)
        for row in raw["rounds"]:
            row["votes"] = dict(reversed(list(row["votes"].items())))
        path = Path(self.enterContext(TemporaryDirectory())) / "rounds.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(breaker.main([str(path)]), 0)
        self.assertEqual(json.loads(output.getvalue()), expected)

    def test_first_round_after_cooldown_needs_new_repetition_to_stop_again(self):
        raw = fixture()
        raw["rounds"].append(debate_round(7))
        raw["as_of_cycle"] = 7
        report = breaker.recommend(raw)
        self.assertEqual(report["status"], "continue")
        self.assertEqual(report["past_cooldowns"][0]["closed_reason"], "resumed")
        self.assertEqual(report["past_cooldowns"][0]["closed_at_cycle"], 7)
        raw["rounds"].extend([debate_round(8), debate_round(9)])
        raw["as_of_cycle"] = 9
        self.assertEqual(breaker.recommend(raw)["deadlock"]["detected_at_cycle"], 9)

    def test_fresh_evidence_closes_cooldown_before_scheduled_resume(self):
        raw = fixture()
        raw["rounds"].append(debate_round(4, evidence=["fixture/independent"]))
        raw["as_of_cycle"] = 4
        report = breaker.recommend(raw)
        self.assertEqual(report["status"], "continue")
        self.assertEqual(report["past_cooldowns"][0]["closed_reason"], "new_evidence")
        self.assertEqual(report["past_cooldowns"][0]["resume_at_cycle"], 7)

    def test_changed_roster_reason_survives_in_trace_after_break(self):
        raw = fixture()
        raw["rounds"].append(debate_round(4, votes={"x": "a", "y": "b", "new": "b"}))
        raw["as_of_cycle"] = 4
        report = breaker.recommend(raw)
        self.assertEqual(report["status"], "continue")
        self.assertEqual(report["past_cooldowns"][0]["closed_reason"], "roster_changed")

    def test_half_or_less_is_not_a_valid_consensus_threshold(self):
        raw = fixture()
        raw["policy"]["consensus"] = {"numerator": 1, "denominator": 2}
        with self.assertRaises(breaker.DeadlockError):
            breaker.recommend(raw)

    def test_empty_history_emits_no_fabricated_outcome(self):
        report = breaker.recommend({**fixture(), "rounds": []})
        self.assertEqual(report["status"], "no_rounds")
        self.assertEqual(report["past_cooldowns"], [])
        self.assertIsNone(report["deadlock"])

    def test_catalog_does_not_require_a_vote_for_every_option_to_find_deadlock(self):
        result = breaker.recommend({**fixture(), "choices": ["a", "b", "unused"]})
        self.assertEqual(result["status"], "cooldown")
