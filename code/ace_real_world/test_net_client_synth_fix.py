"""Regression tests for the net_client_synth expected_keys indentation bug.

Finding (gravity PR #301, test_15, pinned as expectedFailure): when
expected_keys was provided, the synthesized client's schema-check block
was emitted at 4-space indentation inside a 16-space try/with nesting,
so every such client failed to compile (SyntaxError). Fixed by emitting
the block at the nesting level of the surrounding generated code.
"""
from __future__ import annotations

import io
import json
import unittest
from unittest import mock

from ace_real_world.net_client_synth import NetClientSynthesizer


def _load_client(code: str):
    namespace: dict = {}
    exec(compile(code, "<net_client>", "exec"), namespace)
    return namespace["query_api_endpoint"]


class _FakeResponse:
    status = 200

    def __init__(self, payload: dict):
        self._body = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class TestNetClientSynthExpectedKeys(unittest.TestCase):
    def test_synthesized_code_with_expected_keys_compiles(self) -> None:
        rule = NetClientSynthesizer().synthesize_json_client(
            "http://127.0.0.1:1/unreachable", expected_keys=["ok"]
        )
        compile(rule.client_code, "<net_client>", "exec")  # must not raise

    def test_synthesized_code_without_expected_keys_still_compiles(self) -> None:
        rule = NetClientSynthesizer().synthesize_json_client(
            "http://127.0.0.1:1/unreachable"
        )
        compile(rule.client_code, "<net_client>", "exec")

    def test_missing_key_raises_value_error_via_retry_path(self) -> None:
        synth = NetClientSynthesizer()
        rule = synth.synthesize_json_client(
            "http://127.0.0.1:9/api", expected_keys=["ok", "id"], max_retries=1
        )
        fn = _load_client(rule.client_code)
        with mock.patch(
            "urllib.request.urlopen", return_value=_FakeResponse({"ok": True})
        ):
            with self.assertRaises(RuntimeError) as ctx:
                fn()
        # The generated client retries then surfaces the schema failure
        # as the last error inside its RuntimeError.
        self.assertIn("missing keys", str(ctx.exception))

    def test_all_keys_present_returns_data(self) -> None:
        synth = NetClientSynthesizer()
        rule = synth.synthesize_json_client(
            "http://127.0.0.1:9/api", expected_keys=["ok"], max_retries=1
        )
        fn = _load_client(rule.client_code)
        with mock.patch(
            "urllib.request.urlopen",
            return_value=_FakeResponse({"ok": True, "extra": 1}),
        ):
            self.assertEqual(fn(), {"ok": True, "extra": 1})


if __name__ == "__main__":
    unittest.main()
