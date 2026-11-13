"""Weakness-targeting curriculum generator (design:
ACE_CURRICULUM_GEN_DESIGN_20261113.md).

The catalog gap tool (``catalog_gap.py``) reads a
discovery record back and ranks where the operator
catalog is blind: classes with zero admitted
operators, classes declared in the universe but never
measured, and partial classes ranked by the headroom
the extended solver still leaves unsolved. This
module is the consumer of that ranking. It turns a
gap report into a *practice set* — fresh tasks aimed
at the blind classes, in the report's own priority
order — so the next round of discovery practice is
spent where the measured weakness is.

A practice task only teaches if its shown cases
identify the pattern it targets. The Stage C lesson
(Addendum 17): a fix can be perfect on the shown
cases and wrong on holdout, and a shown-driven
search stops there, at a code that merely looks
finished. So every generated task passes an
identifiability control before it enters the set:

1. **exposure** — the buggy program must fail at
   least one shown case. A shown set the defect
   never touches carries no signal about it.
2. **discrimination** — when the task source can
   name rival patterns (partial fixes, wrong-class
   twins), at least one rival must fail some shown
   case. If every rival is consistent with all
   shown cases, the shown set cannot tell the
   target pattern from its rivals and the task is
   rejected — counted in the manifest, never
   annotated and shipped anyway.

When the source provides no rivals, only exposure
is checked and the task is annotated
``identifiability.level == "shown_only"``: the
manifest states plainly that the stronger control
was not constructible for that family, rather than
claiming a check that did not happen.

The generator is pure orchestration: no file IO,
no discovery, no solving of its own. The family's
builder and runner arrive through the task-source
interface (see :func:`generate_practice_set`).
Deterministic from ``seed`` — the same gap report,
source behaviour and seed yield the same manifest,
including ordering. Fail-closed: a malformed gap
report, a malformed task, or a broken source raises
:class:`CurriculumGenError`; a class that cannot
fill its quota is reported as a shortfall in the
manifest, never silently padded with unchecked
tasks.
"""
from __future__ import annotations

from typing import Any, Callable

from .catalog_gap import (
    STATUS_CATALOG_ONLY, STATUS_COVERED, STATUS_GAP, STATUS_PARTIAL,
    STATUS_SATURATED, STATUS_UNMEASURED)

GENERATOR_NAME = "curriculum_generator"
GENERATOR_VERSION = 1

# Identifiability levels recorded per task.
LEVEL_DISCRIMINATING = "discriminating"
LEVEL_SHOWN_ONLY = "shown_only"

# Per-class rejection reasons counted in the manifest.
REJECT_GENERATION_FAILURE = "generation_failure"
REJECT_DUPLICATE_TASK_ID = "duplicate_task_id"
REJECT_NO_EXPOSURE = "shown_does_not_expose_defect"
REJECT_ALL_RIVALS_PASS = "shown_consistent_with_all_rivals"

_KNOWN_STATUSES = {STATUS_COVERED, STATUS_PARTIAL, STATUS_GAP,
                   STATUS_SATURATED, STATUS_CATALOG_ONLY,
                   STATUS_UNMEASURED}
_GAP_TIER_STATUSES = {STATUS_GAP, STATUS_UNMEASURED}


class CurriculumGenError(ValueError):
    """Raised when a gap report, a task, or a task
    source is malformed. Fail-closed: no practice
    set is produced from input the generator cannot
    trust."""


# ------------------------------------------------------------------
# validation helpers
# ------------------------------------------------------------------

def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _require_quota(name: str, value: Any, minimum: int) -> int:
    if not _is_int(value) or value < minimum:
        raise CurriculumGenError(
            f"{name} must be an int >= {minimum}, got {value!r}")
    return value


