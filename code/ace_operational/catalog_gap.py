"""Catalog gap analysis (design:
ACE_CATALOG_GAP_DESIGN_20261113.md).

ACE's discovery runs produce two records: a discovery
evidence record (per-class pool/candidate/admission and
evaluation numbers, the ``operator_discovery_v*.json``
shape) and a materialised operator catalog (the
``operator_catalog_v*.json`` shape: admitted operator
and chain keys per defect class). Until now nothing
read those two records back to answer the coverage
question: *which classes of the schema space does the
catalog actually cover, which are empty, and which are
saturated?* The next discovery agenda was chosen by a
human looking at the raw tables.

This module is that read-back. It is a pure function
over the two record dicts — no solving, no discovery,
no file IO — and it is deterministic and fail-closed:
malformed input raises :class:`CatalogGapError`
(a ``ValueError``) naming the offending field, rather
than producing a partial or guessed report.

What the tool cannot see is as important as what it
can: a defect class the schema space itself cannot
express (the statement_order lesson — the schema
enumerates expression-level edits only, so no
statement-motion fix can ever be discovered, admitted,
or counted here) leaves no trace in either input
record. Such classes enter the report only through
the ``blind_spots`` argument: entries declared by a
human or a design document, copied verbatim, never
inferred by this module. An empty ``blind_spots``
list in a report means "none declared", never
"none exist".
"""
from __future__ import annotations

import copy
from typing import Any

# A measured class counts as saturated when the
# unaided (baseline) solver already solves at least
# this share of its evaluation tasks and the catalog
# adds exactly zero further solves: there is no
# headroom left for discovery to buy.
SATURATION_BASELINE_RATE = 0.90
SATURATION_LIFT_TASKS = 0

# Class statuses assigned in the per-class records.
STATUS_COVERED = "covered"        # extended solver solves every eval task
STATUS_PARTIAL = "partial"        # admitted operators exist, headroom remains
STATUS_GAP = "gap"                # measured, but zero admitted operators/chains
STATUS_SATURATED = "saturated"    # baseline at ceiling, catalog adds nothing
STATUS_CATALOG_ONLY = "catalog_only"  # in catalog, never in discovery evidence
STATUS_UNMEASURED = "unmeasured"  # declared in universe, absent from both records


class CatalogGapError(ValueError):
    """Raised when a discovery record or catalog
    artifact is malformed. Fail-closed: no report is
    produced from input the tool cannot trust."""


# ------------------------------------------------------------------
# validation helpers
# ------------------------------------------------------------------

def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _require_count(record: dict[str, Any], field: str,
                   where: str) -> int:
    if field not in record:
        raise CatalogGapError(f"{where}: missing required field {field!r}")
    value = record[field]
    if not _is_int(value):
        raise CatalogGapError(
            f"{where}: field {field!r} must be an int, "
            f"got {type(value).__name__}")
    if value < 0:
        raise CatalogGapError(
            f"{where}: field {field!r} must be >= 0, got {value}")
    return value


def _require_key_list(record: dict[str, Any], field: str,
                      where: str) -> list[str]:
    value = record.get(field, [])
    if not isinstance(value, list) or \
            not all(isinstance(item, str) for item in value):
        raise CatalogGapError(
            f"{where}: field {field!r} must be a list of strings")
    if len(set(value)) != len(value):
        raise CatalogGapError(
            f"{where}: field {field!r} contains duplicate keys; "
            "canonical records hold each admitted key once")
    return list(value)


