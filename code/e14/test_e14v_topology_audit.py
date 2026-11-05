import unittest
from .e14u_primitive import PAIR_SPACE,graph_from_routes
from .e14v_topology import fork
from .e14v_topology_audit import independent_cost,audit

class IndependentAudit(unittest.TestCase):
    def test_independent_oracle_matches_shared_fork(self):
        pair=PAIR_SPACE[0]
        g=fork(pair,(2,7))
        self.assertEqual(independent_cost(g,pair,(1,2)),1*(4+2)+2*(4+7))
        self.assertEqual(independent_cost(g,pair,'product'),(4+2)*(4+7))
        self.assertEqual(independent_cost(g,pair,'offset-plus-1'),(4+2)+(4+7)+1)

    def test_actual_policy_replay_on_new_topology(self):
        r=audit(indices=(0,),operators=((2,1),'product'))
        self.assertEqual((r['worlds'],r['arm_count'],r['unique_independent_oracle_checks']),(2,8,12))
        for mode,v in r['summary'].items():
            self.assertEqual(v['structural_covered'],v['accepted']*6)
            self.assertLessEqual(v['target_labels'],8)

    def test_repeat_audit_determinism(self):
        a=audit(indices=(0,),operators=((2,1),))
        b=audit(indices=(0,),operators=((2,1),))
        self.assertEqual(a,b)

if __name__=='__main__':unittest.main()