def _validate_gap_report(gap_report: Any) -> tuple[dict, list]:
    """Validate the parts of a catalog_gap report this
    generator consumes; return (per_class, gaps)."""
    if not isinstance(gap_report, dict):
        raise CurriculumGenError("gap report must be a dict")
    per_class = gap_report.get("per_class")
    if not isinstance(per_class, dict):
        raise CurriculumGenError(
            "gap report: 'per_class' must be a dict of class records")
    gaps = gap_report.get("gaps")
    if not isinstance(gaps, list):
        raise CurriculumGenError(
            "gap report: 'gaps' must be a ranked list of gap entries")
    for cls, record in per_class.items():
        if not isinstance(cls, str) or not cls:
            raise CurriculumGenError(
                "gap report: class names must be non-empty strings")
        where = f"gap report class {cls!r}"
        if not isinstance(record, dict):
            raise CurriculumGenError(f"{where}: class record must be a dict")
        status = record.get("status")
        if status not in _KNOWN_STATUSES:
            raise CurriculumGenError(
                f"{where}: unknown or missing 'status' {status!r}")
        headroom = record.get("headroom_tasks")
        if headroom is not None and (not _is_int(headroom) or headroom < 0):
            raise CurriculumGenError(
                f"{where}: 'headroom_tasks' must be a non-negative int "
                "or None")
        if status == STATUS_PARTIAL and headroom is None:
            raise CurriculumGenError(
                f"{where}: a partial class is ranked by headroom, so "
                "'headroom_tasks' must be present")
    for entry in gaps:
        if not isinstance(entry, dict):
            raise CurriculumGenError("gap report: gap entries must be dicts")
        cls = entry.get("class")
        if not isinstance(cls, str) or not cls:
            raise CurriculumGenError(
                "gap report: gap entries require a non-empty 'class'")
        if cls not in per_class:
            raise CurriculumGenError(
                f"gap report: gap entry names class {cls!r} which has "
                "no per_class record; the report is inconsistent")
    return per_class, gaps


def _source_parts(task_source: Any) -> tuple[Callable, Callable,
                                             Callable | None, str | None]:
    """Extract (build, run, rivals, name) from a task
    source given as an object or as a dict of callables.

    Required: ``build(class_name, seed) -> task | None``
    (None = generation failure, retried with the next
    derived seed) and ``run(code, case) -> output``.
    Optional: ``rivals(task) -> [(name, code)] | None``
    and ``name``.
    """
    if isinstance(task_source, dict):
        build = task_source.get("build")
        run = task_source.get("run")
        rivals = task_source.get("rivals")
        name = task_source.get("name")
    else:
        build = getattr(task_source, "build", None)
        run = getattr(task_source, "run", None)
        rivals = getattr(task_source, "rivals", None)
        name = getattr(task_source, "name", None)
    if not callable(build):
        raise CurriculumGenError(
            "task source must provide a callable build(class_name, seed)")
    if not callable(run):
        raise CurriculumGenError(
            "task source must provide a callable run(code, case)")
    if rivals is not None and not callable(rivals):
        raise CurriculumGenError(
            "task source 'rivals' must be callable when provided")
    if name is not None and not isinstance(name, str):
        raise CurriculumGenError("task source 'name' must be a string")
    return build, run, rivals, name


def _validate_task(task: Any, cls: str) -> dict[str, Any]:
    """A built task must carry the family task-dict
    shape this generator checks against: the
    shown/holdout split of the existing families
    (``grid_generalization`` shape). Malformed tasks
    are builder bugs — fail closed, do not retry."""
    if not isinstance(task, dict):
        raise CurriculumGenError(
            f"task source built a non-dict task for class {cls!r}")
    task_id = task.get("task_id")
    if not isinstance(task_id, str) or not task_id:
        raise CurriculumGenError(
            f"task for class {cls!r}: 'task_id' must be a non-empty "
            "string")
    where = f"task {task_id!r}"
    defects = task.get("defects")
    if not isinstance(defects, list) or \
            not all(isinstance(name, str) and name for name in defects):
        raise CurriculumGenError(
            f"{where}: 'defects' must be a list of class names")
    if cls not in defects:
        raise CurriculumGenError(
            f"{where}: built for target class {cls!r} but its defects "
            f"are {defects!r}; the builder answered a different "
            "question than it was asked")
    if not isinstance(task.get("buggy_code"), str):
        raise CurriculumGenError(f"{where}: 'buggy_code' must be a string")
    shown_cases = task.get("shown_cases")
    shown_truth = task.get("shown_truth")
    if not isinstance(shown_cases, list) or not shown_cases:
        raise CurriculumGenError(
            f"{where}: 'shown_cases' must be a non-empty list; a task "
            "with no shown cases cannot be identifiability-checked")
    if not isinstance(shown_truth, list) or \
            len(shown_truth) != len(shown_cases):
        raise CurriculumGenError(
            f"{where}: 'shown_truth' must be a list aligned with "
            "'shown_cases'")
    return task


