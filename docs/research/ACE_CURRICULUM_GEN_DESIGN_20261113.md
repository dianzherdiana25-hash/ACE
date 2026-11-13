# Weakness-targeting curriculum generator — design

Status: **DESIGN + WORKING PROTOTYPE** (2026-11-13).
Module: `code/ace_operational/curriculum_generator.py`
(`generate_practice_set`); tests:
`code/ace_operational/test_curriculum_generator.py`
(17 tests, all passing). Wiring demonstration against
the real v4 gap report in §6.

## 1. Purpose

The catalog gap tool (`ACE_CATALOG_GAP_DESIGN_20261113.md`)
answers the coverage question: which classes of the
schema space the operator catalog covers, which are
empty, which are saturated. Its output is a ranked
agenda — but an agenda nobody executes is a
suggestion. Until now, the practice pools for
discovery runs were assembled by hand, class by
class, with no mechanical link to the measured
weakness.

This generator is that link. It consumes a gap
report and produces a **practice set**: fresh tasks
aimed at the classes the report ranks as blind —
measured gaps first, never-measured classes next,
partial classes by remaining headroom — so the next
round of discovery practice is spent where the
measurement says the catalog is weak.

Its second job is a gate. A practice task only
teaches if its shown cases *identify* the pattern
it targets; §4 defines the identifiability control
every shipped task must pass.

## 2. Inputs

- **Gap report** — the output of
  `catalog_gap.analyze_catalog_gaps`. Consumed:
  `per_class` (each class's `status` and
  `headroom_tasks`) and the ranked `gaps` list.
  Nothing else is read. The report is validated
  before use (known status vocabulary, partial
  classes carrying headroom, gap entries naming
  classes that exist in `per_class`); an
  inconsistent report raises `CurriculumGenError`.
- **Task source** — the family's builder, supplied
  by the caller as an object or a dict of
  callables:

  | member | contract |
  |---|---|
  | `build(class_name, seed)` | one task dict in the existing families' shape (`task_id`, `defects` including the target class, `buggy_code`, `shown_cases`, `shown_truth`, holdout split carried through untouched), or `None` for a generation failure |
  | `run(code, case)` | the program's output on one case, compared against the shown truth |
  | `rivals(task)` (optional) | a list of `(name, code)` rival-pattern programs, or `None` / empty when the family cannot construct rivals |
  | `name` (optional) | family name, recorded in the manifest |

  `build` must be deterministic in `seed`: the
  manifest records every build seed, and the set
  is reproducible from them.

## 3. The targeting rule

Deterministic, and entirely driven by the report:

1. **Gap tier** — classes whose status is `gap`
   (measured, zero admitted operators or chains)
   or `unmeasured` (declared in the universe,
   absent from both records), taken in the gap
   report's own ranked order: measured gaps by
   severity, then unmeasured classes. Quota:
   `tasks_per_gap` each.
2. **Partial tier** — classes with status
   `partial`, ordered by `headroom_tasks`
   descending (class name breaks ties): the
   classes where the extended solver still leaves
   the most evaluation tasks unsolved get practice
   first. Quota: `tasks_per_partial` each.
3. **Never targeted** — `saturated` (baseline at
   the ceiling, catalog adds nothing: practice
   buys nothing), `covered` (the extended solver
   already solves every evaluation task), and
   `catalog_only` (admitted operators exist but
   the class was never measured, so the report
   carries neither a ranking nor headroom for it).
   Exclusions are recorded in the manifest with
   reasons, not silently dropped.

`class_limit` caps the number of targeted classes
(after ranking) for budgeted runs; deferred
targets join the exclusion list with that reason
stated.

Retries: a `None` from `build`, a duplicate
`task_id`, or an identifiability rejection (§4)
retries with the next derived seed, up to
`max_attempts` per task. A class that still
cannot fill its quota is reported as a
**shortfall** in the manifest. The set is never
padded with unchecked tasks to make the numbers
round.

## 4. The identifiability control

The Stage C lesson (Addendum 17): a single-defect
fix can be perfect on the shown cases and wrong on
holdout, and a shown-driven search stops there —
at a code that merely looks finished. A pool task
whose shown cases are consistent with several
patterns teaches the search to stop at the wrong
one. So before a generated task enters the set,
its shown set is checked against the task itself,
using the family's own runner:

1. **Exposure** — the buggy program must fail at
   least one shown case. A shown set the defect
   never touches carries no signal about it.
   (For grid tasks this is guaranteed by the
   family's builder, which draws shown cases from
   the buggy-failing set; the control re-verifies
   it rather than trusting the builder.)
2. **Discrimination** — when the source names
   rivals, at least one rival must fail some
   shown case. If *every* rival passes all shown
   cases, the shown set cannot tell the target
   pattern from its rivals and the task is
   rejected (counted under
   `shown_consistent_with_all_rivals`).

