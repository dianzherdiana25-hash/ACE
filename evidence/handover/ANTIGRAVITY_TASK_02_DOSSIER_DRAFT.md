# ANTIGRAVITY TASK 02 — DRAFT DESIGN: G3 TWO-FAMILY APPLICATION DOSSIER

Status: **DRAFT FOR RATIFICATION** by the program director (ila).
Author: Antigravity bench room (ila operating the bench; drafted
without the Gemini brain — its quota is exhausted until
~2026-11-18 ~22:14 WIB). Date: 2026-11-13.
Design source: PR #135, `docs/research/ACE_G3_INSTRUMENT_DESIGN_20261112.md`.
Companion work: Task 01 (the `g3_instrument.py` build) was
reassigned to Ian after the bench's clean quota stop; this dossier
is the step *after* the instrument exists.

**This document claims no result. It is not a preregistration.
G3 remains NOT_ASSESSED.** Nothing in it may be quoted as a G3
finding. It becomes operative only when ila ratifies the decisions
in §10 and a preregistration is created in the OMEGA-06 kernel
from the ratified text.

---

## 1. Purpose

Design the first live application of the G3 instrument: one
improvement, artifact-identical, evaluated in two distinct task
families — **grid** and **pricing** — with each family's baseline
and effect margin fixed in this dossier *before* any result is
seen, so that the instrument can mechanically score the outcome
as exactly one of:

- `TRANSFER_DEMONSTRATED`
- `SPECIALIZATION`
- `NOT_DEMONSTRATED` (with missing/failed items named)

## 2. The improvement under test

**Candidate:** the operator-discovery mechanism
(`code/ace_operational/operator_discovery.py`, incl. composition
discovery v2): generic AST edit schemas (schema, AST path,
parameter); operators discovered from a family's discovery pool;
an operator is admitted to the extended catalog only if it fixes
≥2 independent pool tasks; chains are discovered by greedy
re-enumeration on intermediate programs (depth bound 3); solving
is the greedy extended-catalog solver. Baseline arm = the same
solver restricted to the pre-discovery (authored) catalog.

**Existing source-family evidence (orientation only — NOT dossier
evidence):** on the grid universe, `evidence/operator_discovery_v4.json`
records baseline 0 → extended 15 held-out single-defect solves
across the four defect classes (bounds_off_by_one,
dist_step_2, returns_start_distance, wall_char_x), chain pool
3/6, mixed 2-defect evaluation 18/18 vs 0/18, control 34/34,
wall 1,337 s. That run was stage work: it was not created as an
OMEGA-06-kernel preregistration with an audit in the form C1
requires (see decision D2, §10).

## 3. Artifact identity — the decision this dossier turns on

C2 identity is by **artifact digest, never by name**. Two
readings exist, and the dossier must fix one before running:

