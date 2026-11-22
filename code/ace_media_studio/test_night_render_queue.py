from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import canonical, identity
from .night_render_queue import queue, run_selected
from .render_recipe import freeze_recipe
from .test_render_recipe import geometry


class NightQueueTests(unittest.TestCase):
    def test_budget_holds_even_with_spare_time_and_replay_proves_bytes(self):
        image = geometry()
        expected, recipe = freeze_recipe("geometry_png", image, identity(image))
        raw = canonical(recipe)
        ref = {"path": "recipe.json", "sha256": sha256(raw).hexdigest()}

        def job(key, priority, seconds, watts):
            return {"id": key, "recipe": ref, "priority": priority, "seconds": seconds, "watts": watts}

        plan = {"schema": "ace.media.night-queue.v1", "from_utc": "2025-05-01T22:00:00Z",
                "to_utc": "2025-05-02T01:00:00Z", "max_watts": 90, "max_watt_seconds": 450,
                "jobs": [job("first", 4, 4, 85), job("big", 3, 1, 100), job("last", 2, 4, 30)]}
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "recipe.json").write_bytes(raw)
            now = "2025-05-01T23:00:00Z"
            files, report = run_selected(plan, identity(plan), now, root, clock=lambda: 2)
            self.assertEqual(files, {"first.png": expected})
            self.assertEqual(report["estimated_watt_seconds"], 340)
            self.assertEqual([row["reason"] for row in report["skipped"]], ["peak_budget", "energy_budget"])
            self.assertEqual(report["receipts"][0]["status"], "rendered")
            self.assertEqual(queue(plan, identity(plan), plan["to_utc"])["selected"], [])
            readings = iter((0, 7200))
            files, report = run_selected(plan, identity(plan), now, root, clock=lambda: next(readings))
            self.assertEqual(files, {})
            self.assertEqual(report["receipts"], [{"id": "first", "status": "window_elapsed"}])