# ------------------------------------------------------------------
# targeting
# ------------------------------------------------------------------

def _targeting(per_class: dict, gaps: list) -> tuple[list, list]:
    """Split the report's classes into (targets,
    excluded). Targets are ordered: the gap tier in
    the gap report's own ranked order (measured gaps
    by severity, then unmeasured classes), then the
    partial tier by headroom descending with class
    name as the deterministic tiebreak. Saturated,
    covered and catalog-only classes are excluded
    with a stated reason — practice spent there buys
    nothing the measurement can see."""
    targets: list[dict[str, Any]] = []
    targeted: set[str] = set()
    for position, entry in enumerate(gaps):
        cls = entry["class"]
        status = per_class[cls]["status"]
        if status in _GAP_TIER_STATUSES and cls not in targeted:
            targets.append({
                "class": cls, "status": status, "tier": "gap",
                "headroom_tasks": per_class[cls].get("headroom_tasks"),
                "rank_reason": (
                    f"gap report rank {position} "
                    f"(kind {entry.get('kind')!r}, "
                    f"severity {entry.get('severity')!r})")})
            targeted.add(cls)
    # Defensive: a hand-built report might carry a
    # gap/unmeasured class its gaps list omits.
    for cls in sorted(per_class):
        if per_class[cls]["status"] in _GAP_TIER_STATUSES \
                and cls not in targeted:
            targets.append({
                "class": cls, "status": per_class[cls]["status"],
                "tier": "gap",
                "headroom_tasks": per_class[cls].get("headroom_tasks"),
                "rank_reason": "gap-tier class absent from the gaps "
                               "list; appended by class name"})
            targeted.add(cls)
    partials = [cls for cls in per_class
                if per_class[cls]["status"] == STATUS_PARTIAL]
    partials.sort(key=lambda cls: (-per_class[cls]["headroom_tasks"], cls))
    for position, cls in enumerate(partials):
        targets.append({
            "class": cls, "status": STATUS_PARTIAL, "tier": "partial",
            "headroom_tasks": per_class[cls]["headroom_tasks"],
            "rank_reason": (
                f"partial tier rank {position} "
                f"(headroom_tasks {per_class[cls]['headroom_tasks']})")})
        targeted.add(cls)
    excluded = []
    for cls in sorted(per_class):
        if cls in targeted:
            continue
        status = per_class[cls]["status"]
        reason = {
            STATUS_SATURATED: "saturated: the baseline already sits "
                              "at the ceiling and the catalog adds "
                              "nothing; practice buys nothing here",
            STATUS_COVERED: "covered: the extended solver already "
                            "solves every evaluation task in this "
                            "class",
            STATUS_CATALOG_ONLY: "catalog_only: admitted operators "
                                 "exist but the class was never "
                                 "measured, so the report carries "
                                 "neither a gap ranking nor headroom "
                                 "for it",
        }.get(status, f"status {status!r} is not a practice target")
        excluded.append({"class": cls, "status": status,
                         "reason": reason})
    return targets, excluded


# ------------------------------------------------------------------
# identifiability control
# ------------------------------------------------------------------