def _validate_report(report: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(report, dict):
        raise CatalogGapError("discovery report must be a dict")
    by_class = report.get("by_class")
    if not isinstance(by_class, dict):
        raise CatalogGapError(
            "discovery report: 'by_class' must be a dict of class records")
    validated: dict[str, dict[str, Any]] = {}
    for cls, record in by_class.items():
        if not isinstance(cls, str) or not cls:
            raise CatalogGapError(
                "discovery report: class names must be non-empty strings")
        where = f"discovery report class {cls!r}"
        if not isinstance(record, dict):
            raise CatalogGapError(f"{where}: class record must be a dict")
        pool_tasks = _require_count(record, "pool_tasks", where)
        candidates = _require_count(record, "candidate_operators", where)
        eval_tasks = _require_count(record, "eval_tasks", where)
        base = _require_count(record, "eval_solved_baseline", where)
        ext = _require_count(record, "eval_solved_extended", where)
        if base > eval_tasks:
            raise CatalogGapError(
                f"{where}: eval_solved_baseline ({base}) exceeds "
                f"eval_tasks ({eval_tasks})")
        if ext > eval_tasks:
            raise CatalogGapError(
                f"{where}: eval_solved_extended ({ext}) exceeds "
                f"eval_tasks ({eval_tasks})")
        pool_fixed = record.get("pool_tasks_fixed")
        if pool_fixed is not None:
            if not _is_int(pool_fixed) or pool_fixed < 0:
                raise CatalogGapError(
                    f"{where}: field 'pool_tasks_fixed' must be a "
                    "non-negative int when present")
            if pool_fixed > pool_tasks:
                raise CatalogGapError(
                    f"{where}: pool_tasks_fixed ({pool_fixed}) exceeds "
                    f"pool_tasks ({pool_tasks})")
        validated[cls] = {
            "pool_tasks": pool_tasks,
            "pool_tasks_fixed": pool_fixed,
            "candidate_operators": candidates,
            "admitted_operators": _require_key_list(
                record, "admitted_operators", where),
            "admitted_chains": _require_key_list(
                record, "admitted_chains", where),
            "eval_tasks": eval_tasks,
            "eval_solved_baseline": base,
            "eval_solved_extended": ext,
        }
    return validated


def _validate_catalog(catalog: Any) -> dict[str, dict[str, list[str]]]:
    if not isinstance(catalog, dict):
        raise CatalogGapError("catalog artifact must be a dict")
    classes = catalog.get("classes")
    if not isinstance(classes, dict):
        raise CatalogGapError(
            "catalog artifact: 'classes' must be a dict of class records")
    validated: dict[str, dict[str, list[str]]] = {}
    for cls, record in classes.items():
        if not isinstance(cls, str) or not cls:
            raise CatalogGapError(
                "catalog artifact: class names must be non-empty strings")
        where = f"catalog class {cls!r}"
        if not isinstance(record, dict):
            raise CatalogGapError(f"{where}: class record must be a dict")
        validated[cls] = {
            "operators": _require_key_list(record, "operators", where),
            "chains": _require_key_list(record, "chains", where),
        }
    return validated


def _validate_universe(universe_classes: Any) -> list[str]:
    if universe_classes is None:
        return []
    if not isinstance(universe_classes, list) or \
            not all(isinstance(name, str) and name
                    for name in universe_classes):
        raise CatalogGapError(
            "universe_classes must be a list of non-empty class names")
    if len(set(universe_classes)) != len(universe_classes):
        raise CatalogGapError("universe_classes contains duplicates")
    return list(universe_classes)


def _validate_blind_spots(blind_spots: Any) -> list[dict[str, Any]]:
    """Blind spots are declarations, not inferences:
    each entry must arrive with a name and a stated
    reason from whoever declares it. Copied verbatim."""
    if blind_spots is None:
        return []
    if not isinstance(blind_spots, list):
        raise CatalogGapError("blind_spots must be a list of declarations")
    validated = []
    for entry in blind_spots:
        if not isinstance(entry, dict):
            raise CatalogGapError("blind_spot entries must be dicts")
        name = entry.get("name")
        reason = entry.get("reason")
        if not isinstance(name, str) or not name:
            raise CatalogGapError(
                "blind_spot entry requires a non-empty 'name'")
        if not isinstance(reason, str) or not reason:
            raise CatalogGapError(
                f"blind_spot {name!r} requires a stated 'reason': a "
                "blind spot without a declared reason is a guess")
        validated.append(copy.deepcopy(entry))
    validated.sort(key=lambda entry: entry["name"])
    return validated


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round(numerator / denominator, 6)


# ------------------------------------------------------------------
# analysis
# ------------------------------------------------------------------

def analyze_catalog_gaps(report: dict[str, Any],
                         catalog: dict[str, Any],
                         *,
                         universe_classes: list[str] | None = None,
                         blind_spots: list[dict[str, Any]] | None = None,
                         ) -> dict[str, Any]:
    """Measure catalog coverage from a discovery
    evidence record and a materialised catalog.

    ``report`` is a discovery evidence dict (the
    ``operator_discovery_v*`` shape: a ``by_class``
    mapping of per-class pool/candidate/admission and
    evaluation counts). ``catalog`` is a catalog
    artifact dict (the ``operator_catalog_v*`` shape:
    a ``classes`` mapping of admitted operator/chain
    key lists). ``universe_classes`` optionally
    declares the full class inventory of the task
    universe (e.g. every defect the generator can
    produce); declared classes absent from both
    records are reported as unmeasured gaps.
    ``blind_spots`` optionally carries human/design
    declarations of what the schema space cannot
    express; they are copied into the report verbatim
    and are never inferred here.

    Returns ``{"per_class": {...}, "gaps": [...],
    "saturated": [...], "blind_spots": [...]}``.
    Deterministic: identical inputs yield identical
    output, including ordering.
    """
    evidence = _validate_report(report)
    catalog_classes = _validate_catalog(catalog)
    universe = _validate_universe(universe_classes)
    declared_blind_spots = _validate_blind_spots(blind_spots)

    inventory = sorted(set(evidence) | set(catalog_classes)
                       | set(universe))
    per_class: dict[str, dict[str, Any]] = {}
    gaps: list[dict[str, Any]] = []
    saturated: list[dict[str, Any]] = []

    for cls in inventory:
        record = evidence.get(cls)
        catalog_record = catalog_classes.get(cls)
        if record is not None:
            admitted_operators = len(record["admitted_operators"])
            admitted_chains = len(record["admitted_chains"])
            catalog_consistent = None
            if catalog_record is not None:
                catalog_consistent = (
                    set(catalog_record["operators"])
                    == set(record["admitted_operators"])
                    and set(catalog_record["chains"])
                    == set(record["admitted_chains"]))
            eval_tasks = record["eval_tasks"]
            base = record["eval_solved_baseline"]
            ext = record["eval_solved_extended"]
            lift_tasks = ext - base
            baseline_rate = _rate(base, eval_tasks)
            entry = {
                "status": None,
                "pool_tasks": record["pool_tasks"],
                # The v4 evidence shape does not record how
                # many pool tasks the admitted set fixes;
                # the field is read when a future record
                # carries it and is None (never guessed)
                # when it does not.
                "pool_tasks_fixed": record["pool_tasks_fixed"],
                "candidate_operators": record["candidate_operators"],
                "candidate_yield": _rate(
                    admitted_operators, record["candidate_operators"]),
                "admitted_operators": admitted_operators,
                "admitted_chains": admitted_chains,
                "eval_tasks": eval_tasks,
                "eval_solved_baseline": base,
                "eval_solved_extended": ext,
                "baseline_rate": baseline_rate,
                "extended_rate": _rate(ext, eval_tasks),
                "lift_tasks": lift_tasks,
                "lift_rate": _rate(lift_tasks, eval_tasks),
                "headroom_tasks": eval_tasks - ext,
                "evidence_strength": (record["pool_tasks"] + eval_tasks
                                      + record["candidate_operators"]),
                "in_catalog": catalog_record is not None,
                "catalog_consistent": catalog_consistent,
            }
            admitted_total = admitted_operators + admitted_chains
            if admitted_total == 0:
                entry["status"] = STATUS_GAP
                severity = eval_tasks - base
                gaps.append({
                    "class": cls,
                    "kind": "no_admitted_operators",
                    "severity": severity,
                    "evidence_strength": entry["evidence_strength"],
                    "reason": (
                        f"class measured ({record['candidate_operators']} "
                        f"candidate operators examined over "
                        f"{record['pool_tasks']} pool tasks) but zero "
                        f"operators or chains admitted; {severity} "
                        f"evaluation tasks are left unsolved by the "
                        "baseline solver"),
                })
            elif (lift_tasks == SATURATION_LIFT_TASKS and eval_tasks > 0
                  and baseline_rate is not None
                  and baseline_rate >= SATURATION_BASELINE_RATE):
                entry["status"] = STATUS_SATURATED
                saturated.append({
                    "class": cls,
                    "baseline_rate": baseline_rate,
                    "lift_tasks": lift_tasks,
                    "eval_tasks": eval_tasks,
                    "reason": (
                        f"baseline already solves {base}/{eval_tasks} "
                        f"evaluation tasks (rate {baseline_rate}) and "
                        "the catalog adds zero further solves; no "
                        "headroom remains for discovery to buy"),
                })
            elif eval_tasks > 0 and ext == eval_tasks:
                entry["status"] = STATUS_COVERED
            else:
                entry["status"] = STATUS_PARTIAL
            per_class[cls] = entry
        elif catalog_record is not None:
            per_class[cls] = {
                "status": STATUS_CATALOG_ONLY,
                "pool_tasks": None,
                "pool_tasks_fixed": None,
                "candidate_operators": None,
                "candidate_yield": None,
                "admitted_operators": len(catalog_record["operators"]),
                "admitted_chains": len(catalog_record["chains"]),
                "eval_tasks": None,
                "eval_solved_baseline": None,
                "eval_solved_extended": None,
                "baseline_rate": None,
                "extended_rate": None,
                "lift_tasks": None,
                "lift_rate": None,
                "headroom_tasks": None,
                "evidence_strength": 0,
                "in_catalog": True,
                "catalog_consistent": None,
            }
        else:
            per_class[cls] = {
                "status": STATUS_UNMEASURED,
                "pool_tasks": None,
                "pool_tasks_fixed": None,
                "candidate_operators": None,
                "candidate_yield": None,
                "admitted_operators": 0,
                "admitted_chains": 0,
                "eval_tasks": None,
                "eval_solved_baseline": None,
                "eval_solved_extended": None,
                "baseline_rate": None,
                "extended_rate": None,
                "lift_tasks": None,
                "lift_rate": None,
                "headroom_tasks": None,
                "evidence_strength": 0,
                "in_catalog": False,
                "catalog_consistent": None,
            }
            gaps.append({
                "class": cls,
                "kind": "unmeasured",
                "severity": 0,
                "evidence_strength": 0,
                "reason": (
                    "class declared in the universe inventory but "
                    "absent from both the discovery evidence and the "
                    "catalog; no measurement of it exists"),
            })

    # Ranking: measured gaps first — larger measured
    # loss (severity) first, stronger evidence first,
    # class name as the deterministic tiebreak — then
    # unmeasured classes by name. An unmeasured class
    # never outranks a measured loss: the agenda acts
    # on evidence before absence.
    gaps.sort(key=lambda gap: (
        0 if gap["kind"] == "no_admitted_operators" else 1,
        -gap["severity"], -gap["evidence_strength"], gap["class"]))
    saturated.sort(key=lambda entry: entry["class"])

    return {"per_class": per_class,
            "gaps": gaps,
            "saturated": saturated,
            "blind_spots": declared_blind_spots}
