"""Verifier ranking aging, deadline kumulatif dan budget per kelas."""
import unittest

from ace_perception import perception_priority as model


def job(key, n, *, priority=1, mins=0, **changes):
    fields = {"id": key, "class": "ocr", "source_ref": f"fixture/{key}", "media_sha256": f"{n}"*64,
              "config_sha256": "a"*64, "created_at": f"2026-11-21T00:{mins:02d}:00Z",
              "deadline": None, "priority": priority, "estimated_ms": 1000, "estimated_bytes": 100}
    return {**fields, **changes}


def run(rows, **settings):
    payload = {"schema": "ace.perception-priority.v1", "plan_ref": "fixture/plan", "as_of": "2026-11-21T00:30:00Z",
               "age_minutes_per_point": 10, "budget_ms": 2000, "budget_bytes": 200,
               "maximum_jobs": 3, "class_caps": {"ocr": 1, "scene": 2}, "jobs": rows, **settings}
    return model.schedule(model._canonical(payload), model._sha(payload))


class PriorityTests(unittest.TestCase):
    def test_rank_duplicate_and_aging_keep_each_reason(self):
        rows = [job("small", 1, priority=2, mins=20), job("aged", 0), job("repeat", 0, mins=29),
                job("space", 2, **{"class": "scene"}), job("future", 3, mins=35, priority=999)]
        result = run(rows)
        self.assertEqual([row["id"] for row in result["schedule"]], ["future", "aged", "space", "small", "repeat"])
        status = {row["id"]: row for row in result["schedule"]}
        self.assertEqual(status["future"]["reasons"], ["not_arrived"])
        self.assertEqual(status["aged"]["status"], "scheduled")
        self.assertEqual(status["repeat"]["duplicate_of"], "aged")
        self.assertEqual(status["small"]["reasons"], ["class_cap", "time_budget", "byte_budget"])
        self.assertEqual(result["remaining"], {"bytes": 0, "milliseconds": 0,
                                              "slots": 1, "by_class": {"ocr": 0, "scene": 1}})

    def test_deadline_checks_queued_execution_before_scheduling(self):
        rows = [job("regular", 0, priority=10), job("exact", 1, deadline="2026-11-21T00:30:01.999999Z")]
        product = run(rows, class_caps={"ocr": 2})
        self.assertEqual(product["schedule"][1]["reasons"], ["deadline_unreachable"])
        rows[1]["deadline"] = "2026-11-21T00:30:02Z"
        self.assertEqual(run(rows, class_caps={"ocr": 2})["schedule"][1]["status"], "scheduled")
