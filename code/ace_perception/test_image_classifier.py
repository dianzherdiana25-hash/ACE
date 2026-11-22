"""Verifier voting gambar, ambang bukti, dan penolakan proporsi palsu."""
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from ace_perception import image_classifier as model


IMAGES = {key: str(index)*64 for index, key in enumerate(("consensus", "tie", "alone", "empty"), 1)}
ORGANS = {"a": 3, "b": 2, "c": 2, "d": 3}


def vote(image, organ, label, score=9000):
    return {"image_id": image, "organ_id": organ, "image_sha256": IMAGES[image],
            "label": label, "confidence_bp": score, "receipt_ref": f"fixture/vote/{image}/{organ}"}


def fixture():
    receipts = [vote("consensus", "a", "grid"), vote("consensus", "b", "grid"),
                vote("consensus", "c", "photo"), vote("consensus", "d", "grid"),
                vote("tie", "a", "grid"), vote("tie", "b", "grid"),
                vote("tie", "c", "photo"), vote("tie", "d", "photo"),
                vote("alone", "a", "grid"), vote("alone", "b", "grid", score=4999),
                vote("alone", "c", None, None)]
    raw = {"plan_ref": "fixture/vote_plan", "taxonomy_ref": "fixture/labels", "receipt_sha256": model._sha(receipts),
           "labels": ["grid", "photo"], "organs": [{"id": key, "weight": value, "organ_ref": f"fixture/organ/{key}"}
                                                   for key, value in ORGANS.items()],
           "images": [{"id": key, "image_sha256": value, "image_ref": f"fixture/image/{key}"} for key, value in IMAGES.items()],
           "minimum_voters": 2, "minimum_coverage_bp": 7000, "minimum_winner_bp": 5000, "minimum_margin_bp": 1000,
           "minimum_vote_confidence_bp": 5000}
    return raw, receipts


def classify(raw, receipts):
    return model.classify(raw, receipts, model._sha(raw))


def fresh(raw, votes):
    raw["receipt_sha256"] = model._sha(votes)
    return classify(raw, votes)


def rows(result):
    return {row["id"]: row for row in result["classifications"]}


class VotingTests(unittest.TestCase):
    def test_weighted_consensus_and_tie_without_lexical_verdict(self):
        plan, receipts = fixture()
        result = classify(plan, receipts)
        self.assertEqual((result["resolved"], result["unresolved"]), (1, 3))
        self.assertEqual(result["receipt_sha256"], model._sha(receipts))
        winning = rows(result)["consensus"]
        self.assertEqual(winning["label"], "grid")
        self.assertEqual(winning["status"], "classified")
        self.assertEqual(winning["eligible_weight"], 10)
        self.assertEqual(winning["ranking"], [{"label": "grid", "weight": 8, "organs": ["a", "b", "d"]},
                                              {"label": "photo", "weight": 2, "organs": ["c"]}])
        tied = rows(result)["tie"]
        self.assertEqual(tied["reasons"], ["margin"])
        self.assertEqual(tied["eligible_weight"], 10)
        self.assertTrue(all(item["receipt_ref"] for item in tied["observations"]))
        self.assertIsNone(tied["label"])
        self.assertEqual(tied["ranking"][0]["weight"], tied["ranking"][1]["weight"])

    def test_abstain_missing_and_low_confidence_are_distinct_and_do_not_change_denominator(self):
        listed = rows(classify(*fixture()))
        alone = listed["alone"]
        self.assertEqual(alone["registered_weight"], 10)
        self.assertEqual(alone["eligible_weight"], 3)
        self.assertEqual([item["status"] for item in alone["observations"]], ["counted", "low_confidence", "abstained", "missing"])
        self.assertEqual(alone["reasons"], ["coverage", "quorum", "support"])
        self.assertIsNone(alone["label"])
        self.assertIsNone(alone["observations"][-1]["receipt_ref"])
        self.assertEqual(listed["empty"]["reasons"], ["coverage", "quorum"])

    def test_exact_winner_confidence_coverage_and_margin_boundaries(self):
        plan, votes = fixture()
        selected = [vote("consensus", "a", "grid", 5000), vote("consensus", "b", "grid"),
                    vote("consensus", "c", "photo")]
        plan["minimum_margin_bp"] = 3000
        row = rows(fresh(plan, selected))["consensus"]
        self.assertEqual(row["label"], "grid")
        self.assertEqual(row["eligible_weight"], 7)
        for field in ("minimum_winner_bp", "minimum_margin_bp", "minimum_coverage_bp", "minimum_vote_confidence_bp"):
            modified = {**plan, field: plan[field]+1}
            with self.subTest(field=field):
                self.assertIsNone(rows(classify(modified, selected))["consensus"]["label"])

    def test_tampering_with_known_snapshot_or_plan_is_distinguished(self):
        raw, votes = fixture()
        anchor = model._sha(raw)
        votes[0]["label"] = "photo"
        with self.assertRaisesRegex(ValueError, "komitmen"):
            model.classify(raw, votes, anchor)
        raw["receipt_sha256"] = model._sha(votes)
        with self.assertRaisesRegex(ValueError, "anchor"):
            model.classify(raw, votes, anchor)

    def test_unknown_and_misbound_evidence_never_enters_majority(self):
        for changes in ({"label": "other"}, {"image_sha256": "f"*64}, {"organ_id": "unregistered"},
                        {"receipt_ref": "fixture/vote/tie/a"}, {"confidence_bp": True},
                        {"label": None, "confidence_bp": 9000}, {"image_id": "other"}):
            raw, votes = fixture()
            votes[0].update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                fresh(raw, votes)
        raw, votes = fixture()
        votes.append({**votes[0], "receipt_ref": "fixture/vote/extra"})
        with self.assertRaisesRegex(ValueError, "ganda"):
            fresh(raw, votes)

    def test_roster_must_bind_unique_image_bytes(self):
        raw, votes = fixture()
        raw["images"][1]["image_sha256"] = raw["images"][0]["image_sha256"]
        with self.assertRaisesRegex(ValueError, "mengulang hash"):
            classify(raw, votes)

    def test_cli_sorts_views_without_mutating_snapshot(self):
        raw, votes = fixture()
        original = classify(raw, votes)
        votes.reverse()
        result = fresh(raw, votes)
        self.assertEqual(result["classifications"], original["classifications"])
        self.assertNotEqual(result["receipt_sha256"], original["receipt_sha256"])
        folder = Path(self.enterContext(TemporaryDirectory()))
        plan, data = folder/"plan", folder/"votes"
        plan.write_bytes(model._canonical(raw))
        data.write_bytes(model._canonical(votes))
        process = subprocess.run([sys.executable, "-m", "ace_perception.image_classifier", str(plan), str(data),
                                  "--expect-sha256", model._sha(raw)], capture_output=True)
        self.assertEqual(process.returncode, 1)
        self.assertEqual(json.loads(process.stdout), result)
        self.assertEqual(data.read_bytes(), model._canonical(votes))
