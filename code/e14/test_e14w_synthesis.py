"""E1.4w unit tests: finite DSL program induction and negative epistemic cases."""
from __future__ import annotations
import unittest
from .e14_shared_budget import BudgetContractError
from .e14u_primitive import PAIR_SPACE
from .e14w_synthesis import (library,signatures,GRID,render,evaluate,
     candidate_ids,select_question,select_fast,target_for,outsider_for,
     motif_query,out_of_basis)
from .e14w_study import ADV_OUTSIDERS,NOVEL_OUTSIDERS,IN_FAMILY_EXPRESSIONS
from .e14w_audit import alternate_eval,alternate_score

class GrammarTests(unittest.TestCase):
    def test_library_counts_and_semantic_dedup(self):
        self.assertEqual((len(library(3)),len(library(5)),len(GRID)),(17,68,120))
        self.assertEqual(len(set(signatures(5))),len(library(5)))

    def test_bottom_up_constructs_operators_not_only_named_options(self):
        expressions=set(map(render,library(5)))
        for s in ('(hi*lo)','(lo+(1+hi))','(hi+(lo*lo))','(lo*(hi+hi))'):
            self.assertIn(s,expressions)

    def test_iterative_auditor_agrees_with_recursive_model_on_all_grid(self):
        for tree in library(5):
            self.assertEqual(tuple(evaluate(tree,*x) for x in GRID),
                             tuple(alternate_eval(tree,*x) for x in GRID))

    def test_queries_are_deterministic_and_discriminating(self):
        ids=tuple(range(len(library(5))))
        one=select_fast(ids,[],mode='active')
        self.assertEqual(one,select_fast(ids,[],mode='active'))
        self.assertEqual(one,select_question(ids,[],mode='active'))
        self.assertIsNotNone(one)

    def test_no_rebuying_identical_cost_pair(self):
        ids=tuple(range(len(library(5))))
        a,b=select_fast(ids,[],mode='active')
        y=evaluate(library(5)[7],4+min(a,b),4+max(a,b))
        other=select_fast(ids,[((4+min(a,b),4+max(a,b)),y)])
        self.assertNotEqual((min(a,b),max(a,b)),(min(other),max(other)))

    def test_solver_rejects_illegal_fields(self):
        with self.assertRaises(BudgetContractError):library(7)
        with self.assertRaises(BudgetContractError):candidate_ids([((4,18),True)])
        with self.assertRaises(BudgetContractError):candidate_ids([((5,20),4)])
        with self.assertRaises(BudgetContractError):select_question((0,),[],mode='unsafe')
        with self.assertRaises(BudgetContractError):select_fast((0,),[],mode='unsafe')

    def test_composition_semantics_on_real_graph(self):
        pair=PAIR_SPACE[0]
        graph=motif_query(pair,0,5)
        exp=library(5)[8]
        self.assertEqual(target_for(pair,exp)(graph),4*9)
        self.assertEqual(alternate_score(graph,pair,render(exp)),4*9)

    def test_oob_semantics_not_equivalent_to_any_synthesized_program(self):
        for kind in (*ADV_OUTSIDERS,*NOVEL_OUTSIDERS):
            with self.subTest(kind=kind):
                target=tuple(out_of_basis(kind)(*x) for x in GRID)
                self.assertNotIn(target,signatures(5))

    def test_any_exploratory_program_has_bounded_nonnegative_outputs(self):
        for sig in signatures(5):
            self.assertTrue(all(type(v) is int and 0<=v<=960 for v in sig))

    def test_grids_do_not_leak_target_oracle(self):
        a=select_fast(tuple(range(68)),[],seed=1)
        b=select_fast(tuple(range(68)),[],seed=876)
        self.assertEqual(a,b)

    def test_stress_truths_distinguishable_on_cost_grid(self):
        kind='gap-parity'
        graph=motif_query(PAIR_SPACE[0],7,13)
        self.assertEqual(outsider_for(PAIR_SPACE[0],kind)(graph),
                         11+17)
        neighbor=motif_query(PAIR_SPACE[0],7,14)
        self.assertEqual(outsider_for(PAIR_SPACE[0],kind)(neighbor),
                         11+18+1)

    def test_outsider_rejects_unknown_expression_name(self):
        with self.assertRaises(BudgetContractError):out_of_basis('invented-hidden-rule')

if __name__=='__main__':unittest.main()
