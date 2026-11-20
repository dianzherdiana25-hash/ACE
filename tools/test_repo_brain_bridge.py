"""Kontrak byte JSON bridge pada proses fixture dan restart governor."""
from contextlib import contextmanager
import json
from pathlib import Path
import select
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen


TOOLS = Path(__file__).resolve().parent


@contextmanager
def service(name, *args):
    with subprocess.Popen([sys.executable, str(TOOLS / f"{name}.py"), "--port", "0", *map(str, args)],
                          stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True) as child:
        try:
            if not select.select([child.stdout], [], [], 5)[0]:
                raise AssertionError("Fixture tidak mendengarkan dalam lima detik.")
            listening = child.stdout.readline().strip()
            port = int(listening.rsplit(":", 1)[-1])
            yield f"http://127.0.0.1:{port}"
        finally:
            child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()


def request(base, path, payload=None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = Request(base + path, data=data, headers={"Content-Type": "application/json"})
    try:
        response = urlopen(req, timeout=5)
    except HTTPError as exc:
        response = exc
    with response:
        return response.code, json.load(response)


class RepoBrainBridgeTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(TemporaryDirectory()))
        self.state = self.root / "state.json"
        self.log = self.root / "calls.jsonl"
        self.budgets = self.root / "budgets.json"
        self.budgets.write_text(json.dumps(dict.fromkeys(
            ("front", "coder", "validator", "embedding", "judge"), 1
        )))
        for provider, response in (("groq", {"content": "fixture"}), ("gemini", {"values": [1, 2]})):
            helper = self.root / "helpers" / f"custom.{provider}" / "bin" / f"{provider}_call.py"
            helper.parent.mkdir(parents=True)
            helper.write_text(f"print({json.dumps(response)!r})\n", encoding="utf-8")
        self.args = ("--state", self.state, "--log", self.log, "--helpers", self.root / "helpers",
                     "--budgets", self.budgets)

    def test_chat_embed_and_budget_survive_restart(self):
        payload = {"role": "front", "messages": [{"role": "user", "content": "uji"}]}
        with service("brain_bridge", *self.args) as url:
            status, health = request(url, "/health")
            self.assertEqual((status, health["ok"], health["budgets"]["front"]), (200, True, 1))
            status, reply = request(url, "/v1/chat/completions", payload)
            self.assertEqual(status, 200)
            self.assertEqual(reply["choices"][0]["message"]["content"], "fixture")
            _, embedding = request(url, "/v1/embeddings", {"role": "embedding", "input": "uji"})
            self.assertEqual(embedding["data"][0]["embedding"], [1, 2])
            _, budget = request(url, "/v1/budget")
            self.assertEqual(budget["roles"]["front"]["remaining"], 0)
        with service("brain_bridge", *self.args) as url:
            status, refused = request(url, "/v1/chat/completions", payload)
            self.assertEqual((status, refused["error"]["type"]), (429, "budget_exhausted"))
        self.assertEqual([json.loads(row)["result"] for row in self.log.read_text().splitlines()],
                         ["ok", "ok", "over_budget"])

    def test_relay_configured_loopback_health(self):
        with service("bridge_relay", "--spool", self.root / "spool", "--timeout", 1) as url:
            status, health = request(url, "/health")
            self.assertEqual((status, health["ok"], health["side"]), (200, True, "sandbox-relay"))


if __name__ == "__main__":
    unittest.main()
