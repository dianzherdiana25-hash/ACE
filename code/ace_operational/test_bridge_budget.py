"""Jaga agar pembacaan saldo governor tersedia tanpa menghabiskan jatah."""
import importlib
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest import mock

from ace_operational import brain_bridge as bridge
from ace_operational import brain_bridge_relay as relay
from ace_operational import brain_endpoints as endpoints


DAY = "2026-01-18"
BRIDGE = "http://127.0.0.1:18931"


class BudgetEndpointTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        self.state = root / "bridge_state.json"
        self.log = root / "bridge_calls.jsonl"
        for patcher in (
                mock.patch.object(bridge, "STATE", self.state),
                mock.patch.object(bridge, "LOG", self.log),
                mock.patch.object(bridge, "_today", return_value=DAY)):
            patcher.start()
            self.addCleanup(patcher.stop)

    def get(self, path="/v1/budget"):
        handler = bridge.Handler.__new__(bridge.Handler)
        handler.path = path
        handler._send = mock.Mock()
        handler.do_GET()
        handler._send.assert_called_once()
        return handler._send.call_args.args

    def seed(self, day=DAY, counts=None):
        self.state.write_text(json.dumps({"day": day, "counts": counts or {},
                                          "private_fixture": "noise"}),
                              encoding="utf-8")
        return self.state.read_bytes()

    def test_current_state_and_config_are_the_only_budget_sources(self):
        counts = {"front": 3, "judge": bridge.BUDGETS["judge"] + 1,
                  "unregistered": 7}
        snapshot = self.seed(counts=counts)
        with mock.patch.object(bridge, "_budget_check") as charge:
            status, body = self.get()
            charge.assert_not_called()
        self.assertEqual(status, 200)
        self.assertEqual(body, {"initialized": True, "roles": {
            role: {"daily_budget": limit, "used_today": counts.get(role, 0),
                   "remaining": max(0, limit - counts.get(role, 0))}
            for role, limit in bridge.BUDGETS.items()
        }})
        self.assertEqual(self.state.read_bytes(), snapshot)
        self.assertFalse(self.log.exists())

    def test_missing_state_is_explicit_and_has_no_write(self):
        status, body = self.get()
        self.assertEqual(status, 200)
        self.assertIs(body["initialized"], False)
        for role, limit in bridge.BUDGETS.items():
            self.assertEqual(body["roles"][role], {
                "daily_budget": limit, "used_today": 0, "remaining": limit})
        self.assertFalse(self.state.exists())
        self.assertFalse(self.log.exists())

    def test_yesterday_counters_are_not_used_or_reset_on_disk(self):
        snapshot = self.seed(day="2026-01-17", counts={"front": 10})
        status, body = self.get()
        self.assertEqual(status, 200)
        self.assertIs(body["initialized"], False)
        self.assertEqual(body["roles"]["front"]["used_today"], 0)
        self.assertEqual(self.state.read_bytes(), snapshot)

    def test_corrupted_state_reports_unavailable_without_exposing_contents(self):
        for data in (b"bad-fixture-state", b"null", b"[]",
                     b'{"day":"2026-01-18","counts":{"front":true}}',
                     b'{"day":"2026-01-18","counts":[]}'):
            with self.subTest(data=data):
                self.state.write_bytes(data)
                status, body = self.get()
                self.assertEqual(status, 503)
                self.assertEqual(body, {"error": {
                    "message": "bridge budget state unavailable",
                    "type": "budget_state_unavailable"}})
                self.assertEqual(self.state.read_bytes(), data)

    def test_post_budget_is_never_counted(self):
        for handler_class in (bridge.Handler, relay.Handler):
            with self.subTest(handler=handler_class):
                handler = handler_class.__new__(handler_class)
                handler.path = "/v1/budget"
                handler._send = mock.Mock()
                with mock.patch.object(bridge, "_budget_check") as charge, \
                        mock.patch.object(relay, "spool_fetch") as fetch:
                    handler.do_POST()
                handler._send.assert_called_once_with(405, {"error": "method not allowed"})
                charge.assert_not_called()
                fetch.assert_not_called()

    def test_relay_forwards_to_same_snapshot_before_budget_accounting(self):
        self.seed(counts={"coder": 5})
        # The pump creates its spool directory on import. Keep the fixture local.
        with mock.patch("os.makedirs"):
            pump = importlib.import_module("ace_operational.brain_bridge_pump")

        def spool_fetch(payload):
            status, body = pump.execute(payload["path"], payload["request"])
            return {"status": status, "body": body}

        handler = relay.Handler.__new__(relay.Handler)
        handler.path = "/v1/budget"
        handler._send = mock.Mock()
        with mock.patch.object(pump, "bridge", bridge), \
                mock.patch.object(bridge, "_budget_check") as charge, \
                mock.patch.object(bridge, "serve_chat") as chat, \
                mock.patch.object(relay, "spool_fetch", side_effect=spool_fetch) as fetch:
            handler.do_GET()
        fetch.assert_called_once_with({"path": "/v1/budget", "request": {}})
        charge.assert_not_called()
        chat.assert_not_called()
        handler._send.assert_called_once_with(*self.get())


class BudgetClientTests(unittest.TestCase):
    def test_bridge_uses_get_and_requested_timeout(self):
        result = {"initialized": True, "roles": {
            "coder": {"daily_budget": 200, "used_today": 5, "remaining": 195}}}
        with mock.patch.dict(os.environ, {endpoints.BRIDGE_ENV_VAR: BRIDGE + "/"}), \
                mock.patch.object(endpoints, "_request", return_value=result) as request:
            self.assertEqual(endpoints.bridge_budget(timeout=3.0), result)
        request.assert_called_once_with(BRIDGE + "/v1/budget", None, 3.0)

    def test_local_mode_returns_none_without_transport(self):
        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch.object(endpoints, "_request") as request:
            self.assertIsNone(endpoints.bridge_budget())
        request.assert_not_called()

    def test_transport_failure_remains_brain_unavailable(self):
        with mock.patch.dict(os.environ, {endpoints.BRIDGE_ENV_VAR: BRIDGE}), \
                mock.patch.object(endpoints, "_request",
                                  side_effect=endpoints.BrainUnavailable("offline")):
            with self.assertRaisesRegex(endpoints.BrainUnavailable, "offline"):
                endpoints.bridge_budget()

    def test_non_object_response_fails_closed(self):
        with mock.patch.dict(os.environ, {endpoints.BRIDGE_ENV_VAR: BRIDGE}), \
                mock.patch.object(endpoints, "_request", return_value=[]):
            with self.assertRaises(endpoints.BrainUnavailable):
                endpoints.bridge_budget()


if __name__ == "__main__":
    unittest.main()
