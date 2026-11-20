"""Uji drift individu, perpindahan distribusi dan perubahan roster."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_deliberation import position_drift as drift


def record(number, *observations):
    return {"number": number, "source_ref": f"fixture/round/{number}", "positions": [
        {"participant": actor, "issue": issue, "position": stance, "source_ref": f"fixture/{number}/{actor}/{issue}"}
        for actor, issue, stance in observations
    ]}


def fixture():
    return {"issues": [{"id": "one", "weight": 3, "source_ref": "fixture/one"},
                       {"id": "two", "weight": 1, "source_ref": "fixture/two"}],
            "rounds": [
                record(1, ("a", "one", "support"), ("b", "one", "oppose"), ("a", "two", "undecided"),
                       ("departed", "two", "support")),
                record(2, ("a", "one", "oppose"), ("b", "one", "support"), ("a", "two", "support"),
                       ("new", "two", "oppose")),
            ]}


def q(n, d=1):
    return {"numerator": n, "denominator": d}


class PositionDriftTests(unittest.TestCase):
    def test_people_swap_positions_without_creating_distribution_shift(self):
        diff, = drift.measure(fixture())["comparisons"]
        self.assertEqual(diff["weighted_individual_drift"], q(13, 14))
        self.assertEqual(diff["weighted_distribution_drift"], q(1, 7))
        self.assertEqual([row["total_variation"] for row in diff["issues"]], [q(0), q(1)])
        self.assertEqual([row["paired_count"] for row in diff["issues"]], [2, 1])
        self.assertEqual([item["reversal"] for item in diff["changes"]], [True, False, True])
        self.assertEqual(diff["changes"][0]["standardized_shift"], q(-1))

    def test_new_or_missing_participant_does_not_create_synthetic_transition(self):
        diff, = drift.measure(fixture())["comparisons"]
        self.assertEqual(diff["paired_count"], 3)
        self.assertEqual(diff["arrivals"], [{"participant": "new", "issue": "two", "source_ref": "fixture/2/new/two"}])
        self.assertEqual(diff["departures"], [{"participant": "departed", "issue": "two",
                                              "source_ref": "fixture/1/departed/two"}])
        self.assertEqual(set(item["participant"] for item in diff["changes"]), {"a", "b"})

    def test_no_overlap_is_unknown_instead_of_reported_no_drift(self):
        raw = fixture()
        raw["rounds"] = [record(1, ("a", "one", "support")), record(2, ("b", "one", "support"))]
        diff, = drift.measure(raw)["comparisons"]
        self.assertIsNone(diff["weighted_individual_drift"])
        self.assertIsNone(diff["weighted_distribution_drift"])
        self.assertIsNone(diff["issues"][0]["total_variation"])

    def test_same_positions_produce_measured_zero(self):
        raw = fixture()
        raw["rounds"] = [record(1, ("a", "one", "support")), record(2, ("a", "one", "support"))]
        diff, = drift.measure(raw)["comparisons"]
        self.assertEqual(diff["weighted_individual_drift"], q(0))
        self.assertEqual(diff["weighted_distribution_drift"], q(0))

    def test_adjacent_rounds_compare_separately_and_keep_source_pointers(self):
        raw = fixture()
        raw["rounds"].append(record(4, ("a", "two", "oppose")))
        first, last = drift.measure(raw)["comparisons"]
        self.assertEqual((first["before_round"], first["after_round"]), (1, 2))
        self.assertEqual((last["before_round"], last["after_round"]), (2, 4))
        self.assertEqual(last["changes"][0]["after_ref"], "fixture/4/a/two")

    def test_unknown_duplicate_or_unprovenanced_observation_is_refused(self):
        raw = fixture()
        original = raw["rounds"][1]["positions"][0]
        raw["rounds"][1]["positions"].append({**original, "source_ref": "fixture/duplicate"})
        with self.assertRaises(drift.DriftError):
            drift.measure(raw)
        raw = fixture()
        raw["issues"][0]["source_ref"] = raw["rounds"][0]["source_ref"]
        with self.assertRaises(drift.DriftError):
            drift.measure(raw)

    def test_cli_is_stable_under_round_and_ballot_reordering(self):
        raw = fixture()
        expected = drift.measure(raw)
        raw["rounds"].reverse()
        for row in raw["rounds"]:
            row["positions"].reverse()
        path = Path(self.enterContext(TemporaryDirectory())) / "drift.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(drift.main([str(path)]), 0)
        self.assertEqual(json.loads(output.getvalue()), expected)

    def test_issue_profile_keeps_net_shifts_reversals_and_source_refs(self):
        first, second = drift.measure(fixture())["comparisons"][0]["issues"]
        self.assertEqual(first["net_shift"], q(0))
        self.assertEqual(first["individual_drift"], q(1))
        self.assertEqual(first["reversals"], 2)
        self.assertEqual(first["source_ref"], "fixture/one")
        self.assertEqual(second["net_shift"], q(1, 2))
        self.assertEqual(second["individual_drift"], q(1, 2))
        self.assertEqual(second["reversals"], 0)

    def test_pairwise_change_matches_ordinal_oracle_for_every_stance_transition(self):
        from itertools import product

        score = {"oppose": -1, "undecided": 0, "support": 1}
        for before, after in product(score, repeat=2):
            with self.subTest(before=before, after=after):
                raw = fixture()
                raw["rounds"] = [record(1, ("solo", "one", before)), record(2, ("solo", "one", after))]
                result = drift.measure(raw)["comparisons"][0]
                profile = result["issues"][0]
                delta = score[after] - score[before]
                self.assertEqual(profile["net_shift"]["numerator"] / profile["net_shift"]["denominator"],
                                 delta / 2)
                self.assertEqual(profile["reversals"], int(abs(delta) == 2))
                self.assertEqual(profile["total_variation"], q(int(before != after)))

    def test_one_round_has_no_comparison_and_cannot_fabricate_drift(self):
        raw = fixture()
        raw["rounds"].pop()
        self.assertEqual(drift.measure(raw)["round_count"], 1)
        self.assertEqual(drift.measure(raw)["comparisons"], [])

    def test_no_overlap_keeps_issue_direction_unknown(self):
        raw = fixture()
        raw["rounds"] = [record(1, ("a", "one", "support")), record(2, ("a", "two", "oppose"))]
        one, two = drift.measure(raw)["comparisons"][0]["issues"]
        self.assertTrue(all(item["net_shift"] is None and item["individual_drift"] is None for item in (one, two)))
