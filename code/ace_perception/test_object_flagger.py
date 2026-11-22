"""Verifier pembatas regio dan confidence atas receipt objek yang dirujuk."""
from hashlib import sha256
import unittest

from ace_perception import _vision, object_flagger as model


ASSET = _vision.encode(8, 8, bytearray([212]*64))


def plan():
    return {"schema": "ace.perception-object-policy.v1", "image_sha256": sha256(ASSET).hexdigest(),
            "regions": [{"id": key, "box": [x, x, x+2, x+2]} for x, key in enumerate(("a", "b", "c", "d"))],
            "rules": [{"id": "fixture-policy", "label": "blocked-fixture", "regions": ["a", "b"],
                       "confidence_min_bp": 8000, "source_ref": "fixture/rule"}]}


def vote(region, score, label="blocked-fixture", **changes):
    return {"region": region, "receipt_ref": f"fixture/observed/{region}", "label": label, "confidence_bp": score, **changes}


def report(rows):
    limits = plan()
    receipts = {"schema": "ace.perception-object-observations.v1", "image_sha256": sha256(ASSET).hexdigest(),
                "observations": rows}
    return model.flag(ASSET, model._canonical(limits), model._canonical(receipts), model._sha(limits))


class ObjectFlagTests(unittest.TestCase):
    def test_flags_limit_exact_threshold_and_does_not_assume_coverage(self):
        output = report([vote("a", 8000), vote("b", 7999), vote("c", 9999)])
        self.assertEqual(output["status"], "flagged")
        self.assertEqual(output["flags"], [{"region": "a", "rule": "fixture-policy", "rule_ref": "fixture/rule",
                                           "receipt_ref": "fixture/observed/a"}])
        self.assertEqual([row["status"] for row in output["regions"]],
                         ["flagged", "low_confidence", "no_rule_hit", "missing"])

    def test_abstain_makes_status_incomplete_while_other_observations_retained(self):
        output = report([vote("a", None, None), vote("b", 5000, "other")])
        self.assertEqual(output["status"], "incomplete")
        self.assertEqual(output["regions"][0]["status"], "abstained")
        self.assertEqual(output["flags"], [])
        clear = report([vote(key, 5000, "other") for key in "abcd"])
        self.assertEqual(clear["status"], "no_rule_hit")

    def test_reject_duplicates_and_inconsistent_abstention(self):
        for entries in ([vote("a", 1000)]*2, [vote("a", 1000, None)], [vote("z", 9000)]):
            with self.subTest(entries=entries), self.assertRaises(ValueError):
                report(entries)
