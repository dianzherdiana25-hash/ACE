"""Tests for the independent, evaluator-side E1.4 shared-label budget."""

import copy
import json
import unittest

from e14.e14_shared_budget import BudgetContractError, SharedLabelBudget


class SharedBudgetTests(unittest.TestCase):
    @staticmethod
    def cost():
        return {"nodes": 16, "edges": 16, "events": 0}

    def test_one_label_is_reused_across_diagnosis_repair_and_inheritance(self):
        book = SharedLabelBudget()
        receipt = book.reserve("diagnosis", {"edges": [[0, 1, 0, 3]]}, cost=self.cost())
        book.settle(receipt, 11)
        self.assertEqual(book.reuse(receipt, "repair"), 11)
        self.assertEqual(book.reuse(receipt, "inheritance"), 11)
        self.assertEqual(book.purchased, 1)
        self.assertEqual(book.remaining, 3)
        self.assertEqual(book.snapshot()["receipts"][0]["reused_in"], ["repair", "inheritance"])

    def test_four_label_cap_is_shared_across_all_stages(self):
        book = SharedLabelBudget()
        for stage in ("diagnosis", "repair", "qualification", "inheritance"):
            i = book.reserve(stage, [book.purchased], cost=self.cost())
            book.settle(i, None)
        self.assertTrue(book.assert_complete())
        self.assertEqual((book.purchased, book.remaining), (4, 0))
        with self.assertRaisesRegex(BudgetContractError, "cap exhausted"):
            book.reserve("repair", [99], cost=self.cost())
        self.assertEqual(book.purchased, 4)

    def test_pending_reservation_charged_and_resume_reconciled(self):
        book = SharedLabelBudget()
        identifier = book.reserve("diagnosis", [1, 2], cost=self.cost())
        with self.assertRaisesRegex(BudgetContractError, "pending"):
            book.reserve("repair", [2, 3], cost=self.cost())
        with self.assertRaisesRegex(BudgetContractError, "unreconciled"):
            book.assert_complete()
        restored = SharedLabelBudget.from_snapshot(json.loads(json.dumps(book.snapshot())))
        self.assertEqual(restored.remaining, 3)
        restored.settle(identifier, None)
        nxt = restored.reserve("repair", [2, 3], cost=self.cost())
        restored.settle(nxt, 9)
        self.assertTrue(restored.assert_complete())
        self.assertEqual(restored.purchased, 2)

    def test_duplicate_query_cannot_be_rebought_to_hide_cost(self):
        book = SharedLabelBudget()
        rid = book.reserve("diagnosis", {"b": 2, "a": 1}, cost=self.cost())
        book.settle(rid, 12)
        with self.assertRaisesRegex(BudgetContractError, "duplicate"):
            book.reserve("qualification", {"a": 1, "b": 2}, cost=self.cost())
        self.assertEqual(book.purchased, 1)

    def test_none_is_real_settled_negative_label(self):
        book = SharedLabelBudget()
        rid = book.reserve("diagnosis", [1], cost=self.cost())
        book.settle(rid, None)
        self.assertIsNone(book.reuse(rid, "qualification"))
        self.assertTrue(book.assert_complete())
        self.assertEqual(book.snapshot()["receipts"][0]["status"], "settled")

    def test_snapshot_round_trip_and_resource_accounting(self):
        book = SharedLabelBudget()
        a = book.reserve("diagnosis", [1], cost={"nodes": 5, "edges": 4, "events": 0})
        book.settle(a, 6)
        book.reuse(a, "repair")
        b = book.reserve("qualification", {"nodes": 9}, cost={"nodes": 9, "edges": 8, "events": 0})
        book.settle(b, None)
        state = json.loads(json.dumps(book.snapshot()))
        self.assertEqual(SharedLabelBudget.from_snapshot(state).snapshot(), state)
        self.assertEqual(state["query_cost_totals"], {"nodes": 14, "edges": 12, "events": 0})

    def test_modified_digest_is_rejected(self):
        book = SharedLabelBudget()
        rid = book.reserve("diagnosis", [1], cost=self.cost())
        book.settle(rid, 2)
        bad = copy.deepcopy(book.snapshot())
        bad["receipts"][0]["label"] = 99
        with self.assertRaisesRegex(BudgetContractError, "corrupted"):
            SharedLabelBudget.from_snapshot(bad)

    def test_cost_boolean_missing_and_negative_rejected(self):
        for cost in (None, {"nodes": 1, "edges": 0},
                     {"nodes": True, "edges": 0, "events": 0},
                     {"nodes": -1, "edges": 1, "events": 0}):
            with self.subTest(cost=cost):
                with self.assertRaises(BudgetContractError):
                    SharedLabelBudget().reserve("repair", [1], cost=cost)

    def test_unknown_stage_or_bad_cap_rejected(self):
        with self.assertRaises(BudgetContractError):
            SharedLabelBudget(cap=5)
        with self.assertRaises(BudgetContractError):
            SharedLabelBudget().reserve("free_oracle", [1], cost=self.cost())

    def test_double_settle_and_unsettled_reuse_rejected(self):
        book = SharedLabelBudget()
        rid = book.reserve("diagnosis", [1], cost=self.cost())
        with self.assertRaises(BudgetContractError):
            book.reuse(rid, "repair")
        book.settle(rid, 4)
        with self.assertRaises(BudgetContractError):
            book.settle(rid, 5)

    def test_non_json_or_noncanonical_input_rejected(self):
        book = SharedLabelBudget()
        with self.assertRaises(BudgetContractError):
            book.reserve("diagnosis", {1: "not a string key"}, cost=self.cost())
        with self.assertRaises(BudgetContractError):
            book.reserve("diagnosis", [float("nan")], cost=self.cost())

    def test_integrity_fails_if_replay_renumbers_rows_or_changes_cost(self):
        book = SharedLabelBudget()
        for i in range(2):
            rid = book.reserve("diagnosis", [i], cost=self.cost())
            book.settle(rid, i)
        bad = book.snapshot()
        bad["receipts"][0]["id"] = "q1000"
        with self.assertRaises(BudgetContractError):
            SharedLabelBudget.from_snapshot(bad)
        bad = book.snapshot()
        bad["query_cost_totals"]["edges"] = 1
        with self.assertRaises(BudgetContractError):
            SharedLabelBudget.from_snapshot(bad)


if __name__ == "__main__":
    unittest.main()
