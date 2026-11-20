"""Latih urutan cutover dan rollback tanpa menjalankan perintah rencana."""
from contextlib import ExitStack
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import unittest
from urllib.parse import urlsplit

from tools.bridge_home import BUNDLE_MANIFEST_SCHEMA, REQUIRED_ENTRY_NAMES, plan_home
from tools.test_bridge_home import CONFIG


class HealthHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        self.server.requests.append(self.path)
        healthy = self.server.healthy and self.path == "/health"
        self.send_response(200 if healthy else 503)
        self.end_headers()
        self.wfile.write(json.dumps({"ok": healthy}).encode())


class CutoverE2ETests(unittest.TestCase):
    def setUp(self):
        self.stack = self.enterContext(ExitStack())
        root = Path(self.stack.enter_context(TemporaryDirectory()))
        self.manifest = root / "manifest.json"
        self.manifest.write_text(json.dumps({"schema": BUNDLE_MANIFEST_SCHEMA,
                                             "entries": [{"name": n} for n in REQUIRED_ENTRY_NAMES]}))
        self.config = {**CONFIG, "pid_file": str(root / "fresh.pid")}
        self.requests = []

    def server(self, healthy, requests):
        server = self.stack.enter_context(ThreadingHTTPServer(("127.0.0.1", 0), HealthHandler))
        server.healthy, server.requests = healthy, requests
        return server

    def start(self, server):
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.stack.callback(thread.join)
        self.stack.callback(server.shutdown)

    def health(self, url):
        parts = urlsplit(url)
        self.assertEqual((parts.scheme, parts.hostname), ("http", "127.0.0.1"))
        self.requests.append(parts.netloc)
        conn = HTTPConnection("127.0.0.1", parts.port, timeout=2)
        try:
            conn.request("GET", "/health")
            response = conn.getresponse()
            body = json.load(response)
            return response.status == 200 and body["ok"] is True
        finally:
            conn.close()

    def run_scenario(self, new_healthy):
        old_paths, new_paths = [], []
        old, new = self.server(True, old_paths), self.server(new_healthy, new_paths)
        self.start(old)
        previous = f"http://127.0.0.1:{old.server_port}"
        plan = plan_home({**self.config, "current_bridge_url": previous, "port": new.server_port},
                         bundle_manifest=self.manifest)
        state = {"target": previous}
        visited = []
        for step in plan["steps"]:
            kind = step["id"]
            visited.append(kind)
            if kind == "preflight":
                self.assertTrue(plan["preflight"]["safe_to_continue"])
                self.assertTrue(self.health(previous))
            elif kind == "launch":
                self.assertIn("--port " + str(new.server_port), step["action"])
                self.start(new)
            elif kind == "health":
                if not self.health(plan["target_bridge_url"]):
                    self.assertTrue(self.health(previous))
                    return plan, visited, state, old_paths, new_paths
            elif kind == "cutover":
                state["target"] = plan["target_bridge_url"]
            else:
                self.fail(f"Langkah fixture tidak dikenal {kind}")
        return plan, visited, state, old_paths, new_paths

    def test_health_pass_allows_simulated_cutover(self):
        plan, visited, state, old, new = self.run_scenario(True)
        self.assertEqual(visited, ["preflight", "launch", "health", "cutover"])
        self.assertEqual(state["target"], plan["target_bridge_url"])
        self.assertEqual((old, new), (["/health"], ["/health"]))

    def test_health_failure_stops_and_preserves_rollback(self):
        plan, visited, state, old, new = self.run_scenario(False)
        self.assertEqual(visited, ["preflight", "launch", "health"])
        self.assertEqual(state["target"], plan["current_bridge_url"])
        self.assertIn(plan["current_bridge_url"], plan["rollback"][0])
        self.assertEqual((old, new), (["/health", "/health"], ["/health"]))
