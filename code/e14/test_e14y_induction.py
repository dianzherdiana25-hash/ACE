"""E1.4y tests for finite AST synthesis, source/target custody and OOD abstention."""
import json
import tempfile
import unittest
from pathlib import Path
from e14.e14_shared_budget import BudgetContractError
from e14.e14_integrated_graph import DurableGraphBudget, graph_routes, audit_journal
from e14.e14u_primitive import PAIR_SPACE
from e14.e14v_topology import fork
from e14.e14w_synthesis import GRID
from e14.e14y_induction import (ast_eval,base_ast,residue_ast,threshold_ast,grammar,
                                 value_at,candidates,choose_query,information_state,OUTSIDERS)
from e14.e14y_bank import build,digest,SOURCE_PAIRS,TARGET_PAIRS
from e14.e14y_study import (truth_of,source_learn,run_arm,study,heldout_probes,
                            source_oracle,independent_oracle,TARGET_QUERY_GRID,
                            TARGET_PROBE_GRID,MODES,question)


class ASTTests(unittest.TestCase):
    def test_nontrivial_residue_program_is_synthesized(self):
        p=residue_ast(4,2,-3)
        self.assertEqual(ast_eval(p,4,10),11)
        self.assertEqual(ast_eval(p,5,10),15)

    def test_threshold_expression_is_not_a_named_operator(self):
        p=threshold_ast(7,2)
        self.assertEqual(ast_eval(p,5,10),15)
        self.assertEqual(ast_eval(p,5,12),19)

    def test_no_ambiguous_semantic_signatures(self):
        self.assertEqual(len({entry[2] for entry in grammar()}),len(grammar()))
        self.assertGreater(len(grammar()),100)

    def test_unknown_forms_not_accidentally_in_new_grammar(self):
        signatures={entry[2] for entry in grammar()}
        for name in OUTSIDERS:
            self.assertNotIn(tuple(value_at(('unknown',name),xy) for xy in GRID),signatures)

    def test_unique_from_all_grid_observations(self):
        g=grammar()[42]
        rows=[(xy,y) for xy,y in zip(GRID,g[2])]
        self.assertEqual(candidates(rows[:16]),candidates(rows[:16]))
        # Entire domain is not admitted under the bounded online interface.
        with self.assertRaises(BudgetContractError):candidates(rows)

    def test_selector_is_observation_only(self):
        ids=tuple(range(len(grammar())))
        q1=choose_query(ids,[],seed=123)
        q2=choose_query(ids,[],seed=789)
        self.assertEqual(q1,q2)
        self.assertIn(q1,GRID)
        self.assertEqual(choose_query(ids,[],allowed=TARGET_QUERY_GRID),
                         choose_query(ids,[],allowed=TARGET_QUERY_GRID))

    def test_selector_rejects_bad_types_and_domain(self):
        for ids,observed,kwargs in (([True],[],{}),
                                    ([len(grammar())],[],{}),
                                    ([0,1],[],{'allowed':[(0,0)]})):
            with self.subTest(ids=ids,kwargs=kwargs):
                self.assertRaises(BudgetContractError,choose_query,ids,observed,**kwargs)

    def test_candidate_history_rejects_bool_and_noninteger(self):
        for row in [[((4,4),True)],[((4,4),4.0)],[((4,19),3)]]:
            self.assertRaises(BudgetContractError,candidates,row)

    def test_false_open_world_guarantee_is_not_emitted(self):
        r=information_state([((4,4),8)])
        self.assertNotIn('scientific_go',r)
        self.assertFalse(r['unique'])


