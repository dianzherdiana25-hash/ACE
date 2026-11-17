"""Uji kasus tepi tambahan untuk ace_operational.brain_endpoints (>=25 kasus)."""
from __future__ import annotations

import json
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest import mock

from ace_operational import brain_endpoints as be


class _ConfigurableHandler(BaseHTTPRequestHandler):
    """Server HTTP stub lokal untuk menguji variasi payload dan status."""

    routes: dict[str, tuple[int, bytes]] = {}
    last_post_bodies: dict[str, dict] = {}

    def log_message(self, *args) -> None:
        pass

    def _reply(self, status: int, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        status, body = self.routes.get(self.path, (404, b"{}"))
        self._reply(status, body)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        if raw:
            try:
                self.last_post_bodies[self.path] = json.loads(raw.decode("utf-8"))
            except ValueError:
                pass
        status, body = self.routes.get(self.path, (404, b"{}"))
        self._reply(status, body)


class BrainEndpointsEdgeTests(unittest.TestCase):
    """Kumpulan >=25 kasus tepi routing, parsing, fail-closed, wake, dan embed."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.server = HTTPServer(("127.0.0.1", 0), _ConfigurableHandler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()

    def setUp(self) -> None:
        _ConfigurableHandler.routes = {
            "/health": (200, b'{"status": "ok"}'),
            "/v1/chat/completions": (
                200,
                json.dumps(
                    {
                        "choices": [{"message": {"content": "ok", "reasoning_content": ""}}],
                        "timings": {},
                    }
                ).encode(),
            ),
            "/embedding": (200, json.dumps([{"embedding": [[0.5, 0.5]]}]).encode()),
        }
        _ConfigurableHandler.last_post_bodies = {}
        be.drain_wake_events()

    def _env_all_stub(self):
        url = f"http://127.0.0.1:{self.port}"
        return mock.patch.dict(
            os.environ,
            {
                "ACE_BRAIN_FRONT_URL": url,
                "ACE_BRAIN_CODER_URL": url,
                "ACE_BRAIN_EMBEDDING_URL": url,
                "ACE_BRAIN_A3B_URL": url,
            },
        )

    # --- Routing & Organ URL edge cases ---

    def test_organ_url_rejects_empty_whitespace_and_case_variants(self) -> None:
        for bad in ("", " front", "FRONT", "a3b ", "unknown"):
            with self.subTest(organ=bad), self.assertRaises(ValueError):
                be.organ_url(bad)

    def test_organ_url_strips_multiple_trailing_slashes(self) -> None:
        with mock.patch.dict(os.environ, {"ACE_BRAIN_CODER_URL": "http://127.0.0.1:9002///"}):
            self.assertEqual(be.organ_url("coder"), "http://127.0.0.1:9002")

    def test_organ_pair_is_frozen_immutable(self) -> None:
        pair = be.proposer_validator_pair("code")
        with self.assertRaises(AttributeError):
            pair.proposer = "front"  # type: ignore[misc]

    def test_organ_pair_as_dict_reflects_env_overrides(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                "ACE_BRAIN_CODER_URL": "http://127.0.0.1:18002/",
                "ACE_BRAIN_FRONT_URL": "http://127.0.0.1:18001/",
            },
        ):
            d = be.proposer_validator_pair("language").as_dict()
        self.assertEqual(d["task_kind"], "language")
        self.assertEqual(d["proposer_url"], "http://127.0.0.1:18001")
        self.assertEqual(d["validator_url"], "http://127.0.0.1:18002")

    def test_proposer_validator_pair_rejects_empty_and_uppercase_task_kind(self) -> None:
        for bad in ("", "CODE", "Language", "math"):
            with self.subTest(task_kind=bad), self.assertRaises(ValueError):
                be.proposer_validator_pair(bad)

    def test_role_url_proposer_and_validator_language_swap(self) -> None:
        self.assertEqual(be.role_url("proposer", "language"), be.DEFAULT_URLS["front"])
        self.assertEqual(be.role_url("validator", "language"), be.DEFAULT_URLS["coder"])

    def test_role_url_proposer_rejects_bad_task_kind_while_fixed_roles_ignore_it(self) -> None:
        with self.assertRaises(ValueError):
            be.role_url("proposer", "invalid")
        with self.assertRaises(ValueError):
            be.role_url("validator", "invalid")
        self.assertEqual(be.role_url("chat", "invalid"), be.DEFAULT_URLS["front"])
        self.assertEqual(be.role_url("deep", "invalid"), be.DEFAULT_URLS["a3b"])
        self.assertEqual(be.role_url("recall", "invalid"), be.DEFAULT_URLS["embedding"])

    def test_role_url_rejects_empty_role(self) -> None:
        with self.assertRaises(ValueError):
            be.role_url("")

    # --- Parsing edge cases ---

    def test_parse_chat_response_preserves_zero_timings(self) -> None:
        payload = {
            "choices": [{"message": {"content": "x", "reasoning_content": ""}}],
            "timings": {"prompt_per_second": 0.0, "predicted_per_second": 0.0, "predicted_n": 0},
        }
        res = be.parse_chat_response(payload)
        self.assertEqual(res.prompt_per_second, 0.0)
        self.assertEqual(res.predicted_per_second, 0.0)
        self.assertEqual(res.predicted_tokens, 0)
        self.assertFalse(res.organ_woke)

    def test_parse_chat_response_handles_none_timings(self) -> None:
        payload = {
            "choices": [{"message": {"content": "jawaban", "reasoning_content": None}}],
            "timings": None,
        }
        res = be.parse_chat_response(payload)
        self.assertEqual(res.content, "jawaban")
        self.assertEqual(res.reasoning, "")
        self.assertIsNone(res.prompt_per_second)
        self.assertIsNone(res.predicted_per_second)
        self.assertIsNone(res.predicted_tokens)

    # --- Health & fail-closed HTTP edge cases ---

    def test_health_false_on_non_json_200_body(self) -> None:
        _ConfigurableHandler.routes["/health"] = (200, b"NOT_JSON")
        with self._env_all_stub():
            self.assertFalse(be.health("front", timeout=1.0))

    def test_health_false_on_503_status(self) -> None:
        _ConfigurableHandler.routes["/health"] = (503, b'{"error": "loading"}')
        with self._env_all_stub():
            self.assertFalse(be.health("front", timeout=1.0))

    def test_health_unknown_organ_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            be.health("nonexistent")

    def test_require_health_passes_when_healthy_and_raises_when_down(self) -> None:
        with self._env_all_stub():
            be.require_health("front")
            _ConfigurableHandler.routes["/health"] = (500, b"{}")
            with self.assertRaises(be.BrainUnavailable):
                be.require_health("front")

    def test_chat_raises_brain_unavailable_on_invalid_json_response(self) -> None:
        _ConfigurableHandler.routes["/v1/chat/completions"] = (200, b"{truncated")
        with self._env_all_stub(), self.assertRaises(be.BrainUnavailable):
            be.chat("front", [{"role": "user", "content": "hi"}], check_health=False)

    @unittest.expectedFailure
    def test_bug_chat_malformed_200_json_missing_choices_not_fail_closed(self) -> None:
        # Suspected bug: _request() succeeds for HTTP 200 valid JSON {"error": ...},
        # lalu parse_chat_response() melempar KeyError alih-alih BrainUnavailable.
        _ConfigurableHandler.routes["/v1/chat/completions"] = (200, b'{"error": "bad_payload"}')
        with self._env_all_stub(), self.assertRaises(be.BrainUnavailable):
            be.chat("front", [{"role": "user", "content": "hi"}], check_health=False)

    # --- Chat & chat_structured payload edge cases ---

    def test_chat_preserves_seed_zero_and_omits_seed_none(self) -> None:
        with self._env_all_stub():
            be.chat("front", [{"role": "user", "content": "a"}], seed=0, check_health=False)
            self.assertEqual(_ConfigurableHandler.last_post_bodies["/v1/chat/completions"]["seed"], 0)
            be.chat("front", [{"role": "user", "content": "a"}], seed=None, check_health=False)
            self.assertNotIn("seed", _ConfigurableHandler.last_post_bodies["/v1/chat/completions"])

    def test_chat_omits_empty_template_kwargs(self) -> None:
        with self._env_all_stub():
            be.chat(
                "front",
                [{"role": "user", "content": "a"}],
                template_kwargs={},
                check_health=False,
            )
            self.assertNotIn(
                "chat_template_kwargs",
                _ConfigurableHandler.last_post_bodies["/v1/chat/completions"],
            )

    def test_chat_structured_applies_default_and_allows_override_without_mutating_constant(self) -> None:
        before = dict(be.STRUCTURED_TEMPLATE_KWARGS)
        with self._env_all_stub():
            be.chat_structured("front", [{"role": "user", "content": "json"}], check_health=False)
            sent_default = _ConfigurableHandler.last_post_bodies["/v1/chat/completions"]
            self.assertEqual(sent_default["chat_template_kwargs"], {"enable_thinking": False})

            be.chat_structured(
                "front",
                [{"role": "user", "content": "json"}],
                template_kwargs={"enable_thinking": True},
                check_health=False,
            )
            sent_override = _ConfigurableHandler.last_post_bodies["/v1/chat/completions"]
            self.assertEqual(sent_override["chat_template_kwargs"], {"enable_thinking": True})
        self.assertEqual(be.STRUCTURED_TEMPLATE_KWARGS, before)

    def test_chat_check_health_false_skips_ensure_organ(self) -> None:
        with self._env_all_stub(), mock.patch.object(be, "ensure_organ") as ensure_mock:
            res = be.chat("coder", [{"role": "user", "content": "hi"}], check_health=False)
        ensure_mock.assert_not_called()
        self.assertFalse(res.organ_woke)

    def test_chat_records_organ_woke_true_when_ensure_organ_wakes(self) -> None:
        with self._env_all_stub(), mock.patch.object(be, "ensure_organ", return_value=True):
            res = be.chat("coder", [{"role": "user", "content": "hi"}], check_health=True)
        self.assertTrue(res.organ_woke)

    # --- Wake semantics edge cases ---

    def test_a3b_is_never_woken_even_when_wake_true(self) -> None:
        with mock.patch.object(be, "health", return_value=False), mock.patch.object(
            be, "_start_unit"
        ) as start:
            with self.assertRaises(be.BrainUnavailable):
                be.ensure_organ("a3b", wake=True)
        start.assert_not_called()

    def test_ensure_organ_wake_false_does_not_start_wakeable_unit(self) -> None:
        with mock.patch.object(be, "health", return_value=False), mock.patch.object(
            be, "_start_unit"
        ) as start:
            with self.assertRaises(be.BrainUnavailable):
                be.ensure_organ("coder", wake=False)
        start.assert_not_called()

    def test_ensure_organ_zero_timeout_raises_immediately_after_start(self) -> None:
        with mock.patch.object(be, "health", return_value=False), mock.patch.object(
            be, "_start_unit"
        ) as start:
            with self.assertRaises(be.BrainUnavailable):
                be.ensure_organ("coder", wake_timeout=0.0)
        start.assert_called_once_with("ace-coder")
        self.assertEqual(be.drain_wake_events(), [])

    def test_drain_wake_events_returns_snapshot_and_clears_buffer(self) -> None:
        states = iter([False, True])
        with mock.patch.object(be, "health", side_effect=lambda *a, **k: next(states)), mock.patch.object(
            be, "_start_unit"
        ):
            be.ensure_organ("embedding", wake_timeout=5.0)
        first = be.drain_wake_events()
        second = be.drain_wake_events()
        self.assertEqual(first, [{"organ": "embedding", "unit": "ace-embedding", "woke": True}])
        self.assertEqual(second, [])

    # --- Embed edge cases ---

    def test_embed_single_text_sends_string_multi_text_sends_list(self) -> None:
        with self._env_all_stub():
            be.embed(["satu"], check_health=False)
            self.assertEqual(_ConfigurableHandler.last_post_bodies["/embedding"]["input"], "satu")
            be.embed(["satu", "dua"], check_health=False)
            self.assertEqual(
                _ConfigurableHandler.last_post_bodies["/embedding"]["input"], ["satu", "dua"]
            )

    def test_embed_accepts_flat_dict_and_empty_embedding_list(self) -> None:
        _ConfigurableHandler.routes["/embedding"] = (200, json.dumps({"embedding": [1.0, 2.0]}).encode())
        with self._env_all_stub():
            self.assertEqual(be.embed(["satu"], check_health=False), [[1.0, 2.0]])

        _ConfigurableHandler.routes["/embedding"] = (200, json.dumps([{"embedding": []}]).encode())
        with self._env_all_stub():
            self.assertEqual(be.embed(["satu"], check_health=False), [[]])

    def test_embed_flattens_multiple_chunk_items(self) -> None:
        payload = [
            {"embedding": [[1.0, 0.0], [0.0, 1.0]]},
            {"embedding": [[0.5, 0.5]]},
        ]
        _ConfigurableHandler.routes["/embedding"] = (200, json.dumps(payload).encode())
        with self._env_all_stub():
            self.assertEqual(
                be.embed(["a", "b"], check_health=False),
                [[1.0, 0.0], [0.0, 1.0], [0.5, 0.5]],
            )

    @unittest.expectedFailure
    def test_bug_embed_empty_texts_list_raises_index_error(self) -> None:
        # Suspected bug: texts=[] memenuhi `len(texts) <= 1`, lalu mengakses texts[0]
        # sehingga melempar IndexError alih-alih mengembalikan [] atau ValueError.
        with self._env_all_stub():
            res = be.embed([], check_health=False)
        self.assertEqual(res, [])


if __name__ == "__main__":
    unittest.main()
