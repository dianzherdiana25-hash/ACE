"""Uji urutan laporan watchdog saat beberapa komponen gagal sekaligus."""
from contextlib import redirect_stdout
from datetime import datetime, timezone
from functools import partial
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from tools import house_check


class HouseFailureMatrixTests(unittest.TestCase):
    def test_cli_localizes_each_failure_alone_and_in_pairs(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        pid, engine = root / "pump.pid", root / "status.json"
        pid.write_text("42", encoding="utf-8")
        active = {"pid": 4, "cycle_count": 3, "running": True, "updated_at": "2026-11-20T10:00:00Z"}
        fixtures = {
            "healthy": json.dumps(active),
            "stopped": json.dumps({**active, "running": False}),
            "stale": json.dumps({**active, "updated_at": "2026-11-20T09:54:59Z"}),
            "unavailable": "{malformed",
        }
        now = datetime(2026, 11, 20, 10, tzinfo=timezone.utc)
        cases = [
            (True, True, "healthy", 0, None),
            (False, True, "healthy", 2, "bridge"),
            (True, False, "healthy", 1, "pump"),
            (False, False, "healthy", 2, "bridge"),
        ]
        for state in ("stopped", "stale", "unavailable"):
            cases.extend([(True, True, state, 1, "engine"),
                          (False, True, state, 2, "bridge"),
                          (True, False, state, 1, "pump")])
        inspect = house_check.inspect_house
        for bridge_ok, pump_ok, engine_state, code, first_failure in cases:
            with self.subTest(bridge=bridge_ok, pump=pump_ok, engine=engine_state):
                engine.write_text(fixtures[engine_state], encoding="utf-8")
                probe_fixture = partial(inspect, health_probe=lambda *_: bridge_ok,
                                        pid_probe=lambda _: pump_ok, now=now)
                with patch.object(house_check, "inspect_house", probe_fixture), redirect_stdout(StringIO()) as output:
                    result = house_check.main(["--bridge-url", "fixture", "--pump-pid-file", str(pid),
                                               "--engine-status", str(engine)])
                report = json.loads(output.getvalue())
                self.assertEqual(result, code)
                self.assertEqual(report["exit_code"], code)
                self.assertEqual(report["summary"], ("healthy", "degraded", "dead")[code])
                components = report["components"]
                expected = {"bridge": "healthy" if bridge_ok else "unavailable",
                            "pump": "healthy" if pump_ok else "missing", "engine": engine_state}
                self.assertEqual(list(components), list(expected))
                self.assertEqual({name: item["state"] for name, item in components.items()}, expected)
                self.assertEqual(next((name for name, item in components.items()
                                       if item["state"] != "healthy"), None), first_failure)
