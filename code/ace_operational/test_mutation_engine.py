"""OMEGA-09 tests for the Mutation, Recombination and Diversity Engine.

The test list follows the OMEGA-09 line of the execution programme:
novelty false-positive, candidate duplicates, regression preservation,
invalid mutations, negative results — plus the gate rule that no
"new primitive" claim is ever certified here.
"""
from __future__ import annotations

import unittest

from ace_operational.mutation_engine import (
    MUTATION_CLASSES,
    SCHEMA,
    MutationEngine,
    classify_novelty,
    field_diff,
    genotype_digest,
    genotype_distance,
    validate_genotype,
)

BASE = {
    "planner": "greedy", "algorithm": "hill-climb", "representation": "ast",
    "learning": "none", "architecture": "single", "prompt_template": "direct",
    "tool_set": ["read", "search", "edit", "test"],
    "max_tokens": 512, "temperature": 0.2, "max_attempts": 2,
}
OTHER = {
    "planner": "mcts-lite", "algorithm": "genetic", "representation": "graph",
    "learning": "bandit", "architecture": "ensemble",
    "prompt_template": "socratic", "tool_set": ["read", "shell"],
    "max_tokens": 4096, "temperature": 1.4, "max_attempts": 8,
}


class AdmissionTests(unittest.TestCase):
    def test_valid_genotypes_pass(self):
        self.assertEqual(validate_genotype(BASE), [])
        self.assertEqual(validate_genotype(OTHER), [])

    def test_invalid_mutations_are_rejected_with_reasons(self):
        bad = dict(BASE, planner="telepathic")
        self.assertTrue(any("planner" in e for e in validate_genotype(bad)))
        bad = dict(BASE, tool_set=["read", "teleport"])
        self.assertTrue(any("unknown tools" in e for e in validate_genotype(bad)))
        bad = dict(BASE, max_tokens=10 ** 9)
        self.assertTrue(any("max_tokens" in e for e in validate_genotype(bad)))
        bad = dict(BASE, surprise_field="x")
        self.assertTrue(any("unknown field" in e for e in validate_genotype(bad)))


class MutationTests(unittest.TestCase):
    def test_each_class_touches_only_its_own_fields(self):
        # Regression preservation, per class, across several seeds.
        for mutation_class in MUTATION_CLASSES:
            for seed in range(5):
                engine = MutationEngine(seed=seed)
                child = engine.mutate(BASE, mutation_class)
                self.assertEqual(validate_genotype(child), [])
                self.assertTrue(
                    MutationEngine.verify_invariants(BASE, child, mutation_class),
                    f"{mutation_class} leaked outside its field group (seed {seed})")
                allowed = {f for f, spec in SCHEMA.items()
                           if spec[2] == mutation_class}
                self.assertLessEqual(set(field_diff(BASE, child)), allowed)

    def test_recombination_takes_fields_only_from_parents(self):
        engine = MutationEngine(seed=3)
        child = engine.recombine(BASE, OTHER)
        self.assertEqual(validate_genotype(child), [])
        self.assertTrue(MutationEngine.verify_invariants(
            BASE, child, "recombination", other_parent=OTHER))

    def test_engine_is_deterministic_under_a_seed(self):
        one = MutationEngine(seed=42).propose([BASE, OTHER], budget=6)
        two = MutationEngine(seed=42).propose([BASE, OTHER], budget=6)
        self.assertEqual([p["digest"] for p in one["admitted"]],
                         [p["digest"] for p in two["admitted"]])


class NoveltyTests(unittest.TestCase):
    def test_identical_genotype_is_a_duplicate(self):
        result = classify_novelty(BASE, [BASE, OTHER])
        self.assertEqual(result["class"], "duplicate")
        self.assertEqual(result["nearest_distance"], 0.0)

    def test_cosmetic_jitter_is_not_novel(self):
        # A temperature wiggle below the epsilon dead-zone must not be
        # sold as novelty (the false-positive case).
        jittered = dict(BASE, temperature=BASE["temperature"] + 0.01)
        result = classify_novelty(jittered, [BASE])
        self.assertNotEqual(result["class"], "novel")
        self.assertEqual(genotype_distance(BASE, jittered), 0.0)

    def test_genuinely_different_genotype_is_novel(self):
        result = classify_novelty(OTHER, [BASE])
        self.assertEqual(result["class"], "novel")
        self.assertGreater(result["nearest_distance"], 0.5)

    def test_small_change_is_a_variant(self):
        variant = dict(BASE, planner="beam")
        result = classify_novelty(variant, [BASE])
        self.assertEqual(result["class"], "variant")

    def test_primitive_claims_are_never_certified(self):
        result = classify_novelty(OTHER, [BASE], claims_primitive=True)
        self.assertNotEqual(result["class"], "primitive")
        self.assertTrue(result["primitive_claim_unverified"])


class ProposalTests(unittest.TestCase):
    def test_bounded_search_and_negative_results_are_kept(self):
        engine = MutationEngine(seed=7)
        outcome = engine.propose([BASE], budget=8, population=[BASE])
        self.assertLessEqual(len(outcome["admitted"]) + len(outcome["rejected"]), 8)
        for proposal in outcome["admitted"] + outcome["rejected"]:
            self.assertIn("parents", proposal)
            self.assertIn("mutation_class", proposal)
        for proposal in outcome["rejected"]:
            self.assertTrue(proposal["rejection_reasons"])

    def test_duplicates_against_the_archive_are_rejected(self):
        # Deterministic under a seed: first discover what the engine
        # admits with an empty archive, then replay the same seed with
        # those genotypes already archived — every one must now be
        # rejected as a duplicate, none re-admitted.
        first = MutationEngine(seed=1).propose([BASE], budget=4, population=[])
        self.assertTrue(first["admitted"])
        archived = [p["genotype"] for p in first["admitted"]]
        replay = MutationEngine(seed=1).propose([BASE], budget=4,
                                                population=archived)
        replay_admitted = {p["digest"] for p in replay["admitted"]}
        duplicate_rejections = {
            p["digest"] for p in replay["rejected"]
            if any("duplicate" in r for r in p["rejection_reasons"])}
        for proposal in first["admitted"]:
            self.assertNotIn(proposal["digest"], replay_admitted)
            self.assertIn(proposal["digest"], duplicate_rejections)

    def test_provenance_records_parent_and_diff(self):
        engine = MutationEngine(seed=11)
        outcome = engine.propose([BASE], budget=3)
        self.assertTrue(outcome["admitted"])
        proposal = outcome["admitted"][0]
        self.assertEqual(proposal["parents"], [genotype_digest(BASE)])
        recomputed = field_diff(BASE, proposal["genotype"])
        self.assertEqual(proposal["diff_from_first_parent"], recomputed)


if __name__ == "__main__":
    unittest.main()
