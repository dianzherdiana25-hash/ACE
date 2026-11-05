"""E1.4 Issue #13: trusted evaluator infrastructure for one four-label graph loop.

Engineering-only interface. Candidate workers MUST run in a separately validated
isolation boundary; this module is not that boundary or a scored benchmark.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from copy import deepcopy
from contextlib import closing
from pathlib import Path

from .e14_shared_budget import BudgetContractError, SharedLabelBudget, SHARED_CAP

MAX_NODES = 16
MAX_EDGES = 16
MAX_PATHS = 16
MAX_EVENTS = 256


def _json(value):
    try:
        raw = json.dumps(value, allow_nan=False, ensure_ascii=False,
                         sort_keys=True, separators=(",", ":"))
        if json.loads(raw) != value:
            raise BudgetContractError("noncanonical JSON value")
        return raw
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise BudgetContractError("non-JSON-compatible value") from exc


def _sha(raw):
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _int(value, lo, hi, name):
    if type(value) is not int or not lo <= value <= hi:
        raise BudgetContractError("invalid " + name)
    return value


def graph_routes(graph):
    """Validate a *typed, bounded* forward DAG, return immutable routes and actual costs.

    Every edge must lie on at least one start-to-goal route. Reject exponential
    path blowups before oracle invocation. Event cost counts event positions in
    the enumerated routes, not the worker's claimed topology totals.
    """
    if type(graph) is not dict or set(graph) != {"nodes", "start", "goal", "edges"}:
        raise BudgetContractError("invalid graph fields")
    nodes = _int(graph["nodes"], 2, MAX_NODES, "node count")
    start = _int(graph["start"], 0, nodes-1, "start")
    goal = _int(graph["goal"], start+1, nodes-1, "goal")
    raw_edges = graph["edges"]
    if type(raw_edges) is not list or not 1 <= len(raw_edges) <= MAX_EDGES:
        raise BudgetContractError("invalid edge count")
    edges = []
    seen = set()
    for row in raw_edges:
        if type(row) is not list or len(row) != 4:
            raise BudgetContractError("invalid typed edge")
        a = _int(row[0], start, goal-1, "edge source")
        b = _int(row[1], a+1, goal, "edge destination")
        label = _int(row[2], 0, 3, "edge label")
        cost = _int(row[3], 0, 15, "edge cost")
        key = (a, b, label, cost)
        if key in seen:
            raise BudgetContractError("duplicate typed edge")
        seen.add(key)
        edges.append(key)
    by_node = {n: [] for n in range(nodes)}
    for e in edges:
        by_node[e[0]].append(e)
    # Explicit stack: no potentially unbounded recursion over branching graphs.
    stack = [(start, (), 0, ())]
    routes, used = [], set()
    while stack:
        node, labels, total, traversed = stack.pop()
        if node == goal:
            routes.append((tuple(1 if a == b else 2 for a, b in zip(labels, labels[1:])), total))
            used.update(traversed)
            if len(routes) > MAX_PATHS:
                raise BudgetContractError("graph route cap exceeded")
            continue
        for edge in reversed(by_node[node]):
            stack.append((edge[1], labels+(edge[2],), total+edge[3], traversed+(edge,)))
        if len(stack) > 512:
            raise BudgetContractError("graph exploration cap exceeded")
    if not routes or used != set(edges):
        raise BudgetContractError("disconnected or off-route graph edge")
    events = sum(len(events) for events, _ in routes)
    if events > MAX_EVENTS:
        raise BudgetContractError("graph event cap exceeded")
    actual = {"nodes": nodes, "edges": len(edges), "events": events}
    return tuple(routes), actual


def graph_cost(graph):
    return graph_routes(graph)[1]


def canonical_graph(graph):
    """Sort typed edges to reject semantically identical repeat purchases."""
    graph_routes(graph)
    result = json.loads(_json(graph))
    result["edges"].sort()
    return result


def graph_oracle(graph, word):
    """Public-development exact-cost oracle. Never expose a hidden word to workers."""
    if type(word) not in (tuple, list) or not 1 <= len(word) <= 12:
        raise BudgetContractError("invalid oracle word")
    for event in word:
        _int(event, 1, 2, "oracle word event")
    routes, _ = graph_routes(graph)
    target = tuple(word)
    return min((cost for events, cost in routes
                if any(events[i:i+len(target)] == target
                       for i in range(len(events)-len(target)+1))), default=None)


class DurableGraphBudget:
    """One SQLite-backed arm journal. Every transition commits before returning.

    A pending record consumes one label. On an oracle error or process crash it
    MUST be reconciled against trusted external evidence; never reissue the call.
    SQLite protects transaction atomicity, not host-disk or oracle durability.
    """

    def __init__(self, path, arm):
        if type(arm) is not str or not 1 <= len(arm) <= 128 or "\x00" in arm:
            raise BudgetContractError("invalid arm key")
        self.path = Path(path)
        self.arm = arm
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db:
            db.execute("CREATE TABLE IF NOT EXISTS arm_budget ("
                       "arm TEXT PRIMARY KEY, revision INTEGER NOT NULL, "
                       "payload TEXT NOT NULL, digest TEXT NOT NULL)")
            initial = _json(SharedLabelBudget().snapshot())
            db.execute("INSERT OR IGNORE INTO arm_budget VALUES (?, 0, ?, ?)",
                       (self.arm, initial, _sha(initial)))

    def _connect(self):
        db = sqlite3.connect(str(self.path), timeout=15, isolation_level=None)
        db.execute("PRAGMA busy_timeout=15000")
        db.execute("PRAGMA synchronous=FULL")
        return db

    def _read_locked(self, db):
        row = db.execute("SELECT revision, payload, digest FROM arm_budget WHERE arm=?",
                         (self.arm,)).fetchone()
        if row is None or _sha(row[1]) != row[2]:
            raise BudgetContractError("missing or corrupted durable journal")
        try:
            decoded = json.loads(row[1])
            if _json(decoded) != row[1]:
                raise BudgetContractError("noncanonical stored journal")
            budget = SharedLabelBudget.from_snapshot(decoded)
            _validate_graph_receipts(budget)
        except (ValueError, TypeError, KeyError, OverflowError) as exc:
            raise BudgetContractError("invalid durable journal") from exc
        return _int(row[0], 0, 2**63-2, "journal revision"), budget

    def _transition(self, mutation):
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                version, book = self._read_locked(db)
                result = mutation(book)
                raw = _json(book.snapshot())
                updated = db.execute(
                    "UPDATE arm_budget SET revision=?, payload=?, digest=? "
                    "WHERE arm=? AND revision=?",
                    (version+1, raw, _sha(raw), self.arm, version))
                if updated.rowcount != 1:
                    raise BudgetContractError("concurrent journal update")
                db.execute("COMMIT")
                return result
            except BaseException:
                db.execute("ROLLBACK")
                raise

    def snapshot(self):
        with closing(self._connect()) as db:
            return self._read_locked(db)[1].snapshot()

    def reserve(self, stage, graph, *, declared_cost=None):
        # Own one immutable-by-caller request before calculating or charging it.
        checked = canonical_graph(deepcopy(graph))
        actual = graph_cost(checked)
        if declared_cost is not None:
            if (type(declared_cost) is not dict or set(declared_cost) != set(actual)
                    or any(type(v) is not int for v in declared_cost.values())
                    or declared_cost != actual):
                raise BudgetContractError("untrusted resource declaration differs from topology")
        return self._transition(lambda book: book.reserve(stage, checked, cost=actual))

    def settle(self, receipt_id, label):
        if label is not None:
            _int(label, 0, 960, "oracle label")
        return self._transition(lambda book: book.settle(receipt_id, label))

    def reuse(self, receipt_id, stage):
        return self._transition(lambda book: book.reuse(receipt_id, stage))

    def assert_complete(self):
        with closing(self._connect()) as db:
            return self._read_locked(db)[1].assert_complete()

    def pending(self):
        return tuple(r["id"] for r in self.snapshot()["receipts"] if r["status"] == "pending")


def purchase(journal, stage, graph, oracle, *, declared_cost=None):
    """Durably reserve, invoke trusted oracle once, settle; fail visibly on errors."""
    checked = canonical_graph(deepcopy(graph))
    receipt_id = journal.reserve(stage, checked, declared_cost=declared_cost)
    # Deliberately never retries an oracle exception. The reservation stays paid.
    label = oracle(deepcopy(checked))
    journal.settle(receipt_id, label)
    return receipt_id, label


def _validate_graph_receipts(book):
    """Recovery validates graph-specific meaning as well as JSON/checksums."""
    for row in book.snapshot()["receipts"]:
        if canonical_graph(row["query"]) != row["query"]:
            raise BudgetContractError("noncanonical purchased graph")
        if graph_cost(row["query"]) != row["cost"]:
            raise BudgetContractError("forged topology cost")
        if row["status"] == "settled" and row["label"] is not None:
            _int(row["label"], 0, 960, "oracle label")


def audit_journal(snapshot, oracle=None):
    """Validate full receipt integrity/topology; optional trusted oracle replay.

    Oracle replays are separate auditor calls; they are NOT the four purchased
    interventions and must be accounted for independently in a research report.
    """
    book = SharedLabelBudget.from_snapshot(snapshot)
    _validate_graph_receipts(book)
    checked = 0
    for row in book.snapshot()["receipts"]:
        if graph_cost(row["query"]) != row["cost"]:
            raise BudgetContractError("forged topology cost")
        if row["status"] != "settled":
            raise BudgetContractError("cannot audit unsettled oracle receipt")
        if oracle is not None:
            actual_label = oracle(deepcopy(row["query"]))
            if type(actual_label) is not type(row["label"]) or actual_label != row["label"]:
                raise BudgetContractError("oracle replay mismatch")
            checked += 1
    return {"purchased": book.purchased, "auditor_oracle_calls": checked,
            "resource_totals": book.snapshot()["query_cost_totals"]}


def execute_protocol(journal, policy, oracle, *, max_actions=16):
    """Engineering driver for deterministic policy tests; NOT an isolation layer.

    Policy receives only a deep-copy of its own purchased observations; it must
    be run in a validated separate process before use on sealed experiments.
    """
    _int(max_actions, 1, 64, "action cap")
    actions = []
    for _ in range(max_actions):
        view = {"receipts": deepcopy(journal.snapshot()["receipts"]),
                "remaining": journal.snapshot()["remaining"]}
        action = policy(view)
        if type(action) is not dict or action.get("action") not in ("query", "reuse", "abstain", "accept"):
            raise BudgetContractError("invalid policy action")
        kind = action["action"]
        if kind == "query":
            if set(action) != {"action", "stage", "graph"}:
                raise BudgetContractError("invalid query action fields")
            rid, y = purchase(journal, action["stage"], action["graph"], oracle)
            actions.append({"action": "query", "stage": action["stage"],
                            "receipt_id": rid, "label": y})
        elif kind == "reuse":
            if set(action) != {"action", "stage", "receipt_id"}:
                raise BudgetContractError("invalid reuse action fields")
            y = journal.reuse(action["receipt_id"], action["stage"])
            actions.append({**action, "label": y})
        else:
            if kind == "abstain" and set(action) != {"action"}:
                raise BudgetContractError("invalid abstention fields")
            if kind == "accept" and (set(action) != {"action", "word"} or
                                     type(action["word"]) is not list or
                                     not 1 <= len(action["word"]) <= 12 or
                                     any(type(v) is not int or v not in (1, 2) for v in action["word"])):
                raise BudgetContractError("invalid acceptance fields")
            actions.append(deepcopy(action))
            journal.assert_complete()
            return {"decision": kind, "actions": actions, "journal": journal.snapshot()}
    raise BudgetContractError("policy action cap exhausted; no silent continuation")
