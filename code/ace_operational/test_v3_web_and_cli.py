"""Tests for Command Center v3 REST Endpoints (WEB25 auth-gated), `ace_mcp.cli` v3 subcommands, and orchestrator daemon."""
from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from ace_mcp.cli import main as cli_main
from ace_operational.store import OperationalStore
from ace_operational.web_server import ACEWebServer
import tools.ace_autonomous_daemon as daemon_mod


def _http_json(url: str, *, method: str = "GET", payload: dict | None = None, token: str | None = None) -> tuple[int, dict]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"} if payload is not None else {}
    if token:
        headers["X-ACE-Token"] = token
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=10) as resp:
            return int(resp.status), json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        raw = exc.read().decode("utf-8")
        return int(exc.code), json.loads(raw) if raw.strip() else {}


class V3WebAndCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="ace-v3-web-cli-")
        self.ws = Path(self._tmp.name) / "ws"
        self.store = OperationalStore(self.ws)
        self.server = ACEWebServer(self.store, host="127.0.0.1", port=0)
        self.url = self.server.start_background()
        self.addCleanup(self.server.stop)
        self.tok = self.server.auth_token

    def tearDown(self) -> None:
        self.store.close()
        self._tmp.cleanup()

    def _run_cli(self, argv: list[str]) -> tuple[int, dict]:
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = cli_main(argv)
        return rc, json.loads(buf.getvalue())

    def test_v3_web_endpoints_enforce_token_gate_and_work_e2e(self) -> None:
        # Unauthenticated calls MUST return 401
        for ep in ("/api/goals", "/api/agents", "/api/connectors/status", "/api/calibration"):
            st, _ = _http_json(f"{self.url}{ep}")
            self.assertEqual(st, 401, ep)
        st, _ = _http_json(f"{self.url}/api/goals", method="POST", payload={"title": "x", "user_request": "y"})
        self.assertEqual(st, 401)

        # Authenticated flow
        st, reg = _http_json(
            f"{self.url}/api/agents/register",
            method="POST",
            payload={"agent_id": "antigravity-local", "vendor": "antigravity", "roles": ["brain", "coder"]},
            token=self.tok,
        )
        self.assertEqual(st, 200)
        self.assertEqual(reg["agent_id"], "antigravity-local")

        st, goal = _http_json(
            f"{self.url}/api/goals",
            method="POST",
            payload={"title": "Goal Uji Web", "user_request": "Buat aplikasi sederhana", "domain": "general"},
            token=self.tok,
        )
        self.assertEqual(st, 200)
        gid = goal["goal_id"]

        st, rel = _http_json(
            f"{self.url}/api/relay/export",
            method="POST",
            payload={"vendor": "chatgpt", "work_order_id": goal["stages"][0]["work_order_id"]},
            token=self.tok,
        )
        self.assertEqual(st, 200)
        self.assertIn("ChatGPT Web", rel["prompt"])

        st, conn = _http_json(f"{self.url}/api/connectors/status", token=self.tok)
        self.assertEqual(st, 200)
        self.assertIn("facebook", conn["vault"]["venues"])
        self.assertIn("kbm", conn["vault"]["venues"])

        st, tick = _http_json(f"{self.url}/api/goals/{gid}/tick", method="POST", payload={}, token=self.tok)
        self.assertEqual(st, 200)
        self.assertEqual(tick["action"], "awaiting_agent_submission")

    def test_cli_v3_subcommands_and_daemon_orchestrator_cycle(self) -> None:
        ws_arg = str(self.ws)
        rc, out = self._run_cli(["--workspace", ws_arg, "setup", "--vendor", "all"])
        self.assertEqual(rc, 0)
        self.assertIn("antigravity", out["vendors"])
        self.assertIn("muse.ai", out["vendors"])

        rc, goal = self._run_cli([
            "--workspace", ws_arg, "--read-write", "goal", "create",
            "--title", "CLI Goal", "--request", "Uji orkestrasi CLI", "--domain", "research",
        ])
        self.assertEqual(rc, 0)
        gid = goal["goal_id"]

        rc, gl = self._run_cli(["--workspace", ws_arg, "goal", "list"])
        self.assertEqual(rc, 0)
        self.assertTrue(any(g["goal_id"] == gid for g in gl["goals"]))

        rc, ori = self._run_cli(["--workspace", ws_arg, "agent", "orient", "--agent-id", "antigravity-ide"])
        self.assertEqual(rc, 0)
        self.assertEqual(ori["schema"], "ace.directive_packet.v1")

        rc, vstat = self._run_cli(["--workspace", ws_arg, "vault", "status"])
        self.assertEqual(rc, 0)
        self.assertIn("facebook", vstat["venues"])

        d_res = daemon_mod.run_orchestrator_cycle(workspace=self.ws)
        self.assertGreaterEqual(d_res["goals_checked"], 1)


if __name__ == "__main__":
    unittest.main()
