import unittest
from oracle import make_episode,apply_primitive,apply_program,choose_primitive,wrap
from agents import ALL_PRIMITIVES,discover,find_target,solve_linear_mod17,decompose_targets,SOURCE_BUDGET,TARGET_BUDGET
class TestE12(unittest.TestCase):
 def test_source_count(self):self.assertEqual(len(ALL_PRIMITIVES),216)
 def test_primitive_range(self):
  for p in ALL_PRIMITIVES:
   y=apply_primitive(p,(0,5,10,15,3,9))
   self.assertEqual(len(y),6);self.assertTrue(all(0<=z<17 for z in y))
 def test_wraps(self):
  for w in ('id','inc','dec','rol','ror','rev'):self.assertEqual(len(wrap(w,(1,2,3))),3)
 def test_deterministic(self):self.assertEqual(make_episode(22),make_episode(22))
 def test_disjoint(self):
  ep=make_episode(22)
  for t in ep.targets:
   self.assertFalse(set(x for x,_ in t['demos'])&set(x for x,_ in t['h9']))
   self.assertFalse(set(x for x,_ in t['h9'])&set(x for x,_ in t['h13']))
 def test_invention_not_base_atom(self):
  p=choose_primitive(15,'source');self.assertEqual(len(p),5)
  self.assertIn(p,ALL_PRIMITIVES)
 def test_source_fit(self):
  ep=make_episode(22);p,_=discover(ep.source_examples,apply_primitive)
  self.assertTrue(all(apply_primitive(p,x)==y for x,y in ep.source_examples))
 def test_source_budget(self):self.assertEqual(SOURCE_BUDGET,216)
 def test_target_budget(self):self.assertEqual(TARGET_BUDGET,64)
 def test_common_initial(self):
  ep=make_episode(22);p,_=discover(ep.source_examples,apply_primitive);task=ep.targets[0]
  data=[find_target(policy,p if policy!='TARGET_ONLY' else None,task['demos'],apply_program,task['task_id'])
        for policy in ('REUSE','TARGET_ONLY','SHAM','WRONG')]
  self.assertEqual(len({r['common_initial_sha256'] for r in data}),1)
 def test_feedback_changes(self):
  ep=make_episode(23);p,_=discover(ep.source_examples,apply_primitive)
  task=ep.targets[0];z=find_target('REUSE',p,task['demos'],apply_program,task['task_id'])
  self.assertTrue(z['selected'])
 def test_solver_structure(self):
  ep=make_episode(22);t=ep.targets[0]
  self.assertTrue(list(decompose_targets(t['demos'])))
 def test_linear(self):
  rows=((1,0,0,0,1),(0,1,0,0,2),(0,0,1,0,3),(0,0,0,1,4))
  self.assertEqual(solve_linear_mod17(rows),(1,2,3,4))
 def test_hidden_unseen_interface(self):
  ep=make_episode(24)
  q=ep.targets[0]
  self.assertNotIn('h9',find_target.__code__.co_varnames)
  self.assertNotIn('truths',find_target.__code__.co_varnames)
if __name__=='__main__':unittest.main(verbosity=2)
