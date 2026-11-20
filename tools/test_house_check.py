"""Jalankan watchdog pada HTTP loopback dan berkas status fixture."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import unittest

from tools.house_check import inspect_house


class HealthHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        self.send_response(200 if self.path == "/health" else 404)
        self.end_headers()
        self.wfile.write(b'{"ok":true}')


class HouseCheckTests(unittest.TestCase):
    def setUp(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        self.pid = root / "pump.pid"
        self.engine = root / "status.json"
        self.pid.write_text(str(os.getpid()))
        self.status(True)

    def status(self, running):
        self.engine.write_text(json.dumps({"pid": 1, "cycle_count": 7, "running": running}))

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


if __name__ == "__main__":
    unittest.main()
