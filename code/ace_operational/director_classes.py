"""Kelompokkan proposal sebelum operator dapat mempertimbangkan eksekusi."""

from collections.abc import Mapping


DEFAULT_RULES = [
    {"class": "C", "when": {"touches_money": True}, "reason": "touches_money"},
    {"class": "C", "when": {"touches_publication": True}, "reason": "touches_publication"},
    {"class": "C", "when": {"touches_external": True}, "reason": "touches_external"},
    {"class": "C", "when": {"reversible": False}, "reason": "not_reversible"},
    {"class": "B", "when": {"known_kind": False}, "reason": "unknown_task_kind"},
    {"class": "B", "when": {"has_based_on": False}, "reason": "based_on_missing"},
    {"class": "B", "when": {"has_evidence": False}, "reason": "evidence_refs_missing"},
    {"class": "B", "when": {"explicit_boundaries": False}, "reason": "ambiguous_boundaries"},
    {"class": "A", "when": {"known_kind": True, "has_based_on": True, "has_evidence": True,
                           "reversible": True, "touches_money": False,
                           "touches_publication": False, "touches_external": False},
     "reason": "explicit_local_reversible_evidence_backed"},
]

_BOUNDARIES = ("reversible", "touches_money", "touches_publication", "touches_external")
_RANK = {"A": 0, "B": 1, "C": 2}


def _references(value):
    return isinstance(value, list) and bool(value) and all(
        isinstance(item, str) and item.strip() for item in value
    )


def classify_proposal(task, *, rules=None):
    """Nilai checkpoint tugas director. Semua aturan cocok dilaporkan.

    `checkpoint.proposal.based_on` adalah bentuk warisan bila
    `checkpoint.based_on` absen. Prioritas C, B, lalu A. Tabel pengganti
    memakai predicate boolean eksak pada fakta yang sama.
    """
    task = task if isinstance(task, Mapping) else {}
    checkpoint = task.get("checkpoint")
    checkpoint = checkpoint if isinstance(checkpoint, Mapping) else {}
    proposal = checkpoint.get("proposal")
    proposal = proposal if isinstance(proposal, Mapping) else {}
    facts = {key: checkpoint.get(key) for key in _BOUNDARIES}
    facts.update(
        known_kind=task.get("kind") == "director_proposal",
        has_based_on=_references(checkpoint.get("based_on", proposal.get("based_on"))),
        has_evidence=_references(checkpoint.get("evidence_refs")),
        explicit_boundaries=all(type(value) is bool for value in facts.values()),
    )
    matches = []
    for rule in DEFAULT_RULES if rules is None else rules:
        when = rule["when"]
        if (rule["class"] not in _RANK or not when or
                any(key not in facts or type(value) is not bool for key, value in when.items())):
            raise ValueError("Aturan klasifikasi tidak sah.")
        if all(facts[key] is value for key, value in when.items()):
            matches.append(rule)
    category = max((rule["class"] for rule in matches), key=_RANK.get, default="B")
    return {"class": category,
            "reasons": [rule["reason"] for rule in matches] or ["no_rule_matched"]}
