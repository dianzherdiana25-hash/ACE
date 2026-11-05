import tempfile
import unittest
from pathlib import Path

from .e14aa_online import OnlineSemanticGuard
from .e14_shared_budget import BudgetContractError
from .e14_integrated_graph import DurableGraphBudget, purchase
from .e14u_primitive import PAIR_SPACE
from .e14y_induction import base_ast
from .e14y_study import question, TARGET_QUERY_GRID


class OnlineGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)/'journal.sqlite'
        self.journal = DurableGraphBudget(self.path, 'epoch-1')
        self.pair = PAIR_SPACE[18]

    def guard(self, **kw):
        return OnlineSemanticGuard(self.pair, base_ast(), **kw)

    def buy(self, xy, label):
        return purchase(self.journal, 'qualification', question(self.pair, xy), lambda _: label)

    def test_quarantine_precedes_next_prediction(self):
        g = self.guard(scope='bounded-dsl-assumed')
        self.buy((4, 4), 8)
        self.buy((4, 6), 10)
        self.assertEqual(g.predict(self.journal.snapshot(), (5, 7)), 12)
        self.buy((4, 8), 13)
        self.assertEqual(g.inspect(self.journal.snapshot())['decision'], 'quarantine')
        self.assertIsNone(g.predict(self.journal.snapshot(), (5, 7)))
        self.assertIsNone(g.next_query(self.journal.snapshot(), allowed=TARGET_QUERY_GRID))

    def test_later_agreement_cannot_erase_contradiction(self):
        self.buy((4, 4), 9)
        self.buy((4, 6), 10)
        report = self.guard(scope='bounded-dsl-assumed').inspect(self.journal.snapshot())
        self.assertEqual(report['first_contradicting_receipt'], 'q0001')
        self.assertEqual(report['decision'], 'quarantine')

    def test_restart_reconstructs_quarantine(self):
        self.buy((4, 4), None)
        resumed = DurableGraphBudget(self.path, 'epoch-1')
        self.assertEqual(self.guard().inspect(resumed.snapshot())['decision'], 'quarantine')
        self.assertEqual(resumed.snapshot()['purchased'], 1)

    def test_pending_blocks_without_oracle_reissue(self):
        self.journal.reserve('qualification', question(self.pair, (4, 4)))
        g = self.guard(scope='bounded-dsl-assumed')
        self.assertEqual(g.inspect(self.journal.snapshot())['decision'], 'blocked_pending')
        self.assertIsNone(g.predict(self.journal.snapshot(), (4, 5)))

    def test_open_world_agreement_never_certifies(self):
        self.buy((4, 4), 8)
        self.buy((4, 6), 10)
        report = self.guard().inspect(self.journal.snapshot())
        self.assertEqual(report['decision'], 'abstain_open_world')
        self.assertFalse(report['absence_of_drift_proven'])

    def test_distinct_queries_and_four_label_cap(self):
        g = self.guard(seed=17)
        seen = []
        for _ in range(4):
            xy = g.next_query(self.journal.snapshot(), allowed=TARGET_QUERY_GRID)
            seen.append(xy)
            self.buy(xy, sum(xy))
        self.assertEqual(len(set(seen)), 4)
        self.assertIsNone(g.next_query(self.journal.snapshot(), allowed=TARGET_QUERY_GRID))

    def test_artifact_and_domain_validation(self):
        for kwargs in ({'min_checks': True}, {'seed': True}, {'scope': 'unconditional'}):
            with self.assertRaises(BudgetContractError):
                self.guard(**kwargs)
        with self.assertRaises(BudgetContractError):
            OnlineSemanticGuard(self.pair, ('const', 1000))
        with self.assertRaises(BudgetContractError):
            self.guard().next_query(self.journal.snapshot(), allowed=[(4, 4), (4, 4)])

    def test_permutation_is_deterministic_without_truth(self):
        a, b = self.guard(seed=9), self.guard(seed=9)
        self.assertEqual(a.next_query(self.journal.snapshot(), allowed=TARGET_QUERY_GRID),
                         b.next_query(self.journal.snapshot(), allowed=TARGET_QUERY_GRID))

    def test_numeric_aliases_and_unbounded_ast_rejected(self):
        for point in ((4.0, 4), (True, 4), [4, 4]):
            with self.assertRaises(BudgetContractError):
                self.guard().predict(self.journal.snapshot(), point)
            with self.assertRaises(BudgetContractError):
                self.guard().next_query(self.journal.snapshot(), allowed=[point])
        nested = base_ast()
        for _ in range(32):
            nested = ('add', nested, ('const', 0))
        with self.assertRaises(BudgetContractError):
            OnlineSemanticGuard(self.pair, nested)


if __name__ == '__main__':
    unittest.main()
