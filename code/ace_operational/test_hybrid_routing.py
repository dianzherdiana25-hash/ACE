"""Unit tests for Dynamic Hybrid Routing in ModelRouter."""
import sys
from pathlib import Path

# Ensure code directory is at head of sys.path
_code_dir = Path(__file__).resolve().parent.parent
if str(_code_dir) not in sys.path:
    sys.path.insert(0, str(_code_dir))

import unittest
import tempfile
from unittest.mock import patch
from ace_operational.models_backend import ModelRouter
from ace_operational.store import OperationalStore


class TestDynamicHybridRouting(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="test-routing-")
        self.addCleanup(self.temp.cleanup)
        self.tmp_dir = Path(self.temp.name)
        self.store = OperationalStore(workspace=self.tmp_dir)
        self.addCleanup(self.store.close)
        self.router = ModelRouter(self.store)
        self.discovery = patch.object(self.router, "discover_local_gguf", return_value={
            "ready": False, "valid_models": [], "llama_binary": "", "server_healthy": False,
        })
        self.discovery.start()
        self.addCleanup(self.discovery.stop)

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
        self.assertFalse(res["success"])
        self.assertEqual(res["error_code"], "UNSUPPORTED_DETERMINISTIC_INFERENCE")
        self.assertEqual(res["text"], "")

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
        self.assertFalse(res["success"])
        self.assertEqual(res["backend_used"], "unavailable")
        self.assertEqual(res["error_code"], "NO_LOCAL_MODEL")


if __name__ == "__main__":
    unittest.main()
