"""Control-plane tests; mocked inference is never counted as model ability."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from ace_operational.coding_loop import CodingAgentLoop
from ace_operational.local_repo_workflow import LocalRepoWorkflow
from ace_operational.store import OperationalStore


class FakeRouter:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def generate_text(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        return self.payload


class FakeSandbox:
    def __init__(self, outcomes):
        self.outcomes = iter(outcomes)
        self.calls = 0

    def run_tests(self, *args):
        self.calls += 1
        status = next(self.outcomes)
        return {"status": status, "stdout": "", "stderr": "development test feedback",
                "runner_completion": {"tests_run": 1}}


class LocalRepositoryWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.repo, self.candidate = root / "repo", root / "candidate"
        self.evaluator = root / "evaluator"
        self.evaluator.mkdir()
        self.repo.mkdir()
        (self.repo / "access.py").write_text("def authorize():\n    return False\n")
        for args in [("init", "-q"), ("add", "."),
                     ("-c", "user.name=test", "-c", "user.email=test@example.invalid", "commit", "-qm", "fixture"),
                     ("worktree", "add", "-qb", "candidate", str(self.candidate))]:
            subprocess.run(["git", "-C", str(self.repo), *args], check=True, capture_output=True)
        self.store = OperationalStore(root / "state")

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def run_flow(self, router, sandbox, **options):
        return LocalRepoWorkflow(self.store, router=router, sandbox=sandbox).run(
            repository=self.candidate, issue="Perbaiki access authorize", evaluator_dir=self.evaluator,
            **options)

    def proposal(self, path="access.py", content="def authorize():\n    return True\n"):
        return {"success": True, "text": json.dumps({"plan": ["repair access"],
                "edits": [{"path": path, "content": content}]}),
                "backend_used": "local-gguf:mock-control-test", "model": {"sha256": "0" * 64}}

    def test_model_failure_never_writes_or_verifies_candidate(self):
        before = (self.candidate / "access.py").read_bytes()
        sandbox = FakeSandbox(["FAIL"])
        router = FakeRouter({"success": False, "status": "NO_MODEL", "text": ""})
        result = self.run_flow(router, sandbox)
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["reason"], "NO_MODEL")
        self.assertEqual((self.candidate / "access.py").read_bytes(), before)
        self.assertEqual(sandbox.calls, 1)
        self.assertFalse(self.store.list_receipts()[0]["passed"])

    def test_escape_and_test_edits_rejected(self):
        for path in ["../outside.py", "test_access.py", "/tmp/pwn.py"]:
            with self.subTest(path=path):
                result = self.run_flow(FakeRouter(self.proposal(path)), FakeSandbox(["FAIL"]), max_attempts=1)
                self.assertEqual(result["status"], "FAIL")
                self.assertIn("unknown/duplicate", result["attempts"][0]["error"])

    def test_blocked_sandbox_prevents_inference(self):
        router = FakeRouter(self.proposal())
        result = self.run_flow(router, FakeSandbox(["BLOCKED_ENVIRONMENT"]))
        self.assertEqual(result["status"], "BLOCKED_ENVIRONMENT")
        self.assertEqual(router.calls, [])

    def test_passing_baseline_does_not_claim_repair(self):
        router = FakeRouter(self.proposal())
        result = self.run_flow(router, FakeSandbox(["PASS"]))
        self.assertEqual(result["status"], "HOLD")
        self.assertEqual(router.calls, [])

    def test_real_edits_checkpoint_restart_and_tamper_control(self):
        router, sandbox = FakeRouter(self.proposal()), FakeSandbox(["FAIL", "PASS"])
        result = self.run_flow(router, sandbox)
        self.assertEqual(result["status"], "LOCALLY_VERIFIED")
        self.assertEqual(result["scientific_status"], "NOT_ASSESSED")
        self.assertIn("return True", (self.candidate / "access.py").read_text())
        self.assertTrue(self.store.list_receipts()[0]["passed"])
        self.store.close()
        self.store = OperationalStore(Path(self.tmp.name) / "state")
        resumed = self.run_flow(router, sandbox, task_id=result["task_id"])
        self.assertTrue(resumed["replayed"])
        self.assertEqual(len(router.calls), 1)
        (self.candidate / "access.py").write_text("def authorize():\n    return False\n")
        with self.assertRaisesRegex(ValueError, "changed after verification"):
            self.run_flow(router, sandbox, task_id=result["task_id"])

    def test_main_checkout_and_symlink_source_rejected(self):
        with self.assertRaisesRegex(ValueError, "isolated Git linked"):
            LocalRepoWorkflow(self.store, router=FakeRouter({}), sandbox=FakeSandbox([])).run(
                repository=self.repo, issue="fix access", evaluator_dir=self.evaluator)

    def test_invalid_json_keeps_negative_evidence(self):
        payload = self.proposal()
        payload["text"] = "done"
        result = self.run_flow(FakeRouter(payload),
                               FakeSandbox(["FAIL"]), max_attempts=1)
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("Invalid candidate", result["attempts"][0]["error"])
        saved = self.store.workspace / "artifacts" / result["task_id"] / "attempt-1.json"
        self.assertIn('"text": "done"', saved.read_text())

    def test_remote_and_unidentified_backend_cannot_claim_local_patch(self):
        payload = self.proposal()
        payload["backend_used"] = "host-bridge"
        result = self.run_flow(FakeRouter(payload), FakeSandbox(["FAIL"]), max_attempts=1)
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("digest-identified local model", result["reason"])

    def test_symbol_edit_preserves_surrounding_source(self):
        original = (self.candidate / "access.py").read_text()
        (self.candidate / "access.py").write_text("CONSTANT = 7\n" + original)
        subprocess.run(["git", "-C", str(self.candidate), "add", "."], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(self.candidate), "-c", "user.name=test", "-c",
                        "user.email=test@example.invalid", "commit", "-qm", "add surrounding source"],
                       check=True, capture_output=True)
        payload = self.proposal()
        parsed = json.loads(payload["text"])
        parsed["edits"][0]["symbol"] = "authorize"
        payload["text"] = json.dumps(parsed)
        result = self.run_flow(FakeRouter(payload), FakeSandbox(["FAIL", "PASS"]), patch_format="symbol")
        self.assertEqual(result["status"], "LOCALLY_VERIFIED")
        self.assertTrue((self.candidate / "access.py").read_text().startswith("CONSTANT = 7\n"))
        self.assertIn("implementation_digests", result)

    def test_symbol_edit_rejects_extra_top_level_code(self):
        payload = self.proposal(content="def authorize():\n    return True\nraise SystemExit(0)\n")
        parsed = json.loads(payload["text"])
        parsed["edits"][0]["symbol"] = "authorize"
        payload["text"] = json.dumps(parsed)
        result = self.run_flow(FakeRouter(payload), FakeSandbox(["FAIL"]),
                               patch_format="symbol", max_attempts=1)
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("exactly one", result["attempts"][0]["error"])

    def test_symbol_edit_rejects_changed_arguments_and_decorators(self):
        for content in ["def authorize(other):\n    return True\n",
                        "@staticmethod\ndef authorize():\n    return True\n"]:
            with self.subTest(content=content):
                payload = self.proposal(content=content)
                parsed = json.loads(payload["text"])
                parsed["edits"][0]["symbol"] = "authorize"
                payload["text"] = json.dumps(parsed)
                result = self.run_flow(FakeRouter(payload), FakeSandbox(["FAIL"]),
                                       patch_format="symbol", max_attempts=1)
                self.assertEqual(result["status"], "FAIL")
                self.assertIn("identical arguments", result["attempts"][0]["error"])

    def test_evaluator_change_invalidates_restart(self):
        result = self.run_flow(FakeRouter(self.proposal()), FakeSandbox(["FAIL", "PASS"]))
        (self.evaluator / "test_changed.py").write_text("raise RuntimeError('drift')\n")
        with self.assertRaisesRegex(ValueError, "restart contract changed"):
            self.run_flow(FakeRouter({}), FakeSandbox([]), task_id=result["task_id"])

    def test_unselected_file_change_invalidates_restart(self):
        result = self.run_flow(FakeRouter(self.proposal()), FakeSandbox(["FAIL", "PASS"]))
        (self.candidate / "new_module.py").write_text("x = 1\n")
        with self.assertRaisesRegex(ValueError, "tree changed"):
            self.run_flow(FakeRouter({}), FakeSandbox([]), task_id=result["task_id"])

    def test_existing_coding_loop_exposes_local_workflow(self):
        self.assertTrue(callable(CodingAgentLoop(self.store).repair_repository_with_local_model))


if __name__ == "__main__":
    unittest.main()
