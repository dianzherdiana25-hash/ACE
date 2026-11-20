"""Rekam batas kontrak status engine di antara watchdog dan rencana cutover."""
from datetime import datetime, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools import bridge_home, house_check
from tools.test_bridge_home import CONFIG


class HouseStateAgreementTests(unittest.TestCase):
    def matrix(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        state, pump, bundle = (root / name for name in ("engine.json", "pump.pid", "markers.json"))
        pump.write_text("42", encoding="utf-8")
        bundle.write_text(json.dumps({
            "schema": bridge_home.BUNDLE_MANIFEST_SCHEMA,
            "entries": [{"name": name} for name in bridge_home.REQUIRED_ENTRY_NAMES],
        }), encoding="utf-8")
        config = {**CONFIG, "pid_file": str(root / "missing-bridge.pid"), "engine_status_file": str(state)}
        now = datetime(2026, 11, 20, 10, tzinfo=timezone.utc)
        active = {"pid": 4, "cycle_count": 3, "running": True, "updated_at": now.isoformat()}
        cases = {
            "fresh": json.dumps(active),
            "stale": json.dumps({**active, "updated_at": "2026-11-20T09:54:59Z"}),
            "stopped": json.dumps({**active, "running": False}),
            "invalid": "{malformed",
        }
        observations = {}
        for name, data in cases.items():
            state.write_text(data, encoding="utf-8")
            status = house_check.inspect_house("fixture", pump, state, health_probe=lambda *_: True,
                                               pid_probe=lambda _: True, now=now)
            plan = bridge_home.plan_home(config, bundle_manifest=bundle)
            observations[name] = {
                "house_engine": status["components"]["engine"]["state"],
                "house_safe": status["exit_code"] == 0,
                "bridge_preflight_safe": plan["preflight"]["safe_to_continue"],
                "bridge_status_safe": plan["preflight"].get("engine_status", {}).get("safe_to_continue"),
                "path_referenced": str(state) in json.dumps(plan),
            }
        return observations

    def test_matrix_observes_current_contract_and_fresh_preflight_agreement(self):
        observed = self.matrix()
        print(json.dumps({"house_agreement_matrix": observed}, sort_keys=True))
        self.assertEqual(observed, {
            name: {"house_engine": state, "house_safe": safe, "bridge_preflight_safe": True,
                   "bridge_status_safe": None, "path_referenced": False}
            for name, state, safe in (
                ("fresh", "healthy", True), ("stale", "stale", False),
                ("stopped", "stopped", False), ("invalid", "unavailable", False),
            )
        })
        self.assertEqual(observed["fresh"]["house_safe"], observed["fresh"]["bridge_preflight_safe"])

    @unittest.expectedFailure
    def test_status_gate_agreement_is_blocked_until_cutover_references_status_file(self):
        # plan_home currently checks PID and bundle markers. It only mentions
        # engine status in prose after cutover, so it cannot make this decision.
        actual = {name: (row["path_referenced"], row["bridge_status_safe"])
                  for name, row in self.matrix().items()}
        self.assertEqual(actual, {"fresh": (True, True), "stale": (True, False),
                                  "stopped": (True, False), "invalid": (True, False)})
