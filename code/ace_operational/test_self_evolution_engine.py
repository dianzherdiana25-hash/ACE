"""Unit tests for ACE Self-Evolution Engine."""
import sys
from pathlib import Path

_code_dir = Path(__file__).resolve().parent.parent
if str(_code_dir) not in sys.path:
    sys.path.insert(0, str(_code_dir))

import unittest
import tempfile
from unittest.mock import patch
from ace_operational.models_backend import ModelRouter
from ace_operational.self_evolution_engine import SelfEvolutionEngine
from ace_operational.store import OperationalStore


class TestSelfEvolutionEngine(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="ace-self-evolution-test-")
        self.addCleanup(tmp.cleanup)
        self.tmp_dir = Path(tmp.name)
        environment = patch.dict("os.environ", {"ACE_MODEL_CACHE": str(self.tmp_dir / "models")})
        environment.start()
        self.addCleanup(environment.stop)
        self.store = OperationalStore(workspace=self.tmp_dir)
        self.addCleanup(self.store.close)
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
        with patch.object(self.router, "health_check", return_value={"local_gguf": {"ready": False}}), \
                patch.object(self.router, "generate_text", return_value={
                    "success": False, "status": "FAILED", "text": "", "error_code": "NO_LOCAL_MODEL",
                }):
            bench = self.engine.benchmark_cognitive_inference()
        self.assertFalse(bench["backend_healthy"])
        self.assertEqual(bench["status"], "HOLD")
        self.assertEqual(bench["error_code"], "NO_LOCAL_MODEL")
        self.assertEqual(bench["throughput_tokens_per_sec"], 0)
        self.assertGreaterEqual(bench["latency_seconds"], 0.0)

    def test_inference_health_requires_output_identity_and_recorded_success(self):
        result = {"success": True, "status": "SUCCESS", "text": "Fungsi rekursif faktorial.",
                  "backend_used": "local-gguf:fixture", "model": {"id": "fixture-model"},
                  "evidence_event_id": "evt-fixture", "inference_id": "inf-fixture"}
        with patch.object(self.router, "health_check", return_value={"local_gguf": {"ready": True}}), \
                patch.object(self.router, "generate_text", return_value=result):
            bench = self.engine.benchmark_cognitive_inference()
        self.assertTrue(bench["backend_healthy"])
        self.assertEqual(bench["status"], "PASS")
        self.assertTrue(bench["throughput_is_estimate"])
        self.assertFalse(bench["task_verified"])
        self.assertEqual(bench["evidence_event_id"], "evt-fixture")
        for change in ({"success": False}, {"status": "FAILED"}, {"text": ""},
                       {"model": None}, {"evidence_event_id": None},
                       {"backend_used": "local-deterministic-v4"}):
            with self.subTest(change=change), \
                    patch.object(self.router, "health_check", return_value={"local_gguf": {"ready": True}}), \
                    patch.object(self.router, "generate_text", return_value={**result, **change}):
                self.assertFalse(self.engine.benchmark_cognitive_inference()["backend_healthy"])

    def test_verify_and_promote_capabilities(self):
        promoted = self.engine.verify_and_promote_self_capabilities()
        self.assertGreaterEqual(len(promoted), 2)
        frontier_items = {c["capability_id"]: c for c in self.store.list_frontier()}
        self.assertIn("cap_self_codebase_auditor", frontier_items)
        self.assertIn("cap_dynamic_hybrid_router", frontier_items)
        self.assertEqual(frontier_items["cap_self_codebase_auditor"]["status"], "KNOWN_AND_TESTED")
        self.assertNotIn("cap_software_factory", frontier_items)
        self.assertNotIn("cap_software_factory", {entry["id"] for entry in promoted})

    def test_legacy_factory_marker_requires_retest_without_rewriting_real_evidence(self):
        for evidence, expected in (("verified:software_factory_end_to_end_pass", "RETEST_REQUIRED"),
                                   ("rcpt-real-factory-run", "KNOWN_AND_TESTED")):
            with self.subTest(evidence=evidence):
                self.store.set_frontier_capability(
                    capability_id="cap_software_factory", name_id="Software Factory", category="coding",
                    status="KNOWN_AND_TESTED", evidence_ref=evidence,
                )
                promoted = self.engine.verify_and_promote_self_capabilities()
                frontier = {c["capability_id"]: c for c in self.store.list_frontier()}
                self.assertEqual(frontier["cap_software_factory"]["status"], expected)
                self.assertNotIn("cap_software_factory", {entry["id"] for entry in promoted})
                if expected == "KNOWN_AND_TESTED":
                    self.assertEqual(frontier["cap_software_factory"]["evidence_ref"], evidence)

    def test_run_evolution_cycle(self):
        with patch.object(self.router, "health_check", return_value={"local_gguf": {"ready": False}}), \
                patch.object(self.router, "generate_text", return_value={
                    "success": False, "status": "FAILED", "text": "", "error_code": "NO_LOCAL_MODEL",
                }):
            cycle = self.engine.run_evolution_cycle()
        self.assertIn("duration_seconds", cycle)
        self.assertTrue(cycle["code_health"]["codebase_clean"])
        self.assertFalse(cycle["inference_bench"]["backend_healthy"])
        self.assertIn("HOLD", cycle["self_improvement_proposal"]["recommendation"])
        self.assertIn("self_improvement_proposal", cycle)
        self.assertTrue(self.engine.status_path.exists())


if __name__ == "__main__":
    unittest.main()
