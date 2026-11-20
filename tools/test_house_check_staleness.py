"""Uji usia status engine dengan jam fixture tetap."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools.house_check import inspect_house


NOW = datetime(2026, 11, 20, tzinfo=timezone.utc)


class HouseStalenessTests(unittest.TestCase):
    def setUp(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        self.pump, self.engine = root / "pump.pid", root / "engine.json"
        self.pump.write_text("123", encoding="utf-8")

    def check(self, age, *, running=True, timestamp=None):
        data = {"running": running, "pid": 42, "cycle_count": 7,
                "updated_at": timestamp if timestamp is not None else (NOW - timedelta(seconds=age)).isoformat()}
        self.engine.write_text(json.dumps(data), encoding="utf-8")
        return inspect_house("fixture", self.pump, self.engine, health_probe=lambda *_: True,
                             pid_probe=lambda _: True, max_age_seconds=60, now=NOW)

    def test_before_at_and_after_age_threshold(self):
        for age, state, code in ((59, "healthy", 0), (60, "healthy", 0), (61, "stale", 1)):
            with self.subTest(age=age):
                result = self.check(age)
                self.assertEqual(result["components"]["engine"]["state"], state)
                self.assertEqual(result["components"]["engine"]["age_seconds"], age)
                self.assertEqual(result["exit_code"], code)

    def test_stopped_precedes_stale(self):
        result = self.check(600, running=False)
        self.assertEqual(result["components"]["engine"]["state"], "stopped")
        self.assertEqual(result["exit_code"], 1)

    def test_malformed_future_or_naive_status_unavailable(self):
        for stamp in ("bad", "2026-11-19T23:59:59", "2026-11-20T00:00:01Z"):
            with self.subTest(stamp=stamp):
                self.assertEqual(self.check(0, timestamp=stamp)["components"]["engine"]["state"],
                                 "unavailable")


if __name__ == "__main__":
    unittest.main()
