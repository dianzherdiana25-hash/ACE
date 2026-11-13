"""Distractor-inoculation battery for the regression
anchor (design: ACE_DISTRACTOR_INOCULATION_DESIGN_
20261113). Standing ammunition: distractor keys that
were MEASURED to divert the discovery solver's search
path (registry: distractor_registry.json, fail-closed
loading) are injected, one at a time, into a catalog
under test; the distractor's witness tasks are then
solved with and without the injection. A catalog is
flagged SUSCEPTIBLE to a distractor when a witness
the clean catalog solves becomes unsolved under
injection — the measured signature of search-path
diversion (Stage 0/1/2, PR #174).

The battery is solver-agnostic: the caller supplies
``solve(task_id, keys) -> bool``. It changes no
catalog and no solver; it reports. Schema of the
report: ace.distractor_inoculation.v1.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

SCHEMA = "ace.distractor_inoculation.v1"
REGISTRY_SCHEMA = "ace.distractor_registry.v1"

_REQUIRED = ("id", "key", "mechanism", "witness_tasks",
             "witness_universe", "catalog_context",
             "evidence", "registered")


class DistractorRegistryError(ValueError):
    """Raised on any malformed registry content."""


def _parse_key(raw: str):
    try:
        key = ast.literal_eval(raw)
    except (ValueError, SyntaxError) as exc:
        raise DistractorRegistryError(
            f"unparseable distractor key: {raw!r}") from exc
    if not isinstance(key, tuple) or not key:
        raise DistractorRegistryError(
            f"distractor key is not a non-empty tuple: {raw!r}")
    return key


def load_registry(path) -> list[dict]:
    """Load and validate the distractor registry,
    fail-closed: any schema, field, key or witness
    defect raises DistractorRegistryError."""
    data = json.loads(Path(path).read_text())
    if data.get("schema") != REGISTRY_SCHEMA:
        raise DistractorRegistryError(
            f"registry schema mismatch: {data.get('schema')!r}")
    records = data.get("distractors")
    if not isinstance(records, list):
        raise DistractorRegistryError("distractors not a list")
    seen = set()
    for rec in records:
        if not isinstance(rec, dict):
            raise DistractorRegistryError("record not an object")
        for field in _REQUIRED:
            if field not in rec:
                raise DistractorRegistryError(
                    f"record missing field {field!r}")
        if rec["id"] in seen:
            raise DistractorRegistryError(
                f"duplicate distractor id {rec['id']!r}")
        seen.add(rec["id"])
        rec["_key_tuple"] = _parse_key(rec["key"])
        if not rec["witness_tasks"] or not all(
                isinstance(t, str) and t
                for t in rec["witness_tasks"]):
            raise DistractorRegistryError(
                f"record {rec['id']!r} has no witness tasks")
        if not isinstance(rec["evidence"], dict) or not \
                rec["evidence"]:
            raise DistractorRegistryError(
                f"record {rec['id']!r} carries no evidence "
                "pointers — suspicion is not registrable")
    return records


def inject(keys, key_tuple) -> list:
    """Catalog keys with the distractor appended iff
    absent (position: end — the battery tests presence,
    not position; Stage 1 measured the outcome to be
    order-invariant for the seed distractor)."""
    out = list(keys)
    if key_tuple not in out:
        out.append(key_tuple)
    return out


def run_battery(*, catalog_keys, solve, registry) -> dict:
    """For each registered distractor: solve its
    witnesses under the clean catalog and under the
    injected catalog; flag susceptibility per witness.
    ``solve(task_id, keys) -> bool`` is caller-supplied.
    """
    entries = []
    for rec in registry:
        key_tuple = rec.get("_key_tuple") or _parse_key(
            rec["key"])
        injected = inject(catalog_keys, key_tuple)
        already = key_tuple in list(catalog_keys)
        witnesses = []
        susceptible = False
        for task_id in rec["witness_tasks"]:
            clean = bool(solve(task_id, list(catalog_keys)))
            dosed = bool(solve(task_id, list(injected)))
            flag = clean and not dosed
            susceptible = susceptible or flag
            witnesses.append({
                "task_id": task_id, "solved_clean": clean,
                "solved_injected": dosed,
                "diverted": flag})
        entries.append({
            "distractor_id": rec["id"], "key": rec["key"],
            "mechanism": rec["mechanism"],
            "already_in_catalog": already,
            "witnesses": witnesses,
            "verdict": "SUSCEPTIBLE" if susceptible
                       else "NOT_SUSCEPTIBLE"})
    return {
        "schema": SCHEMA,
        "catalog_size": len(list(catalog_keys)),
        "distractors": entries,
        "overall": "SUSCEPTIBLE" if any(
            e["verdict"] == "SUSCEPTIBLE" for e in entries)
            else "NOT_SUSCEPTIBLE",
    }
