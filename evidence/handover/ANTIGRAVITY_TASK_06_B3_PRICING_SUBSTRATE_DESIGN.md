# ANTIGRAVITY TASK 06 — DESIGN NOTE: B-3, the authored pricing substrate stage

Status: **DESIGN ONLY.** No code is changed by this note and it
authorises no build. It designs the stage that ratified
decision B-3 (Task 05) requires: an authored pricing repair
substrate, built and frozen as its own stage *before* any
pricing discovery runs, so the G3 dossier's baseline arm is a
real mechanism and not an enumeration in disguise.
Precedent: Phase 2 Stage C — the grid substrate
(`grid_substrate.py`, PR #125) — mirrored deliberately below.
Author: Antigravity bench room, 2026-11-13 (no Gemini).

---

## 1. Shape of the stage (the Stage C pattern, restated)

Stage C's anatomy, which this stage copies:

1. A **comparator measurement already exists** showing the
   generic solver cannot reach the defect classes (grid:
   token-search 0/58).
2. A substrate module: one **structural operator generator**
   per measured defect class (or per class group), each a
   function `tree -> [modified trees]` that recognises its
   defect's *structural signature* in the buggy code and emits
   repaired variants; a `*_variants(code, operators)` union
   function (parse-checked, deduplicated, change-only); a
   greedy shown-scored solver mirroring `solve_grid`.
3. A **probe**: substrate vs the generic comparator on the
   *identical* task set, holdout judged by the curriculum
   verifier, results recorded per task.
4. An **epistemic label**, stated in the deliverable itself:
   operators authored against a known defect catalog prove
   that structure-level operators *reach* these classes — not
   generalisation to unseen classes. That question belongs to
   discovery, later.

Proposed module: `code/ace_operational/pricing_substrate.py`,
with `pricing_variants(code, operators=...)` and
`solve_pricing(task, budget, *, shown_total, ...)` signatures
parallel to grid's, so the P1 adapter (Task 04/05) can bind
`baseline_variants = pricing_variants` directly. Scoring uses
the `reasoning_lab.Budget` pattern (shown cases only, score =
*count* of passed shown cases).

## 2. Operators: structural, signature-based, never string-replace

The family's defect *transforms* in `curriculum_lab` are
string replacements of the reference. The substrate must
**not** be: an operator that works by searching for the
defect's literal text is reading the answer key, breaks under
renaming, and cannot distinguish defect from correct code in
general. Each operator below recognises a *symptom structure*
in the buggy AST and repairs it generically — the wall-guard
precedent (it rebuilds index names from surviving code rather
than assuming them) applied to `total()`.

The accumulator discipline comes first, shared by two of the
three operators: in `total()`, the accumulator is the variable
bound from the first parameter in the opening assignment
(`t = subtotal`) and targeted by the discount/tax augmented
assignments. Operators identify it **structurally** (first
assignment binding a parameter name; AugAssign target), never
by the literal name `t` — the substrate must survive the lab's
renaming normalisation.

- **`_variants_threshold` → class `threshold_boundary`.**
  Signature: an `If` whose test is a single `Compare` with op
  `Gt` between the first parameter and an integer constant,
  guarding a discount AugAssign. Variant: the same test with
  `GtE`. On correct code (test already `GtE`) it emits nothing.
- **`_variants_rebase_basis` → classes `tax_basis` and
  `member_basis`.** Signature: an AugAssign (`+=` or `-=`)
  whose right-hand side is a multiplication chain *rooted at
  the raw parameter* instead of the accumulator. Variant, one
  per offending statement: rebase that statement's chain onto
  the accumulator. One generator serving two classes is the
  grid pattern (`_variants_directions` serves two classes);
  the final unconditional statement is the tax site, the one
  inside the member `If` is the member site, and the variants
  are emitted per site so the greedy solver can compose them
  across rounds for pair defects.
- **`_OPERATORS`** = the tuple of the two generators, in a
  fixed order, named in the freeze record (§5).

Composition: pairs are repaired by the greedy solver applying
one operator per round (grid precedent: `max_rounds=6`,
frontier ≤4, pairs solved 58/58). The known pricing masking
(tax masks member — fixing member first gains no shown case)
is a *path* property the lab's gradient-path guarantee already
handles at the task level; the probe (§3) must still report
pair results per pair class so a stall is visible, not
averaged away.

Unit tests, mirroring `test_grid_substrate.py`'s three:
variants change code and parse · the reference produces **no**
variants (operators fire only on defect signatures) · the
solver repairs single *and* pair defects.

## 3. Probe protocol (the 58/58 analogue)

- **Probe set first, operators second.** Before any operator
  is written, the coordinator/director fixes the probe set by
  declaring a seed range; tasks are generated by
  `curriculum_lab.generate_task`, deduplicated by
  `normalized_form`, and the set (task ids + program digests,
  per class: singles of all three classes, all three pair
  classes) is recorded in the stage's evidence file. Target
  size ≥50 unique programs with every defect class and pair
  class represented ≥5 times; the actual census (§6, B3-R5)
  bounds what is achievable and is reported, not rounded.
  **Operators are then authored against the defect catalog —
  never iterated against the probe set.** If the probe fails,
  operator revisions constitute substrate v2 and are probed on
  a **fresh** set from a new seed range. One-shot per version:
  this is the fence against tuning-to-the-probe, the pricing
  form of reward hacking.
- **Arms:** (a) comparator — `reasoning_lab.solver_token_search`
  at budget 400 (the program's smoke value, kept for
  cross-family comparability); (b) substrate — `solve_pricing`
  with the same evaluation-budget ceiling. Both see shown
  cases only; **holdout judgement by the lab verifier**
  (`verify_candidate` over all cases) for both arms.
- **Declared success bar** (fixed here, before any run): the
  substrate solves ≥95% of the probe set on holdout, including
  **all** single-defect tasks; the comparator's number is
  reported as measured context with no bar. Wall time
  recorded. A miss is a stage finding, published as measured —
  the stage does not quietly re-probe.
- **Epistemic label** in the stage report, verbatim in spirit
  from Stage C: this probe proves the operators *reach* the
  three pricing defect classes; it says nothing about unseen
  classes, and nothing about transfer — that is G3's question,
  asked later, by a different instrument.

## 4. Control population: real, and not an enumeration subset

The dossier's control set (Task 02: ≥30 tasks, zero-regression
rule) is drawn **from this substrate's solved population**:

- Source: unique pricing programs the **frozen** substrate
  solves on holdout, spanning L1–L3 (singles alone nearly
  exhaust the finite universe once pool/evaluation/calibration
  take their shares — see B3-R5), class-balanced, from a seed
  range disjoint from the discovery pool, evaluation, and
  calibration ranges, deduplicated against all three by
  `normalized_form`.
- At freeze time the substrate's solve rate over the declared
  control set is verified to be **100%** and recorded; in a
  dossier run, any baseline-arm miss on control is therefore
  an integrity finding about the run, not a property of the
  tasks.
- **Why this is not the B-2 collapse:** the fence from Task 05
  was against a baseline *generator* equal to the discovery
  enumeration (the extended arm would add nothing). A control
  *population* defined by the baseline's competence is the
  opposite arrangement — it is exactly grid's `catalog_control`
  (34 tasks the authored catalog solves, 34/34 before and
  after discovery). Control measures whether the extended arm
  *breaks what the baseline already had*; it is not where the
  transfer effect is measured, and no control task may appear
  in the evaluation set.

## 5. Freeze, digest, attribution

- **Freeze event:** the substrate ships as its own stage —
  own branch and draft PR (Stage C precedent: PR #125), module
  + tests green in the package sweep, probe report written to
  `evidence/` (per-task results for both arms, probe-set
  digests, wall time). The coordinator's ratification of the
  freeze is recorded in the checkpoint lineage (an Addendum),
  with the stage's brain of origin named in commits and in
  the report, per the handover rules.
- **Digest (this becomes `baseline_catalog_id` in Task 05's
  adapter and the baseline reference in the dossier's artifact
  manifest):** SHA-256 over the canonical bundle — substrate
  module bytes · the ordered `_OPERATORS` generator names ·
  solver parameters (`max_rounds`, frontier width) · probe
  report digest · the `curriculum_lab` generator digest at
  freeze time (operator signatures are fitted to its reference
  template; if the template moves, the substrate must be
  re-probed — see B3-R3).
- **Versioning:** frozen as **pricing substrate v1**. Any
  post-freeze change — operator, signature, solver parameter —
  is v2: new probe on a fresh set, new digest, new freeze
  record. A dossier preregistration names version + digest;
  a discovery run executed against any other digest is an
  integrity failure of that run, full stop.
- **Custody:** the substrate's author does not select the
  probe set (fixed by seed range before authoring, §3) and,
  per the two-hats rule, is not the brain that later runs the
  measured discovery dossier against this baseline.

## 6. Risks and ambiguities (named, not resolved)

- **B3-R1 — Straw-man by authorship.** The baseline's author
  knows it will be compared against discovery. The fences are
  procedural, and they are the design: probe set fixed before
  authoring, one-shot probe per version, success bar declared
  in this note, freeze ratified by the coordinator. Residual
  risk stands and is recorded here so the dossier's readers
  can weigh it.
- **B3-R2 — Operator overreach.** `_variants_rebase_basis`
  fires on any parameter-rooted multiplication in an AugAssign.
  In today's template that shape *is* the defect; a future
  template where a parameter-rooted basis is correct would be
  misrepaired. Mitigations in-design: variants are only
  *candidates* — adoption is shown-score-gated, holdout judges
  — and the reference-no-variants test pins today's boundary.
- **B3-R3 — Template brittleness.** Signatures are fitted to
  the current 7-line `total()` template. P4's harder-regeneration
  levers 3–4 (case-grid or defect-catalog changes) may move
  the template after the substrate is frozen; the freeze
  bundle therefore includes the generator digest, and any
  generator change invalidates the freeze until re-probed.
  Sequencing consequence for the program: **P4 calibration
  levers that touch the generator must be decided before, or
  jointly with, this freeze** — calibrating after freezing
  with a generator-changing lever would burn the freeze.
- **B3-R4 — Pair masking at solve time.** The gradient-path
  guarantee is about the *true* fix order; greedy best-first
  can still stall on a pair if its first-step candidates all
  score flat. Probe reports pairs per class precisely so this
  shows up as data, and `max_rounds`/frontier are freeze
  parameters, not tuning knobs after the fact.
- **B3-R5 — Population arithmetic.** The stage must publish a
  **census**: enumerate a wide seed range, dedupe by
  `normalized_form`, count unique programs per class and level
  (theoretical ceiling 216; the real number is whatever
  generation yields). Every downstream allocation — probe set,
  control ≥30, discovery pool 12, evaluation ≥45+18,
  calibration — is drawn against this census at
  preregistration. If the census cannot fund all sets at
  their designed sizes, sizes are amended *before*
  preregistration (Task 05, P2-R1), never by overlap.
- **B3-R6 — Comparator fairness.** Token-search at budget 400
  is a *reach* comparator (can generic search touch these
  classes at all?), not a rival baseline for the dossier. The
  stage report must not present the probe as substrate-vs-
  baseline for G3 purposes; the dossier's baseline arm is the
  substrate itself, full stop.

— End of design note. Decisions embedded (probe bar ≥95% +
all singles; one-shot probe rule; control from the frozen
solved population; freeze bundle composition) are design
proposals for the coordinator's ratification at the stage's
turn, not instructions to build.
