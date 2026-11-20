"""Jalankan watchdog pada HTTP loopback dan berkas status fixture."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory
import threading
import unittest

from tools.house_check import inspect_house


SCRIPT = Path(__file__).with_name("house_check.py")


class HealthHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        self.send_response(200 if self.path == "/health" else 404)
        self.end_headers()
        self.wfile.write(b'{"ok":true}')


def _closed_loopback_url() -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    return f"http://127.0.0.1:{port}"


class HouseCheckTests(unittest.TestCase):
    def setUp(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        self.pid = root / "pump.pid"
        self.engine = root / "status.json"
        self.pid.write_text(str(os.getpid()))
        self.status(True)

    def status(self, running, **extra):
        self.engine.write_text(json.dumps({"pid": 1, "cycle_count": 7, "running": running, **extra}))

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *map(str, args)],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_healthy_loopback(self):
        with ThreadingHTTPServer(("127.0.0.1", 0), HealthHandler) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                result = inspect_house(f"http://127.0.0.1:{server.server_port}", self.pid, self.engine)
            finally:
                server.shutdown()
                thread.join()
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["components"]["engine"]["cycle_count"], 7)

    def test_bridge_dead(self):
        result = inspect_house("fixture", self.pid, self.engine, health_probe=lambda *_: False)
        self.assertEqual(result["exit_code"], 2)
        self.assertEqual(result["components"]["bridge"]["state"], "unavailable")
        self.assertEqual(result["components"]["pump"]["state"], "healthy")

    def test_stopped_engine(self):
        self.status(False)
        result = inspect_house("fixture", self.pid, self.engine, health_probe=lambda *_: True)
        self.assertEqual(result["exit_code"], 1)
        self.assertEqual(result["components"]["engine"]["state"], "stopped")

    def test_cli_exit_0_1_and_2_on_loopback_and_closed_port(self):
        with ThreadingHTTPServer(("127.0.0.1", 0), HealthHandler) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            url = f"http://127.0.0.1:{server.server_port}"
            try:
                healthy = self.run_cli(
                    "--bridge-url", url,
                    "--pump-pid-file", self.pid,
                    "--engine-status", self.engine,
                )
                self.assertEqual(healthy.returncode, 0, healthy.stderr)
                parsed_0 = json.loads(healthy.stdout)
                self.assertEqual((parsed_0["exit_code"], parsed_0["summary"]), (0, "healthy"))

                self.status(False)
                degraded = self.run_cli(
                    "--bridge-url", url,
                    "--pump-pid-file", self.pid,
                    "--engine-status", self.engine,
                )
                self.assertEqual(degraded.returncode, 1, degraded.stderr)
                parsed_1 = json.loads(degraded.stdout)
                self.assertEqual((parsed_1["exit_code"], parsed_1["summary"]), (1, "degraded"))
            finally:
                server.shutdown()
                thread.join()

        self.status(True)
        dead = self.run_cli(
            "--bridge-url", _closed_loopback_url(),
            "--pump-pid-file", self.pid,
            "--engine-status", self.engine,
        )
        self.assertEqual(dead.returncode, 2)
        parsed_2 = json.loads(dead.stdout)
        self.assertEqual((parsed_2["exit_code"], parsed_2["summary"]), (2, "dead"))
        self.assertEqual(parsed_2["components"]["bridge"]["state"], "unavailable")

    def test_cli_invalid_argv_combinations_do_not_leak_status_file_contents(self):
        canary = "CANARY_SECRET_STATUS_PAYLOAD_99481"
        self.engine.write_text(json.dumps({
            "pid": 1, "cycle_count": 7, "running": True, "private_note": canary
        }), encoding="utf-8")
        invalid_argvs = [
            (),
            ("--bridge-url", "http://127.0.0.1:9"),
            ("--bridge-url", "http://127.0.0.1:9", "--pump-pid-file", self.pid),
            (
                "--bridge-url", "http://127.0.0.1:9",
                "--pump-pid-file", self.pid,
                "--engine-status", self.engine,
                "--max-age-seconds", "-5",
            ),
            (
                "--bridge-url", "http://127.0.0.1:9",
                "--pump-pid-file", self.pid,
                "--engine-status", self.engine,
                "--max-age-seconds", "bukan-angka",
            ),
            (
                "--bridge-url", "http://127.0.0.1:9",
                "--pump-pid-file", self.pid,
                "--engine-status", self.engine,
                "--flag-asing",
            ),
        ]
        for argv in invalid_argvs:
            with self.subTest(argv=argv):
                proc = self.run_cli(*argv)
                self.assertEqual(proc.returncode, 2)
                self.assertEqual(proc.stdout, "")
                self.assertNotIn(canary, proc.stdout)
                self.assertNotIn(canary, proc.stderr)


if __name__ == "__main__":
    unittest.main()