def _identifiability(task: dict[str, Any], run: Callable,
                     rivals_fn: Callable | None) -> tuple[dict | None, str | None]:
    """Run the identifiability control on one task.

    Returns (annotation, None) when the task enters
    the set, or (None, rejection_reason) when the
    control rejects it."""
    shown_cases = task["shown_cases"]
    shown_truth = task["shown_truth"]
    buggy_failures = sum(
        1 for case, want in zip(shown_cases, shown_truth)
        if run(task["buggy_code"], case) != want)
    if buggy_failures == 0:
        return None, REJECT_NO_EXPOSURE
    annotation: dict[str, Any] = {
        "level": LEVEL_SHOWN_ONLY,
        "shown_cases": len(shown_cases),
        "buggy_shown_failures": buggy_failures,
        "rivals_checked": None,
        "rivals_failing_shown": None,
        "rivals_not_excluded": None,
    }
    if rivals_fn is None:
        return annotation, None
    rivals = rivals_fn(task)
    if rivals is None:
        return annotation, None
    if not isinstance(rivals, list):
        raise CurriculumGenError(
            f"task {task['task_id']!r}: rivals() must return a list "
            "of (name, code) pairs or None")
    if not rivals:
        return annotation, None
    checked: list[tuple[str, str]] = []
    for item in rivals:
        if not isinstance(item, (list, tuple)) or len(item) != 2 \
                or not isinstance(item[0], str) \
                or not isinstance(item[1], str):
            raise CurriculumGenError(
                f"task {task['task_id']!r}: each rival must be a "
                "(name, code) pair of strings")
        checked.append((item[0], item[1]))
    not_excluded = []
    failing = 0
    for name, code in checked:
        passes_all = all(run(code, case) == want
                         for case, want in zip(shown_cases, shown_truth))
        if passes_all:
            not_excluded.append(name)
        else:
            failing += 1
    if failing == 0:
        return None, REJECT_ALL_RIVALS_PASS
    annotation.update({
        "level": LEVEL_DISCRIMINATING,
        "rivals_checked": len(checked),
        "rivals_failing_shown": failing,
        "rivals_not_excluded": not_excluded,
    })
    return annotation, None


def _derive_seed(seed: int, class_index: int, ordinal: int,
                 attempt: int) -> int:
    """One deterministic build seed per (class,
    ordinal, attempt) — retries never reuse a seed,
    and the whole schedule is a pure function of the
    generator seed and the targeting order."""
    return seed * 1_000_003 + class_index * 10_007 + ordinal * 101 + attempt


# ------------------------------------------------------------------
# generation
# ------------------------------------------------------------------

