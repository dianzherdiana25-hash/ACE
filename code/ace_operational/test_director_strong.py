"""Stage-1 evidence: director-strong registration + origin discipline."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from ace_operational.brain_registry import BrainRegistry
from ace_operational.director_strong import (
    DIRECTOR_CAPABILITIES,
    SMOKE_RECORD,
    brain_of_origin,
    register_director_strong,
)


class DirectorStrongTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ace-dstrong-")
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "brains.json"
        self.registry = BrainRegistry(self.path)

    def test_both_organs_registered_active_director_only(self):
        records = register_director_strong(self.registry)
        self.assertEqual([r["brain_id"] for r in records],
                         ["director-strong-groq", "director-strong-gemini"])
        for record in records:
            self.assertEqual(record["status"], "active")
            self.assertEqual(record["kind"], "external-director")
            self.assertEqual(record["capabilities"],
                             list(DIRECTOR_CAPABILITIES))
            # the measurement path is not a director capability
            self.assertNotIn("measurement", record["capabilities"])
            self.assertNotIn("judge", record["capabilities"])

    def test_registration_persists_and_is_replayable(self):
        register_director_strong(self.registry)
        reloaded = BrainRegistry(self.path)
        self.assertIsNotNone(reloaded.get("director-strong-groq"))
        self.assertIsNotNone(reloaded.get("director-strong-gemini"))
        kinds = [e["kind"] for e in reloaded.events()]
        self.assertEqual(kinds, ["registered", "registered"])

    def test_reregistration_keeps_two_brains(self):
        register_director_strong(self.registry)
        register_director_strong(self.registry)
        self.assertEqual(len(self.registry.brains()), 2)

    def test_dismissal_is_fail_closed_and_local_unaffected(self):
        self.registry.register("front-local", kind="local-gguf",
                               descriptor="Qwen3.5-4B-MTP")
        register_director_strong(self.registry)
        self.registry.dismiss("director-strong-groq", reason="drill")
        self.assertTrue(self.registry.is_dismissed("groq"))
        self.assertFalse(self.registry.is_dismissed("Qwen3.5-4B"))

    def test_brain_of_origin_format(self):
        self.assertEqual(brain_of_origin("groq", "openai/gpt-oss-120b"),
                         "groq/openai/gpt-oss-120b")
        self.assertEqual(brain_of_origin("gemini", "gemini-2.5-pro"),
                         "gemini/gemini-2.5-pro")
        self.assertEqual(SMOKE_RECORD["brain_of_origin"],
                         "groq/openai/gpt-oss-120b")

    def test_brain_of_origin_refuses_unregistered_provider(self):
        with self.assertRaises(ValueError):
            brain_of_origin("freellm", "gpt-oss-120b")
        with self.assertRaises(ValueError):
            brain_of_origin("local", "Qwen3.5-4B")
        with self.assertRaises(ValueError):
            brain_of_origin("groq", "  ")


if __name__ == "__main__":
    unittest.main()
