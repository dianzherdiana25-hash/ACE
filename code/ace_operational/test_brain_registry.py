"""Stage G evidence: brain registry lifecycle + router dismissal
enforcement (the dismissal drill's unit-level half)."""
from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ace_operational.brain_registry import BrainRegistry
from ace_operational.models_backend import ModelRouter
from ace_operational.store import OperationalStore


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ace-brains-")
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "brains.json"
        self.registry = BrainRegistry(self.path)
        self.registry.register("qwen3-8b", kind="local-gguf",
                               descriptor="Qwen3-8B-Q4_K_M.gguf")
        self.registry.register("claude", kind="external",
                               descriptor="claude",
                               status="declared-unavailable")

    def test_dismissal_is_recorded_and_persistent(self):
        self.registry.dismiss("qwen3-8b", reason="drill")
        self.assertTrue(self.registry.is_dismissed("Qwen3-8B"))
        reloaded = BrainRegistry(self.path)
        self.assertTrue(reloaded.is_dismissed("qwen3-8b-q4"))
        kinds = [e["kind"] for e in reloaded.events()]
        self.assertEqual(kinds, ["registered", "registered",
                                 "dismissed"])

    def test_declared_unavailable_is_not_dismissed(self):
        self.assertFalse(self.registry.is_dismissed("claude"))
        self.assertEqual(self.registry.get("claude")["status"],
                         "declared-unavailable")

    def test_reinstate_is_explicit_and_recorded(self):
        self.registry.dismiss("qwen3-8b", reason="drill")
        self.registry.reinstate("qwen3-8b", reason="drill complete")
        self.assertFalse(self.registry.is_dismissed("Qwen3-8B"))
        self.assertEqual(self.registry.events()[-1]["kind"],
                         "reinstated")


class RouterGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ace-brain-gate-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = OperationalStore(self.root / "workspace")
        self.addCleanup(self.store.close)
        self.env = patch.dict(os.environ,
                              {"ACE_MODEL_CACHE": str(self.root / "models"),
                               "ACE_DEFAULT_MODEL": "",
                               "ACE_LLAMA_CONTEXT": "4096",
                               "ACE_LLAMA_THREADS": "2"})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.router = ModelRouter(self.store)
        self.registry = BrainRegistry(self.root / "brains.json")
        self.registry.register("qwen3-8b", kind="local-gguf",
                               descriptor="Qwen3-8B-Q4_K_M.gguf")
        self.router.brain_registry = self.registry
        self.messages = [{"role": "user", "content": "Halo"}]

    def test_dismissed_brain_refused_before_any_inference(self):
        self.registry.dismiss("qwen3-8b", reason="drill")
        result = self.router.generate_text(
            self.messages, target_model="Qwen3-8B")
        self.assertFalse(result["success"])
        codes = [f["code"] for f in result["failures"]]
        self.assertIn("BRAIN_DISMISSED", codes)

    def test_active_brain_is_not_blocked_by_the_gate(self):
        # No backends exist in this fixture, so the call must fail —
        # but with a backend error, never BRAIN_DISMISSED.
        result = self.router.generate_text(
            self.messages, target_model="Qwen3-8B")
        codes = [f["code"] for f in result["failures"]]
        self.assertNotIn("BRAIN_DISMISSED", codes)


if __name__ == "__main__":
    unittest.main()