def generate_practice_set(gap_report: dict[str, Any],
                          task_source: Any,
                          *,
                          seed: int = 0,
                          tasks_per_gap: int = 2,
                          tasks_per_partial: int = 1,
                          max_attempts: int = 8,
                          class_limit: int | None = None,
                          ) -> dict[str, Any]:
    """Generate a weakness-targeted practice set from
    a catalog gap report.

    ``gap_report`` is the output of
    ``catalog_gap.analyze_catalog_gaps`` (its
    ``per_class`` statuses and ranked ``gaps`` list
    are consumed; nothing else is read). ``task_source``
    is the family's builder, as an object or a dict
    of callables:

    - ``build(class_name, seed)`` -> task dict or
      None. The task dict follows the existing
      families' shape: ``task_id``, ``defects``
      (must include the target class), ``buggy_code``,
      ``shown_cases``, ``shown_truth`` (and, for the
      consumer's sake, the holdout split — carried
      through untouched). None means generation
      failure and is retried with the next derived
      seed, up to ``max_attempts`` per task.
    - ``run(code, case)`` -> the program's output on
      one case, compared against the shown truth.
    - ``rivals(task)`` (optional) -> a list of
      ``(name, code)`` rival-pattern programs, or
      None / an empty list when the family cannot
      construct rivals; those tasks are annotated
      ``shown_only``.
    - ``name`` (optional) -> the family name,
      recorded in the manifest.

    Targeting: gap-tier classes first, in the gap
    report's ranked order, ``tasks_per_gap`` each;
    then partial classes by headroom descending,
    ``tasks_per_partial`` each. Saturated, covered
    and catalog-only classes are never targeted.
    ``class_limit`` caps how many classes are
    targeted (after ranking) for budgeted runs.

    Returns the practice set manifest: targeting
    decisions, exclusions with reasons, per-class
    build/rejection counts and shortfalls, and the
    accepted tasks with their identifiability
    annotations and full task dicts (so the set is
    self-contained and reproducible from the
    recorded build seeds).
    """
    if not _is_int(seed):
        raise CurriculumGenError(f"seed must be an int, got {seed!r}")
    tasks_per_gap = _require_quota("tasks_per_gap", tasks_per_gap, 0)
    tasks_per_partial = _require_quota(
        "tasks_per_partial", tasks_per_partial, 0)
    max_attempts = _require_quota("max_attempts", max_attempts, 1)
    if class_limit is not None:
        class_limit = _require_quota("class_limit", class_limit, 1)
    if tasks_per_gap == 0 and tasks_per_partial == 0:
        raise CurriculumGenError(
            "tasks_per_gap and tasks_per_partial are both zero; "
            "nothing would be generated")
    per_class, gaps = _validate_gap_report(gap_report)
    build, run, rivals_fn, source_name = _source_parts(task_source)
    targets, excluded = _targeting(per_class, gaps)
    if class_limit is not None:
        for entry in targets[class_limit:]:
            excluded.append({
                "class": entry["class"], "status": entry["status"],
                "reason": "targeted by the ranking but beyond this "
                          f"run's class_limit ({class_limit})"})
        targets = targets[:class_limit]
        excluded.sort(key=lambda entry: entry["class"])

    manifest_tasks: list[dict[str, Any]] = []
    targeting_records: list[dict[str, Any]] = []
    seen_task_ids: set[str] = set()
    for class_index, target in enumerate(targets):
        cls = target["class"]
        quota = tasks_per_gap if target["tier"] == "gap" \
            else tasks_per_partial
        rejected = {REJECT_GENERATION_FAILURE: 0,
                    REJECT_DUPLICATE_TASK_ID: 0,
                    REJECT_NO_EXPOSURE: 0,
                    REJECT_ALL_RIVALS_PASS: 0}
        built = 0
        for ordinal in range(quota):
            accepted = False
            for attempt in range(max_attempts):
                build_seed = _derive_seed(seed, class_index, ordinal,
                                          attempt)
                task = build(cls, build_seed)
                if task is None:
                    rejected[REJECT_GENERATION_FAILURE] += 1
                    continue
                task = _validate_task(task, cls)
                if task["task_id"] in seen_task_ids:
                    rejected[REJECT_DUPLICATE_TASK_ID] += 1
                    continue
                annotation, reason = _identifiability(task, run, rivals_fn)
                if annotation is None:
                    rejected[reason] += 1
                    continue
                seen_task_ids.add(task["task_id"])
                manifest_tasks.append({
                    "task_id": task["task_id"],
                    "class": cls,
                    "defects": list(task["defects"]),
                    "build_seed": build_seed,
                    "identifiability": annotation,
                    "task": task,
                })
                built += 1
                accepted = True
                break
            if not accepted:
                # The shortfall is recorded in the class
                # record below; generation moves on to
                # the next ordinal/class rather than
                # padding the set with unchecked tasks.
                pass
        targeting_records.append({
            **target,
            "requested": quota,
            "built": built,
            "rejected": rejected,
            "shortfall": quota - built,
        })

    by_level: dict[str, int] = {}
    for entry in manifest_tasks:
        level = entry["identifiability"]["level"]
        by_level[level] = by_level.get(level, 0) + 1
    return {
        "generator": GENERATOR_NAME,
        "generator_version": GENERATOR_VERSION,
        "seed": seed,
        "source": source_name,
        "quotas": {"tasks_per_gap": tasks_per_gap,
                   "tasks_per_partial": tasks_per_partial,
                   "max_attempts": max_attempts,
                   "class_limit": class_limit},
        "targeting": targeting_records,
        "excluded": excluded,
        "tasks": manifest_tasks,
        "totals": {
            "classes_targeted": len(targeting_records),
            "requested": sum(r["requested"] for r in targeting_records),
            "built": len(manifest_tasks),
            "by_identifiability": by_level,
        },
    }
