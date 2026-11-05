"""A bounded, *mapped-only* Issue #13 engineering control, not a new learner.

Reuse the already-tested E1.4r mapping query and E1.4s shorter-motif guard.
It demonstrates a diagnosis -> mapped interpretation -> qualification -> evidence
reuse flow. It neither invents graph grammars nor repairs unseen semantics.
Only the policy runs in a worker; hidden oracle/truth belong to the evaluator.
"""

from __future__ import annotations

from .e14_shared_budget import BudgetContractError
from .e14p_worker import word_of
from .e14r_worker import mappings, witness
from .e14s_worker import decide


def mapped_only_policy(artifact, mode="active"):
    word = word_of(artifact)
    if mode not in ("active", "fixed", "receipt"):
        raise BudgetContractError("unknown mapped control")

    def plan(view):
        if type(view) is not dict or set(view) != {"receipts", "remaining"}:
            raise BudgetContractError("invalid evaluator observation")
        rows = view["receipts"]
        if type(rows) is not list or len(rows) > 3:
            raise BudgetContractError("unexpected qualification history")
        if not rows:
            return {"action": "query", "stage": "diagnosis",
                    "graph": witness(mappings(word))}
        first = rows[0]
        if first["stage"] != "diagnosis" or first["status"] != "settled":
            raise BudgetContractError("diagnosis not settled")
        if "repair" not in first["reused_in"]:
            # Reuses evidence to select a mapped hypothesis; NOT a grammar repair.
            return {"action": "reuse", "receipt_id": first["id"], "stage": "repair"}
        if "inheritance" not in first["reused_in"]:
            return {"action": "reuse", "receipt_id": first["id"], "stage": "inheritance"}
        if any(r["stage"] != "qualification" or r["status"] != "settled" for r in rows[1:]):
            raise BudgetContractError("invalid qualification receipt")
        selection = decide(word, mode, 3, [r["label"] for r in rows])
        if selection["action"] == "query":
            return {"action": "query", "stage": "qualification", "graph": selection["graph"]}
        if selection["action"] == "accept":
            return {"action": "accept", "word": selection["word"]}
        if selection["action"] == "abstain":
            return {"action": "abstain"}
        raise BudgetContractError("unrecognized qualification decision")

    return plan