class BankAndAccounting(unittest.TestCase):
    def test_source_and_target_pair_indices_disjoint(self):
        self.assertTrue(set(SOURCE_PAIRS).isdisjoint(TARGET_PAIRS))
        self.assertEqual((len(SOURCE_PAIRS),len(TARGET_PAIRS)),(3,2))

    def test_disjoint_intervention_and_probe_cost_domains(self):
        self.assertFalse(set(TARGET_QUERY_GRID)&set(TARGET_PROBE_GRID))
        self.assertEqual(set(TARGET_QUERY_GRID)|set(TARGET_PROBE_GRID),set(GRID))

    def test_bank_reproducible_and_type_counts(self):
        bank=build()
        self.assertEqual(bank,build())
        self.assertEqual(bank['candidate_count'],len(grammar()))
        self.assertEqual(len(bank['rows']),40)
        self.assertEqual(sum(bank['strata_counts'].values()),40)
        self.assertEqual(len({r['id'] for r in bank['rows']}),40)
        self.assertEqual(digest(bank),digest(json.loads(json.dumps(bank))))

    def test_bank_mutation_fails_closed(self):
        bank=build();bank['rows'][0]['program_id']=999
        with self.assertRaisesRegex(BudgetContractError,'bank has been modified'):
            study(bank,indices=(0,))

    def test_target_probes_are_held_out_and_stable(self):
        row=build()['rows'][0]
        a=heldout_probes(row,TARGET_PAIRS[0]);b=heldout_probes(row,TARGET_PAIRS[0])
        self.assertEqual(a,b)
        from e14.e14v_operator import pairs_of
        for graph in a:
            costs=pairs_of(graph_routes(graph)[0],PAIR_SPACE[TARGET_PAIRS[0]])
            self.assertEqual(len(costs),1)
            self.assertIn(costs[0],TARGET_PROBE_GRID)

    def test_independent_oracle_checks_two_graph_topologies(self):
        row=build()['rows'][0];pair=PAIR_SPACE[TARGET_PAIRS[0]]
        form=truth_of(row)
        for tolls in ((0,10),(7,12),(4,3)):
            a=question(pair,(4+min(tolls),4+max(tolls)))
            b=fork(pair,tolls)
            self.assertEqual(source_oracle(a,pair,form),independent_oracle(a,pair,form))
            self.assertEqual(source_oracle(b,pair,form),independent_oracle(b,pair,form))

    def test_three_source_tasks_purchase_under_four_each(self):
        row=build()['rows'][0]
        with tempfile.TemporaryDirectory() as d:
            s=source_learn(row,Path(d))
        self.assertEqual(len(s['source']),3)
        self.assertEqual(s['source_purchased'],sum(r['labels'] for r in s['source']))
        self.assertTrue(all(0<=r['labels']<=4 and r['labels']==r['replay'] for r in s['source']))

    def test_target_modes_share_exact_source_acquisitions(self):
        r=study(build(),indices=(0,))
        self.assertEqual((r['operator_worlds'],r['target_worlds'],r['arms']),(1,2,10))
        self.assertEqual(r['source_labels'],r['source_replay'])
        self.assertEqual({row['source_label_cost'] for row in r['rows']},
                         {r['source_labels']})
        self.assertEqual(set(row['mode'] for row in r['rows']),set(MODES))

    def test_target_replay_cap_and_abstention_coverage(self):
        r=study(build(),indices=(0,))
        for row in r['rows']:
            self.assertLessEqual(row['target_labels'],4)
            self.assertEqual(row['target_labels'],row['target_replayed'])
            if row['abstain']:
                self.assertEqual(row['accepted_probes'],0)
                self.assertEqual(row['probe_errors'],0)

    def test_false_receipt_hash_caught(self):
        row=build()['rows'][0]
        with tempfile.TemporaryDirectory() as temp:
            db=Path(temp)
            state=source_learn(row,db)
            v=run_arm(row,truth_of(row),state,TARGET_PAIRS[0],'cold-new',db)
            snap=v['target_journal'];snap['receipts'][0]['label']=999
            with self.assertRaises(BudgetContractError):audit_journal(snap)

    def test_independent_oracle_on_outside_grammar(self):
        bank=build();row=next(r for r in bank['rows'] if r['family']=='unrepresented')
        pair=PAIR_SPACE[TARGET_PAIRS[0]];form=truth_of(row)
        for xy in ((4,5),(4,14),(14,18)):
            graph=question(pair,xy)
            self.assertEqual(source_oracle(graph,pair,form),independent_oracle(graph,pair,form))

    def test_small_outsider_run_reports_no_scientific_go(self):
        r=study(build(),indices=(34,))
        self.assertEqual(r['scientific_decision'],'NOT_ASSESSED')
        self.assertEqual(r['operator_worlds'],1)
        self.assertEqual(r['arms'],10)
        self.assertTrue(any(row['family']=='unrepresented' for row in r['rows']))


if __name__=='__main__':unittest.main()
