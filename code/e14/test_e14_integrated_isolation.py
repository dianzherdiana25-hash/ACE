"""Issue #13 worker mount and fail-closed isolation adapter tests."""
import tempfile
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from e13.contract import canonical_json
from .e14_integrated_graph import DurableGraphBudget, graph_oracle
from .e14_integrated_isolation import (
    FORBIDDEN, WORKER_FILES, execute_isolated, validate_worker_mount,
    worker_invoke, worker_stage,
)
from .e14_shared_budget import BudgetContractError

WORD = (1,2,1,1,2,2,1)
ARTIFACT = {"kind":"edge-relative-word-v1","word":list(WORD),"source_sha256":"0"*64}


class WorkerMountTests(unittest.TestCase):
    def test_worker_mount_has_no_evaluator_source(self):
        with worker_stage() as root:
            files = {p.name for p in (root/"e14").iterdir()}
            self.assertEqual(files, {"__init__.py", *WORKER_FILES})
            self.assertFalse((root/"e14/e14_integrated_graph.py").exists())
            self.assertFalse((root/"e14/e14p_graph.py").exists())
            self.assertFalse((root/"e14/e14_integrated_isolation.py").exists())
            self.assertEqual({p.name for p in (root/"e13").iterdir()},
                             {"__init__.py", "contract.py"})

    def test_worker_stage_imports_policy_without_evaluator(self):
        # Functional import smoke only, not an isolation security claim.
        with worker_stage() as root:
            code = ("import sys;sys.path.insert(0,sys.argv[1]);"
                    "from e14.e14_integrated_policy import mapped_only_policy;"
                    "assert callable(mapped_only_policy)")
            result = subprocess.run([sys.executable, "-I", "-B", "-S", "-c",
                                     code, str(root)], capture_output=True, text=True,
                                    timeout=10, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_isolated_execution_requires_native_boundary(self):
        with tempfile.TemporaryDirectory() as temp:
            journal = DurableGraphBudget(Path(temp)/"j.sqlite", "test:active")
            with patch("e14.e14_integrated_isolation.validate_boundary",
                       side_effect=RuntimeError("native Bubblewrap unavailable")):
                with self.assertRaisesRegex(RuntimeError,"Bubblewrap"):
                    execute_isolated(journal, ARTIFACT, "active", lambda _:None)
            self.assertEqual(journal.snapshot()["purchased"],0)

    def test_worker_response_rejects_forged_cost_and_bad_action(self):
        def fake(_args, _payload, *, solver):
            return canonical_json({"action":{"action":"query","stage":"diagnosis",
                "graph":{"nodes":True,"start":0,"goal":1,"edges":[[0,1,0,1]]}},
                "cpu_us":10,"rss_kib":200}),100
        with worker_stage() as root, patch("e14.e14_integrated_isolation._sandbox_python",fake):
            with self.assertRaises(BudgetContractError):
                worker_invoke(root, {"artifact":ARTIFACT,"mode":"active","view":{"receipts":[],"remaining":4}})

    def test_mount_probe_denies_any_evaluator_module(self):
        def fake(_args, _payload=b"", *, solver):
            return canonical_json({name:True for name in FORBIDDEN}),100
        with worker_stage() as root, patch("e14.e14_integrated_isolation.validate_boundary",
                                          return_value={"native_elf":True}), patch(
                                              "e14.e14_integrated_isolation._sandbox_python",fake):
            self.assertEqual(len(validate_worker_mount(root)),len(FORBIDDEN))

    def test_mount_probe_fails_on_one_leaked_evaluator(self):
        def fake(_args, _payload=b"", *, solver):
            return canonical_json({name:name != FORBIDDEN[0] for name in FORBIDDEN}),100
        with worker_stage() as root, patch("e14.e14_integrated_isolation.validate_boundary",
                                          return_value={"native_elf":True}), patch(
                                              "e14.e14_integrated_isolation._sandbox_python",fake):
            with self.assertRaisesRegex(RuntimeError,"can import trusted evaluator"):
                validate_worker_mount(root)

    def test_fake_sandbox_action_flow_reuses_one_label(self):
        # Tests orchestration only; monkeypatch is NOT evidence of native isolation.
        from .e14_integrated_policy import mapped_only_policy
        with tempfile.TemporaryDirectory() as temp:
            journal = DurableGraphBudget(Path(temp)/"j.sqlite","world:active")
            def fake(_args, payload=b"", *, solver):
                packet = __import__("json").loads(payload)
                action = mapped_only_policy(packet["artifact"],packet["mode"])(packet["view"])
                return canonical_json({"action":action,"cpu_us":10,"rss_kib":300}),100
            with patch("e14.e14_integrated_isolation.validate_boundary",
                       return_value={"native_elf":True}), patch(
                           "e14.e14_integrated_isolation._sandbox_python",fake):
                result = execute_isolated(journal,ARTIFACT,"active",
                                          lambda graph:graph_oracle(graph,WORD))
            self.assertEqual(result["decision"],"accept")
            self.assertEqual(result["actions"][-1]["word"],list(WORD))
            self.assertLessEqual(journal.snapshot()["purchased"],3)
            self.assertTrue(result["isolation_checks"])

if __name__ == "__main__":
    unittest.main()
