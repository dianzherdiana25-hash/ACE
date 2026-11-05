"""Engineering tests for Issue #13 shared-budget durable graph interfaces."""
import json
import sqlite3
import tempfile
from contextlib import closing
import threading
import unittest
from pathlib import Path

from .e14_shared_budget import BudgetContractError
from .e14_integrated_graph import (
    DurableGraphBudget, audit_journal, canonical_graph, execute_protocol, graph_cost, graph_oracle,
    graph_routes, purchase,
)


def chain(events, *, surcharge=1):
    color = 0
    edges = [[0, 1, color, surcharge]]
    for i, e in enumerate(events, 1):
        color ^= int(e == 2)
        edges.append([i, i+1, color, 1])
    return {"nodes": len(events)+2, "start": 0,
            "goal": len(events)+1, "edges": edges}


class GraphValidation(unittest.TestCase):
    def test_valid_chain_and_actual_resources(self):
        g = chain((1, 2, 1, 2, 1))
        routes, cost = graph_routes(g)
        self.assertEqual(routes, (((1, 2, 1, 2, 1), 6),))
        self.assertEqual(cost, {"nodes": 7, "edges": 6, "events": 5})
        self.assertEqual(graph_oracle(g, (1, 2, 1, 2, 1)), 6)
        self.assertIsNone(graph_oracle(g, (2, 2, 2, 2, 2)))

    def test_branch_costs_and_labels_independent_of_worker(self):
        g = {"nodes": 5, "start": 0, "goal": 4,
             "edges": [[0,1,0,1],[1,2,0,3],[1,3,1,2],[2,4,1,4],[3,4,0,2]]}
        routes, cost = graph_routes(g)
        self.assertEqual(len(routes), 2)
        self.assertEqual(cost, {"nodes": 5, "edges": 5, "events": 4})
        self.assertEqual(graph_oracle(g, (1,2)), 8)
        self.assertEqual(graph_oracle(g, (2,2)), 5)

    def test_boolean_and_bad_integer_fields_rejected(self):
        g = chain((1, 2, 1, 2, 1))
        for field, value in (("nodes", True), ("goal", True), ("start", -1)):
            with self.subTest(field=field):
                self.assertRaises(BudgetContractError, graph_cost, {**g, field:value})
        for j, val in ((0, True), (1, 0), (2, 9), (3, -1)):
            bad = json.loads(json.dumps(g))
            bad["edges"][0][j] = val
            with self.subTest(index=j):
                self.assertRaises(BudgetContractError, graph_cost, bad)

    def test_duplicate_offroute_and_extra_fields_rejected(self):
        g = chain((1, 2, 1, 2, 1))
        self.assertRaises(BudgetContractError, graph_cost, {**g, "target":"hidden"})
        self.assertRaises(BudgetContractError, graph_cost, {**g, "edges":g["edges"]+[g["edges"][0]]})
        bad = json.loads(json.dumps(g))
        bad["edges"] += [[0, 3, 0, 1]]
        # The extra edge is reachable and has a goal path, so valid.
        self.assertEqual(graph_cost(bad)["edges"], 7)
        bad = json.loads(json.dumps(g))
        bad["edges"] = bad["edges"][:-1]
        self.assertRaises(BudgetContractError, graph_cost, bad)

    def test_exponential_paths_rejected(self):
        # Fibonacci DAG: 15 edges but 34 complete start-to-goal routes.
        edges = [[i, i+1, 0, 1] for i in range(8)]
        edges += [[i, i+2, 1, 1] for i in range(7)]
        g = {"nodes": 9, "start": 0, "goal": 8, "edges": edges}
        self.assertEqual(len(edges), 15)
        self.assertRaisesRegex(BudgetContractError, "route cap", graph_cost, g)

    def test_oracle_words_fail_closed(self):
        g = chain((1, 2, 1, 2, 1))
        for x in ([], [1,True], [3], "121", [1]*13):
            self.assertRaises(BudgetContractError, graph_oracle, g, x)