For the grid family the rival set is: every
**partial fix** (the reference carrying a proper
subset of the task's defects — the classic
Stage C trap shape) and every **wrong-class twin**
(the reference carrying one other defect). The
twin check is signal the family's own builder
does not produce: its R1/R2 gate reasons about
removing the task's *own* defects, not about
whether the shown cases distinguish this class
from the other seven.

When the source provides no rivals, only exposure
is checked and the task is annotated
`identifiability.level == "shown_only"`. The
annotation is the honesty mechanism: the manifest
states that the stronger control was not
constructible for that family, instead of
claiming a check that did not happen.

**Limits, stated plainly.**

- The control certifies that *at least one* rival
  fails the shown set — not that all do. Rivals
  that still pass every shown case are named per
  task in `rivals_not_excluded`: they are the
  patterns this task's shown evidence cannot rule
  out, and they stay visible rather than being
  averaged away. The §6 demo contains a real
  instance.
- The rival set is the family's declaration,
  like the gap tool's blind spots: a family that
  names weak rivals gets a weak control. The
  generator never invents rivals for a family.
- Exposure is necessary, not sufficient — that
  asymmetry is the whole reason the `shown_only`
  level exists as a label instead of a pass.
- Targeting is per class, because the gap report
  ranks classes. Pair-defect practice tasks
  (where partial-fix rivals do the real work) are
  supported by the rival machinery but are not
  yet generated: ranking pairs is future work,
  not a silent gap.

## 5. Determinism and failure behaviour

- Build seeds derive arithmetically from the
  generator `seed`, the class's position in the
  targeting order, the ordinal, and the attempt —
  retries never reuse a seed, and identical
  inputs yield an identical manifest, ordering
  included.
- Fail-closed throughout: a malformed gap
  report, a malformed task (missing fields,
  defects not containing the target class, an
  empty shown set), or a broken source raises
  `CurriculumGenError` and no practice set is
  produced. Generation failures (`None` builds)
  and identifiability rejections are *not*
  errors — they are counted per class in the
  manifest, with shortfalls.

## 6. Wiring demonstration — real v4 gap report

Run once (script:
`~/workspace/ace-omega/curriculum_wiring_demo.py`;
full manifest:
`evidence/curriculum_wiring_demo.json`).
Inputs: `evidence/operator_discovery_v4.json` ×
`operator_catalog_v4.json` (the G4-materialised
catalog), the 8-class grid universe inventory,
and the four blind spots declared in the catalog
gap design §5 — the same inputs as the gap tool's
own first real run. Generator parameters:
`seed=20261113`, `tasks_per_gap=1`,
`tasks_per_partial=1`, `max_attempts=2`,
`class_limit=6`. Task source: the grid family
(`grid_generalization`'s own task builder; rivals
= wrong-class twins — the demo tasks are all
single-defect, so no partial fixes arise).

Result (0.38 s wall, **6 task builds** of the
12-build budget, zero rejections, zero
shortfalls):

| class | tier | shown | buggy fails shown | rivals failing / checked | rivals not excluded |
|---|---|---|---|---|---|
| diagonal_moves | gap (unmeasured) | 8 | 8 | 7 / 7 | — |
| no_up | gap (unmeasured) | 3 | 3 | 7 / 7 | — |
| start_offset | gap (unmeasured) | 8 | 8 | 7 / 7 | — |
| walls_passable | gap (unmeasured) | 3 | 3 | 7 / 7 | — |
| wall_char_x | partial (headroom 12) | 3 | 3 | 7 / 7 | — |
| dist_step_2 | partial (headroom 8) | 8 | 8 | 5 / 7 | `rival_class:wall_char_x`, `rival_class:walls_passable` |

Targeting followed the report exactly: the four
unmeasured substrate-catalog classes first (the
gap report's ranked order), then the partials by
headroom — `wall_char_x` (12), then `dist_step_2`
(winning the 8-headroom tie with
`returns_start_distance` on class name).
`returns_start_distance` and `bounds_off_by_one`
(headroom 4) were deferred by `class_limit` and
are recorded as excluded with that reason.

All six tasks are annotated `discriminating`.
The one imperfect annotation is the informative
one: the `dist_step_2` task's shown set does not
exclude the two wall-character twins — its shown
cases never exercise wall behaviour, so on shown
evidence alone a wall-defect hypothesis survives.
The control still certifies the task (five rivals
fail its shown set), and `rivals_not_excluded`
keeps the two survivors on the record: a
discovery run practising on this task should not
expect it to teach anything about wall classes.

## 7. What this does not do

- **No discovery, no solving.** The generator
  builds and checks practice tasks; running
  discovery over the set is a separate, future
  agenda step (and a separate budget).
- **No cross-family claims.** A practice set is
  built from one family's source against one
  family's gap report; the pricing family's
  coverage lives in its own records (declared
  blind spot 3 of the gap run).
- **No agenda authority of its own.** The
  generator executes the gap report's ranking;
  it does not re-rank, and it cannot see classes
  the schema space cannot express — those remain
  declared blind spots, upstream.
