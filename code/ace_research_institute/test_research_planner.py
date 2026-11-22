import unittest

from ._contracts import ResearchError, identity
from .research_planner import build_plan


def fixture():
    base = {"question": "Bagaimana pengukuran cahaya?", "method": "measurement",
            "specification": {"outcome": "lux", "population": "meja uji", "comparator": "tanpa lampu", "minimum_n": 6},
            "evidence": ["Tabel sampel"], "falsifier": "Delta proyeksi di bawah nol",
            "after": [], "person_hours": 2, "priority": 10, "covers": ["cahaya"]}
    return {"schema": "ace.institute.research-plan.v1", "question": "Apakah cahaya berubah?",
            "focus": ["cahaya", "warna"], "max_hours": 3, "exclusions": ["Eksperimen baru"],
            "tasks": [base | {"id": "a"}, base | {"id": "b", "person_hours": 4, "after": ["a"]},
                      base | {"id": "c", "after": ["b"], "covers": ["warna"], "priority": 100}]}


class PlanningTests(unittest.TestCase):
    def test_custody_falsifier_dependencies_and_hours(self):
        plan = fixture()
        report = build_plan(plan, identity(plan))
        self.assertEqual(report["schedule"][0]["artefact"], "measurement_table")
        self.assertEqual(report["allocated_hours"], 2)
        self.assertEqual(report["schedule"][0]["falsifier"], "Delta proyeksi di bawah nol")
        self.assertEqual(report["uncovered_focus"], ["warna"])
        self.assertEqual([r["reason"] for r in report["unplanned"]], ["hours_exhausted", "prerequisite_unplanned"])
        plan["tasks"][0]["after"] = ["c"]
        with self.assertRaisesRegex(ResearchError, "siklus"):
            build_plan(plan, identity(plan))
