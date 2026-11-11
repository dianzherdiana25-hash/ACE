"""Unit tests for Dynamic Hybrid Routing in ModelRouter."""
import sys
from pathlib import Path

# Ensure code directory is at head of sys.path
_code_dir = Path(__file__).resolve().parent.parent
if str(_code_dir) not in sys.path:
    sys.path.insert(0, str(_code_dir))

import unittest
from ace_operational.models_backend import ModelRouter
from ace_operational.store import OperationalStore


class TestDynamicHybridRouting(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path("/tmp/test_routing_workspace")
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        self.store = OperationalStore(workspace=self.tmp_dir)
        self.router = ModelRouter(self.store)

    def test_classify_task_tier(self):
        self.assertEqual(self.router.classify_task_tier("Mohon buatkan arsitektur desain sistem multi-agent"), "deep")
        self.assertEqual(self.router.classify_task_tier("Buatkan snippet fungsi cepat untuk konversi suhu"), "fast")
        self.assertEqual(self.router.classify_task_tier("Validasi regex dan perbaiki format schema json"), "deterministic")
        self.assertEqual(self.router.classify_task_tier("Tuliskan implementasi lengkap full-stack"), "deep")

    def test_deterministic_tier_execution(self):
        res = self.router.generate_text(
            [{"role": "user", "content": "Perbaiki lint dan format AST schema json"}],
            tier="deterministic",
        )
        self.assertEqual(res["tier_used"], "deterministic")
        self.assertEqual(res["backend_used"], "local-deterministic-v4")
        self.assertIn("pemrosesan AST", res["text"])

    def test_auto_classification_in_generate_text(self):
        res = self.router.generate_text(
            [{"role": "user", "content": "Perbaiki skema format json ast"}],
        )
        self.assertEqual(res["tier_used"], "deterministic")

    def test_deep_tier_routes_to_server_or_fallback(self):
        res = self.router.generate_text(
            [{"role": "user", "content": "Rancang arsitektur sistem full-stack"}],
            tier="deep",
            max_tokens=16,
        )
        self.assertTrue(
            res["backend_used"].startswith("local-gguf-server")
            or res["backend_used"].startswith("local-deterministic")
        )


if __name__ == "__main__":
    unittest.main()
