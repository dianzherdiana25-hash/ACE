import unittest
from dataclasses import replace

from .evaluator.bank import development_bank
from .evaluator.selection import POLICIES, SelectionError, audit_bank, input_key, public_rules, rank


class SelectionTests(unittest.TestCase):
    def test_rejects_relabelled_development_and_oracle_inside_checkout(self):
        episodes = development_bank()[0]
        with self.assertRaisesRegex(SelectionError, "three related"):
            audit_bank(episodes, public_rules())
        subset = tuple(episode for index, episode in enumerate(episodes) if index < 6 or 12 <= index < 18)
        rule = replace(public_rules()[0], shape=("novel", "symbolic"))
        with self.assertRaisesRegex(SelectionError, "inside candidate"):
            audit_bank(subset, (rule, public_rules()[1]))

    def test_edge_order_cannot_hide_a_repeated_case(self):
        edges = [[0, 1, 2, 1], [1, 0, 2, 0]]
        graph = {"nodes": 2, "start": 0, "goal": 1, "edges": edges}
        self.assertEqual(input_key("G", graph), input_key("G", {**graph, "edges": edges[::-1]}))

    def test_rank_uses_equal_family_accuracy_and_cpu_then_lexical(self):
        rows = []
        for policy in POLICIES:
            for family in ("S", "G"):
                row = {"policy": policy, "family": family,
                       "total_cpu_us": 3 if policy == "structured" else 2,
                       "scores": {"ordinary": {"total": 10, "correct": 5, "failures": 0}}}
                rows.append(row)
        self.assertEqual([row["policy"] for row in rank(rows)], ["beam", "enumerative", "structured"])
        rows[0]["scores"]["ordinary"]["correct"] = 6
        self.assertEqual(rank(rows)[0]["policy"], "structured")
