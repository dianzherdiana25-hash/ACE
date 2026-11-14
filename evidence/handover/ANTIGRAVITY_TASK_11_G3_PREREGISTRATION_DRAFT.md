# ANTIGRAVITY TASK 11 — DRAFT TEXT: G3 APPLICATION PREREGISTRATION (kernel-ready)

Status: **DRAFT TEXT — NOT SUBMITTED.** Author: Antigravity
bench room, 2026-11-13 (no Gemini). Sources: the ratified
Task 02 dossier design (decisions D1–D6, ratified 2026-11-13),
the Task 07 initial pricing census with composition caps
CAP-1/2/3 (ratified as allocation amendments 2026-11-13), the
Task 04/05/06 prerequisite designs, and the built G3
instrument (PR #143) with its coordinator rulings.

**This text is not a preregistration. No protocol hash exists
for it. G3 remains NOT_ASSESSED.** It is written so that, once
every blocker in §10 has closed, it can be submitted to the
OMEGA-06 kernel *as written* — the only fields still open are
marked ⟨TBD-AT-SUBMISSION⟩ and are mechanical (digests,
seeds, names), never substantive. Any substantive change
after submission is a new preregistration.

---

## 1. Hypothesis (falsifiable)

**H1.** The frozen operator-discovery mechanism (§2), applied
unchanged to two distinct task families — grid (source) and
pricing (target) — discovers, from each family's own discovery
pool, an admitted catalog that improves that family's solver
on held-out evaluation tasks by the margin fixed in §6.

H1 is **falsified for pricing** if the pricing effect is not
positive under §6; **falsified as a transfer claim** if either
family's effect is not positive (outcome `SPECIALIZATION` or
`NOT_DEMONSTRATED` per §6's mapping). A null result is a
publishable measured outcome; no re-run until green is
permitted under this registration.

## 2. The artifact (frozen, identity by digest)

Reading M (D1): the artifact is the discovery **mechanism
core** — the `operator_discovery.py` module bytes at the
frozen commit **after** the P1 refactor, the schema-space
enumeration, the admission rule (an operator is admitted only
if it fixes ≥2 independent pool tasks), the chain-discovery
bounds (composition discovery v2 included, per D5), and the
greedy solver loop. The catalog discovered per family is
*output* and is expected to differ per family; the transfer
claim of this registration is mechanism transfer, stated
openly wherever results are reported.

At submission, the registration records an `artifact_manifest`:
artifact name, frozen commit, and a SHA-256 digest over the
canonical bundle (module bytes + schema list + admission /
chain / solver parameters + baseline catalog reference).
Manifest digest: ⟨TBD-AT-SUBMISSION — computed at freeze⟩.
Any change to the mechanism after the freeze is a new
improvement: this registration is void for it.

Family machinery is **not** part of the artifact: task
generators, per-family baseline variant generators, scorers,
budgets. The two arms' generators must differ **exactly** by
the admitted catalog (the arm-collapse fence); both generator
identities are named in §3 so the audit can check this.

## 3. Candidates, baseline, negative control

- **Candidate:** the §2 mechanism; per family, the extended
  solver = baseline solver + the catalog admitted from that
  family's pool.
- **Required baseline (per family):** the same solver
  restricted to the pre-discovery solver path.
  - Grid baseline generator: `grid_variants` / `_OPERATORS`
    (the authored v1 catalog path, post-P1 adapter form).
  - Pricing baseline generator: the **frozen B-3 substrate's**
    operator set (Task 06 design) —
    ⟨TBD-AT-SUBMISSION: exact generator identity, nameable
    only once the substrate exists and is frozen⟩.
- **Negative control:** a sham arm per family — the extended
  solver loaded with an **empty** discovered catalog — run on
  that family's evaluation singles. Expected result: identical
  solved set to the baseline arm (±0 tasks). Any deviation is
  a harness-leakage finding: the run is invalid, the deviation
  is recorded, and no family effect may be scored from it.

## 4. Sets and allocation

All sets are pairwise disjoint (by task id for grid; by
`normalized_form` program identity for pricing), drawn from
seed ranges fixed at submission and disjoint from every prior
run's seeds ⟨TBD-AT-SUBMISSION: ranges + prior-usage
enumeration⟩. Evaluation tasks are never touched by discovery;
calibration tasks are sealed after P4 and never reused as
evaluation tasks.

**Grid (fresh universe; sizes per D4):**

| Set | Size | Composition |
|---|---|---|
| Discovery pool | 12 | 3 per defect class × 4 classes |
| Evaluation | ≥40 singles + 18 mixed | held-out single-defect + 2-defect |
| Control | ≥30 | baseline-solvable |

**Pricing (against the census universe of 216 unique
programs — 108 singles, 108 pairs — with the ratified caps):**

| Set | Size | Composition rule |
|---|---|---|
| Discovery pool | 12 singles | 4 per defect class × 3 classes |
| Evaluation | 45 singles + 18 pairs | 15 singles per class |
| Control | ≥30 | **CAP-1:** ≤10 singles, rest pairs (drawn from the frozen substrate's solved population) |
| B-3 probe (reserved, owned by the B-3 stage) | ≥50 | **CAP-2:** ≤20 singles; each single & pair class ≥5 |
| Calibration (P4) | per §5 | **CAP-3:** ≤12 singles (4/class) |
| Reserve | ≈41 (9 singles, 32 pairs) | replacements for tasks rejected pre-results; never a silent top-up after results |

Worst-case draw under the caps: 99/108 singles, 76/108 pairs
(Task 07 census §3, incl. its per-class check). **Fallback**
(only if the caps are rejected at submission): evaluation
singles 45 → 36. If the official B-3 census (§10, B5)
supersedes the initial census numbers, this table is
re-verified against it and amended **before** submission —
never after.

## 5. Procedure

1. **P1 replication guard (pre-freeze):** the refactored
   runner re-run on the Stage F / v4 grid universe reproduces
   the v4 headline numbers exactly (15 singles, chain pool
   3/6, mixed 18/18, control 34/34). Any deviation is recorded
   and explained; the freeze (§2) happens only after a clean
   or fully-explained replication.
2. **P4 calibration (pre-submission):** on the calibration
   set only, the pricing baseline arm's solved fraction is
   measured per the Task 05 interface (per-class + pooled).
   If pooled baseline ≥0.90, the hardening levers decided in
   the Task 05/06 designs are applied (max 2 rounds); if
   headroom still fails, the D6 path applies: shipping is
   substituted as target family by amendment to this text
   **before** submission, or the submission waits. The
   calibration outcome (fractions, rounds used) is recorded
   in the submission package.
3. **Discovery:** per family, on that family's pool only,
   under split custody (§7). Discovered catalogs are sealed
   (per-family catalog digest recorded) before evaluation
   opens.
4. **Evaluation:** per family, both arms + negative control
   on the identical evaluation/control sets, same budgets,
   arms as separate processes with no shared state. Scoring
   under the timeout-guard discipline (a timeout is a failed
   candidate, never a hang).
5. **Budget:** wall-clock budget for the whole run:
   ⟨TBD-AT-SUBMISSION — planning figure 25–45 min for both
   families from Task 02 §5; the kernel budget field is set
   at submission and the run must fit it or abstain⟩.

## 6. Pass rule (mechanical; verdicts derived, never asserted)

A family's effect is **positive** iff all three hold on its
audited report:

1. **Δ ≥ +10.0 percentage points** (extended − baseline
   solved fraction on evaluation singles; the report carries
   `margin_pp: 10.0`, fixed by this text).
2. **≥3 net-new solves:** ≥3 evaluation tasks solved by the
   extended arm that the baseline arm does not solve.
3. **Zero control regression:** every control task the
   baseline arm solves is also solved by the extended arm.

Overall outcome, scored by `g3_instrument.py` over the §8
dossier (criteria version recorded on the assessment):

| Grid | Pricing | Outcome |
|---|---|---|
| positive | positive | `TRANSFER_DEMONSTRATED` |
| positive | not positive | `SPECIALIZATION` |
| not positive | positive | `NOT_DEMONSTRATED` * |
| not positive | not positive | `NOT_DEMONSTRATED` |
| any item missing/malformed, digest mismatch, audit not CLEAN, negative-control deviation | — | `NOT_DEMONSTRATED`, items named |

\* Grid is the C1 source family (effect re-measured fresh
under this registration, per D2 — the v4 stage evidence is
orientation, not dossier evidence). A pricing-only positive
is recorded in the report text as a named observation — a
candidate new source effect for a future registration — and
is never rescored into this one.

## 7. Custody and audit requirements

- **Split custody (OMEGA-06):** the candidate custodian and
  the evaluator custodian are different parties, named at
  submission ⟨TBD-AT-SUBMISSION⟩; each signs their artifact
  digests (mechanism manifest; evaluation sets + evaluator)
  per the kernel's HMAC discipline. Evaluation seeds stay
  sealed with the evaluator custodian until the run.
- **Kernel audit must return CLEAN** over the registration +
  both family reports before the instrument scores anything.
  An audit of INCOMPLETE (tampered/truncated ledger) is not
  CLEAN and fails the dossier by name.
- Every family report carries: this registration's protocol
  hash (back-reference, must equal), kernel audit result,
  the artifact digest as evaluated (must equal the §2
  manifest — mismatch triggers the instrument's hard fence),
  its discovered catalog's digest, task-id lists for
  pool/evaluation/control, per-arm solved counts and
  fractions, `margin_pp`, control regression count, wall
  time, runner identity, brain-of-origin.
- The results ledger is append-only; forged or post-hoc
  edited entries invalidate the run at audit.

## 8. Dossier and scoring

The dossier assembled for the instrument follows Task 02 §7
as conformed to the built instrument's final schema (P3):
the grid report serves as both the C1 source report and a
family evaluation (the instrument's declared interpretation);
family identities are exactly `grid` and `pricing`; margins
are read by the instrument from the reports. The assessment,
its criteria version, and the brain-of-origin of every
contribution are recorded in the checkpoint lineage. ila
independently verifies (diff, instrument re-run, audit
trail) before any figure reaches the owner.

## 9. Reporting commitments

Results are reported to the owner as one consolidated report
stating: the outcome word, per-family numbers, the Reading-M
caveat (mechanism transfer; catalogs differ per family), the
calibration outcome, and any named failures. A null or
`SPECIALIZATION` outcome is reported with the same prominence
as a positive one.

## 10. BLOCKERS — what still prevents submission today

This text may **not** be submitted until every item below
closes with its named artifact. (Status at drafting:
2026-11-13.)

- **B1 — P1 refactor not built.** `run_discovery` is still
  grid-coupled. Design exists (Task 04); the refactor + its
  v4-replication guard have not run. *Closes with:* the
  refactored runner + replication report (§5.1). (Includes
  the open canonical-tree question R7 from Task 04.)
- **B2 — P2 pricing adapter not built.** No pricing
  FamilyAdapter exists. Design exists (Task 05).
  *Closes with:* the adapter + its tests.
- **B3 — B-3 pricing substrate not built or frozen.** The
  pricing baseline generator (§3) cannot be named, and the
  control set (§4) cannot be drawn, until the substrate
  exists, passes its ≥95% holdout bar, and is frozen with its
  digest bundle. Design exists (Task 06). *Closes with:* the
  frozen substrate + freeze report + its official census
  (B5).
- **B4 — P4 calibration not run.** Headroom of the pricing
  evaluation universe is unmeasured against the real baseline
  (B3). *Closes with:* the calibration report (§5.2),
  including the D6 decision if triggered.
- **B5 — Official B-3 census not run.** §4's numbers rest on
  the Task 07 *initial* census (generator as-is). The official
  census re-runs against the frozen substrate/generator at
  B3 and supersedes them. *Closes with:* the official census
  + re-verification of §4 (amendment before submission if
  the caps no longer fit).
  **ANNOTATION (hub ratification, 2026-11-13, mandatory):**
  the B-3 hardening lever is ratified as **case-grid
  expansion only** — widen the `_pricing_family` parameter
  ranges, with NO new defect classes and NO new templates —
  because the 216-program universe is saturated even for a
  generic comparator (216/216). Consequence: the official
  B-3 census will run over the EXPANDED generator, so §4's
  allocation numbers (exact against today's 216) are
  **placeholders**: at submission the allocation is
  **re-derived** from the new official census and its caps —
  not merely re-verified against them. Any §4 figure quoted
  before that re-derivation must carry this status.
- **B6 — P3 instrument corrections to confirm landed.** The
  two coordinator rulings from the G3 build verification
  (source report checked once; C2 verdict from valid
  evidence with invalid extras as warnings) must be confirmed
  in the shipped instrument the dossier will be scored with.
  *Closes with:* the corrected instrument + its tests green.
- **B7 — Seed ranges unfixed.** §4's ranges are
  ⟨TBD-AT-SUBMISSION⟩ by design; they must be enumerated
  disjoint from all prior runs (grid v1–v4, pilots, B-3 probe
  draws) at submission. *Closes with:* the seed table in the
  submission package.
- **B8 — Custodians unnamed.** Split custody (§7) requires
  two named parties. *Closes with:* custodian assignments
  recorded in the submission package.

## 11. Submission checklist (when §10 is empty)

1. Re-verify §4 against the official census (B5).
2. Run P4 calibration; record outcome; apply D6 if triggered
   (B4).
3. Complete the P1 replication guard (B1); freeze the
   mechanism; compute the §2 manifest digest.
4. Fix the seed table (B7); name both baseline generators
   (§3) and both custodians (B8).
5. Confirm the instrument build includes B6's corrections.
6. Submit this text to the OMEGA-06 kernel; record the
   returned protocol hash in the checkpoint lineage.
7. Only then: discovery, evaluation, dossier, scoring (§5,
   §8).

— End of draft text. Prepared under the owner's no-idle
directive as desk work; it authorizes no run and claims no
result.
