"""Development-only controls for Ollama -> coding agent delegation.

These tests never contact Ollama, Codex, Antigravity, or a paid provider.
They validate orchestration contracts, not real autonomous coding success.
"""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ace_operational.agent_fabric import (
    AgentDirector, CLIWorker, OllamaLocalPlanner, WorkOrder, WorkPlan,
    WorkerResult, validate_work_plan, require_isolated_worktree,
)


def sample_payload(*, worker="codex", mode="read-only"):
    return {"orders": [
        {
            "id": "inspect", "worker": worker, "mode": mode,
            "instruction": "Inspect unfamiliar repository for one bug",
            "depends_on": [],
        }
    ]}


class WorkPlanTests(unittest.TestCase):
    def test_valid_multiagent_dag(self):
        p = sample_payload()
        p["orders"].append({
            "id": "implement", "worker": "antigravity", "mode": "workspace-write",
            "instruction": "Implement a regression repair", "depends_on": ["inspect"],
        })
        plan = validate_work_plan("Fix the bug", p, planner="ollama:qwen3-coder")
        self.assertEqual([o.order_id for o in plan.orders], ["inspect", "implement"])
        self.assertEqual(plan.orders[1].depends_on, ("inspect",))
        self.assertEqual(plan.plan_digest, validate_work_plan(
            "Fix the bug", p, planner="ollama:qwen3-coder"
        ).plan_digest)

    def test_reject_unknown_worker_and_extra_command_field(self):
        p = sample_payload(worker="unauthorized-shell")
        with self.assertRaises(ValueError):
            validate_work_plan("Check code", p, planner="ollama")
        p = sample_payload()
        p["orders"][0]["shell"] = "rm -rf ~"
        with self.assertRaises(ValueError):
            validate_work_plan("Check code", p, planner="ollama")

    def test_reject_forward_dependency_and_duplicate_ids(self):
        p = sample_payload()
        p["orders"][0]["depends_on"] = ["future"]
        with self.assertRaises(ValueError):
            validate_work_plan("Check code", p, planner="ollama")
        p = sample_payload()
        p["orders"].append(dict(p["orders"][0]))
        with self.assertRaises(ValueError):
            validate_work_plan("Check code", p, planner="ollama")

    def test_reject_excess_steps_and_unbounded_prompt(self):
        p = sample_payload()
        p["orders"] *= 9
        with self.assertRaises(ValueError):
            validate_work_plan("Check code", p, planner="ollama")
        p = sample_payload()
        p["orders"][0]["instruction"] = "x" * 6001
        with self.assertRaises(ValueError):
            validate_work_plan("Check code", p, planner="ollama")

    def test_nonloopback_model_endpoint_forbidden(self):
        for endpoint in ("http://10.1.2.3:11434/api/chat",
                         "https://127.0.0.1:11434/api/chat",
                         "http://localhost:11434/api/pull",
                         "http://127.0.0.1:11434/api/chat?token=leak"):
            with self.subTest(endpoint=endpoint):
                with self.assertRaises(ValueError):
                    OllamaLocalPlanner(endpoint=endpoint)


