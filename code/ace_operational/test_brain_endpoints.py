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


class MalformedShapeTests(unittest.TestCase):
    """A 200 with a broken body is an organ fault: BrainUnavailable,
    never a raw KeyError/IndexError/TypeError escaping the wrapper."""

    def test_parse_rejects_broken_shapes(self):
        broken = [
            {},
            {"error": "bad_payload"},
            {"choices": []},
            {"choices": [{"nope": 1}]},
            {"choices": "nope"},
            {"choices": [{"message": "not-a-dict"}]},
            [],
            "just a string",
        ]
        for payload in broken:
            with self.assertRaises(be.BrainUnavailable, msg=repr(payload)):
                be.parse_chat_response(payload)


class _CapturingStubHandler(_StubHandler):
    last_bodies = {}

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        try:
            type(self).last_bodies[self.path] = json.loads(raw)
        except ValueError:
            type(self).last_bodies[self.path] = None
        if self.path == "/v1/chat/completions":
            payload = {"choices": [{"message": {
                "content": "halo", "reasoning_content": "hm"}}],
                "timings": {"predicted_per_second": 2.0, "predicted_n": 4}}
        elif self.path == "/embedding":
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


class _MalformedStubHandler(_StubHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)
        if self.path == "/v1/chat/completions":
            payload = {"unexpected": "shape"}
        elif self.path == "/embedding":
            payload = [{"no_embedding_here": 1}]
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


class _StubServerMixin:
    handler = _StubHandler

    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), cls.handler)
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


class StructuredKwargsTests(_StubServerMixin, unittest.TestCase):
    handler = _CapturingStubHandler

    def test_structured_kwargs_are_sent(self):
        with self._env():
            be.chat_structured("front", [{"role": "user", "content": "hai"}],
                               max_tokens=8)
        sent = _CapturingStubHandler.last_bodies["/v1/chat/completions"]
        self.assertEqual(sent["chat_template_kwargs"],
                         {"enable_thinking": False})

    def test_plain_chat_sends_no_template_kwargs(self):
        with self._env():
            be.chat("front", [{"role": "user", "content": "hai"}],
                    max_tokens=8)
        sent = _CapturingStubHandler.last_bodies["/v1/chat/completions"]
        self.assertNotIn("chat_template_kwargs", sent)

    def test_explicit_kwargs_pass_through(self):
        with self._env():
            be.chat("front", [{"role": "user", "content": "hai"}],
                    max_tokens=8, template_kwargs={"enable_thinking": True})
        sent = _CapturingStubHandler.last_bodies["/v1/chat/completions"]
        self.assertEqual(sent["chat_template_kwargs"],
                         {"enable_thinking": True})


class MalformedEndToEndTests(_StubServerMixin, unittest.TestCase):
    handler = _MalformedStubHandler

    def test_chat_200_broken_shape_is_unavailable(self):
        with self._env():
            with self.assertRaises(be.BrainUnavailable):
                be.chat("front", [{"role": "user", "content": "hai"}],
                        max_tokens=8)

    def test_embed_200_broken_shape_is_unavailable(self):
        with self._env():
            with self.assertRaises(be.BrainUnavailable):
                be.embed(["satu kalimat"])


class EmbedEmptyInputTests(_StubServerMixin, unittest.TestCase):
    handler = _CapturingStubHandler

    def test_embed_empty_list_returns_empty_without_a_request(self):
        # Found by gravity fuzz review (PR #262): embed([])
        # used to reach texts[0] and raise a raw IndexError.
        # An empty input is a vacuous request: no organ call,
        # no wake, an empty result.
        _CapturingStubHandler.last_bodies = {}
        with self._env():
            self.assertEqual(be.embed([]), [])
        self.assertNotIn("/embedding",
                         _CapturingStubHandler.last_bodies)


if __name__ == "__main__":
    unittest.main()
