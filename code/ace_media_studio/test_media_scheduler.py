import unittest

from ._contracts import ContractError, identity
from .media_scheduler import schedule


def task(key, duration, end, ram, after=(), priority=10):
    return {"id": key, "duration": duration, "release": 0, "deadline": end,
            "ram_mib": ram, "slots": 1, "after": list(after), "priority": priority}


class ScheduleTests(unittest.TestCase):
    def test_dependencies_and_ram_are_applied_at_each_minute(self):
        plan = {"schema": "ace.media.schedule-plan.v1", "horizon_minutes": 120, "windows": [
                    {"id": "first", "start": 10, "end": 40, "slots": 2, "ram_mib": 125},
                    {"id": "second", "start": 60, "end": 90, "slots": 1, "ram_mib": 220}],
                "tasks": [task("publish_draft", 10, 80, 100, ("mix_audio", "draft_video")),
                          task("draft_video", 20, 40, 90), task("mix_audio", 20, 90, 60),
                          task("poster", 10, 35, 30), task("too_big", 5, 90, 250),
                          task("blocked", 2, 120, 20, ("too_big",))]}
        result = schedule(plan, identity(plan))
        self.assertEqual({r["id"]: (r["start"], r["end"]) for r in result["placements"]},
                         {"draft_video": (10, 30), "poster": (10, 20), "mix_audio": (60, 80)})
        self.assertEqual({r["id"]: r["reason"] for r in result["unplaced"]},
                         {"blocked": "dependency_not_scheduled", "too_big": "no_slot_in_greedy_plan",
                          "publish_draft": "no_slot_in_greedy_plan"})
        plan["tasks"][1]["after"] = ["publish_draft"]
        with self.assertRaisesRegex(ContractError, "putaran"):
            schedule(plan, identity(plan))