class OllamaTests(unittest.TestCase):
    def test_local_http_json_schema_request_and_validated_plan(self):
        response = SimpleNamespace(
            status=200,
            read=lambda max_bytes: json.dumps({
                "message": {"content": json.dumps(sample_payload())}
            }).encode("utf-8"),
        )
        with patch("ace_operational.agent_fabric.http.client.HTTPConnection") as conn:
            conn.return_value.getresponse.return_value = response
            planner = OllamaLocalPlanner(model="qwen3-coder")
            plan = planner.plan("Inspect unfamiliar code")
            self.assertEqual(plan.orders[0].worker, "codex")
            args = conn.return_value.request.call_args
            self.assertEqual(args.args[0:2], ("POST", "/api/chat"))
            body = json.loads(args.kwargs["body"])
            self.assertEqual(body["model"], "qwen3-coder")
            self.assertIsInstance(body["format"], dict)
            self.assertFalse(body["stream"])
            conn.return_value.close.assert_called_once()

    def test_local_model_malformed_response_is_not_execution_authority(self):
        for bad in ({"orders": []}, {"orders": [{"worker": "shell"}]}):
            response = SimpleNamespace(
                status=200,
                read=lambda n, candidate=bad: json.dumps({
                    "message": {"content": json.dumps(candidate)}
                }).encode(),
            )
            with patch("ace_operational.agent_fabric.http.client.HTTPConnection") as conn:
                conn.return_value.getresponse.return_value = response
                with self.assertRaises(ValueError):
                    OllamaLocalPlanner().plan("Fix unfamiliar issue")

    def test_non_200_model_response_fails(self):
        with patch("ace_operational.agent_fabric.http.client.HTTPConnection") as conn:
            conn.return_value.getresponse.return_value = SimpleNamespace(status=503)
            with self.assertRaises(RuntimeError):
                OllamaLocalPlanner().plan("Do the work")


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "worktree"
        self.root.mkdir()
        (self.root / ".git").write_text(
            "gitdir: " + str(Path(self.tmp.name) / "git" / "worktrees" / "worktree"),
            encoding="utf-8",
        )

    def tearDown(self):
        self.tmp.cleanup()

    def order(self, worker="codex", mode="read-only"):
        return WorkOrder("inspect", worker, mode, "Inspect x; && echo injected",
                         ())

    def test_reject_plain_checkout(self):
        (self.root / ".git").unlink()
        (self.root / ".git").mkdir()
        with self.assertRaises(ValueError):
            require_isolated_worktree(self.root)

    def test_codex_argv_is_not_shell_and_requires_terminal_receipt(self):
        events = [
            {"type": "item.completed", "item": {
                "type": "agent_message", "text": "Found a bug"}},
            {"type": "turn.completed", "usage": {"input_tokens": 100}},
        ]
        completed = SimpleNamespace(
            returncode=0, stdout="\n".join(json.dumps(e) for e in events),
            stderr="",
        )
        with patch("ace_operational.agent_fabric.subprocess.run", return_value=completed) as run:
            result = CLIWorker().run(self.order(), self.root)
            self.assertTrue(result.success)
            self.assertEqual(result.response, "Found a bug")
            self.assertEqual(result.usage["input_tokens"], 100)
            args = run.call_args
            self.assertEqual(args.args[0][0:2], ["codex", "exec"])
            self.assertIn("--sandbox", args.args[0])
            self.assertIn("read-only", args.args[0])
            self.assertFalse(args.kwargs.get("shell", False))
            self.assertIn("&& echo injected", args.kwargs["input"])

    def test_codex_no_terminal_event_is_not_success(self):
        completed = SimpleNamespace(
            returncode=0, stdout=json.dumps({"type": "thread.started"}),
            stderr="",
        )
        with patch("ace_operational.agent_fabric.subprocess.run", return_value=completed):
            result = CLIWorker().run(self.order(), self.root)
            self.assertFalse(result.success)

    def test_antigravity_read_only_headless_json(self):
        completed = SimpleNamespace(
            returncode=0,
            stdout=json.dumps({"status": "SUCCESS", "response": "Reviewed changes",
                               "usage": {"total_tokens": 321}}),
            stderr="",
        )
        with patch("ace_operational.agent_fabric.subprocess.run", return_value=completed) as run:
            result = CLIWorker().run(self.order("antigravity"), self.root)
            self.assertTrue(result.success)
            self.assertEqual(result.usage["total_tokens"], 321)
            argv = run.call_args.args[0]
            self.assertEqual(argv[0], "agy")
            self.assertIn("--output-format", argv)
            self.assertIn("--sandbox", argv)
            self.assertIn("--mode=plan", argv)
            self.assertNotIn("--dangerously-skip-permissions", argv)

    def test_antigravity_write_has_sandbox_not_permission_bypass(self):
        completed = SimpleNamespace(
            returncode=0, stdout=json.dumps({
                "status": "SUCCESS", "response": "Noted"
            }), stderr="",
        )
        with patch("ace_operational.agent_fabric.subprocess.run", return_value=completed) as run:
            CLIWorker().run(self.order("antigravity", "workspace-write"), self.root)
            argv = run.call_args.args[0]
            self.assertIn("--mode=auto", argv)
            self.assertIn("--sandbox", argv)
            self.assertNotIn("--dangerously-skip-permissions", argv)

    def test_antigravity_non_success_json_rejected_even_exit_zero(self):
        completed = SimpleNamespace(
            returncode=0,
            stdout=json.dumps({"status": "ERROR", "error": "authentication required"}),
            stderr="authentication required",
        )
        with patch("ace_operational.agent_fabric.subprocess.run", return_value=completed):
            result = CLIWorker().run(self.order("antigravity"), self.root)
            self.assertFalse(result.success)

    def test_uninstalled_worker_fails_closed(self):
        with patch("ace_operational.agent_fabric.subprocess.run",
                   side_effect=FileNotFoundError()):
            with self.assertRaises(RuntimeError):
                CLIWorker().run(self.order(), self.root)


