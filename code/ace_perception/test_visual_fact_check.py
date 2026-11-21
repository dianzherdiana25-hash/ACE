"""Verifier dukungan independen dan bukti bertentangan."""
import unittest

from ace_perception import visual_fact_check as model


def run(rows):
    plan = {"schema": "ace.perception-visual-claims.v1", "plan_ref": "fixture/plan", "minimum_sources": 2,
            "claims": [{"id": "one", "value": 17, "claim_ref": "fixture/claim"}]}
    data = {"schema": "ace.perception-visual-evidence.v1", "observations": rows}
    return model.check(model._canonical(plan), model._canonical(data), model._sha(plan))["claims"][0]


def source(author, media, ref, value=17):
    return {"value": value, "origin_group": author, "media_sha256": media*64,
            "receipt_ref": "fixture/source/"+ref, "claim_id": "one"}


class FactCheckTests(unittest.TestCase):
    def test_distinct_media_and_authorship_are_both_needed(self):
        one = source("a", "1", "one")
        two = source("b", "1", "two")
        self.assertEqual(run([one, two])["independent_support"], 1)
        alt = source("a", "2", "three")
        suite = run([one, two, alt])
        self.assertEqual(suite["status"], "supported")
        self.assertEqual(suite["independent_support"], 2)
        self.assertEqual([row["receipt_ref"] for row in suite["selected_sources"]],
                         ["fixture/source/three", "fixture/source/two"])

    def test_conflict_outweighs_two_matching_independent_receipts(self):
        report = run([source("a", "1", "one"), source("b", "2", "two"), source("c", "3", "three", 0)])
        self.assertEqual(report["status"], "conflicting")
        self.assertEqual(report["independent_support"], 2)
        self.assertEqual(report["counterevidence"][0]["receipt_ref"], "fixture/source/three")
        self.assertEqual(run([])["status"], "insufficient")
