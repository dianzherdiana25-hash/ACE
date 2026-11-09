"""Unit tests for ACE Real-World Capability Domain."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ace_real_world.log_parser_synth import LogParserSynthesizer
from ace_real_world.system_tool_synth import SystemToolSynthesizer
from ace_real_world.data_wrangler_synth import DataWranglerSynthesizer
from ace_real_world.git_analyzer_synth import GitAnalyzerSynthesizer
from ace_real_world.process_sentinel import ProcessSentinel
from ace_real_world.net_client_synth import NetClientSynthesizer
from ace_real_world.mission_integration import RealWorldMissionIntegrator
from ace_mission.bus import MissionBus


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

    def test_git_analyzer(self):
        repo_root = Path(__file__).resolve().parent.parent.parent
        analyzer = GitAnalyzerSynthesizer(str(repo_root))
        metrics = analyzer.compute_codebase_metrics()
        self.assertGreater(metrics.total_commits, 0)
        self.assertGreater(metrics.total_python_files, 0)
        self.assertGreater(metrics.total_loc, 100)

    def test_process_sentinel(self):
        sentinel = ProcessSentinel()
        if sentinel.is_available():
            load = sentinel.audit_system_load()
            self.assertIn("load_1m", load)
            self.assertIn("total_python_rss_mb", load)

    def test_net_client_synthesis(self):
        synth = NetClientSynthesizer()
        rule = synth.synthesize_json_client(
            endpoint_url="http://localhost:8080/api/data",
            expected_keys=["heartbeat", "research_state"],
        )
        self.assertIsNotNone(rule)
        self.assertIn("def query_api_endpoint", rule.client_code)

    def test_mission_integration(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            bus_file = Path(tmp_dir) / "bus.sqlite3"
            bus = MissionBus(str(bus_file))
            repo_root = Path(__file__).resolve().parent.parent.parent
            integrator = RealWorldMissionIntegrator(bus, str(repo_root))

            missions = integrator.generate_real_world_missions()
            self.assertEqual(len(missions), 3)

            # Claim and execute first mission
            m_id = missions[0]["mission_id"]
            res = integrator.execute_real_world_mission(m_id)
            self.assertEqual(res["status"], "COMPLETED")
            self.assertTrue(res["receipt"]["passed"])


if __name__ == "__main__":
    unittest.main()
