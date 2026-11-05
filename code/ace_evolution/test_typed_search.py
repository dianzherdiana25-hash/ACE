import unittest
from typed_search import search


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.train = [(-3,2,-13),(-2,-1,-4),(0,1,-2),(2,0,6)]
        self.valid = [(-5,3,-21),(4,-2,16),(1,5,-7)]

    def test_find_unenumerated_linear_expression(self):
        result = search(self.train, self.valid, max_depth=3, max_ops=3, max_candidates=3000)
        self.assertEqual(result['status'],'FOUND')
        self.assertEqual(result['validation_error'],0)
        self.assertLessEqual(result['candidates_evaluated'],3000)

    def test_deterministic(self):
        self.assertEqual(search(self.train,self.valid),search(self.train,self.valid))

    def test_tight_budget_fails_closed(self):
        r=search(self.train,self.valid,max_candidates=2)
        self.assertEqual(r['status'],'NO_TRAIN_FIT')
        self.assertTrue(r['truncated'])

    def test_holdout_not_an_argument(self):
        with self.assertRaises(TypeError):
            search(self.train,self.valid,holdout=[(9,9,9)])

    def test_invalid_input(self):
        for train in ([],[(1,2,'3')],[(1,2,999)]):
            with self.assertRaises(ValueError):
                search(train,self.valid)

    def test_budget_ceiling(self):
        with self.assertRaises(ValueError):
            search(self.train,self.valid,max_depth=10)

    def test_negative_no_fit(self):
        r=search([(0,0,100),(0,0,-100)],self.valid)
        self.assertEqual(r['status'],'NO_TRAIN_FIT')

if __name__=='__main__': unittest.main()