- **Reading M (mechanism-as-artifact) — RECOMMENDED.** The
  artifact is the discovery *mechanism core*: the
  `operator_discovery.py` module bytes at a frozen commit, the
  schema-space enumeration, the admission rule (≥2 pool fixes),
  the chain-discovery bounds, and the greedy solver loop. The
  catalog it discovers is *output*, expected to differ per
  family. This is the reading the design doc itself names in
  its §6 ("the discovery mechanism — artifact-identical — is
  applied to grid and to a second family").
- **Reading C (catalog-as-artifact).** The artifact is the
  grid-admitted catalog itself, applied byte-identical to
  pricing code. Registered as the stricter variant, not the
  primary: catalog keys bind AST site paths and parameters of
  `navigate()`; most cannot even locate their site in pricing
  code, so Reading C would largely measure site-path portability,
  not mechanism transfer. It may be added later as a separate,
  explicitly-labelled dossier; it must not be silently mixed
  into this one.

**Identity rule under Reading M.** The preregistration records
an `artifact_manifest`: artifact name, frozen commit, and a
SHA-256 digest over the canonical bundle (module file bytes +
schema list + admission/chain/solver parameters + baseline
catalog reference). Both family evaluations must present the
identical manifest digest; any mismatch →
`NOT_DEMONSTRATED` with the mismatch named (the instrument's
anti-reward-hacking fence, Task 01 brief). Any change to the
mechanism after the freeze is a *new improvement*: this dossier
is void for it and must be re-preregistered — never amended
retroactively.

**Family machinery is not part of the artifact:** task
generators, per-family baseline variant generators, scorers and
budgets. The boundary is policed by §4-P1's replication check.

## 4. Preconditions (all must close before preregistration)

- **P1 — Family decoupling of the discovery runner.**
  `run_discovery` is currently grid-coupled (it imports the grid
  budget/scorer and calls `grid_variants` for baseline variants
  inside its solver). Refactor to an injected per-family adapter
  (task builder, budget/scorer, baseline variant generator)
  *without changing the discovery algorithm, schema space, or
  admission rule*. Guard: after the refactor, re-running the
  Stage F / v4 grid universe must reproduce the v4 headline
  numbers (15 singles, chain pool 3/6, mixed 18/18, control
  34/34); any deviation is recorded and explained before
  proceeding, and the frozen digest is taken *after* this
  refactor, never before.
- **P2 — Pricing adapter.** Task builder over
  `curriculum_lab._pricing_family` (reference `total(subtotal,
  member)`; defect classes: `threshold_boundary`,
  `tax_basis`, `member_basis`): buggy code = defect applied to
  the reference; shown cases for pool tasks, held-out cases for
  evaluation; scoring under the same timeout-guard discipline
  as `_safe_score` (a timeout is a failed candidate, never a
  hang). Baseline variant generator for pricing = the family's
  pre-improvement solver path, explicitly excluding discovered
  operators; the exact generator is named in the preregistration.
- **P3 — Instrument readiness.** `g3_instrument.py` exists
  (Ian's Task 01 build) and its dossier field schema is final.
  §7's field list is written against the PR #135 design; if the
  shipped instrument's schema differs, this dossier is amended
  to match *before* preregistration — never after results.
- **P4 — Pricing headroom (anti-saturation).** Pilot A/B/C v2
  saturated pricing+shipping under its arms (220/220), so a
  pricing evaluation with no headroom cannot measure an effect.
  Before preregistration, run a calibration on *separate*
  calibration tasks (never the evaluation tasks): if the
  baseline arm solves ≥90% of them, the evaluation universe is
  regenerated harder (2-defect compositions; `threshold_boundary`
  weighted) and recalibrated, until baseline headroom exists.
  Calibration tasks are then sealed and never reused as
  evaluation tasks.

## 5. Experimental design (per family, common protocol)

Splits, all seed ranges fixed in the preregistration and disjoint
from every prior run's seeds (prior usage enumerated at
preregistration time): **pool** (discovery; shown cases only),
**evaluation** (held out; discovery never touches it), **control**
(tasks the baseline already solves; regression check).

| | Grid (source family) | Pricing (target family) |
|---|---|---|
| Pool | 12 tasks — 3 per defect class × 4 classes (mirrors v4) | 12 tasks — 4 per defect class × 3 classes |
| Evaluation | ≥40 held-out single-defect tasks + 18 mixed 2-defect tasks (mirrors v4) | ≥45 held-out single-defect tasks (15/class) + 18 composed 2-defect tasks |
| Control | ≥30 baseline-solvable tasks | ≥30 baseline-solvable tasks |
| Arms | baseline catalog vs + admitted catalog discovered on the grid pool | baseline vs + admitted catalog discovered on the pricing pool |
| Effect | Δ = solved fraction (extended − baseline) on evaluation tasks | same |

Discovery runs per family on that family's own pool — under
Reading M that *is* the transfer claim (same mechanism, new
family), and the dossier states this openly wherever results
are reported. Runtime planning figure: ~25–45 min wall for both
families on the Muse VM (v4 grid alone: 1,337 s), to be
scheduled so as not to starve other benches' attested runs.

## 6. Margin and decision rule (fixed here, before results)

A family's transfer effect counts as **positive** iff all three
hold on its audited evaluation report:

1. **Δ ≥ +10 percentage points** (extended − baseline solved
   fraction). Rationale: below the observed grid source effect
   (~+32 pp in v4) by a wide factor, above one-task noise at
   n ≥ 40 (one task ≈ 2.5 pp).
2. **≥3 evaluation tasks** solved by the extended arm that the
   baseline arm does not solve (absolute floor against
   small-n artifacts).
3. **Zero control regression:** the extended arm solves every
   control task the baseline arm solves.

Outcome mapping for this two-family dossier:

| Grid effect | Pricing effect | Instrument outcome |
|---|---|---|
| positive | positive | `TRANSFER_DEMONSTRATED` (C1+C2+C3 pass) |
| positive | not positive | `SPECIALIZATION` |
| not positive | positive | `NOT_DEMONSTRATED`* |
| not positive | not positive | `NOT_DEMONSTRATED` |
| any dossier item missing/malformed, digest mismatch, audit not CLEAN | — | `NOT_DEMONSTRATED`, items named |

\* Grid is the C1 source family: if the source effect itself
does not reproduce under preregistration, C1 fails and no
transfer claim can stand on it, whatever pricing shows. A
pricing-only positive is recorded in the report text as a
named observation (a candidate *new* source effect for a
future dossier), never rescored into this one.

No re-runs until green: a null result is a publishable measured
outcome (cf. G2's two nulls). Any protocol change after
preregistration = a new preregistration, with the old one
preserved.

## 7. Dossier contents (what the instrument will score)

Per family, a sealed report file; plus shared items:

- `preregistration` — OMEGA-06 kernel record: protocol hash,
  this dossier's ratified text hash, seed ranges, split sizes,
  margin (§6 verbatim), frozen `artifact_manifest` digest.
- `artifact_manifest` — name, frozen commit, bundle digest (§3),
  brain-of-origin and freeze timestamp.
- `source_report` (grid) and `family_report` (pricing) — each:
  protocol hash back-reference, kernel audit result (must be
  CLEAN), artifact digest as evaluated (must equal the
  manifest), task-id lists for pool/evaluation/control,
  per-arm solved counts and fractions, control regression
  count, wall time, runner identity.
- `audit` — kernel audit output over all of the above.
Criteria version recorded on the assessment by the instrument,
per the G1 pattern.

## 8. Custody and anti-leakage

Split-custody as in OMEGA-06: whoever generates evaluation tasks
does not run discovery on them; evaluation seeds stay sealed
until the run; the improvement is frozen (§3) before any family
evaluation starts; no parameter, schema, or margin may change
after the first evaluation result is seen. Post-hoc discovery of
a protocol defect is recorded as a finding and handled by
re-preregistration, not by silent repair.

## 9. Principal risks

- **Pricing saturation** — mitigated by P4; residual risk that
  even composed pricing tasks saturate under the *baseline* arm,
  which would make pricing unmeasurable as a target family.
  Fallback, decided at ratification time only if P4 fails
  twice: substitute shipping (same generator family class in
  the curriculum lab) as target, recorded as a dossier amendment
  *before* preregistration.
- **Refactor drift (P1)** — the decoupling could quietly change
  the mechanism; the v4-replication guard is the fence, and the
  digest freeze happens after it.
- **Arm collapse** — if the pricing baseline variant generator
  accidentally includes the generic schema enumeration, the two
  arms measure the same thing and Δ ≈ 0 by construction; the
  preregistration must name both generators explicitly so the
  audit can check they differ exactly by the admitted catalog.
- **Compute contention** — long discovery runs on a shared VM
  have starved attested-server health windows before (cold-cache
  pattern); schedule per §5's planning figure.

## 10. Decisions requested at ratification

- **D1 — Artifact identity:** adopt Reading M
  (mechanism-as-artifact, §3); Reading C deferred to a possible
  later dossier.
- **D2 — Source effect:** re-measure the grid source effect
  under this preregistration on a fresh universe (recommended;
  C1-clean) rather than importing the v4 stage evidence.
- **D3 — Margin:** +10 pp, ≥3-task floor, zero control
  regression (§6) as written.
- **D4 — Sample sizes:** §5 table as written.
- **D5 — Frozen artifact scope:** include composition discovery
  v2 (chains) in the frozen mechanism (recommended — it is part
  of the current mechanism; freezing the superseded v3 would
  measure an improvement the program no longer runs).
- **D6 — Saturation fallback:** the §9 shipping substitution
  rule, pre-authorized as a pre-preregistration amendment only.

## 11. Execution order (after ratification)

1. Ian: P1 refactor + replication guard; P2 pricing adapter.
2. Director: P4 calibration; confirm headroom.
3. Director: create the kernel preregistration from the ratified
   dossier; freeze the artifact manifest.
4. Runner (director's mechanism, not an external brain — the
   two-hats rule applies to the measured run): execute both
   family evaluations under custody.
5. Ian/ila: assemble the dossier (§7); score it with
   `g3_instrument.py`; record the assessment and the brain of
   origin of every contribution in the checkpoint lineage.
6. ila: independent verification (diff, re-run instrument,
   audit trail) before any figure enters the consolidated
   report to the owner.

— End of draft. Awaiting ratification; ambiguities above are
findings, not silent resolutions.
