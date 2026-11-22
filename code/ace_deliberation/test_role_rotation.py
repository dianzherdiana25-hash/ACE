"""Uji rotasi yang lengkap, minimum, dan dapat dipakai sebagai rencana debat."""
from contextlib import redirect_stdout
from io import StringIO
from itertools import permutations
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_deliberation import debate_protocol, role_rotation


def fixture():
    return {"roster": [{"participant": name, "eligible_roles": list(role_rotation.ROLES)}
                       for name in ("c", "a", "b")],
            "seats": dict.fromkeys(role_rotation.ROLES, 1), "rounds": 3, "history": [],
            "repeat_penalty": 10}


class RotationTests(unittest.TestCase):
    def test_three_unrestricted_members_get_every_role_once(self):
        raw = fixture()
        result = role_rotation.rotate(raw)
        self.assertEqual(result["status"], "scheduled")
        self.assertEqual(result["role_counts_after"], dict.fromkeys(("a", "b", "c"), raw["seats"]))
        self.assertTrue(all(not row["repeated"] and row["cost"] == 0 for row in result["schedule"]))
        for index, row in enumerate(result["schedule"], 1):
            plan = debate_protocol.DebatePlan.from_dict({
                "debate_id": f"round-{index}", "question": "Periksa metode",
                "seats": row["seats"], "rounds": 1, "budget": 5,
            })
            self.assertEqual(plan.seats[0].role, "proponent")
            self.assertEqual(plan.seats[-1].role, "reviewer")

    def test_constrained_roster_requires_assignment_beyond_local_greedy(self):
        raw = fixture()
        raw["roster"] = [
            {"participant": "a", "eligible_roles": ["challenger", "proponent"]},
            {"participant": "b", "eligible_roles": ["challenger"]},
            {"participant": "c", "eligible_roles": ["reviewer"]},
        ]
        result = role_rotation.rotate(raw)
        self.assertEqual(result["schedule"][0]["seats"], [
            {"participant": "a", "role": "proponent"},
            {"participant": "b", "role": "challenger"},
            {"participant": "c", "role": "reviewer"},
        ])
        self.assertEqual(result["schedule"][1]["repeated"], ["a", "b", "c"])
        self.assertEqual(result["schedule"][1]["cost"], 33)

    def test_first_rotation_matches_exhaustive_optimum_and_tie_break(self):
        raw = fixture()
        history = [{"source_ref": f"fixture/{index}", "assignments": assignments}
                   for index, assignments in enumerate((
                       {"a": "proponent", "b": "challenger", "c": "reviewer"},
                       {"a": "reviewer", "b": "proponent", "c": "challenger"},
                   ))]
        raw["history"] = history
        result = role_rotation.rotate(raw)
        members = ("a", "b", "c")
        possible = []
        for roles in permutations(role_rotation.ROLES):
            cost = sum(row["assignments"][name] == role for row in history
                       for name, role in zip(members, roles))
            cost += raw["repeat_penalty"] * sum(history[-1]["assignments"][name] == role
                                               for name, role in zip(members, roles))
            possible.append((cost, roles))
        expected_cost, expected_roles = min(possible)
        first = result["schedule"][0]
        assignments = {row["participant"]: row["role"] for row in first["seats"]}
        self.assertEqual((first["cost"], tuple(assignments[name] for name in members)),
                         (expected_cost, expected_roles))
        self.assertEqual(result["history_refs"], ["fixture/0", "fixture/1"])

    def test_infeasible_plan_produces_no_partial_round_and_cli_failure(self):
        raw = fixture()
        for member in raw["roster"]:
            member["eligible_roles"] = ["reviewer"]
        path = Path(self.enterContext(TemporaryDirectory())) / "rotation.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(role_rotation.main([str(path)]), 1)
        result = json.loads(output.getvalue())
        self.assertEqual((result["status"], result["blocked_round"], result["schedule"]), ("infeasible", 1, []))

    def test_reordering_catalog_has_no_effect(self):
        raw = fixture()
        expected = role_rotation.rotate(raw)
        raw["roster"].reverse()
        for member in raw["roster"]:
            member["eligible_roles"].reverse()
        self.assertEqual(role_rotation.rotate(raw), expected)

    def test_rejects_duplicate_history_refs_or_invalid_seat_totals(self):
        raw = fixture()
        row = {"source_ref": "fixture/old", "assignments": {"a": "reviewer"}}
        for updates in ({"history": [row, row]}, {"rounds": False},
                        {"seats": {"proponent": 2, "reviewer": 2, "challenger": 1}}):
            with self.subTest(updates=updates), self.assertRaises(role_rotation.RotationError):
                role_rotation.rotate({**raw, **updates})

    def test_sample_of_eligibility_patterns_agrees_with_independent_enumeration(self):
        from itertools import product

        raw = fixture()
        members = sorted(row["participant"] for row in raw["roster"])
        raw["rounds"] = 1
        eligibility = [
            ("challenger", "reviewer"), ("proponent", "reviewer"),
            ("proponent",), role_rotation.ROLES, ("reviewer",),
        ]
        for pattern in product(eligibility, repeat=3):
            with self.subTest(pattern=pattern):
                allowed = dict(zip(members, pattern))
                raw["roster"] = [{"participant": name, "eligible_roles": list(allowed[name])}
                                 for name in members]
                choices = [path for path in permutations(role_rotation.ROLES)
                           if all(role in allowed[name] for name, role in zip(members, path))]
                result = role_rotation.rotate(raw)
                if not choices:
                    self.assertEqual(result["status"], "infeasible")
                    continue
                seats = {row["participant"]: row["role"] for row in result["schedule"][0]["seats"]}
                self.assertEqual(tuple(seats[name] for name in members), min(choices))

    def test_recent_partial_attendance_does_not_award_a_repeat_penalty_to_an_absent_member(self):
        raw = fixture()
        raw["history"] = [{"source_ref": "fixture/recent", "assignments": {"a": "proponent"}}]
        first = role_rotation.rotate(raw)["schedule"][0]
        self.assertEqual(first["repeated"], [])
        self.assertEqual(first["cost"], 0)

    def test_history_counts_include_recent_change_in_eligibility(self):
        raw = fixture()
        raw["roster"][0]["eligible_roles"] = ["reviewer"]
        raw["history"] = [{"source_ref": "fixture/old", "assignments": {"c": "proponent"}}]
        result = role_rotation.rotate(raw)
        self.assertEqual(result["role_counts_after"]["c"], {"challenger": 0, "proponent": 1, "reviewer": 3})
