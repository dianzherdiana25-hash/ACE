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

    def test_malformed_checkpoint_matrix_never_a_ambiguous_b_and_c_wins(self):
        ambiguous_cases = [
            ("task_none", None, "B"),
            ("task_not_mapping", ["not", "a", "dict"], "B"),
            ("checkpoint_missing", {"kind": "director_proposal"}, "B"),
            ("checkpoint_none", {"kind": "director_proposal", "checkpoint": None}, "B"),
            ("checkpoint_string", {"kind": "director_proposal", "checkpoint": "invalid"}, "B"),
            ("checkpoint_list", {"kind": "director_proposal", "checkpoint": ["receipt-1"]}, "B"),
            ("missing_kind", {"checkpoint": proposal()["checkpoint"]}, "B"),
            ("missing_based_on", {"kind": "director_proposal", "checkpoint": {
                k: v for k, v in proposal()["checkpoint"].items() if k != "based_on"
            }}, "B"),
            ("missing_evidence_refs", {"kind": "director_proposal", "checkpoint": {
                k: v for k, v in proposal()["checkpoint"].items() if k != "evidence_refs"
            }}, "B"),
            ("empty_evidence_refs", proposal(evidence_refs=[]), "B"),
            ("missing_reversible", {"kind": "director_proposal", "checkpoint": {
                k: v for k, v in proposal()["checkpoint"].items() if k != "reversible"
            }}, "B"),
            ("missing_touches_money", {"kind": "director_proposal", "checkpoint": {
                k: v for k, v in proposal()["checkpoint"].items() if k != "touches_money"
            }}, "B"),
            ("missing_touches_publication", {"kind": "director_proposal", "checkpoint": {
                k: v for k, v in proposal()["checkpoint"].items() if k != "touches_publication"
            }}, "B"),
            ("missing_touches_external", {"kind": "director_proposal", "checkpoint": {
                k: v for k, v in proposal()["checkpoint"].items() if k != "touches_external"
            }}, "B"),
            ("reversible_string_true", proposal(reversible="true"), "B"),
            ("reversible_string_false", proposal(reversible="false"), "B"),
            ("evidence_refs_string", proposal(evidence_refs="receipt-1"), "B"),
            ("based_on_string", proposal(based_on="gap-1"), "B"),
            ("touches_money_string", proposal(touches_money="false"), "B"),
        ]
        for label, payload, expected_class in ambiguous_cases:
            with self.subTest(case=label):
                result = classify_proposal(payload)
                self.assertNotEqual(result["class"], "A")
                self.assertEqual(result["class"], expected_class)

        # Bukti kosong vs hilang sama-sama memicu alasan evidence_refs_missing -> kelas B
        missing_ev = classify_proposal({"kind": "director_proposal", "checkpoint": {
            k: v for k, v in proposal()["checkpoint"].items() if k != "evidence_refs"
        }})
        empty_ev = classify_proposal(proposal(evidence_refs=[]))
        self.assertEqual(missing_ev["class"], "B")
        self.assertEqual(empty_ev["class"], "B")
        self.assertIn("evidence_refs_missing", missing_ev["reasons"])
        self.assertIn("evidence_refs_missing", empty_ev["reasons"])

        # Menyentuh uang/publikasi/eksternal -> C berapa pun bentuk cacat field lainnya
        c_flags = ("touches_money", "touches_publication", "touches_external")
        malformed_shapes = [
            {},
            {"based_on": "bukan-list", "evidence_refs": "bukan-list", "reversible": "yes"},
            {"based_on": [], "evidence_refs": [], "reversible": None},
            {"proposal": "bukan-mapping"},
        ]
        for flag in c_flags:
            for idx, shape in enumerate(malformed_shapes):
                for kind in ("director_proposal", "unknown", None):
                    with self.subTest(flag=flag, shape_idx=idx, kind=kind):
                        task_obj = {"kind": kind, "checkpoint": {**shape, flag: True}}
                        res = classify_proposal(task_obj)
                        self.assertEqual(res["class"], "C")
                        self.assertIn(flag, res["reasons"])


if __name__ == "__main__":
    unittest.main()
