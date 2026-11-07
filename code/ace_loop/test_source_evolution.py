"""Unit tests for E1.6-V2 Typed Source Mutation Engine."""
from __future__ import annotations

import ast
import unittest

from ace_loop.source_evolution import (
    MUTATION_RULES,
    SEED_GENE,
    SourceEvolutionError,
    TypedGene,
    compile_function,
    compute_sha,
    generate_source,
    mutate_gene,
    validate_ast,
)


class TestSourceEvolution(unittest.TestCase):
    def test_seed_gene_generation_and_execution(self):
        src = generate_source(SEED_GENE)
        self.assertIsInstance(src, bytes)
        fn = compile_function(src, SEED_GENE)
        # length=10, density=4, stride_val=5
        # 1 * (10 * 1 + 4 * 2 + (5 % 3) - 1) = 1 * (10 + 8 + 2 - 1) = 19
        res = fn(10, 4, 5)
        self.assertEqual(res, 19)

    def test_deterministic_mutation(self):
        g1 = mutate_gene(SEED_GENE, 0)
        g2 = mutate_gene(SEED_GENE, 0)
        self.assertEqual(g1, g2)
        self.assertNotEqual(g1, SEED_GENE)

        src1 = generate_source(g1)
        src2 = generate_source(g2)
        self.assertEqual(src1, src2)
        self.assertEqual(compute_sha(src1), compute_sha(src2))

    def test_mutation_rules_coverage(self):
        for idx in range(len(MUTATION_RULES)):
            mut = mutate_gene(SEED_GENE, idx)
            src = generate_source(mut)
            fn = compile_function(src, mut)
            val = fn(5, 2, 7)
            self.assertIsInstance(val, int)

    def test_evil_code_injection_rejection(self):
        evil_snippets = [
            b"import os\ndef evaluate_mechanism(l, d, s): return 0\n",
            b'def evaluate_mechanism(length, density, stride_val):\n    return open("/etc/passwd").read()\n',
            b"def evaluate_mechanism(length, density, stride_val):\n    print('leak')\n    return 0\n",
            b"def evaluate_mechanism(length, density, stride_val):\n    return __import__('os').system('ls')\n",
            b"x = 1\ndef evaluate_mechanism(length, density, stride_val): return 0\n",
            b"def evil(): return 1\n",
            b"def evaluate_mechanism(length, density, stride_val): return unauthorized_var\n",
        ]
        for snippet in evil_snippets:
            with self.subTest(snippet=snippet):
                with self.assertRaises(SourceEvolutionError):
                    validate_ast(snippet)

    def test_invalid_gene_bounds_rejection(self):
        with self.assertRaises(SourceEvolutionError):
            TypedGene(window_stride=5, modulus=3, parity_threshold=1, weight_length=1, weight_density=1, sign=1)
        with self.assertRaises(SourceEvolutionError):
            TypedGene(window_stride=2, modulus=1, parity_threshold=1, weight_length=1, weight_density=1, sign=1)
        with self.assertRaises(SourceEvolutionError):
            TypedGene(window_stride=2, modulus=3, parity_threshold=1, weight_length=1, weight_density=1, sign=0)
        with self.assertRaises(SourceEvolutionError):
            TypedGene(window_stride=2, modulus=3, parity_threshold=10, weight_length=1, weight_density=1, sign=1)


if __name__ == "__main__":
    unittest.main()
