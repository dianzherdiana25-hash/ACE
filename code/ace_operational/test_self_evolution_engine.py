"""Unit tests for ACE Self-Evolution Engine."""
import sys
from pathlib import Path

_code_dir = Path(__file__).resolve().parent.parent
if str(_code_dir) not in sys.path:
    sys.path.insert(0, str(_code_dir))

import unittest
from ace_operational.models_backend import ModelRouter
from ace_operational.self_evolution_engine import SelfEvolutionEngine
from ace_operational.store import OperationalStore


class TestSelfEvolutionEngine(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path("/tmp/test_self_evolution_workspace")
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        self.store = OperationalStore(workspace=self.tmp_dir)
        self.router = ModelRouter(self.store)
        self.engine = SelfEvolutionEngine(self.store, self.router, code_root=_code_dir)

    def test_audit_internal_codebase(self):
        audit = self.engine.audit_internal_codebase()
        self.assertGreater(audit["total_python_files"], 5)
        self.assertGreater(audit["total_lines_of_code"], 1000)
        self.assertEqual(audit["syntax_errors_count"], 0)
        self.assertTrue(audit["codebase_clean"])
        self.assertEqual(audit["health_score"], 100.0)

    def test_benchmark_cognitive_inference(self):
        bench = self.engine.benchmark_cognitive_inference()
        self.assertTrue(bench["backend_healthy"])
        self.assertGreaterEqual(bench["latency_seconds"], 0.0)
        self.assertIn("throughput_tokens_per_sec", bench)

    def test_verify_and_promote_capabilities(self):
        promoted = self.engine.verify_and_promote_self_capabilities()
        self.assertGreaterEqual(len(promoted), 2)
        frontier_items = {c["capability_id"]: c for c in self.store.list_frontier()}
        self.assertIn("cap_self_codebase_auditor", frontier_items)
        self.assertIn("cap_dynamic_hybrid_router", frontier_items)
        self.assertEqual(frontier_items["cap_self_codebase_auditor"]["status"], "KNOWN_AND_TESTED")

    def test_run_evolution_cycle(self):
        cycle = self.engine.run_evolution_cycle()
        self.assertIn("duration_seconds", cycle)
        self.assertTrue(cycle["code_health"]["codebase_clean"])
        self.assertIn("self_improvement_proposal", cycle)
        self.assertTrue(self.engine.status_path.exists())


if __name__ == "__main__":
    unittest.main()
