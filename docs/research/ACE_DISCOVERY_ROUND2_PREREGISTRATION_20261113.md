# Discovery round 2 — preregistered confirmatory sandbox run

Experiment: `discovery-round2-01`. Status: **DRAFT** — this
text fixes the criteria before the confirmatory run
executes; it is not a gate preregistration and submits
nothing to any kernel. The run's verdict feeds the
next gate design decision; it is not a gate verdict.

Design source: `ACE_DISCOVERY_VNEXT_DESIGN_20261113.md`
(PR #154; design + sandbox prototype). The run
measures the PROTOTYPE's schema family (statement
motion keys + the prototype's greedy solver), not the
full §2.2 depth-5 beam design — the beam is design,
not prototype, and is out of scope for this run.

## §0 Exploratory disclosure (read before the numbers)

The prototype already measured this band
exploratorily (PR #154, evidence
`evidence/discovery_vnext_sandbox_20261113.json`):
arm A 8/30, arm B 13/30, arm C 13/30; shown-
discriminating subset 13 tasks with A 8/13, B 13/13;
controls 30/30 + 30/30. Those numbers motivated
this run and are cited here, not hidden. This run
is a preregistered CONFIRMATORY REPLICATION on the
same band under the criteria fixed below, executed
by a fresh driver (`round2_run.py`) that recomputes
per-task solved sets. If its numbers differ from
the exploratory ones, the preregistered run governs
and the difference is reported. A fresh-band
confirmatory run (seeds 72000–72099) is a named
follow-on stage, not part of this run.

## §1 Operator space (pinned for this run)

- Motion keys: `("move_stmt", moved_fingerprint,
  anchor_fingerprint)`; fingerprint = (kind, binding
  target, operator, leftmost leaf name of value/test)
  + per-program occurrence suffix; constants are NOT
  part of the fingerprint. Collision-stability limit
  (per-program suffixes) is a known design limit and
  is NOT repaired in this run.
- Movable kinds: top-level `Assign` / `AugAssign`
  only. Anchors: any top-level statement. Motions
  never land after a `Return`. If-block motion and
  nested motion are design, not prototype — out of
  scope.
- Legality filter: def/use — a motion is enumerated
  only if every name a statement uses is defined
  before that use in the resulting order (parameters
  defined at entry). Reorderings among statements
  mutating the same accumulator are NOT filtered.
- Solver: the prototype's greedy loop mirroring
  `run_discovery.solve_with` (frontier ≤ 4, ≤ 6
  rounds, timeout-guarded scoring), variant provider
  injected. No frozen core module is edited.
- Admission: a motion key is admitted iff it fixes
  ≥ 2 independent pool tasks (`min_pool_fixes = 2`,
  credited per defect class; one class here).

## §2 Bands (fixed before the run)

- Class tasks: statement_order tasks from pricing
  seeds **70000–70099** (in order; first 10 built =
  pool, next 30 = evaluation). Validity gate:
  the variant must fail ≥ 1 case of the reference's
  grid (the prototype's gate, unchanged).
- Controls: ordinary lab pricing singles, level 1
  seeds **71000–71029** and levels 2–3 seeds
  **71000–71014** (the frozen generator's own
  classes).
- Fences: all bands disjoint from the statement_order
  calibration band (40000–40023), every G3
  application band (pricing 50000–59999, 60000–
  60099; grid 20261112–20261153), and the B-3 probe
  bands. The lab generator and the B-3 v1 freeze
  are not modified; the B-3 branch, wt-g3run,
  g3-run/, g3-kernel/ are not touched.

## §3 Arms

- **A** — frozen substrate via the frozen adapter
  (carried byte-identical: substrate `791fd77f…`,
  adapter `0f19ff1c…`, generator `22304a45…`).
- **B** — A + every legal motion (reachability
  ceiling for the family).
- **C** — A + motion keys admitted from the pool
  only (transfer).

## §4 Metrics and verdicts (fixed before the run)

Per-task solved sets are recorded for A, B, C on
the evaluation set and for A, B on the controls.
A task is **shown-discriminating** iff the buggy
program fails ≥ 1 shown case (shown cases and
truth from the task record; judged on shown, never
on holdout).

- **H1 — reachability.** B's solved share of the
  shown-discriminating tasks: ≥ 80% = PASS;
  < 50% = FALSIFIED; between = PARTIAL.
- **H2 — transfer.** Capture = (C − A) / (B − A)
  in solved counts on the evaluation set (all 30,
  not the discriminating subset): ≥ 60% = PASS;
  C − A = 0 solves = FALSIFIED (the frozen
  mechanism's calibration result, repeated);
  between = PARTIAL. If B − A = 0 the ratio is
  undefined and H2 is recorded INCONCLUSIVE
  (no gain exists to capture).
- **H3 — no regression.** On every control set
  where A is below ceiling: B ≥ A = PASS, else
  FAIL. On ceiling sets (A at maximum) the check
  is one-sided by construction and is reported as
  such; it cannot fail.

Overall outcome:
- `ROUND2_CONFIRMED` — H1 PASS, H2 PASS, H3 PASS.
- `ROUND2_PARTIAL` — any PARTIAL, none falsified.
- `ROUND2_FALSIFIED` — any hypothesis falsified.
- H2 INCONCLUSIVE (B − A = 0) is reported as its
  own outcome, not folded into PARTIAL.

## §5 Execution and evidence

Driver: `round2_run.py` (harness tree), importing
the prototype module from the round-2 worktree;
no frozen file is edited. Evidence:
`evidence/discovery_round2_run.json` (per-task
solved sets, admitted keys, control numbers,
walls). The dossier is this text + the evidence
file + the verdict table; it is scored by the
criteria above, not by an instrument, and no
kernel record is written.

## §6 Pre-written consequences

- CONFIRMED → the round-2 mechanism (motion keys
  as built) is the named input to the next gate
  design: core lift behind a replication guard,
  under its own fresh-band preregistration.
- PARTIAL → the design refinement is named from
  the numbers (which hypothesis fell short, by how
  much) before any further build.
- FALSIFIED → the schema-space round-2 direction
  is recorded as falsified on this class at this
  scale; the G3 SPECIALIZATION reading stands
  either way.
- H2 INCONCLUSIVE → the class's shown set cannot
  discriminate the arms; a fresh-band run with
  order-discriminating shown sets is required
  before any transfer claim.

Brain of origin: Muse (Ian). Addendum record to
follow the run.
