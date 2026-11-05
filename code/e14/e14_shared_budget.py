"""Evaluator-side shared purchased-label ledger for future E1.4 integration.

This is engineering support, not a scorer or a change to any frozen bank.
Every attempted oracle purchase must first reserve one of four shared slots.
A settled receipt can be reused in later stages without purchasing a new label.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy


STAGES = frozenset({"diagnosis", "repair", "qualification", "inheritance"})
SHARED_CAP = 4


class BudgetContractError(ValueError):
    """Fail closed on an invalid charge, replay, or budget transition."""


def _canonical(value):
    try:
        encoded = json.dumps(value, allow_nan=False, sort_keys=True,
                             ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        # Prevent JSON-unsafe objects or unsupported non-string map keys.
        if json.loads(encoded) != value:
            raise BudgetContractError("noncanonical JSON value")
    except (TypeError, ValueError, OverflowError) as exc:
        raise BudgetContractError("non-JSON-compatible value") from exc
    return encoded


def _digest(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def _stage(stage):
    if type(stage) is not str or stage not in STAGES:
        raise BudgetContractError("unknown evidence stage")


def _cost(value):
    if type(value) is not dict or set(value) != {"nodes", "edges", "events"}:
        raise BudgetContractError("missing explicit query resource cost")
    if any(type(v) is not int or v < 0 for v in value.values()):
        raise BudgetContractError("invalid query resource cost")
    return {key: value[key] for key in ("nodes", "edges", "events")}


class SharedLabelBudget:
    """Evaluator-only purchase journal; does not access the target oracle.

    reserve() is called BEFORE requesting an oracle answer; reservations remain
    charged if the worker/process is interrupted.  A pending reservation must
    be reconciled by the trusted evaluator before another purchase is made.
    """

    def __init__(self, cap=SHARED_CAP):
        if type(cap) is not int or cap != SHARED_CAP:
            raise BudgetContractError("the integrated benchmark requires one shared four-label cap")
        self.cap = cap
        self._receipts = []

    @property
    def purchased(self):
        return len(self._receipts)

    @property
    def remaining(self):
        return self.cap - self.purchased

    def reserve(self, stage, query, *, cost):
        _stage(stage)
        cost = _cost(cost)
        query = json.loads(_canonical(query))
        digest = _digest(query)
        if self.remaining == 0:
            raise BudgetContractError("shared label cap exhausted")
        if any(r["status"] == "pending" for r in self._receipts):
            raise BudgetContractError("pending oracle purchase must be reconciled")
        if any(r["query_sha256"] == digest for r in self._receipts):
            raise BudgetContractError("duplicate purchased query; reuse the existing receipt")
        receipt_id = "q" + str(self.purchased + 1).zfill(4)
        self._receipts.append({"id": receipt_id, "stage": stage,
                               "query": query, "query_sha256": digest,
                               "cost": cost, "status": "pending", "label": None,
                               "label_sha256": None, "reused_in": []})
        return receipt_id

    def _find(self, receipt_id):
        if type(receipt_id) is not str:
            raise BudgetContractError("unknown receipt")
        for receipt in self._receipts:
            if receipt["id"] == receipt_id:
                return receipt
        raise BudgetContractError("unknown receipt")

    def settle(self, receipt_id, label):
        receipt = self._find(receipt_id)
        if receipt["status"] != "pending":
            raise BudgetContractError("receipt has already been settled")
        label = json.loads(_canonical(label))
        receipt["label"] = label
        receipt["label_sha256"] = _digest(label)
        receipt["status"] = "settled"

    def reuse(self, receipt_id, stage):
        _stage(stage)
        receipt = self._find(receipt_id)
        if receipt["status"] != "settled":
            raise BudgetContractError("unsettled receipt cannot be reused")
        if stage != receipt["stage"] and stage not in receipt["reused_in"]:
            receipt["reused_in"].append(stage)
        return deepcopy(receipt["label"])

    def assert_complete(self):
        if any(r["status"] != "settled" for r in self._receipts):
            raise BudgetContractError("unreconciled oracle reservation")
        return True

    def snapshot(self):
        rows = deepcopy(self._receipts)
        return {"version": 1, "shared_cap": self.cap, "purchased": len(rows),
                "remaining": self.remaining,
                "query_cost_totals": {k: sum(row["cost"][k] for row in rows)
                                      for k in ("nodes", "edges", "events")},
                "receipts": rows}

    @classmethod
    def from_snapshot(cls, data):
        """Check every recorded transition/digest, including pending reservations."""
        if type(data) is not dict or set(data) != {"version", "shared_cap", "purchased",
                                                     "remaining", "query_cost_totals", "receipts"}:
            raise BudgetContractError("invalid budget journal structure")
        if type(data["version"]) is not int or data["version"] != 1 or type(data["receipts"]) is not list:
            raise BudgetContractError("invalid budget journal version")
        obj = cls(data["shared_cap"])
        for original in data["receipts"]:
            if type(original) is not dict or set(original) != {"id", "stage", "query", "query_sha256",
                                                             "cost", "status", "label", "label_sha256", "reused_in"}:
                raise BudgetContractError("invalid receipt fields")
            new_id = obj.reserve(original["stage"], original["query"], cost=original["cost"])
            if new_id != original["id"]:
                raise BudgetContractError("invalid receipt order")
            if original["status"] == "settled":
                obj.settle(new_id, original["label"])
                if type(original["reused_in"]) is not list:
                    raise BudgetContractError("invalid reuse record")
                for stage in original["reused_in"]:
                    if stage == original["stage"] or stage in obj._find(new_id)["reused_in"]:
                        raise BudgetContractError("duplicate reuse stage")
                    obj.reuse(new_id, stage)
            elif original["status"] != "pending" or original["label"] is not None or original["label_sha256"] is not None or original["reused_in"] != []:
                raise BudgetContractError("invalid pending reservation")
        if obj.snapshot() != data:
            raise BudgetContractError("corrupted or noncanonical budget journal")
        return obj
