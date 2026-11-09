"""Unit tests for ACE Real-World Capability Domain."""
from __future__ import annotations

import unittest
from pathlib import Path
import tempfile

from ace_real_world.log_parser_synth import LogParserSynthesizer
from ace_real_world.system_tool_synth import SystemToolSynthesizer
from ace_real_world.data_wrangler_synth import DataWranglerSynthesizer


class TestRealWorldSynthesis(unittest.TestCase):
    def test_log_parser_synthesis(self):
        synth = LogParserSynthesizer()
        samples = [
            "2026-11-09T17:00:00Z [INFO] worker_1 200 SUCCESS",
            "2026-11-09T17:01:00Z [ERROR] worker_2 500 FAILED",
            "2026-11-09T17:02:00Z [WARN] worker_3 404 NOT_FOUND",
        ]
        expected = [
            {"time": "2026-11-09T17:00:00Z", "level": "[INFO]", "code": "200"},
            {"time": "2026-11-09T17:01:00Z", "level": "[ERROR]", "code": "500"},
            {"time": "2026-11-09T17:02:00Z", "level": "[WARN]", "code": "404"},
        ]
        rule = synth.synthesize_regex_parser(samples, expected)
        self.assertIsNotNone(rule)
        self.assertIn("def parse_log_entry", rule.extractor_code)

        # Execute synthesized code
        scope = {}
        exec(rule.extractor_code, scope)
        parsed = scope["parse_log_entry"](samples[0])
        self.assertEqual(parsed["code"], "200")
        self.assertEqual(parsed["level"], "[INFO]")

    def test_system_tool_sanitizer(self):
        synth = SystemToolSynthesizer()
        rule = synth.synthesize_safe_executor("git", {"status": "str", "branch": "str"})
        self.assertIsNotNone(rule)
        self.assertIn("FORBIDDEN_METACHARS", rule.sanitizer_code)

        scope = {}
        exec(rule.sanitizer_code, scope)
        fn = scope["safe_execute_command"]

        # Disallow injection
        with self.assertRaises(ValueError):
            fn({"status": "clean; rm -rf /"})

    def test_data_wrangler_synthesis(self):
        synth = DataWranglerSynthesizer()
        examples = [
            ("user_id: 10928, name: alice", "10928"),
            ("user_id: 20491, name: bob", "20491"),
            ("user_id: 30192, name: charlie", "30192"),
        ]
        rule = synth.synthesize_string_transform(examples)
        self.assertIsNotNone(rule)

        scope = {}
        exec(rule.transform_code, scope)
        self.assertEqual(scope["transform_data_field"]("user_id: 99999, name: eve"), "99999")


if __name__ == "__main__":
    unittest.main()
