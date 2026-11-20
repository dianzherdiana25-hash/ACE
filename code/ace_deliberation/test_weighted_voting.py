"""Uji suara berbobot, transfer preferensi, recusal, dan seri."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_deliberation import weighted_voting as voting


def member(identifier, weight, topic="logic"):
    return {"voter": identifier, "weight": weight, "topic": topic,
            "expertise_ref": f"fixture/competency/{identifier}/{topic}"}


def ballot(identifier, *options):
    return {"voter": identifier, "rankings": list(options), "source_ref": f"fixture/ballot/{identifier}"}


def fixture():
    return {"topic": "logic", "choices": ["x", "y", "z"], "quorum": {"numerator": 3, "denominator": 4},
            "roster": [member("one", 4), member("two", 3), member("three", 2), member("outside", 5, "unknown")],
            "recusals": [], "ballots": [ballot("one", "x", "y"), ballot("two", "y", "x"), ballot("three", "z", "y")]}


class WeightedVotingTests(unittest.TestCase):
    def test_weights_and_transferred_ballot_reverse_first_round_lead(self):
        result = voting.elect(fixture())
        self.assertEqual(result["winner"], "y")
        self.assertEqual(result["rounds"], [
            {"tally": {"x": 4, "y": 3, "z": 2}, "continuing_weight": 9, "eliminated": ["z"]},
            {"tally": {"x": 4, "y": 5}, "continuing_weight": 9, "eliminated": []},
        ])
        self.assertEqual(result["ballots"][0]["expertise_ref"], "fixture/competency/one/logic")

    def test_conflicted_weight_is_excluded_only_with_recusal_and_never_votes(self):
        raw = fixture()
        raw["ballots"].pop()
        self.assertEqual(voting.elect(raw)["required_weight"], 7)
        raw["ballots"].pop()
        raw["recusals"] = [{"voter": "two", "source_ref": "fixture/recusal/two"},
                           {"voter": "three", "source_ref": "fixture/recusal/three"}]
        result = voting.elect(raw)
        self.assertEqual((result["roster_weight"], result["required_weight"], result["winner"]), (4, 3, "x"))
        with self.assertRaises(voting.VotingError):
            voting.elect({**raw, "ballots": [*raw["ballots"], ballot("two", "y")]})

    def test_higher_weight_participation_threshold_blocks_when_missing(self):
        raw = fixture()
        raw["ballots"] = raw["ballots"][:1]
        report = voting.elect(raw)
        self.assertEqual(report["status"], "quorum_missing")
        self.assertEqual(report["rounds"], [])
        self.assertIsNone(report["winner"])

    def test_unsafe_lowest_tie_cannot_be_broken_by_candidate_name(self):
        raw = fixture()
        for row in raw["roster"]:
            row["weight"] = 1
        report = voting.elect(raw)
        self.assertEqual(report["status"], "elimination_tie")
        self.assertIsNone(report["winner"])
        self.assertEqual(report["rounds"][0]["eliminated"], [])

    def test_exhausted_weight_is_removed_from_runoff_denominator(self):
        raw = fixture()
        raw["ballots"][-1] = ballot("three", "z")
        result = voting.elect(raw)
        self.assertEqual(result["participating_weight"], 9)
        self.assertEqual(result["rounds"][-1]["continuing_weight"], 7)
        self.assertEqual(result["winner"], "x")

    def test_unqualified_and_duplicate_ballot_do_not_gain_weight(self):
        raw = fixture()
        for invalid in (ballot("outside", "y"), ballot("one", "z")):
            with self.subTest(invalid=invalid), self.assertRaises(voting.VotingError):
                voting.elect({**raw, "ballots": [*raw["ballots"], invalid]})

    def test_cli_counts_only_requested_domain_and_result_is_deterministic(self):
        raw = fixture()
        expected = voting.elect(raw)
        raw["ballots"].reverse()
        raw["roster"].reverse()
        path = Path(self.enterContext(TemporaryDirectory())) / "voting.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(voting.main([str(path)]), 0)
        self.assertEqual(json.loads(output.getvalue()), expected)

    def test_zero_weight_tie_can_be_eliminated_without_forcing_a_name_order(self):
        raw = fixture()
        raw["choices"].extend(["v", "w"])
        result = voting.elect(raw)
        self.assertEqual(result["rounds"][0]["eliminated"], ["v", "w"])
        self.assertEqual(result["winner"], "y")
        self.assertEqual(len(result["rounds"]), 3)

    def test_roster_weight_keeps_nonparticipants_visible_and_excludes_other_topics(self):
        raw = fixture()
        raw["ballots"].pop()
        report = voting.elect(raw)
        self.assertEqual(report["quorum"], {"numerator": 3, "denominator": 4})
        self.assertEqual([item["voter"] for item in report["eligible_roster"]], ["one", "three", "two"])
        record = report["eligible_roster"][1]
        self.assertFalse(record["participated"])
        self.assertEqual(record["expertise_ref"], "fixture/competency/three/logic")

    def test_empty_matching_roster_yields_no_winner_even_with_threshold_zero_after_calculation(self):
        raw = {**fixture(), "ballots": [], "topic": "unrepresented"}
        report = voting.elect(raw)
        self.assertEqual(report["eligible_roster"], [])
        self.assertEqual(report["status"], "no_eligible_weight")
        self.assertIsNone(report["winner"])

    def test_invalid_partial_rankings_do_not_reduce_participation_silently(self):
        for invalid in (ballot("one"), ballot("one", "x", "x"), ballot("one", "unregistered")):
            raw = fixture()
            raw["ballots"][0] = invalid
            with self.subTest(invalid=invalid), self.assertRaises(voting.VotingError):
                voting.elect(raw)

    def test_quorum_ratio_above_one_is_refused(self):
        with self.assertRaises(voting.VotingError):
            voting.elect({**fixture(), "quorum": {"numerator": 2, "denominator": 1}})
