"""Tes pemeriksa mandiri bridge + engine + status JSON rusak & rencana relight teks (AG37)."""
from __future__ import annotations

from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory
import threading
import unittest
from unittest.mock import patch

from tools.bridge_self_check import SCHEMA, self_check


SCRIPT = Path(__file__).with_name("bridge_self_check.py")


class _HealthyHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        self.send_response(200 if self.path == "/health" else 404)
        self.end_headers()
        self.wfile.write(b'{"ok": true}')


def _closed_url() -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    return f"http://127.0.0.1:{port}"


class BridgeSelfCheckTests(unittest.TestCase):
    def test_classifies_three_states_and_corrupt_json_with_injected_clock_and_no_execution(self) -> None:
        now = datetime(2026, 11, 20, 12, 0, 0, tzinfo=timezone.utc)
        with TemporaryDirectory() as tmp:
            status_file = Path(tmp) / "engine_status.json"
            healthy_payload = {
                "pid": 101,
                "cycle_count": 12,
                "running": True,
                "updated_at": "2026-11-20T11:57:00+00:00",  # usia 180s <= 300s
            }
            stale_payload = {
                **healthy_payload,
                "updated_at": "2026-11-20T11:50:00+00:00",  # usia 600s > 300s
            }

            with patch("subprocess.run") as sp_run:
                # 1. Sehat
                status_file.write_text(json.dumps(healthy_payload), encoding="utf-8")
                res_ok = self_check(
                    "http://127.0.0.1:8931",
                    status_file,
                    max_age_seconds=300,
                    now=now,
                    health_probe=lambda *_: True,
                )
                self.assertEqual(res_ok["schema"], SCHEMA)
                self.assertEqual(res_ok["classification"], "sehat")
                self.assertFalse(res_ok["needs_relight"])
                self.assertFalse(res_ok["executed_relight"])
                self.assertIn("NO-OP", res_ok["relight_plan"])

                # 2. Bridge mati
                res_dead = self_check(
                    "http://127.0.0.1:8931",
                    status_file,
                    max_age_seconds=300,
                    now=now,
                    health_probe=lambda *_: False,
                )
                self.assertEqual(res_dead["classification"], "bridge-mati")
                self.assertTrue(res_dead["needs_relight"])
                self.assertFalse(res_dead["executed_relight"])
                self.assertIn("brain_bridge.py", res_dead["relight_plan"])

                # 3. Engine stale
                status_file.write_text(json.dumps(stale_payload), encoding="utf-8")
                res_stale = self_check(
                    "http://127.0.0.1:8931",
                    status_file,
                    max_age_seconds=300,
                    now=now,
                    health_probe=lambda *_: True,
                )
                self.assertEqual(res_stale["classification"], "engine-stale")
                self.assertEqual(res_stale["engine_detail"]["age_seconds"], 600.0)
                self.assertTrue(res_stale["needs_relight"])
                self.assertIn("ENGINE STALE", res_stale["relight_plan"])

                # 4. Status JSON rusak
                status_file.write_text("{corrupt json", encoding="utf-8")
                res_corrupt = self_check(
                    "http://127.0.0.1:8931",
                    status_file,
                    max_age_seconds=300,
                    now=now,
                    health_probe=lambda *_: True,
                )
                self.assertEqual(res_corrupt["classification"], "status-rusak")
                self.assertEqual(res_corrupt["engine_detail"]["reason"], "invalid_json_or_missing")
                self.assertTrue(res_corrupt["needs_relight"])
                self.assertIn("STATUS ENGINE RUSAK", res_corrupt["relight_plan"])
                sp_run.assert_not_called()

    def test_cli_loopback_healthy_and_closed_port_plan_text(self) -> None:
        with TemporaryDirectory() as tmp:
            status_file = Path(tmp) / "engine_status.json"
            status_file.write_text(
                json.dumps({"pid": 1, "cycle_count": 5, "running": True}),
                encoding="utf-8",
            )
            with ThreadingHTTPServer(("127.0.0.1", 0), _HealthyHandler) as srv:
                t = threading.Thread(target=srv.serve_forever, daemon=True)
                t.start()
                try:
                    ok = subprocess.run(
                        [
                            sys.executable, str(SCRIPT),
                            "--bridge-url", f"http://127.0.0.1:{srv.server_port}",
                            "--engine-status", str(status_file),
                        ],
                        capture_output=True, text=True, check=False,
                    )
                    self.assertEqual(ok.returncode, 0, ok.stderr)
                    self.assertEqual(json.loads(ok.stdout)["classification"], "sehat")
                finally:
                    srv.shutdown()
                    t.join()

            dead_plan = subprocess.run(
                [
                    sys.executable, str(SCRIPT),
                    "--bridge-url", _closed_url(),
                    "--engine-status", str(status_file),
                    "--format", "plan",
                ],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(dead_plan.returncode, 2)
            self.assertIn("RENCANA RELIGHT BRIDGE", dead_plan.stdout)


if __name__ == "__main__":
    unittest.main()
