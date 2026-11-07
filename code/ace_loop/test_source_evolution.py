"""Unit tests for E1.6-V2 Typed Source Mutation Engine."""
from __future__ import annotations

import ast
import unittest

from ace_loop.source_evolution import (
    COMPOSITE_OPERATORS,
    CompositeGene,
    MUTATION_RULES,
    SEED_GENE,
    SourceEvolutionError,
    TypedGene,
    compile_function,
    compute_sha,
    generate_source,
    gene_from_dict,
    mutate_composite_gene,
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

    def test_composite_gene_generation_and_execution(self):
        gene_a = mutate_gene(SEED_GENE, 0)
        gene_b = mutate_gene(SEED_GENE, 1)
        comp = CompositeGene(gene_a=gene_a, gene_b=gene_b, operator="XOR")
        src = generate_source(comp)
        self.assertIn(b"^", src)
        validate_ast(src)
        fn = compile_function(src, comp)
        val = fn(5, 2, 7)
        self.assertIsInstance(val, int)

    def test_mutate_composite_gene_determinism(self):
        c1 = mutate_composite_gene(SEED_GENE, SEED_GENE, 2)
        c2 = mutate_composite_gene(SEED_GENE, SEED_GENE, 2)
        self.assertEqual(c1, c2)
        src1 = generate_source(c1)
        src2 = generate_source(c2)
        self.assertEqual(compute_sha(src1), compute_sha(src2))

    def test_gene_from_dict_roundtrip(self):
        atomic_dict = SEED_GENE.to_dict()
        reconstructed_atomic = gene_from_dict(atomic_dict)
        self.assertEqual(reconstructed_atomic, SEED_GENE)

        comp = CompositeGene(gene_a=SEED_GENE, gene_b=mutate_gene(SEED_GENE, 1), operator="ADD")
        comp_dict = comp.to_dict()
        reconstructed_comp = gene_from_dict(comp_dict)
        self.assertEqual(reconstructed_comp, comp)

    def test_composite_gene_invalid_operator(self):
        with self.assertRaises(SourceEvolutionError):
            CompositeGene(gene_a=SEED_GENE, gene_b=SEED_GENE, operator="INVALID_OP")

    def test_gated_gene_generation_and_execution(self):
        from ace_loop.source_evolution import GatedGene, mutate_gated_gene
        g = mutate_gated_gene(1)
        src = generate_source(g)
        self.assertIn(b"if ((length >=", src)
        validate_ast(src)
        fn = compile_function(src, g)
        # length=4, density=1, stride_val=2 -> (2*1 + 1*1) % 3 = 3 % 3 = 0 -> returns 0
        self.assertEqual(fn(4, 1, 2), 0)
        # length=2 -> returns 1
        self.assertEqual(fn(2, 1, 2), 1)


if __name__ == "__main__":
    unittest.main()
