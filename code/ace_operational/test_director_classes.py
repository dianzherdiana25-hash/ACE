"""Jaga batas bukti dan efek samping klasifikasi director."""
import unittest

from ace_operational.director_classes import classify_proposal


def proposal(**changes):
    return {"kind": "director_proposal", "checkpoint": {
        "based_on": ["gap-1"], "evidence_refs": ["receipt-1"],
        "reversible": True, "touches_money": False, "touches_publication": False,
        "touches_external": False, **changes,
    }}


class DirectorClassTests(unittest.TestCase):
    def test_explicit_local_reversible_proposal(self):
        self.assertEqual(classify_proposal(proposal())["class"], "A")

    def test_incomplete_and_ambiguous_are_b(self):
        for changes in ({"evidence_refs": []}, {"based_on": []}, {"reversible": 1},
                        {"touches_external": None}, {"based_on": [" "]}):
            with self.subTest(changes=changes):
                self.assertEqual(classify_proposal(proposal(**changes))["class"], "B")
        self.assertEqual(classify_proposal({"kind": "unknown"})["class"], "B")

    def test_class_c_overrides_complete_evidence(self):
        for key, value in [("touches_external", True), ("touches_money", True),
                           ("touches_publication", True), ("reversible", False)]:
            with self.subTest(key=key):
                self.assertEqual(classify_proposal(proposal(**{key: value}))["class"], "C")
        self.assertEqual(classify_proposal(proposal(touches_money=True, based_on=[]))["reasons"],
                         ["touches_money", "based_on_missing"])

    def test_rule_table_and_legacy_based_on(self):
        task = proposal(proposal={"based_on": ["gap"]})
        del task["checkpoint"]["based_on"]
        self.assertEqual(classify_proposal(task)["class"], "A")
        rules = [{"class": "B", "when": {"has_evidence": True}, "reason": "operator_review"}]
        self.assertEqual(classify_proposal(task, rules=rules),
                         {"class": "B", "reasons": ["operator_review"]})


if __name__ == "__main__":
    unittest.main()
