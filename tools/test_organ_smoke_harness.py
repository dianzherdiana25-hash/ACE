"""Unit & adversarial tests untuk tools/organ_smoke_harness.py (0 HTTP)."""
from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from tools import organ_smoke_harness as osh


class TestOrganSmokeHarness(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_01_dry_run_passes_all_roles_and_fault_drills_with_zero_network(self):
        rep = osh.run_smoke_protocol()
        self.assertTrue(rep["passed"], rep)
        self.assertEqual(rep["network_calls"], 0)
        self.assertEqual(rep["checks_passed"], rep["checks_total"])
        self.assertEqual(rep["fault_drills_passed"], rep["fault_drills_total"])
        self.assertEqual(set(rep["observed_brain_of_origin"]), {"front", "coder", "validator", "judge", "embedding"})

    def test_02_rejects_live_network_urls_fail_closed(self):
        for url in ("http://127.0.0.1:8931", "https://api.groq.com/openai/v1", "http://localhost:18931"):
            with self.subTest(url=url):
                with self.assertRaises(osh.LiveNetworkDisallowedError):
                    osh.run_smoke_protocol(endpoint_hint=url)

    def test_03_custom_mock_adapter_catches_bad_health_and_empty_models(self):
        def bad_handler(method, path, payload):
            if path == "/health":
                return 200, {"status": "degraded"}
            if path == "/v1/models":
                return 200, {"object": "list", "data": []}
            return osh.DryRunOrganAdapter().handle(method, path, payload)

        rep = osh.run_smoke_protocol(handler=bad_handler)
        self.assertFalse(rep["passed"])
        by_name = {c["check"]: c for c in rep["checks"]}
        self.assertFalse(by_name["health"]["passed"])
        self.assertIn("health_missing_ok_status", by_name["health"]["error"])
        self.assertFalse(by_name["models"]["passed"])
        self.assertIn("models_empty_list", by_name["models"]["error"])

    def test_04_detects_missing_brain_of_origin_and_reasoning_overflow(self):
        def partial_handler(method, path, payload):
            if path == "/v1/chat/completions":
                role = (payload or {}).get("role")
                if role == "front":
                    return 200, {"choices": [{"message": {"content": "ok"}}]}  # missing brain_of_origin
                if role == "coder":
                    return 200, {
                        "brain_of_origin": "groq/qwen/qwen3.8-27b",
                        "choices": [{"message": {"content": "", "reasoning_content": "all budget spent here"}}],
                    }
            return osh.DryRunOrganAdapter().handle(method, path, payload)

        rep = osh.run_smoke_protocol(handler=partial_handler)
        self.assertFalse(rep["passed"])
        by_name = {c["check"]: c for c in rep["checks"]}
        self.assertIn("missing_or_invalid_brain_of_origin", by_name["chat:front"]["error"])
        self.assertIn("empty_content_reasoning_overflow", by_name["chat:coder"]["error"])

    def test_05_embedding_rejects_nan_inf_empty_and_bool(self):
        for bad_vec in ([], [0.1, float("nan")], [0.2, float("inf")], [True, 0.5]):
            with self.subTest(bad_vec=bad_vec):
                with self.assertRaises(osh.SmokeContractError):
                    osh.verify_embedding_response(
                        200,
                        {"brain_of_origin": "gemini/gemini-embedding-001", "data": [{"embedding": bad_vec}]},
                    )

    def test_06_timeout_exception_in_mock_handler_reported_without_crashing(self):
        def flaky_timeout_handler(method, path, payload):
            if path == "/v1/embeddings":
                raise TimeoutError("simulated timeout 120s")
            return osh.DryRunOrganAdapter().handle(method, path, payload)

        rep = osh.run_smoke_protocol(handler=flaky_timeout_handler)
        self.assertFalse(rep["passed"])
        emb = next(c for c in rep["checks"] if c["check"] == "embed:embedding")
        self.assertFalse(emb["passed"])
        self.assertIn("simulated timeout", emb["error"])

    def test_07_adapter_rejects_bad_dim_and_validates_origin_overrides(self):
        with self.assertRaises(ValueError):
            osh.DryRunOrganAdapter(osh.SmokeAdapterSpec(embedding_dim=0))
        with self.assertRaises(ValueError):
            osh.DryRunOrganAdapter(osh.SmokeAdapterSpec(embedding_dim=True))

        custom = osh.DryRunOrganAdapter(
            osh.SmokeAdapterSpec(origin_overrides={"front": "gemini/gemini-3-flash-preview"})
        )
        rep = osh.run_smoke_protocol(handler=custom.handle)
        self.assertTrue(rep["passed"])
        self.assertEqual(rep["observed_brain_of_origin"]["front"], "gemini/gemini-3-flash-preview")

    def test_08_cli_markdown_json_output_and_exit_codes(self):
        md_path = self.root / "smoke.md"
        rc = osh.main(["--format", "markdown", "--output", str(md_path)])
        self.assertEqual(rc, 0)
        text = md_path.read_text(encoding="utf-8")
        self.assertIn("network_calls=0", text)
        self.assertIn("`chat:judge`", text)

        out_buf = io.StringIO()
        with contextlib.redirect_stdout(out_buf):
            rc_json = osh.main(["--no-fault-drills"])
        self.assertEqual(rc_json, 0)
        parsed = json.loads(out_buf.getvalue())
        self.assertEqual(parsed["fault_drills_total"], 0)

        err_buf = io.StringIO()
        with contextlib.redirect_stderr(err_buf):
            rc_err = osh.main(["--endpoint", "http://127.0.0.1:8931"])
        self.assertEqual(rc_err, 1)


if __name__ == "__main__":
    unittest.main()
