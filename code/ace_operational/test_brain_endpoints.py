"""Tests for brain_endpoints: routing, parsing, fail-closed wrapper."""

import json
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest import mock

from ace_operational import brain_endpoints as be


class RoutingTests(unittest.TestCase):
    def test_pair_crossed_by_kind(self):
        code = be.proposer_validator_pair("code")
        self.assertEqual((code.proposer, code.validator), ("coder", "front"))
        lang = be.proposer_validator_pair("language")
        self.assertEqual((lang.proposer, lang.validator), ("front", "coder"))

    def test_pair_always_heterogeneous(self):
        for kind in be.TASK_KINDS:
            pair = be.proposer_validator_pair(kind)
            self.assertNotEqual(pair.proposer, pair.validator)

    def test_pair_rejects_unknown_kind(self):
        with self.assertRaises(ValueError):
            be.proposer_validator_pair("music")

    def test_pair_provenance_dict(self):
        d = be.proposer_validator_pair("code").as_dict()
        self.assertEqual(d["proposer_url"], be.DEFAULT_URLS["coder"])
        self.assertEqual(d["validator_url"], be.DEFAULT_URLS["front"])

    def test_role_urls(self):
        self.assertEqual(be.role_url("chat"), be.DEFAULT_URLS["front"])
        self.assertEqual(be.role_url("embedding"), be.DEFAULT_URLS["embedding"])
        self.assertEqual(be.role_url("recall"), be.DEFAULT_URLS["embedding"])
        self.assertEqual(be.role_url("deep"), be.DEFAULT_URLS["a3b"])
        self.assertEqual(be.role_url("proposer", "code"),
                         be.DEFAULT_URLS["coder"])
        self.assertEqual(be.role_url("validator", "code"),
                         be.DEFAULT_URLS["front"])
        with self.assertRaises(ValueError):
            be.role_url("oracle")

    def test_env_override(self):
        with mock.patch.dict(os.environ,
                             {"ACE_BRAIN_FRONT_URL": "http://127.0.0.1:9999/"}):
            self.assertEqual(be.organ_url("front"), "http://127.0.0.1:9999")
        with self.assertRaises(ValueError):
            be.organ_url("spleen")


class ParseTests(unittest.TestCase):
    def test_content_and_reasoning_kept_separate(self):
        payload = {
            "choices": [{"message": {"content": "Jawaban.",
                                     "reasoning_content": "berpikir..."}}],
            "timings": {"prompt_per_second": 4.0,
                        "predicted_per_second": 1.5, "predicted_n": 42},
        }
        r = be.parse_chat_response(payload)
        self.assertEqual(r.content, "Jawaban.")
        self.assertEqual(r.reasoning, "berpikir...")
        self.assertEqual(r.predicted_tokens, 42)

    def test_missing_channels_become_empty(self):
        payload = {"choices": [{"message": {"content": None}}]}
        r = be.parse_chat_response(payload)
        self.assertEqual(r.content, "")
        self.assertEqual(r.reasoning, "")
        self.assertIsNone(r.predicted_per_second)


class _StubHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # silence
        pass

    def do_GET(self):
        if self.path == "/health":
            body = b'{"status": "ok"}'
            self.send_response(200)
        else:
            body = b"{}"
            self.send_response(404)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)
        if self.path == "/v1/chat/completions":
            payload = {"choices": [{"message": {
                "content": "halo", "reasoning_content": "hm"}}],
                "timings": {"predicted_per_second": 2.0, "predicted_n": 4}}
        elif self.path == "/embedding":
            # Real llama-server shape: embedding is a list of vectors.
            payload = [{"embedding": [[0.1, 0.2, 0.3]]}]
        else:
            self.send_response(404)
            self.end_headers()
            return
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class WrapperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), _StubHandler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever,
                                      daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def _env(self):
        return mock.patch.dict(os.environ, {
            "ACE_BRAIN_FRONT_URL": f"http://127.0.0.1:{self.port}",
            "ACE_BRAIN_EMBEDDING_URL": f"http://127.0.0.1:{self.port}",
        })

    def test_chat_against_stub(self):
        with self._env():
            r = be.chat("front", [{"role": "user", "content": "hai"}],
                        max_tokens=8)
            self.assertEqual(r.content, "halo")
            self.assertEqual(r.reasoning, "hm")

    def test_embed_against_stub(self):
        with self._env():
            vecs = be.embed(["satu kalimat"])
            self.assertEqual(vecs, [[0.1, 0.2, 0.3]])

    def test_fail_closed_on_dead_organ(self):
        with mock.patch.dict(os.environ,
                             {"ACE_BRAIN_FRONT_URL": "http://127.0.0.1:1"}):
            self.assertFalse(be.health("front", timeout=1.0))
            with self.assertRaises(be.BrainUnavailable):
                be.chat("front", [{"role": "user", "content": "hai"}],
                        timeout=1.0)


class WakeTests(unittest.TestCase):
    def setUp(self):
        be.drain_wake_events()

    def test_wake_success_records_event(self):
        states = iter([False, False, True])
        with mock.patch.object(be, "health",
                               side_effect=lambda *a, **k: next(states)), \
             mock.patch.object(be, "_start_unit") as start, \
             mock.patch.object(be, "WAKE_POLL_S", 0.0):
            woke = be.ensure_organ("coder", wake_timeout=5.0)
        self.assertTrue(woke)
        start.assert_called_once_with("ace-coder")
        events = be.drain_wake_events()
        self.assertEqual(events, [{"organ": "coder", "unit": "ace-coder",
                                   "woke": True}])

    def test_wake_failure_is_organ_dead(self):
        with mock.patch.object(be, "health", return_value=False), \
             mock.patch.object(be, "_start_unit"), \
             mock.patch.object(be, "WAKE_POLL_S", 0.0):
            with self.assertRaises(be.BrainUnavailable):
                be.ensure_organ("embedding", wake_timeout=0.05)

    def test_wake_start_failure_is_organ_dead(self):
        import subprocess as sp
        with mock.patch.object(be, "health", return_value=False), \
             mock.patch.object(be, "_start_unit",
                               side_effect=sp.CalledProcessError(1, "sudo")):
            with self.assertRaises(be.BrainUnavailable):
                be.ensure_organ("coder", wake_timeout=0.05)

    def test_front_is_never_woken(self):
        with mock.patch.object(be, "health", return_value=False), \
             mock.patch.object(be, "_start_unit") as start:
            with self.assertRaises(be.BrainUnavailable):
                be.ensure_organ("front")
        start.assert_not_called()

    def test_healthy_organ_is_not_woken(self):
        with mock.patch.object(be, "health", return_value=True), \
             mock.patch.object(be, "_start_unit") as start:
            self.assertFalse(be.ensure_organ("coder"))
        start.assert_not_called()


if __name__ == "__main__":
    unittest.main()