class FakeWorker:
    def __init__(self, fail_on=None):
        self.calls = []
        self.fail_on = fail_on

    def run(self, order, root):
        self.calls.append(order.order_id)
        return WorkerResult(
            worker=order.worker,
            success=order.order_id != self.fail_on,
            response="performed an operation",
            stdout_digest="a" * 64,
            stderr_digest="b" * 64,
            exit_code=1 if order.order_id == self.fail_on else 0,
            usage={},
        )


class DirectorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "worktree"
        self.root.mkdir()
        (self.root / ".git").write_text(
            "gitdir: " + str(Path(self.tmp.name) / "git" / "worktrees" / "worktree")
        )
        self.plan = validate_work_plan("Inspect and repair", {
            "orders": [
                {"id": "inspect", "worker": "codex", "mode": "read-only",
                 "instruction": "Find failing test", "depends_on": []},
                {"id": "repair", "worker": "antigravity",
                 "mode": "workspace-write",
                 "instruction": "Fix a reproducible bug", "depends_on": ["inspect"]},
            ],
        }, planner="ollama")

    def tearDown(self):
        self.tmp.cleanup()

    def test_no_authorization_means_no_worker_calls(self):
        worker = FakeWorker()
        result = AgentDirector(worker, verifier=lambda o, r, x: True).execute(
            self.plan, self.root
        )
        self.assertEqual(result.status, "NOT_AUTHORIZED")
        self.assertEqual(worker.calls, [])

    def test_no_write_permission_means_no_partial_execution(self):
        worker = FakeWorker()
        result = AgentDirector(worker, verifier=lambda o, r, x: True).execute(
            self.plan, self.root, authorized=True
        )
        self.assertEqual(result.status, "WRITE_NOT_AUTHORIZED")
        self.assertEqual(worker.calls, [])

    def test_no_host_verifier_means_no_execution(self):
        worker = FakeWorker()
        result = AgentDirector(worker).execute(
            self.plan, self.root, authorized=True, allow_write=True
        )
        self.assertEqual(result.status, "NO_HOST_VERIFIER")
        self.assertEqual(worker.calls, [])

    def test_explicit_verifier_accepts_each_step(self):
        worker = FakeWorker()
        calls = []
        def verify(order, root, result):
            calls.append(order.order_id)
            return result.success

        result = AgentDirector(worker, verifier=verify).execute(
            self.plan, self.root, authorized=True, allow_write=True
        )
        self.assertEqual(result.status, "LOCALLY_VERIFIED")
        self.assertTrue(result.execution_performed)
        self.assertEqual(result.completed_ids, ("inspect", "repair"))
        self.assertEqual(worker.calls, ["inspect", "repair"])
        self.assertEqual(calls, ["inspect", "repair"])
        self.assertEqual(len(result.receipts), 2)
        self.assertEqual(result.receipts[0]["scientific_status"], "NOT_ASSESSED")

    def test_failed_worker_prevents_dependent_run(self):
        worker = FakeWorker(fail_on="inspect")
        result = AgentDirector(worker, verifier=lambda o, r, x: True).execute(
            self.plan, self.root, authorized=True, allow_write=True
        )
        self.assertEqual(result.status, "REJECTED")
        self.assertEqual(worker.calls, ["inspect"])
        self.assertEqual(result.completed_ids, ())

    def test_host_verifier_veto_blocks_next_agent(self):
        worker = FakeWorker()
        result = AgentDirector(worker, verifier=lambda o, r, x: False).execute(
            self.plan, self.root, authorized=True, allow_write=True
        )
        self.assertEqual(result.status, "REJECTED")
        self.assertEqual(worker.calls, ["inspect"])
        self.assertFalse(result.receipts[0]["host_verification_passed"])

    def test_director_step_limit_fail_closed(self):
        worker = FakeWorker()
        result = AgentDirector(worker, verifier=lambda o, r, x: True).execute(
            self.plan, self.root, authorized=True, allow_write=True,
            max_steps=1,
        )
        self.assertEqual(result.status, "BUDGET_EXCEEDED")
        self.assertEqual(worker.calls, [])


if __name__ == "__main__":
    unittest.main()
