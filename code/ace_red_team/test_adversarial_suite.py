"""Unit tests for ACE Red Team Adversarial Security & Robustness Suite.

Provenance: ADVISOR_AGENT
"""
from __future__ import annotations

import time
import unittest
from typing import Any, List, Tuple

from ace_red_team.adversarial_suite import (
    AdversarialDataPoisoner,
    ComplexityAttacker,
    ComplexityProfile,
    CountermeasureAdvisor,
    CyclicNode,
    FuzzPayloadGenerator,
    FuzzResult,
    FuzzerEngine,
    PoisonDetector,
    PoisonEvaluationResult,
    RedTeamAdversarialEngine,
    RedTeamReport,
    RedTeamVulnerability,
    SeverityLevel,
    VulnerabilityCategory,
)


class TestAdversarialSuite(unittest.TestCase):
    """Validation test suite for ACE Red Team Adversarial Engine."""

    def test_fuzz_payload_generator_completeness(self):
        """Verify all mandatory payload categories and edge cases are generated."""
        payloads = FuzzPayloadGenerator.get_all_payloads()
        required_categories = {
            "empty",
            "super_long",
            "non_ascii",
            "recursive_nesting",
            "stack_exhaustion",
            "cyclic_graph",
        }
        self.assertTrue(required_categories.issubset(set(payloads.keys())))

        # Verify empty payloads include empty string, bytes, and None
        empty_items = payloads["empty"]
        self.assertIn("", empty_items)
        self.assertIn(b"", empty_items)
        self.assertIn(None, empty_items)
        self.assertIn([], empty_items)
        self.assertIn({}, empty_items)

        # Verify super long includes large string and numbers
        long_items = payloads["super_long"]
        self.assertTrue(any(isinstance(x, str) and len(x) >= 10000 for x in long_items))
        self.assertTrue(any(isinstance(x, int) and x >= 2**63 - 1 for x in long_items))

        # Verify non-ascii includes multi-byte unicode, null bytes, and injection strings
        non_ascii = payloads["non_ascii"]
        self.assertTrue(any("admin\x00secret" in str(x) for x in non_ascii))
        self.assertTrue(any("TXT.EXE" in str(x) for x in non_ascii))
        self.assertTrue(any("alert(1)" in str(x) for x in non_ascii))

        # Verify cyclic graph contains self-referencing and cyclic nodes
        cyclic = payloads["cyclic_graph"]
        self.assertTrue(any(isinstance(x, CyclicNode) for x in cyclic))
        self.assertTrue(any(isinstance(x, dict) and x.get("self") is x for x in cyclic))

    def test_fuzzer_robust_target(self):
        """Verify that a defensively designed target survives fuzzing without crashes."""
        def robust_target(val: Any) -> str:
            # Safe defensive parser with bounds and recursion guards
            if val is None:
                return "NONE"
            if isinstance(val, (int, float, bool, bytes)):
                return f"SAFE_{val}"
            if isinstance(val, str):
                return f"SAFE_{val[:50]}"
            try:
                s = str(val)[:50]
                return f"SAFE_{s}"
            except (RecursionError, Exception):
                return "SAFE_GUARDED_RECURSION"

        engine = FuzzerEngine()
        res = engine.fuzz_target(robust_target, timeout_sec=0.2)
        self.assertGreater(res.total_tested, 25)
        self.assertEqual(res.crashes, 0)
        self.assertEqual(res.timeouts, 0)
        self.assertTrue(res.is_clean)
        self.assertEqual(len(res.vulnerabilities), 0)

    def test_fuzzer_crash_and_cycle_vulnerability_detection(self):
        """Verify that vulnerable recursive and cyclic code is caught and flagged."""
        def vulnerable_cyclic_visitor(val: Any) -> int:
            # Naive traversal without cycle tracking or depth limits
            if isinstance(val, (list, tuple)):
                return sum(vulnerable_cyclic_visitor(item) for item in val)
            if isinstance(val, dict):
                return sum(vulnerable_cyclic_visitor(v) for v in val.values())
            if isinstance(val, CyclicNode):
                return sum(vulnerable_cyclic_visitor(n) for n in val.neighbors)
            return 1

        engine = FuzzerEngine()
        res = engine.fuzz_target(vulnerable_cyclic_visitor, timeout_sec=0.2)
        self.assertGreater(res.crashes, 0)
        self.assertFalse(res.is_clean)

        vuln_categories = [v.category for v in res.vulnerabilities]
        self.assertTrue(
            VulnerabilityCategory.CYCLIC_GRAPH_CRASH.value in vuln_categories
            or VulnerabilityCategory.STACK_EXHAUSTION.value in vuln_categories
        )

    def test_adversarial_label_flipping(self):
        """Verify adversarial label flipping modifies targeted labels correctly."""
        data: List[Tuple[str, bool]] = [
            ("alpha", True),
            ("beta", False),
            ("gamma", True),
            ("delta", False),
            ("epsilon", True),
            ("zeta", False),
            ("eta", True),
            ("theta", False),
            ("iota", True),
            ("kappa", False),
        ]
        poisoned = AdversarialDataPoisoner.apply_label_flipping(data, poison_ratio=0.3, seed=123)
        self.assertEqual(len(poisoned), len(data))

        # Count differences in labels
        flipped_count = sum(1 for (orig_in, orig_lbl), (poi_in, poi_lbl) in zip(data, poisoned) if orig_lbl != poi_lbl)
        self.assertGreaterEqual(flipped_count, 1)
        self.assertLessEqual(flipped_count, 5)

        # Ensure input features were unchanged
        for (orig_in, _), (poi_in, _) in zip(data, poisoned):
            self.assertEqual(orig_in, poi_in)

    def test_backdoor_injection_and_detection(self):
        """Verify backdoor trigger insertion and anomaly detection."""
        data: List[Tuple[str, bool]] = [
            ("apple_fruit", False),
            ("orange_fruit", False),
            ("banana_fruit", False),
            ("grape_fruit", False),
            ("cherry_fruit", False),
            ("lemon_fruit", False),
            ("melon_fruit", False),
            ("berry_fruit", False),
        ]
        trigger = "BKDOOR_"
        train_p, test_bk = AdversarialDataPoisoner.apply_backdoor_injection(
            data,
            trigger=trigger,
            target_label=True,
            poison_ratio=0.5,
            seed=42,
        )

        self.assertEqual(len(train_p), len(data))
        self.assertEqual(len(test_bk), len(data))
        # Ensure test set has the backdoor trigger applied to all items
        for inp, lbl in test_bk:
            self.assertTrue(inp.startswith(trigger))
            self.assertTrue(lbl)

        # Test detector identifies candidate trigger
        suspects = PoisonDetector.detect_trigger_anomalies(train_p, min_support=0.1)
        trigger_names = [s["candidate_trigger"] for s in suspects]
        self.assertTrue(any("BKDOOR" in name for name in trigger_names))

    def test_poison_detector_label_conflicts(self):
        """Verify detection of conflicting duplicate inputs."""
        clean_data = [("x1", True), ("x2", False), ("x3", True)]
        conflicted = AdversarialDataPoisoner.apply_contradiction_injection(clean_data, num_conflicts=2)
        self.assertEqual(len(conflicted), len(clean_data) + 2)

        conflicts = PoisonDetector.detect_label_conflicts(conflicted)
        self.assertGreaterEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["input"], "'x1'")

    def test_complexity_attacker_linear_vs_quadratic(self):
        """Verify distinction between linear O(N) and quadratic O(N^2) complexity."""
        def linear_fn(arr: List[int]) -> int:
            return sum(arr)

        def quadratic_fn(arr: List[int]) -> int:
            # Artificial quadratic computation
            s = 0
            for i in arr:
                for j in arr:
                    s += (i ^ j) & 1
            return s

        attacker = ComplexityAttacker()

        # Test linear
        prof_lin = attacker.measure_complexity(
            target_fn=linear_fn,
            input_generator=lambda n: list(range(n)),
            scales=(50, 100, 200, 400),
            repetitions=2,
        )
        self.assertIn(prof_lin.inferred_complexity, ("O(1)", "O(N)", "O(N log N)"))
        self.assertFalse(prof_lin.is_dos_risk)

        # Test quadratic
        prof_quad = attacker.measure_complexity(
            target_fn=quadratic_fn,
            input_generator=lambda n: list(range(n)),
            scales=(100, 200, 400, 800),
            repetitions=2,
        )
        self.assertIn(prof_quad.inferred_complexity, ("O(N^2)", "O(N^3)", "O(2^N)"))
        self.assertTrue(prof_quad.is_dos_risk)

    def test_dos_loop_detection(self):
        """Verify detection of infinite loops or excessive hangs."""
        def hanging_fn(x: Any) -> Any:
            if x == "DOS_TRIGGER":
                while True:
                    time.sleep(0.01)
            return f"Processed_{x}"

        attacker = ComplexityAttacker()
        pathological = ["NORMAL_A", "DOS_TRIGGER", "NORMAL_B"]
        dos_events = attacker.detect_dos_loops(hanging_fn, pathological, timeout_sec=0.1)

        self.assertEqual(len(dos_events), 1)
        self.assertEqual(dos_events[0]["payload_index"], 1)
        self.assertIn("DOS_TRIGGER", dos_events[0]["payload_repr"])

    def test_red_team_report_and_countermeasures(self):
        """Verify report score penalties, JSON/markdown generation, and countermeasure recommendations."""
        vulns = [
            RedTeamVulnerability(
                vuln_id="VULN-001",
                category=VulnerabilityCategory.CYCLIC_GRAPH_CRASH.value,
                severity=SeverityLevel.CRITICAL.value,
                title="Cycle recursion crash",
                description="Crash on cyclic input",
                reproduction_payload=[1],
                countermeasure=CountermeasureAdvisor.get_countermeasure(
                    VulnerabilityCategory.CYCLIC_GRAPH_CRASH.value
                ),
            ),
            RedTeamVulnerability(
                vuln_id="VULN-002",
                category=VulnerabilityCategory.ALGORITHMIC_DOS.value,
                severity=SeverityLevel.HIGH.value,
                title="Super-linear blowup",
                description="O(N^2) worst-case",
                reproduction_payload={"scale": 100},
                countermeasure=CountermeasureAdvisor.get_countermeasure(
                    VulnerabilityCategory.ALGORITHMIC_DOS.value
                ),
            ),
        ]

        # Critical (-25) + High (-15) = 40 penalty -> score 60.0
        report = RedTeamReport(
            target_name="TestTargetSystem",
            timestamp="2026-11-08T00:00:00Z",
            robustness_score=60.0,
            vulnerabilities=vulns,
            fuzzing_summary={"status": "VULNERABILITIES_FOUND"},
            poisoning_summary={"poison_resistance": "ROBUST"},
            complexity_summary={"inferred_complexity": "O(N^2)"},
            countermeasure_suggestions=[v.countermeasure for v in vulns],
        )

        md = report.to_markdown()
        self.assertIn("# ACE Red Team Adversarial Security Audit Report", md)
        self.assertIn("TestTargetSystem", md)
        self.assertIn("60.0 / 100.0", md)
        self.assertIn("VULN-001", md)

        js = report.to_json()
        self.assertIn('"robustness_score": 60.0', js)
        self.assertIn('"VULN-001"', js)

    def test_red_team_adversarial_engine_orchestration(self):
        """Verify end-to-end campaign execution produces a valid RedTeamReport."""
        def sample_synthesizer(spec: List[Tuple[str, bool]]) -> Any:
            # Simple rule learner: accepts if word contains 'a'
            return lambda w: "a" in w

        def system_target(x: Any) -> bool:
            if isinstance(x, str):
                return len(x) > 0 and "a" in x
            return False

        spec_data = [
            ("cat", True),
            ("apple", True),
            ("car", True),
            ("train", True),
            ("dog", False),
            ("fish", False),
            ("bull", False),
            ("fox", False),
        ]

        engine = RedTeamAdversarialEngine()
        report = engine.run_comprehensive_assessment(
            target_fn=system_target,
            target_name="ACESystemPipeline",
            synthesizer_fn=sample_synthesizer,
            spec_data=spec_data,
            scales=(10, 20, 40),
        )

        self.assertIsInstance(report, RedTeamReport)
        self.assertEqual(report.target_name, "ACESystemPipeline")
        self.assertGreaterEqual(report.robustness_score, 0.0)
        self.assertLessEqual(report.robustness_score, 100.0)
        self.assertIn("status", report.fuzzing_summary)
        self.assertIn("inferred_complexity", report.complexity_summary)
        self.assertGreater(len(report.countermeasure_suggestions), 0)


if __name__ == "__main__":
    unittest.main()
