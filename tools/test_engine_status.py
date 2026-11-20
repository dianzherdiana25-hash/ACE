"""Tes parser status engine bersama (AG6) dan kesamaan keluaran house_check/bridge_home."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools import bridge_home, engine_status, house_check


class SharedEngineStatusParserTest(unittest.TestCase):
    def test_shared_parser_matches_house_check_and_bridge_home_outputs(self) -> None:
        now = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)
        active = {"pid": 7, "cycle_count": 12, "running": True, "updated_at": now.isoformat()}
        cases = {
            "healthy_recent": (json.dumps(active), "healthy", True),
            "boundary_exact": (
                json.dumps({**active, "updated_at": "2026-11-20T11:55:00+00:00"}),
                "healthy",
                True,
            ),
            "stale": (
                json.dumps({**active, "updated_at": "2026-11-20T11:54:59+00:00"}),
                "stale",
                False,
            ),
            "stopped_even_old": (
                json.dumps({**active, "running": False, "updated_at": "2026-01-01T00:00:00Z"}),
                "stopped",
                False,
            ),
            "legacy_no_updated_at": (
                json.dumps({"pid": 7, "cycle_count": 3, "running": True}),
                "healthy",
                True,
            ),
            "future_updated_at": (
                json.dumps({**active, "updated_at": "2026-11-20T12:05:00+00:00"}),
                "unavailable",
                False,
            ),
            "corrupt_json": ("{broken", "unavailable", False),
        }

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            status_file = root / "engine.json"
            pump_pid = root / "pump.pid"
            pump_pid.write_text("42", encoding="utf-8")

            for name, (content, expected_state, expected_safe) in cases.items():
                status_file.write_text(content, encoding="utf-8")
                parsed = engine_status.parse_engine_status(status_file, now=now)
                hc = house_check.inspect_house(
                    "http://127.0.0.1:9999",
                    pump_pid,
                    status_file,
                    health_probe=lambda *_: True,
                    pid_probe=lambda _: True,
                    now=now,
                )
                bh = bridge_home._check_engine_status(status_file, max_age_seconds=300, now=now)

                self.assertEqual(parsed["state"], expected_state, msg=name)
                self.assertEqual(parsed["safe_to_continue"], expected_safe, msg=name)
                self.assertEqual(hc["components"]["engine"]["state"], expected_state, msg=name)
                self.assertEqual(hc["exit_code"] == 0, expected_safe, msg=name)
                self.assertEqual(bh["state"], expected_state, msg=name)
                self.assertEqual(bh["safe_to_continue"], expected_safe, msg=name)


if __name__ == "__main__":
    unittest.main()
