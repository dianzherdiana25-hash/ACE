# Catalog gap analysis — design

Status: **DESIGN + WORKING PROTOTYPE** (2026-11-13).
Module: `code/ace_operational/catalog_gap.py`
(`analyze_catalog_gaps`); tests:
`code/ace_operational/test_catalog_gap.py` (27 tests,
all passing). First real output in §7.

## 1. Purpose

ACE's discovery runs write two records and then stop:
a discovery evidence record (per-class pool /
candidate / admission / evaluation numbers) and,
since the G4 work, a materialised operator catalog
(the admitted keys, with a digest). Nothing read
those records back to answer the coverage question —
*which classes of the space does the catalog cover,
which are empty, which are saturated?* — so the next
discovery agenda was chosen by a human eyeballing
raw tables.

This tool is the read-back. It turns the two records
into a ranked gap report, so the next discovery
agenda is an output of measurement: run discovery
where the measured loss is, stop spending search
where the class is saturated, and see — as rows in a
table, not as surprises — the classes that were
never measured at all.

It is deliberately narrow: a pure function over the
two record dicts. No solving, no discovery, no file
IO. Deterministic (identical inputs → identical
output, including ordering) and fail-closed
(malformed input raises `CatalogGapError` naming the
offending field; no partial report is produced from
input the tool cannot trust).

## 2. Inputs

- **Discovery evidence record** — the
  `operator_discovery_v*` shape: a `by_class`
  mapping, per defect class: `pool_tasks`,
  `candidate_operators`, `admitted_operators`
  (key strings), `admitted_chains` (key strings),
  `eval_tasks`, `eval_solved_baseline`,
  `eval_solved_extended`. (An optional
  `pool_tasks_fixed` is read when present — see §6.)
- **Catalog artifact** — the `operator_catalog_v*`
  shape: a `classes` mapping, per class:
  `operators` and `chains` key lists. The catalog's
  own digest is its identity and is verified by
  `catalog_artifact.py`, not here; this tool
  cross-checks the catalog's per-class key sets
  against the evidence record's admitted lists and
  reports agreement per class (`catalog_consistent`).
- **`universe_classes`** (optional) — the full class
  inventory of the task universe, declared by the
  caller (e.g. every defect class the generator can
  produce). Without it, the inventory is only what
  the two records mention.
- **`blind_spots`** (optional) — declarations, see §5.

## 3. Class inventory

The inventory is the union of: classes in the
evidence record, classes in the catalog, and classes
declared in `universe_classes`. For the grid family
the universe inventory is the generator's full
defect map (`grid_generalization.ALL_DEFECTS`):
four substrate-catalog classes (`walls_passable`,
`start_offset`, `no_up`, `diagonal_moves`) and four
holdout classes (`dist_step_2`, `bounds_off_by_one`,
`returns_start_distance`, `wall_char_x`).

## 4. Per-class metrics and classification

Per class the report carries: `pool_tasks`,
`pool_tasks_fixed` (see §6), `candidate_operators`,
`candidate_yield` (admitted ÷ candidates),
`admitted_operators`, `admitted_chains`,
`eval_tasks`, `eval_solved_baseline`,
`eval_solved_extended`, `baseline_rate`,
`extended_rate`, `lift_tasks`, `lift_rate`,
`headroom_tasks` (eval tasks the extended solver
still does not solve), `evidence_strength`
(pool + eval + candidate counts — how much
observation stands behind the row), `in_catalog`,
and `catalog_consistent`.

Each class gets exactly one status:

- **gap** — measured, but zero admitted operators
  and zero admitted chains. The class was searched
  and the catalog holds nothing for it.
- **saturated** — `lift_tasks == 0` and
  `baseline_rate >= 0.90` (the named constants
  `SATURATION_LIFT_TASKS`, `SATURATION_BASELINE_RATE`):
  the unaided solver already solves the class and
  the catalog adds nothing; no headroom remains for
  discovery to buy.
- **covered** — the extended solver solves every
  evaluation task.
- **partial** — admitted operators exist and
  headroom remains.
- **catalog_only** — present in the catalog, never
  in a discovery evidence record (no evaluation
  measurement exists).
- **unmeasured** — declared in the universe
  inventory, absent from both records.

**Gap ranking.** `gaps` lists gap-status classes
(kind `no_admitted_operators`) and unmeasured
classes (kind `unmeasured`). Measured gaps rank
first, by severity descending — severity is the
measured loss, `eval_tasks − eval_solved_baseline`,
the evaluation tasks the unaided solver leaves
unsolved — then by evidence strength descending,
then by class name (the deterministic tiebreak).
Unmeasured classes follow, by name: an unmeasured
class never outranks a measured loss, because the
agenda should act on evidence before absence.
`saturated` lists saturated classes by name, each
with its baseline rate and zero lift.

## 5. Blind spots — declared, never inferred

A defect class the schema space itself cannot
express leaves **no trace** in either input record:
it produces no candidates, admits nothing, and
appears in no table. The canonical lesson is
`statement_order` (Addendum 49): the schema
enumerates expression-level edits only, so a fix
that is a statement reordering is undiscoverable by
construction — discovery admitted 11 operators on
that stratum and the evaluation delta was exactly
0, for a named structural reason.

Therefore this tool **never infers** blind spots.
They enter only through the `blind_spots` argument:
entries with a `name` and a stated `reason`,
declared by a human or a design document, copied
into the report verbatim (an entry without a reason
is rejected — a blind spot without a declared
reason is a guess). An empty `blind_spots` list in
a report means "none declared", never "none exist".

Declared for the grid-family run in §7:

1. **statement_order** — the schema space
   enumerates expression-level edits only; it
   contains no statement motion, so a defect whose
   fix is reordering statements can never be
   discovered, admitted, or counted by this tool.
   Measured consequence (Addendum 49 calibration):
   discovery admitted 11 operators on the
   statement_order stratum and evaluation delta
   was 0.
2. **deep_composition_3plus_defects** — the grid
   universe generator builds single-defect and
   pair tasks only, and chain search is
   depth-bounded; defect combinations of three or
   more interacting defects are never generated,
   so no evidence about them can exist in either
   input record.
3. **pricing_family_out_of_scope** — the §7 report
   was run on the grid family's evidence and
   catalog only. The pricing family's defect
   classes live in separate evidence records;
   their coverage is not measured by that run and
   must not be read into it.
4. **families_without_generators** — defect
   families with no task generator at all (e.g.
   concurrency, I/O, mutable-state defects) have
   no universe, no evidence, and no catalog; they
   are unmeasurable by construction and appear
   nowhere in the report, not even as unmeasured
   rows.

## 6. Honest limits of the tool

- **`pool_tasks_fixed` is not in the v4 evidence
  shape.** `run_discovery` records how many pool
  tasks exist and how many candidates were examined,
  but not how many pool tasks the admitted set
  fixes. The tool reads the field when a record
  carries it and reports `null` — never a guess —
  when it does not. Recommended evidence-shape
  extension: future discovery records should carry
  `pool_tasks_fixed` per class (pool tasks solved by
  the admitted set), which this tool will then
  surface unchanged.
- **Per-task structure is invisible.** The records
  are aggregates; the tool cannot tell whether a
  class's headroom is concentrated in a few task
  shapes or spread evenly, nor which admitted
  operator earns the lift.
- **Schema-kind usage is not summarised.** The
  catalog's keys encode (schema kind, AST path,
  parameter); a histogram of admitted keys by schema
  kind is computable from the catalog but is not
  part of this report's contract. (Noted by hand
  for the v4 catalog in §7; a `schema_coverage`
  section is the named extension if a future agenda
  needs it.)
- **One family per run.** A report covers exactly
  the records it is fed; cross-family claims
  require cross-family inputs (see blind spot 3).

## 7. First real output — v4 evidence × v4 catalog

Run once, read-only, on
`evidence/operator_discovery_v4.json` and
`operator_catalog_v4.json` (the G4-materialised
catalog whose source is that same evidence record),
with the 8-class grid universe inventory and the
four blind spots of §5 declared. Numbers below are
quoted exactly from the tool's output.

Per-class (all four measured classes are
`partial`; all four are `catalog_consistent: true`):

| class | admitted ops | chains | candidates | yield | eval | baseline → extended | lift | headroom | evidence strength |
|---|---|---|---|---|---|---|---|---|---|
| bounds_off_by_one | 3 | 1 | 3 | 1.0 | 8 | 0 → 4 | +4 (0.5) | 4 | 14 |
| returns_start_distance | 1 | 1 | 1 | 1.0 | 13 | 0 → 5 | +5 (0.384615) | 8 | 17 |
| dist_step_2 | 1 | 0 | 1 | 1.0 | 11 | 0 → 3 | +3 (0.272727) | 8 | 15 |
| wall_char_x | 1 | 0 | 55 | 0.018182 | 15 | 0 → 3 | +3 (0.2) | 12 | 73 |

`gaps` — no measured class is a gap (every measured
class admitted at least one operator). All four gap
entries are kind `unmeasured`, severity 0, in ranked
order: **diagonal_moves, no_up, start_offset,
walls_passable** — the substrate's authored catalog
classes. They are absent from the discovery
evidence and from the discovered catalog because
the v4 protocol's discovery pool held holdout
(new_only) singles only; they are covered by the
authored substrate operators, not by anything
discovery admitted. The tool surfaces the fact;
what it means is an agenda question: either a
future discovery pool includes catalog classes, or
the catalog artifact's scope is stated as
holdout-only so the absence is a decision, not a
surprise.

`saturated` — **empty**. No measured class is
saturated: every baseline rate is 0.0, so the
saturation rule (lift 0 at a ≥ 0.90 baseline) fires
nowhere. Saturation is a property this catalog has
not yet reached anywhere.

`blind_spots` — the four declarations of §5,
verbatim.

Two readings the numbers support directly:

- **Headroom is the agenda.** Across the four
  measured classes the extended solver solves
  15 of 47 evaluation tasks; 32 tasks of headroom
  remain, concentrated in `wall_char_x` (12) and
  in `dist_step_2` / `returns_start_distance`
  (8 each). None of it is blocked by saturation.
- **Search efficiency is a second signal.**
  `wall_char_x` examined 55 candidate operators to
  admit 1 (yield 0.018182); the other three classes
  admitted every candidate they examined (yield
  1.0, but from only 1–3 candidates each — their
  pools barely proposed anything). The next
  discovery round has both a coverage problem
  (thin candidate generation on three classes) and
  an efficiency problem (candidate flooding on the
  fourth), and the two are different interventions.

Manually noted (from the catalog, not a tool
output): admitted keys — operators and chain steps
together — use 5 of the 6 schema kinds the
enumerator can emit (`binop_swap` ×3,
`return_indices` ×3, `int_constant` ×2,
`binop_unwrap` ×1, `string_literal` ×1).
`compare_swap` appears in zero admitted keys.
Whether comparison-operator defects are absent from
the universe or merely never fixed by an admitted
operator is exactly the kind of question the next
run of this tool, over richer evidence, should be
able to pose precisely.
