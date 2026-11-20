"""Uji peran, pembulatan, penarikan diri dan provenance kuorum."""
from contextlib import redirect_stdout
from copy import deepcopy
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_deliberation import quorum_engine as quorum


def fixture():
    return {
        "problem_class": "policy",
        "policies": {
            "policy": {"minimum": 2, "fraction": {"numerator": 2, "denominator": 3},
                       "roles": {"reviewer": 1}, "denominator": "roster"},
            "routine": {"minimum": 1, "fraction": {"numerator": 0, "denominator": 1},
                        "roles": {}, "denominator": "roster"},
        },
        "roster": [{"id": name, "role": role, "classes": classes}
                   for name, role, classes in (("a", "author", ["policy"]),
                                               ("b", "reviewer", ["policy", "routine"]),
                                               ("c", "author", ["policy"]),
                                               ("d", "author", ["policy"]),
                                               ("outside", "reviewer", ["routine"]))],
        "attendance": [{"id": name, "status": status, "source_ref": f"fixture/attendance/{name}"}
                       for name, status in (("a", "present"), ("b", "present"), ("c", "recused"),
                                            ("outside", "present"))],
    }


class QuorumTests(unittest.TestCase):
    def test_fraction_rounds_up_and_ineligible_attendance_does_not_vote(self):
        report = quorum.check_quorum(fixture())
        self.assertFalse(report["quorum_met"])
        self.assertEqual(report["threshold"], {"minimum": 2, "fractional": 3, "required": 3})
        self.assertEqual((report["present_count"], report["shortage"]), (2, 1))
        self.assertEqual(report["ineligible"], ["outside"])
        self.assertEqual(report["eligible_without_attendance"], ["d"])
        self.assertEqual(report["by_status"]["recused"], ["c"])

    def test_recusal_changes_denominator_only_when_policy_allows(self):
        raw = fixture()
        raw["policies"]["policy"]["denominator"] = "non_recused"
        report = quorum.check_quorum(raw)
        self.assertTrue(report["quorum_met"])
        self.assertEqual(report["denominator"], {"policy": "non_recused", "count": 3})
        self.assertEqual(report["threshold"]["required"], 2)

    def test_role_requirement_blocks_even_with_enough_attendees(self):
        raw = fixture()
        raw["policies"]["policy"]["minimum"] = 1
        raw["policies"]["policy"]["fraction"]["numerator"] = 0
        raw["attendance"][1]["status"] = "absent"
        report = quorum.check_quorum(raw)
        self.assertEqual(report["shortage"], 0)
        self.assertFalse(report["quorum_met"])
        self.assertEqual(report["role_requirements"],
                         [{"role": "reviewer", "required": 1, "present": 0, "met": False}])

    def test_problem_class_uses_its_own_policy_and_eligibility(self):
        report = quorum.check_quorum({**fixture(), "problem_class": "routine"})
        self.assertTrue(report["quorum_met"])
        self.assertEqual(report["by_status"]["present"], ["b", "outside"])
        self.assertEqual(report["threshold"]["required"], 1)

    def test_rejects_undefined_class_duplicate_presence_and_loose_integers(self):
        raw = fixture()
        invalid = [{**raw, "problem_class": "critical"},
                   {**raw, "attendance": [*raw["attendance"], raw["attendance"][0]]}]
        changed = deepcopy(raw)
        changed["policies"]["policy"]["minimum"] = True
        invalid.append(changed)
        changed = deepcopy(raw)
        changed["attendance"][0]["source_ref"] = changed["attendance"][1]["source_ref"]
        invalid.append(changed)
        for payload in invalid:
            with self.subTest(payload=payload), self.assertRaises(quorum.QuorumError):
                quorum.check_quorum(payload)

    def test_reorder_and_cli_preserve_full_attendance_evidence(self):
        raw = fixture()
        expected = quorum.check_quorum(raw)
        raw["attendance"].reverse()
        raw["roster"].reverse()
        self.assertEqual(expected, quorum.check_quorum(raw))
        path = Path(self.enterContext(TemporaryDirectory())) / "quorum.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(quorum.main([str(path)]), 1)
        self.assertEqual(json.loads(output.getvalue()), expected)

    def test_non_recused_policy_still_requires_minimum_when_everyone_conflicted(self):
        raw = fixture()
        raw["policies"]["policy"]["denominator"] = "non_recused"
        raw["attendance"] = [
            {"id": row["id"], "status": "recused", "source_ref": f"fixture/recusal/{row['id']}"}
            for row in raw["roster"] if "policy" in row["classes"]
        ]
        report = quorum.check_quorum(raw)
        self.assertEqual(report["denominator"]["count"], 0)
        self.assertEqual(report["threshold"]["required"], 2)
        self.assertEqual(report["present_count"], 0)
        self.assertFalse(report["quorum_met"])

    def test_missing_attendance_is_visible_and_never_inferred_as_absent(self):
        raw = fixture()
        raw["attendance"] = []
        report = quorum.check_quorum(raw)
        self.assertEqual(report["eligible_without_attendance"], ["a", "b", "c", "d"])
        self.assertEqual(report["by_status"]["absent"], [])
        self.assertEqual(report["attendance_evidence"], [])

    def test_unknown_attendee_cannot_inflate_count(self):
        raw = fixture()
        raw["attendance"].append({"id": "stray", "status": "present", "source_ref": "fixture/stray"})
        with self.assertRaisesRegex(quorum.QuorumError, "tidak terdaftar"):
            quorum.check_quorum(raw)
