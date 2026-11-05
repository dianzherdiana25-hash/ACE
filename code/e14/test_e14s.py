import unittest

from .e14p_graph import minimum, paths
from .e14r_worker import witness, mappings
from .e14s_run import drive
from .e14s_worker import decide


class E14SQualification(unittest.TestCase):
    def test_same_receipt_rejects_shorter_truth(self):
        word = (1, 2, 1, 1, 2, 2, 1)
        shorter = word[:-1]
        routes = paths(witness(mappings(word)))
        self.assertEqual(minimum(routes, word), minimum(routes, shorter))
        choose = lambda mode, cap, labels: decide(word, mode, cap, labels)
        for truth, correct in ((word, 1), (shorter, 0)):
            result = drive(minimum(routes, truth), truth, "active", 3, choose)
            self.assertEqual(result["wrong"], 0)
            self.assertEqual(result["correct"], correct)

    def test_no_claim_from_first_label_with_unresolved_shorter_words(self):
        word = (1, 2, 2, 1, 2, 1, 2, 1, 1)
        self.assertEqual(decide(word, "active", 1, [10]), {"action": "abstain"})
        self.assertEqual(decide(word, "active", 3, [None]), {"action": "abstain"})
