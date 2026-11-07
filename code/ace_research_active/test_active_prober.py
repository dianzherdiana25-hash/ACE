"""Unit tests for Active Epistemic Querying and Semantic Drift Falsification."""
from __future__ import annotations

import unittest

from ace_research_active import (
    OAIE_ESTABLISHED,
    RELEASE_GATE,
    SCHEMA_VERSION,
    SCIENTIFIC_STATUS,
)
from ace_research_active.prober import ActiveEpistemicProber, DivergentQuerySynthesizer
from ace_research_active.harness import run_active_epistemic_benchmark


class ActiveEpistemicProberTests(unittest.TestCase):

    def setUp(self):
        self.synthesizer = DivergentQuerySynthesizer(alphabet=("a", "b"))
        self.prober = ActiveEpistemicProber(alphabet=("a", "b"), seed=123)

    def test_minimal_string_mutations(self):
        mutations = self.synthesizer.minimal_string_mutations(["ab"])
        # Should contain deletions: 'a', 'b'
        self.assertIn("a", mutations)
        self.assertIn("b", mutations)
        # Should contain substitutions: 'bb', 'aa'
        self.assertIn("bb", mutations)
        self.assertIn("aa", mutations)
        # Should contain insertions: 'aab', 'bab', 'abb'
        self.assertIn("aab", mutations)
        self.assertIn("abb", mutations)

    def test_synthesize_discriminating_probes(self):
        # Candidate requires 'aba', reference rejects all
        cand = lambda w: "aba" in w
        ref = lambda w: False
        probes = self.synthesizer.synthesize_discriminating_probes(cand, ref, ["ab", "ba"], max_probes=4)
        self.assertTrue(len(probes) > 0)
        for p in probes:
            self.assertNotEqual(cand(p), ref(p))

    def test_passive_evaluation_blind_to_drift(self):
        # True rule: even number of 'b's
        true_rule = lambda w: w.count("b") % 2 == 0
        # Drifted candidate: even number of 'b's UNLESS string starts with 'bbb' and length >= 5
        drift_candidate = lambda w: not true_rule(w) if (len(w) >= 5 and w.startswith("bbb")) else true_rule(w)

        # Train and val contain only short words < 5
        train_data = [("a", True), ("b", False), ("aa", True), ("bb", True)]
        val_data = [("aaa", True), ("bbb", False), ("aaaa", True), ("baba", True)]

        res = self.prober.evaluate_candidate(
            candidate_fn=drift_candidate,
            reference_fn=true_rule,
            oracle_fn=true_rule,
            train_examples=train_data,
            val_examples=val_data,
            mode="passive",
        )
        # Passive mode MUST falsely admit the drifted candidate because val accuracy is 1.0
        self.assertTrue(res["admitted"])
        self.assertFalse(res["falsified"])
        self.assertEqual(res["queries_used"], 0)

    def test_active_probing_detects_drift(self):
        true_rule = lambda w: w.count("b") % 2 == 0
        drift_candidate = lambda w: not true_rule(w) if (len(w) >= 5 and w.startswith("bbb")) else true_rule(w)

        train_data = [("a", True), ("b", False), ("aa", True), ("bb", True)]
        val_data = [("aaa", True), ("bbb", False), ("aaaa", True), ("baba", True)]

        res = self.prober.evaluate_candidate(
            candidate_fn=drift_candidate,
            reference_fn=true_rule,
            oracle_fn=true_rule,
            train_examples=train_data,
            val_examples=val_data,
            mode="active",
            query_budget=8,
        )
        # Active probing MUST falsify and reject the drifted candidate
        self.assertFalse(res["admitted"])
        self.assertTrue(res["falsified"])
        self.assertIsNotNone(res["falsifying_counterexample"])
        self.assertTrue(res["queries_used"] > 0)

    def test_clean_candidate_admitted(self):
        true_rule = lambda w: "aa" in w
        clean_candidate = true_rule
        train_data = [("aa", True), ("ab", False), ("ba", False), ("aaa", True)]
        val_data = [("aab", True), ("baa", True), ("bab", False)]

        res = self.prober.evaluate_candidate(
            candidate_fn=clean_candidate,
            reference_fn=lambda w: False,
            oracle_fn=true_rule,
            train_examples=train_data,
            val_examples=val_data,
            mode="active",
            query_budget=8,
        )
        self.assertTrue(res["admitted"])
        self.assertFalse(res["falsified"])

    def test_system_invariants(self):
        self.assertEqual(SCIENTIFIC_STATUS, "NOT_ASSESSED")
        self.assertEqual(RELEASE_GATE, "BLOCK_RELEASE")
        self.assertIs(OAIE_ESTABLISHED, False)
        self.assertEqual(SCHEMA_VERSION, "ace.active_epistemic.v1")

    def test_full_benchmark_gates(self):
        benchmark_results = run_active_epistemic_benchmark()
        self.assertTrue(benchmark_results["hypotheses"]["all_gates_pass"])
        self.assertTrue(benchmark_results["hypotheses"]["H1_passive_drift_blindness"]["passed"])
        self.assertTrue(benchmark_results["hypotheses"]["H2_active_superiority"]["passed"])
        self.assertTrue(benchmark_results["hypotheses"]["H3_clean_admission_preserved"]["passed"])
        self.assertTrue(benchmark_results["hypotheses"]["H4_resource_bounded_efficiency"]["passed"])


if __name__ == "__main__":
    unittest.main()
