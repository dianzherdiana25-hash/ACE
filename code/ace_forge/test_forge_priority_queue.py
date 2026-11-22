"""Verifier replay antrean, waktu keputusan dan admit dengan kapasitas terbatas."""
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from ace_forge import forge_priority_queue as model
from ace_forge._forge_io import canonical, identity


NOW = "2026-11-21T01:00:00Z"


def job(key, priority, ram=2, units=1, **changes):
    raw = {"id": key, "recipe_ref": f"test/recipe/{key}", "priority": priority,
           "enqueued_at": "2026-11-21T00:30:00Z", "deadline": None,
           "duration_minutes": 30, "ram_mib": ram, "units": units, "depends_on": []}
    return {**raw, **changes}


def receipt(key, at=NOW):
    return {"id": key, "completed_at": at, "receipt_ref": f"fixture/receipt/{key}"}


def fixture():
    return {"queue_ref": "fixture/queue", "as_of": NOW, "policy": {"aging_minutes": 30},
            "capacity": {"ram_mib": 7, "units": 4, "slots": 2},
            "completed": [receipt("prep")],
            "jobs": [
                job("prep", 30),
                job("heavy", 20, ram=8),
                job("new", 5, enqueued_at=NOW, depends_on=["prep"]),
                job("old", 4, ram=3, units=2, enqueued_at="2026-11-20T23:30:00Z"),
                job("waits", 50, depends_on=["old", "missing"]),
                job("late", 55, deadline="2026-11-21T01:29:59Z"),
                job("future", 75, enqueued_at="2026-11-21T01:00:01Z"),
                job("small", 0),
            ]}


def schedule(raw):
    return model.schedule(raw, identity(raw))


def rows(report):
    return {row["id"]: row for row in report["jobs"]}


class PriorityQueueTests(unittest.TestCase):
    def test_skip_unschedulable_high_priority_and_preserve_capacity(self):
        result = schedule(fixture())
        self.assertEqual(result["admitted"], ["old", "new"])
        self.assertEqual(result["remaining"], {"ram_mib": 2, "units": 1, "slots": 0})
        queue = rows(result)
        self.assertEqual(queue["old"]["effective_priority"], 7)
        self.assertEqual(queue["new"]["effective_priority"], 5)
        self.assertEqual(queue["prep"]["completed_ref"], "fixture/receipt/prep")
        self.assertEqual(queue["heavy"]["reasons"], ["insufficient_ram_mib"])
        self.assertEqual(queue["small"]["reasons"], ["insufficient_slots"])

    def test_wait_on_terminal_receipt_even_if_parent_is_admitted(self):
        result = rows(schedule(fixture()))
        waiting = result["waits"]
        self.assertEqual(waiting["reasons"], ["unknown_dependency", "waiting_dependency"])
        self.assertEqual(waiting["unknown_dependencies"], ["missing"])
        self.assertEqual(waiting["waiting_dependencies"], ["old"])

    def test_future_arrival_and_deadline_at_second_precision(self):
        raw = fixture()
        raw["jobs"][-1].update(priority=100, deadline="2026-11-21T08:30:00+07:00")
        result = schedule(raw)
        self.assertEqual(result["admitted"][0], "small")
        queue = rows(result)
        self.assertEqual(queue["late"]["reasons"], ["deadline_unreachable"])
        self.assertEqual(queue["future"]["reasons"], ["not_arrived"])

    def test_total_order_prefers_deadline_then_arrival_then_id(self):
        raw = fixture()
        raw["capacity"] = {"ram_mib": 100, "slots": 100, "units": 100}
        raw["completed"] = []
        raw["jobs"] = [job("c", 2), job("a", 2), job("b", 2, enqueued_at="2026-11-21T00:00:01Z"),
                       job("z", 2, deadline="2026-11-21T01:45:00Z"),
                       job("y", 2, deadline="2026-11-21T01:40:00Z")]
        self.assertEqual(schedule(raw)["admitted"], ["y", "z", "b", "a", "c"])
        raw["jobs"].reverse()
        self.assertEqual(schedule(raw)["admitted"], ["y", "z", "b", "a", "c"])

    def test_reject_cycles_including_self_dependency(self):
        for jobs in ([job("a", 1, depends_on=["a"])],
                     [job("a", 1, depends_on=["b"]), job("b", 1, depends_on=["a"])]):
            raw = {**fixture(), "jobs": jobs, "completed": []}
            with self.subTest(jobs=jobs), self.assertRaisesRegex(model.InputError, "Siklus"):
                schedule(raw)

    def test_completion_receipt_must_precede_each_completed_dependent(self):
        raw = fixture()
        raw["completed"] = [receipt("new"), receipt("prep")]
        self.assertEqual(rows(schedule(raw))["new"]["status"], "completed")
        for completion in ([receipt("new")], [receipt("unknown")],
                           [receipt("prep"), receipt("prep")],
                           [receipt("prep", "2026-11-21T01:00:01Z")]):
            with self.subTest(completion=completion), self.assertRaises(model.InputError):
                schedule({**raw, "completed": completion})

    def test_anchor_and_numeric_types(self):
        raw = fixture()
        anchor = identity(raw)
        raw["capacity"]["slots"] = True
        with self.assertRaisesRegex(model.InputError, "anchor"):
            model.schedule(raw, anchor)
        with self.assertRaises(model.InputError):
            schedule(raw)

    def test_empty_queue_leaves_resources_intact(self):
        raw = {**fixture(), "jobs": [], "completed": []}
        result = schedule(raw)
        self.assertEqual(result["remaining"], raw["capacity"])
        self.assertEqual(result["admitted"], [])

    def test_cli_matches_canonical_replay_and_preserves_source(self):
        raw = fixture()
        path = Path(self.enterContext(TemporaryDirectory())) / "queue.json"
        path.write_bytes(canonical(raw))
        command = [sys.executable, "-m", "ace_forge.forge_priority_queue", str(path), "--expect-sha256", identity(raw)]
        process = subprocess.run(command, capture_output=True, check=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        self.assertEqual(json.loads(process.stdout), schedule(raw))
        self.assertEqual(process.stdout, canonical(schedule(raw)) + b"\n")
        self.assertEqual(path.read_bytes(), canonical(raw))
