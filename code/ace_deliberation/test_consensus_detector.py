"""Uji temuan ballot tanpa menyimpulkan niat dari suara peserta."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_deliberation import consensus_detector as detector


def ballot(participant, choice, phase, *, rationale=None, evidence=True):
    return {
        "participant": participant,
        "option": choice,
        "rationale": rationale or f"Rujukan berbeda dari auditor {participant}.",
        "source_ref": f"fixture/{phase}/{participant}",
        "evidence_refs": [f"fixture/evidence/{participant}"] if evidence else [],
    }


def fixture():
    return {
        "options": ["wait", "adopt"],
        "participants": [{"id": name, "authority": 3 if name == "lead" else 0}
                         for name in ("lead", "a", "b", "c")],
        "private": [ballot(name, "adopt" if name == "lead" else "wait", "private")
                    for name in ("lead", "a", "b", "c")],
        "public": [ballot(name, "adopt", "public") for name in ("lead", "a", "b", "c")],
    }


class ConsensusTests(unittest.TestCase):
    def test_high_authority_first_and_two_switches_flagged_with_both_phases(self):
        result = detector.inspect_consensus(fixture())
        self.assertEqual(result["status"], "review_required")
        self.assertEqual(result["apparent_option"], "adopt")
        self.assertEqual(result["tallies"], {"adopt": 4, "wait": 0})
        finding, = result["findings"]
        self.assertEqual(finding["code"], "convergence_after_authority")
        self.assertIn("fixture/private/a", finding["ballot_refs"])
        self.assertIn("fixture/public/lead", finding["ballot_refs"])

    def test_authority_not_first_is_not_treated_as_cause(self):
        raw = fixture()
        raw["public"].reverse()
        result = detector.inspect_consensus(raw)
        self.assertEqual(result["status"], "no_listed_signal")
        self.assertEqual(result["findings"], [])

    def test_duplicate_rationale_matches_normalized_text_and_flags_missing_basis(self):
        raw = fixture()
        raw["private"] = []
        raw["public"] = [
            ballot(name, "adopt", "public", evidence=position == 0, rationale=text)
            for position, (name, text) in enumerate((
                ("a", "Angka tidak masuk batas pemeriksaan."),
                ("b", "ANGKA tidak masuk batas pemeriksaan!"),
                ("c", "Ａngka tidak masuk batas pemeriksaan"),
            ))
        ]
        result = detector.inspect_consensus(raw)
        self.assertEqual([item["code"] for item in result["findings"]],
                         ["missing_private_record", "repeated_rationale", "support_without_evidence"])
        self.assertEqual(result["findings"][-1]["participants"], ["b", "c"])

    def test_turnout_denominator_all_registered_not_just_votes_submitted(self):
        raw = fixture()
        raw["public"] = raw["public"][:2]
        raw["private"] = []
        result = detector.inspect_consensus(raw)
        self.assertEqual(result["status"], "no_consensus")
        self.assertEqual(result["registered_count"], 4)
        self.assertIsNone(result["apparent_option"])

    def test_exact_two_thirds_allows_review_and_awards_no_extra_vote_for_authority(self):
        raw = fixture()
        raw["participants"] = raw["participants"][:3]
        raw["private"] = raw["private"][:3]
        raw["public"] = [*raw["public"][:2], ballot("b", "wait", "public")]
        result = detector.inspect_consensus(raw)
        self.assertEqual(result["apparent_option"], "adopt")
        self.assertEqual(result["tallies"], {"adopt": 2, "wait": 1})

    def test_rejects_reused_ballot_source_or_double_vote(self):
        raw = fixture()
        for posts in ([*raw["public"][:3], raw["public"][0]],
                      [*raw["public"][:3], {**raw["public"][-1], "source_ref": "fixture/private/c"}],
                      [{**raw["public"][0], "option": "made-up"}]):
            with self.subTest(posts=posts), self.assertRaises(detector.ConsensusError):
                detector.inspect_consensus({**raw, "public": posts})

    def test_cli_signals_review_and_returns_ballot_refs(self):
        path = Path(self.enterContext(TemporaryDirectory())) / "ballots.json"
        path.write_text(json.dumps(fixture()), encoding="utf-8")
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(detector.main([str(path)]), 1)
        self.assertEqual(json.loads(output.getvalue())["findings"][0]["code"],
                         "convergence_after_authority")

    def test_order_in_independent_data_does_not_change_the_report(self):
        raw = fixture()
        expected = detector.inspect_consensus(raw)
        reordered = {**raw, "options": raw["options"][::-1],
                     "participants": raw["participants"][::-1], "private": raw["private"][::-1]}
        self.assertEqual(detector.inspect_consensus(reordered), expected)

    def test_one_unsupported_ballot_does_not_imply_independence_or_find_a_pattern(self):
        raw = fixture()
        raw["public"].reverse()
        raw["public"][0]["evidence_refs"] = []
        result = detector.inspect_consensus(raw)
        self.assertEqual(result["status"], "no_listed_signal")
        self.assertEqual(result["findings"], [])
