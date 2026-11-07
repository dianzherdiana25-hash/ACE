"""Unit tests for E1.6-V2 Typed Source Mutation Engine."""
from __future__ import annotations

import ast
import unittest

from ace_loop.source_evolution import (
    COMPOSITE_OPERATORS,
    CompositeGene,
    GatedGene,
    MUTATION_RULES,
    RELATIONAL_GATED_MUTATIONS,
    RelationalGatedGene,
    SEED_GENE,
    SourceEvolutionError,
    TypedGene,
    compile_function,
    compute_sha,
    generate_source,
    gene_from_dict,
    is_coefficient_tuning,
    is_structural_innovation,
    mutate_composite_gene,
    mutate_gated_gene,
    mutate_gene,
    mutate_relational_gated_gene,
    mutate_relational_structure,
    tune_relational_coefficients,
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

    def test_relational_gated_gene_bounds_validation(self):
        """Verify boundary checks on operators, variables, and combiners in RelationalGatedGene."""
        with self.assertRaises(SourceEvolutionError):
            RelationalGatedGene(length_op="INVALID_OP")
        with self.assertRaises(SourceEvolutionError):
            RelationalGatedGene(boundary_op="~=")
        with self.assertRaises(SourceEvolutionError):
            RelationalGatedGene(congruence_op=">")
        with self.assertRaises(SourceEvolutionError):
            RelationalGatedGene(boundary_var="unauthorized_var")
        with self.assertRaises(SourceEvolutionError):
            RelationalGatedGene(combiner="XOR")
        with self.assertRaises(SourceEvolutionError):
            RelationalGatedGene(modulus=1)  # modulus must be >= 2

    def test_relational_gated_gene_conjunction_and_execution(self):
        """Verify multi-clause conjunction (AND) generation, AST validation, and execution."""
        g = mutate_relational_gated_gene(1)
        self.assertEqual(g.combiner, "AND")
        self.assertEqual(g.clause_type, "CONJUNCTION_AND")

        src = generate_source(g)
        self.assertIn(b" and ", src)
        validate_ast(src)

        fn = compile_function(src, g)
        # Ordinal 1: (length >= 4) AND (((stride_val * 1 + density * 1) % 3) == 0) AND (density <= 4)
        # Test matching case: length=5, density=2, stride_val=1 -> 1*1 + 2*1 = 3 % 3 == 0, density <= 4 -> returns 0
        self.assertEqual(fn(5, 2, 1), 0)
        # Test failing length guard: length=3 -> returns 1
        self.assertEqual(fn(3, 2, 1), 1)
        # Test failing modular congruence: length=5, density=2, stride_val=2 -> (2 + 2) % 3 == 1 != 0 -> returns 1
        self.assertEqual(fn(5, 2, 2), 1)
        # Test failing boundary condition: length=5, density=5, stride_val=1 -> density 5 > 4 -> returns 1
        self.assertEqual(fn(5, 5, 1), 1)

    def test_relational_gated_gene_disjunction_and_execution(self):
        """Verify multi-clause disjunction (OR) generation, AST validation, and execution."""
        g = mutate_relational_gated_gene(3)
        self.assertEqual(g.combiner, "OR")
        self.assertEqual(g.clause_type, "DISJUNCTION_OR")

        src = generate_source(g)
        self.assertIn(b" or ", src)
        validate_ast(src)

        fn = compile_function(src, g)
        # Ordinal 3: (length <= 2) OR (((stride_val * 2 + density * -1) % 3) == 0) OR (density >= 5)
        # Match via length <= 2
        self.assertEqual(fn(2, 0, 0), 0)
        # Match via density >= 5 even with length=10
        self.assertEqual(fn(10, 5, 0), 0)
        # Match via modular congruence: stride_val=2, density=1 -> (4 - 1) % 3 == 0
        self.assertEqual(fn(10, 1, 2), 0)
        # Failure: length=10, density=2, stride_val=2 -> (4 - 2) % 3 = 2 != 0, density < 5, length > 2 -> returns 1
        self.assertEqual(fn(10, 2, 2), 1)

    def test_relational_gated_mutations_coverage(self):
        """Verify all 10 deterministic relational gated rules compile and execute."""
        self.assertEqual(len(RELATIONAL_GATED_MUTATIONS), 10)
        for ordinal in range(1, 11):
            gene = mutate_relational_gated_gene(ordinal)
            src = generate_source(gene)
            validate_ast(src)
            fn = compile_function(src, gene)
            val = fn(6, 2, 3)
            self.assertIn(val, (gene.true_val, gene.false_val))

    def test_distinction_between_coefficient_tuning_and_structural_innovation(self):
        """Strictly distinguish parameter coefficient tuning from structural algorithmic novelty."""
        base = mutate_relational_gated_gene(1)

        # 1. Parameter coefficient tuning: modify only weights, thresholds, or modulus
        tuned = tune_relational_coefficients(base, stride_delta=1, density_delta=-1, threshold_delta=2)
        self.assertTrue(base.is_coefficient_tuning(tuned))
        self.assertFalse(base.is_structural_innovation(tuned))
        self.assertTrue(is_coefficient_tuning(base, tuned))
        self.assertFalse(is_structural_innovation(base, tuned))
        self.assertEqual(base.structural_signature(), tuned.structural_signature())
        self.assertNotEqual(base.coefficient_profile(), tuned.coefficient_profile())

        # 2. Structural algorithmic innovation: modify boolean combiner (AND <-> OR)
        struct_or = mutate_relational_structure(base, new_combiner="OR")
        self.assertTrue(base.is_structural_innovation(struct_or))
        self.assertFalse(base.is_coefficient_tuning(struct_or))
        self.assertTrue(is_structural_innovation(base, struct_or))
        self.assertFalse(is_coefficient_tuning(base, struct_or))
        self.assertNotEqual(base.structural_signature(), struct_or.structural_signature())

        # 3. Structural algorithmic innovation: modify relational operator or boundary variable
        struct_op = mutate_relational_structure(base, new_length_op="<=", new_boundary_var="stride_val")
        self.assertTrue(base.is_structural_innovation(struct_op))
        self.assertFalse(base.is_coefficient_tuning(struct_op))

        # 4. Cross-family structural innovation: TypedGene vs RelationalGatedGene
        self.assertTrue(is_structural_innovation(SEED_GENE, base))
        self.assertFalse(is_coefficient_tuning(SEED_GENE, base))

    def test_relational_gated_gene_dict_roundtrip(self):
        """Verify serialization and deserialization roundtrip for RelationalGatedGene."""
        gene = mutate_relational_gated_gene(2)
        d = gene.to_dict()
        self.assertTrue(d.get("is_relational"))
        self.assertTrue(d.get("is_relational_gated"))
        reconstructed = gene_from_dict(d)
        self.assertIsInstance(reconstructed, RelationalGatedGene)
        self.assertEqual(reconstructed, gene)

    def test_relational_gated_gene_determinism(self):
        """Verify identical ordinals produce identical genes, source bytes, and SHAs."""
        g1 = mutate_relational_gated_gene(4)
        g2 = mutate_relational_gated_gene(4)
        self.assertEqual(g1, g2)
        src1 = generate_source(g1)
        src2 = generate_source(g2)
        self.assertEqual(src1, src2)
        self.assertEqual(compute_sha(src1), compute_sha(src2))

    def test_relational_gated_ast_whitelist_compliance(self):
        """Ensure all generated relational gated mechanisms strictly adhere to the AST whitelist."""
        for ord_val in range(1, 11):
            gene = mutate_relational_gated_gene(ord_val)
            src = generate_source(gene)
            func_def = validate_ast(src)
            self.assertEqual(func_def.name, "evaluate_mechanism")


if __name__ == "__main__":
    unittest.main()
