"""Regression evidence for fail-closed inference, separate from model competence."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from ace_operational.models_backend import ModelRouter, _loopback_url, _NoLocalRedirect, get_available_ram_mb
from ace_operational.store import OperationalStore


class TruthfulInferenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ace-truthful-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = OperationalStore(self.root / "workspace")
        self.addCleanup(self.store.close)
        self.env = patch.dict(os.environ, {"ACE_MODEL_CACHE": str(self.root / "models"),
                                          "ACE_DEFAULT_MODEL": "", "ACE_LLAMA_CONTEXT": "4096",
                                          "ACE_LLAMA_THREADS": "2"})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.router = ModelRouter(self.store)
        self.empty = {"ready": False, "llama_binary": "", "server_healthy": False,
                      "server_models": [], "valid_models": [], "endpoint_error": "No server"}
        self.discovery = patch.object(self.router, "discover_local_gguf", return_value=self.empty)
        self.discovery.start()
        self.addCleanup(self.discovery.stop)
        self.messages = [{"role": "user", "content": "Periksa fungsi ini dan perbaiki bug."}]

    def local_model(self, name="model-3b.gguf"):
        model = self.root / name
        model.write_bytes(b"GGUF" + b"actual-test-artifact")
        return {"name": name, "path": str(model), "size_bytes": model.stat().st_size,
                "estimated_ram_mb": 256, "fits_ram": True, "checksum_verified": False}

    def test_no_backend_never_reports_completed_work_and_receipt_survives_restart(self):
        result = self.router.generate_text(self.messages, task_id="task_probe")
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(result["error_code"], "NO_LOCAL_MODEL")
        self.assertEqual(result["text"], "")
        self.assertFalse(result["task_verified"])
        self.assertIsNone(result["model"])
        with OperationalStore(self.store.workspace) as reopened:
            receipt = reopened.list_events()[-1]["technical_detail"]
            self.assertEqual(receipt["task_id"], "task_probe")
            self.assertEqual(receipt["input"], self.messages)
            self.assertEqual(receipt["raw_output"], "")
            self.assertEqual(receipt["error_code"], "NO_LOCAL_MODEL")
        capabilities = self.router.capabilities()
        self.assertFalse(capabilities["supports_local_coding"])

    def test_deterministic_tier_is_no_longer_a_fabricated_ast_execution(self):
        result = self.router.generate_text(self.messages, tier="deterministic")
        self.assertFalse(result["success"])
        self.assertEqual(result["error_code"], "UNSUPPORTED_DETERMINISTIC_INFERENCE")
        self.assertEqual(result["text"], "")

    def test_invalid_messages_and_budget_fail_before_running_a_model(self):
        for messages in ([], ["not-a-message"], [{"role": "user", "content": 7}]):
            with self.subTest(messages=messages):
                self.assertEqual(self.router.generate_text(messages)["error_code"], "INVALID_INPUT")
        self.assertEqual(self.router.generate_text(self.messages, max_tokens=0)["error_code"], "INVALID_BUDGET")
        self.assertEqual(self.router.generate_text(self.messages, max_tokens=100000)["error_code"], "INVALID_BUDGET")
        self.assertEqual(self.router.generate_text(self.messages, timeout_seconds=901)["error_code"], "INVALID_BUDGET")
        for key, value in (("max_tokens", True), ("temperature", False), ("timeout_seconds", True),
                           ("repeat_penalty", True), ("repeat_penalty", 0.79), ("repeat_penalty", 1.51),
                           ("repeat_penalty", float("nan")), ("repeat_penalty", float("inf"))):
            with self.subTest(key=key, value=value):
                self.assertEqual(self.router.generate_text(self.messages, **{key: value})["error_code"], "INVALID_BUDGET")

    def test_cli_success_has_real_output_model_digest_budget_and_input(self):
        artifact = self.local_model()
        self.empty.update(ready=True, llama_binary="/trusted/llama-completion", valid_models=[artifact])
        completed = subprocess.CompletedProcess([], 0, '"jawaban aktual"[end of text]', "timing evidence")
        with patch("ace_operational.models_backend.subprocess.run", return_value=completed) as run:
            result = self.router.generate_text(self.messages, max_tokens=123, target_model="model-3b",
                                              timeout_seconds=17, repeat_penalty=1.0)
        self.assertTrue(result["success"])
        self.assertEqual(result["text"], '"jawaban aktual"')
        self.assertEqual(result["raw_output"], completed.stdout)
        self.assertEqual(result["stderr"], completed.stderr)
        self.assertEqual(result["model"]["sha256"], hashlib.sha256(Path(artifact["path"]).read_bytes()).hexdigest())
        self.assertFalse(result["task_verified"])
        argv = run.call_args.args[0]
        self.assertEqual(argv[argv.index("-n") + 1], "123")
        self.assertEqual(argv[argv.index("--ctx-size") + 1], "4096")
        self.assertEqual(argv[argv.index("--repeat-penalty") + 1], "1.0")
        self.assertEqual(result["inference_config"]["repeat_penalty"], 1.0)
        self.assertIn(self.messages[0]["content"], argv[argv.index("-p") + 1])
        self.assertIn("available_ram_after_mb", result["resource_usage"])
        self.assertGreater(run.call_args.kwargs["timeout"], 0)
        self.assertLessEqual(run.call_args.kwargs["timeout"], 17)

    def test_cli_error_empty_output_and_timeout_preserve_negative_evidence(self):
        self.empty.update(ready=True, llama_binary="/trusted/llama-completion", valid_models=[self.local_model()])
        cases = [subprocess.CompletedProcess([], 9, "partial output", "out of memory"),
                 subprocess.CompletedProcess([], 0, "[end of text]", "no answer")]
        for process in cases:
            with self.subTest(process=process), patch("ace_operational.models_backend.subprocess.run", return_value=process):
                result = self.router.generate_text(self.messages)
                self.assertFalse(result["success"])
                self.assertEqual(result["error_code"], "CLI_INFERENCE_FAILED")
                self.assertEqual(result["text"], "")
                self.assertEqual(result["raw_output"], process.stdout)
        with patch("ace_operational.models_backend.subprocess.run",
                   side_effect=subprocess.TimeoutExpired("completion", 60, output=b"partial", stderr=b"timeout")):
            result = self.router.generate_text(self.messages)
        self.assertEqual(result["error_code"], "INFERENCE_TIMEOUT")
        self.assertEqual(result["raw_output"], "partial")
        self.assertFalse(result["success"])

    def test_requested_model_cannot_silently_use_another_model(self):
        self.empty.update(ready=True, llama_binary="/trusted/llama-completion", valid_models=[self.local_model()])
        with patch("ace_operational.models_backend.subprocess.run") as run:
            result = self.router.generate_text(self.messages, target_model="unknown-model")
        run.assert_not_called()
        self.assertEqual(result["error_code"], "MODEL_NOT_FOUND")
        self.assertFalse(result["success"])

    def test_remote_offline_block_is_recorded_without_a_fake_local_answer(self):
        self.store.set_offline(True)
        result = self.router.generate_text(self.messages, prefer_remote=True)
        self.assertFalse(result["success"])
        self.assertTrue(result["offline_blocked"])
        self.assertGreaterEqual(result["egress_attempts_blocked"], 1)
        self.assertEqual(result["text"], "")
        self.assertIn("OFFLINE_BLOCKED", [failure["code"] for failure in result["failures"]])

    def test_server_failure_can_fallback_only_to_actual_cli_inference(self):
        self.empty.update(ready=True, server_healthy=True, server_url="http://127.0.0.1:8081",
                          server_models=[{"id": "server-model"}], llama_binary="/trusted/llama-completion",
                          valid_models=[self.local_model()])
        with patch("ace_operational.models_backend._local_json", side_effect=TimeoutError("server timed out")), \
                patch("ace_operational.models_backend.subprocess.run", return_value=subprocess.CompletedProcess([], 0, "real CLI output", "")):
            result = self.router.generate_text(self.messages)
        self.assertTrue(result["success"])
        self.assertTrue(result["fallback_triggered"])
        self.assertEqual(result["text"], "real CLI output")
        self.assertEqual(result["inference_config"]["repeat_penalty"], 1.15)
        self.assertEqual(result["failures"][0]["code"], "SERVER_INFERENCE_FAILED")

    def test_server_identity_is_not_misrepresented_as_an_attested_artifact(self):
        self.empty.update(ready=True, server_healthy=True, server_url="http://127.0.0.1:8081",
                          server_models=[{"id": "server-model"}])
        payload = {"model": "server-model", "choices": [{"message": {"content": "actual output"}, "finish_reason": "stop"}],
                   "usage": {"completion_tokens": 2}}
        with patch("ace_operational.models_backend._local_json", return_value=payload) as request:
            result = self.router.generate_text(self.messages, target_model="server-model", repeat_penalty=1.2)
        self.assertEqual(request.call_args.kwargs["body"]["repeat_penalty"], 1.2)
        self.assertEqual(result["inference_config"]["repeat_penalty"], 1.2)
        self.assertTrue(result["success"])
        self.assertEqual(result["model"]["id"], "server-model")
        self.assertIsNone(result["model"]["sha256"])
        self.assertFalse(result["model"]["checksum_verified"])
        with patch("ace_operational.models_backend._local_json") as request:
            result = self.router.generate_text(self.messages, target_model="different-model")
        request.assert_not_called()
        self.assertFalse(result["success"])

    def test_qwen3_cli_prompt_carries_no_think_directive(self):
        artifact = self.local_model("Qwen3-8B-Q4_K_M.gguf")
        self.empty.update(ready=True, llama_binary="/trusted/llama-completion",
                          valid_models=[artifact])
        completed = subprocess.CompletedProcess([], 0, "jawaban", "")
        with patch("ace_operational.models_backend.subprocess.run",
                   return_value=completed) as run:
            result = self.router.generate_text(
                self.messages, target_model="Qwen3-8B")
        self.assertTrue(result["success"])
        argv = run.call_args.args[0]
        prompt = argv[argv.index("-p") + 1]
        self.assertIn("/no_think", prompt)
        # The recorded input stays the caller's messages, unmodified.
        self.assertEqual(result["input"], self.messages)

    def test_qwen3_server_gets_thinking_disabled_other_models_do_not(self):
        payload = {"model": "m", "choices": [{"message": {"content": "ok"},
                                              "finish_reason": "stop"}]}
        for model_id, expect_kwargs in [
                ("Qwen3-8B-Q4_K_M.gguf", True), ("server-model", False)]:
            self.empty.update(ready=True, server_healthy=True,
                              server_url="http://127.0.0.1:8081",
                              server_models=[{"id": model_id}])
            with patch("ace_operational.models_backend._local_json",
                       return_value=payload) as request:
                result = self.router.generate_text(
                    self.messages, target_model=model_id)
            self.assertTrue(result["success"])
            body = request.call_args.kwargs["body"]
            if expect_kwargs:
                self.assertEqual(body["chat_template_kwargs"],
                                 {"enable_thinking": False})
            else:
                self.assertNotIn("chat_template_kwargs", body)

    def test_truncated_server_json_is_rejected_even_if_a_prefix_looks_valid(self):
        self.empty.update(ready=True, server_healthy=True, server_url="http://127.0.0.1:8081",
                          server_models=[{"id": "server-model"}])
        payload = {"model": "server-model", "choices": [{"message": {"content": '{"action":"inspect"}'}, "finish_reason": "length"}]}
        with patch("ace_operational.models_backend._local_json", return_value=payload):
            result = self.router.generate_structured(self.messages, required_keys=["action"])
        self.assertFalse(result["success"])
        self.assertEqual(result["error_code"], "INVALID_JSON")
        self.assertIsNone(result["data"])

    def test_invalid_structured_output_cannot_become_status_ok(self):
        model = self.local_model()
        self.empty.update(ready=True, llama_binary="/trusted/llama-completion", valid_models=[model])
        for raw in ("not JSON", '{"action": "patch"}', '{"action":"patch","status":"ok",}'):
            with self.subTest(raw=raw), patch("ace_operational.models_backend.subprocess.run",
                        return_value=subprocess.CompletedProcess([], 0, raw, "")):
                result = self.router.generate_structured(self.messages, required_keys=["action", "status"])
                self.assertFalse(result["success"])
                self.assertIsNone(result["data"])
                self.assertEqual(result["status"], "INVALID_OUTPUT")
                self.assertEqual(result["error_code"], "INVALID_JSON")
                self.assertEqual(result["raw_output"], raw)
                self.assertIn("INVALID_JSON", result["verification_trace"])
                receipt = self.store.list_events()[-1]["technical_detail"]
                self.assertFalse(receipt["success"])
                self.assertEqual(receipt["inference_event_id"], result["inference_event_id"])

    def test_valid_json_is_attributed_to_real_generation_but_override_is_parser_only(self):
        self.empty.update(ready=True, llama_binary="/trusted/llama-completion", valid_models=[self.local_model()])
        raw = '{"action":"inspect","status":"proposal"}'
        with patch("ace_operational.models_backend.subprocess.run", return_value=subprocess.CompletedProcess([], 0, raw, "")):
            result = self.router.generate_structured(self.messages, required_keys=["action", "status"], repeat_penalty=1.0)
        self.assertTrue(result["success"])
        self.assertEqual(result["inference_config"]["repeat_penalty"], 1.0)
        self.assertEqual(result["data"], json.loads(raw))
        self.assertTrue(result["valid_json"])
        self.assertIn("json_object_required_keys", result["verification_trace"])
        parsed = self.router.generate_structured(self.messages, required_keys=["action"], raw_candidate_override='{"action":"parse",}')
        self.assertFalse(parsed["inference_performed"])
        self.assertEqual(parsed["backend_used"], "parser-only")

    def test_loopback_endpoint_validation_rejects_remote_paths_credentials_and_redirects(self):
        self.assertEqual(_loopback_url("http://localhost:8081"), "http://127.0.0.1:8081")
        self.assertEqual(_loopback_url("http://[::1]:8081"), "http://[::1]:8081")
        for url in ("https://api.example.com", "http://192.168.1.1", "file:///tmp/model", "http://user:pw@localhost",
                    "http://127.0.0.1/x", "http://127.0.0.1?target=external", "http://127.0.0.1.example.com"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                _loopback_url(url)
        from urllib.error import HTTPError
        from urllib.request import Request
        with self.assertRaises(HTTPError):
            _NoLocalRedirect().redirect_request(Request("http://127.0.0.1"), None, 302, "Found", {}, "http://external.invalid")

    def test_cgroup_remaining_memory_caps_host_memory(self):
        contents = {"/proc/meminfo": "MemAvailable: 16777216 kB\n", "/proc/self/cgroup": "0::/\n",
                    "/sys/fs/cgroup/memory.max": str(8 * 1024**3),
                    "/sys/fs/cgroup/memory.current": str(3 * 1024**3)}
        def read(path, *args, **kwargs):
            if str(path) not in contents:
                raise FileNotFoundError(path)
            return contents[str(path)]
        with patch.object(Path, "read_text", read):
            self.assertEqual(get_available_ram_mb(), 5 * 1024)


if __name__ == "__main__":
    unittest.main()
