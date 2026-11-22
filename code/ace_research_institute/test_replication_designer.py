import unittest

from ._contracts import identity
from .replication_designer import plan_replication


class ReplicationPlanTests(unittest.TestCase):
    def test_budgeted_alternatives_select_fastest_feasible_only(self):
        plan = {"schema": "ace.institute.replication-design-plan.v1", "hypothesis": "Kedua laju berbeda?",
                "assumptions": {"baseline_rate": "0.20", "replication_rate": "0.45", "alpha": "0.05",
                                "desired_power": "0.80", "source_ref": "fixture:prior"},
                "limits": {"max_minutes": 220, "max_units": 200, "max_watt_seconds": 15000},
                "design_options": [{"id": key, "setup_minutes": 4, "minutes_per_unit": minutes,
                                    "watt_seconds_per_unit": power, "capacity_units": 200,
                                    "procedure_ref": f"fixture:{key}"} for key, minutes, power in (
                                        ("slow", 2, 20), ("high", 1, 200), ("efficient", 1, 20))]}
        result = plan_replication(plan, identity(plan))
        self.assertEqual(result["units_per_arm"], 54)
        self.assertEqual(result["selected_option"], "efficient")
        self.assertEqual(result["options"][-1]["blocked_by"], ["energy"])
        plan["limits"]["max_units"] = 50
        self.assertEqual(plan_replication(plan, identity(plan))["status"], "no_feasible_design")