class DurableJournal(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "journal.sqlite"
        self.book = DurableGraphBudget(self.path, "world-1:active")
        self.graph = chain((1, 2, 1, 2, 1))

    def test_pending_persists_and_stops_duplicate_oracle(self):
        called = []
        def fail(g):
            called.append(g)
            raise TimeoutError("oracle interrupted")
        with self.assertRaises(TimeoutError):
            purchase(self.book, "diagnosis", self.graph, fail)
        self.assertEqual(len(called), 1)
        self.assertEqual(self.book.pending(), ("q0001",))
        reopened = DurableGraphBudget(self.path, "world-1:active")
        self.assertEqual(reopened.snapshot()["remaining"], 3)
        with self.assertRaisesRegex(BudgetContractError, "pending"):
            purchase(reopened, "repair", chain((1,1,1,1,1)), lambda _: None)
        self.assertEqual(len(called), 1)
        reopened.settle("q0001", None)  # trusted operator-side reconciliation
        self.assertEqual(reopened.pending(), ())
        self.assertEqual(reopened.reuse("q0001", "repair"), None)

    def test_one_diagnosis_label_reused_in_all_stages(self):
        rid, y = purchase(self.book, "diagnosis", self.graph,
                          lambda g: graph_oracle(g, (1,2,1,2,1)))
        self.assertEqual(y, 6)
        for stage in ("repair", "qualification", "inheritance"):
            self.assertEqual(self.book.reuse(rid, stage), y)
        snap = self.book.snapshot()
        self.assertEqual(snap["purchased"], 1)
        self.assertEqual(snap["receipts"][0]["reused_in"],
                         ["repair", "qualification", "inheritance"])
        self.assertEqual(audit_journal(snap, lambda g: graph_oracle(g, (1,2,1,2,1)))["auditor_oracle_calls"], 1)

    def test_four_label_cap_across_four_stages(self):
        for i,stage in enumerate(("diagnosis", "repair", "qualification", "inheritance")):
            purchase(self.book, stage, chain((1,2,1,2,1), surcharge=i+1), lambda _: None)
        self.assertEqual(self.book.snapshot()["remaining"], 0)
        with self.assertRaisesRegex(BudgetContractError, "cap exhausted"):
            purchase(self.book, "repair", chain((2,2,2,2,2)), lambda _:None)

    def test_cost_mismatch_does_not_consume_label(self):
        fake = {"nodes": 7, "edges": 6, "events": 0}
        with self.assertRaisesRegex(BudgetContractError, "resource declaration"):
            self.book.reserve("diagnosis", self.graph, declared_cost=fake)
        self.assertEqual(self.book.snapshot()["purchased"], 0)

    def test_none_counts_as_real_paid_label(self):
        rid, label = purchase(self.book, "diagnosis", self.graph, lambda _:None)
        self.assertIsNone(label)
        self.assertEqual(self.book.snapshot()["purchased"], 1)
        self.assertEqual(self.book.reuse(rid, "repair"), None)
        self.assertEqual(audit_journal(self.book.snapshot(), lambda _:None)["auditor_oracle_calls"],1)

    def test_duplicate_query_cannot_repurchase(self):
        purchase(self.book, "diagnosis", self.graph, lambda _:None)
        with self.assertRaisesRegex(BudgetContractError, "duplicate"):
            purchase(self.book, "repair", self.graph, lambda _:None)

    def test_semantically_identical_edge_order_cannot_rebuy(self):
        graph = json.loads(json.dumps(self.graph))
        purchase(self.book, "diagnosis", graph, lambda _:None)
        graph["edges"].reverse()
        self.assertEqual(canonical_graph(graph), canonical_graph(self.graph))
        with self.assertRaisesRegex(BudgetContractError, "duplicate"):
            purchase(self.book, "qualification", graph, lambda _:None)

    def test_declared_cost_with_boolean_is_rejected(self):
        fake = {"nodes": 7, "edges": 6, "events": True}
        with self.assertRaises(BudgetContractError):
            self.book.reserve("diagnosis", self.graph, declared_cost=fake)
        self.assertEqual(self.book.snapshot()["purchased"], 0)

    def test_oracle_bool_replay_is_not_integer_cost(self):
        purchase(self.book, "diagnosis", self.graph, lambda _:1)
        with self.assertRaisesRegex(BudgetContractError, "replay mismatch"):
            audit_journal(self.book.snapshot(), lambda _:True)

    def test_tampered_payload_checksum_fails_closed(self):
        purchase(self.book, "diagnosis", self.graph, lambda _:None)
        with closing(sqlite3.connect(self.path)) as db:
            db.execute("UPDATE arm_budget SET digest='x' WHERE arm=?", (self.book.arm,))
            db.commit()
        self.assertRaisesRegex(BudgetContractError, "corrupted", self.book.snapshot)

    def test_tampered_cost_even_rehashed_fails_audit(self):
        rid, _ = purchase(self.book, "diagnosis", self.graph, lambda _:None)
        snap = self.book.snapshot()
        snap["receipts"][0]["query"]["edges"][0][3] = 7
        self.assertRaises(BudgetContractError, audit_journal, snap)

    def test_distinct_arm_budgets(self):
        other = DurableGraphBudget(self.path, "world-1:control")
        purchase(self.book, "diagnosis", self.graph, lambda _:None)
        self.assertEqual(other.snapshot()["purchased"], 0)
        purchase(other, "diagnosis", self.graph, lambda _:None)
        self.assertEqual(other.snapshot()["purchased"], 1)

    def test_concurrent_same_arm_reservations_fail_closed(self):
        results = []
        def call():
            try:
                results.append(("ok",self.book.reserve("diagnosis", self.graph)))
            except BudgetContractError:
                results.append(("blocked",None))
        ts = [threading.Thread(target=call) for _ in range(2)]
        for t in ts: t.start()
        for t in ts: t.join()
        self.assertEqual(sorted(x[0] for x in results), ["blocked", "ok"])
        self.assertEqual(self.book.snapshot()["purchased"], 1)

    def test_recovery_across_new_instance_and_reused_receipt(self):
        rid, _ = purchase(self.book, "diagnosis", self.graph, lambda _:6)
        restored = DurableGraphBudget(self.path, "world-1:active")
        self.assertEqual(restored.reuse(rid, "repair"), 6)
        self.assertTrue(restored.assert_complete())

    def test_graph_invalid_cannot_invoke_oracle(self):
        counter = []
        with self.assertRaises(BudgetContractError):
            purchase(self.book, "diagnosis", {**self.graph,"goal":99}, lambda g:counter.append(g))
        self.assertEqual(counter, [])
        self.assertEqual(self.book.snapshot()["purchased"], 0)

    def test_oracle_replay_detects_wrong_answer(self):
        purchase(self.book, "diagnosis", self.graph, lambda _: 123)
        with self.assertRaisesRegex(BudgetContractError, "replay mismatch"):
            audit_journal(self.book.snapshot(), lambda g:graph_oracle(g, (1,2,1,2,1)))

    def test_execute_protocol_sees_no_target_and_reuses_receipt(self):
        def policy(view):
            rows = view["receipts"]
            if not rows: return {"action":"query","stage":"diagnosis","graph":self.graph}
            if "repair" not in rows[0]["reused_in"]:
                return {"action":"reuse","stage":"repair","receipt_id":rows[0]["id"]}
            return {"action":"abstain"}
        result = execute_protocol(self.book, policy, lambda g:graph_oracle(g,(1,2,1,2,1)))
        self.assertEqual([a["action"] for a in result["actions"]], ["query","reuse","abstain"])
        self.assertEqual(result["journal"]["purchased"], 1)

    def test_execute_protocol_rejects_worker_leak_and_infinite_loop(self):
        with self.assertRaises(BudgetContractError):
            execute_protocol(self.book, lambda view:{"action":"accept","word":[1,True]}, lambda _:None)
        with self.assertRaisesRegex(BudgetContractError, "invalid abstention"):
            execute_protocol(self.book, lambda view:{"action":"abstain", "secret":"x"}, lambda _:None)
        rid, _ = purchase(self.book, "diagnosis", self.graph, lambda _:None)
        with self.assertRaisesRegex(BudgetContractError, "action cap"):
            execute_protocol(self.book, lambda view:{"action":"reuse", "stage":"repair", "receipt_id":rid},
                             lambda _:None, max_actions=2)


if __name__ == "__main__":
    unittest.main()
