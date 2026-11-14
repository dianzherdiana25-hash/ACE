# ANTIGRAVITY TASK 05 — DESIGN NOTE: P2, the pricing FamilyAdapter

Status: **DESIGN ONLY.** No code is changed by this note and it
authorises nothing. It fills in precondition P2 of the ratified
Task 02 dossier draft, against the `FamilyAdapter` contract
designed in Task 04 (`ANTIGRAVITY_TASK_04_P1_DECOUPLING_DESIGN.md`).
Author: Antigravity bench room, 2026-11-13 (no Gemini).
Source read in full for this note:
`code/ace_operational/curriculum_lab.py`.

---

## 1. The pricing family, mapped from source

`_pricing_family(rng)` renders one parameter combination —
threshold ∈ {100000, 250000, 500000}, bulk_pct ∈ {5, 10},
member_pct ∈ {5, 10, 15}, tax_pct ∈ {10, 11} (36 combinations) —
into:

- **Reference:** `total(subtotal, member)`, seven lines of pure
  deterministic arithmetic (bulk discount → member discount →
  tax on the running total). No loops, no state, no I/O.
  Entrypoint: `"total"`.
- **Case grid:** 12 cases — subtotal ∈ {0, threshold−1,
  threshold, threshold+1, 2·threshold, 75000} × member ∈
  {False, True}.
- **Defect catalog** (name → subtlety, string-replacement
  transform of the reference):
  - `threshold_boundary` (2): `>= threshold` → `> threshold`
  - `tax_basis` (1): tax computed on `subtotal` instead of the
    running total `t`
  - `member_basis` (1): member discount computed on `subtotal`
    instead of `t` (the transform function is named
    `defect_member_order` in source; the catalog key is
    `member_basis` — use catalog keys everywhere)

`generate_task("pricing", level, seed=…)` composes defects per
the level taxonomy (L1: 1 defect · L2: 1 defect, subtlety ≥2 —
only `threshold_boundary` qualifies · L3: 2 defects · L4: 2
defects, subtlety ≥3, plus adversarial spec dressing), freezes
`expected` by running the reference over the case grid, selects
`shown_cases` under the lab's two hard requirements —
**identifiability** (every partial fix fails a shown case) and
**gradient path** (some fix ordering strictly raises the shown
score at each step), capped at 8 of the 12 cases — and validates
the task at birth (buggy fails, reference passes, level honest,
no leakage into the public bundle).

Two properties matter for everything below:

- **The universe is finite and small.** 36 parameter
  combinations × 6 defect sets (3 singles + 3 pairs) = at most
  216 distinct buggy programs, fewer after invalid combos.
  Seeds do not create new programs; they re-draw old ones.
- **Tasks are born climbable.** The gradient-path requirement
  is enforced at generation — unlike the grid universe, where
  climbability was an empirical question. This raises the
  saturation risk (§4) structurally, not incidentally.

## 2. Task-contract mapping (curriculum task → discovery task)

| Discovery contract | Pricing source |
|---|---|
| `buggy_code` | `task["buggy_code"]` |
| `shown_cases` | `task["shown_cases"]` (tuples) |
| `shown_truth` | `task["expected"]` at the shown cases' indices in `task["cases"]` |
| `holdout_cases` | `task["cases"]` minus shown (4–10 cases) |
| `holdout_truth` | `task["expected"]` at those indices |
| `defects` | `[d["name"] for d in task["defects"]]` |
| `task_id` | `task["task_id"]` |

The case↔expected alignment is positional and silent if wrong
— the adapter's first unit test is: scoring the reference code
through the adapter yields a perfect count on shown *and*
holdout cases, for tasks from every level.

**Deduplication rule (mandatory):** pool / evaluation /
calibration membership is decided over **unique programs**
(`curriculum_lab.normalized_form` of the buggy code), never
over task ids — the same program drawn under two seeds carries
two ids. Split builders must assert pairwise-disjoint
normalized forms across the three sets, in the spirit of the
lab's own `assert_split_integrity`.

## 3. Filling the FamilyAdapter contract

- **`family_id`** — `"pricing"`.
- **`make_budget(task)`** — a budget whose `.score(code)`
  executes the candidate in a fresh namespace (the lab's
  `_run_cases` pattern; lab-generated code only) and returns
  the **count** of shown cases whose output equals the frozen
  `shown_truth`. What "budget" means here: pricing needs no
  step budget — the reference has no loops and no schema edit
  in the frozen space can create one (edits rewrite existing
  nodes; none synthesises a `While`/`For`). The real limits are
  the core's own fences, which stay in force unchanged: the
  0.5 s SIGALRM guard per candidate in `_safe_score`, and an
  exception during execution scores the candidate as failed
  (the `verify_candidate` discipline), never propagates.
- **`passes(code, cases, truth)`** — count of holdout cases
  matching frozen truth, executed the same way, under the
  core's 5 s holdout guard.
- **`extra_string_candidates(code)`** — the empty set. Pricing
  code contains no string literals at all, so the grid `"#"`
  seed would be inert here; it is still routed through the
  adapter (Task 04, K6) so the core stays family-free.
- **`baseline_catalog_id`** — a digest over the baseline
  generator's code and operator list, whatever §3.1 decides;
  recorded in the artifact manifest like grid's.
- **`baseline_variants(code)`** — **the design decision of this
  note; see §3.1.**

### 3.1 What is the baseline arm for a pure-function family?

Grid's baseline is an *authored structural catalog*
(`grid_variants` over `_OPERATORS`) that predates discovery.
Pricing has no equivalent: no pricing repair substrate was ever
built (the pilot's substrate-v2 solver belongs to the A/B/C
machinery — a different solver architecture, unusable here
without confounding solver with catalog). Three candidate
definitions:

- **B-1, empty generator.** Baseline variants = none; the
  baseline arm solves a task only if the buggy code is already
  shown-perfect, which valid tasks never are. Honest but
  degenerate: the grid precedent shows the baseline arm's real
  work is on *control* tasks (grid eval baseline was 0 too;
  control was 34/34), and pricing has no baseline-solvable
  control population under B-1 — the regression check goes
  vacuous.
- **B-2, schema-enumeration generator.** Baseline = the greedy
  solver over `enumerate_variants` (the generic one-edit schema
  space). **Rejected:** admitted operators are a subset of that
  same enumeration, so the extended arm adds almost nothing at
  solve time (chiefly chains applied as single variants) —
  Δ ≈ 0 by construction. This is the arm-collapse failure the
  Task 02 dossier already named.
- **B-3, author a pricing substrate first — RECOMMENDED.**
  Build a small authored pricing catalog as its own stage,
  exactly as Stage C built the grid substrate before Stage I
  discovered on top of it: structural operators over
  `total()`'s AST (e.g. restore-inclusive-threshold,
  tax-on-running-total, member-on-running-total), with its own
  tests, frozen and digested before any discovery runs.
  Baseline = greedy solver over that catalog; control tasks =
  pricing tasks the catalog solves (single-defect tasks in its
  classes), restoring a real regression check. The known risk
  — authoring a baseline *designed to lose* (or to win) — is
  managed the way the program managed it for grid: the
  substrate is built and measured as a deliverable in its own
  right, by a named brain, before the dossier exists, and its
  digest is in the manifest.

Decision requested from the coordinator at P2's turn (not
taken here): **B-3**, with B-1 as the declared fallback if the
program will not spend the stage; B-2 is rejected outright in
either case.

## 4. Anti-saturation calibration interface (P4)

Calibration exists because the pricing baseline may already
solve nearly everything (pilot v2 saturated at 220/220 under a
different solver; here the question is re-asked for *this*
baseline arm and *this* greedy solver).

- **Measured metric:** baseline-arm solved fraction on
  calibration tasks — the full baseline arm (adapter
  `baseline_variants` + core greedy solver, no discovery),
  scored on holdout cases. Reported **per defect class and
  pooled**. Calibration tasks are unique programs (§2) from a
  seed range reserved for calibration, disjoint from and
  deduplicated against pool and evaluation ranges, and are
  sealed forever once used — never recycled into either set.
- **Threshold:** pooled fraction ≥ 0.90 **or any single class
  ≥ 0.90** → the universe is too easy; harden and recalibrate
  (a pooled average must not hide a saturated class).
- **Hardening levers, in order of increasing invasiveness**
  (each round uses exactly one lever, recorded in the
  calibration report):
  1. *Level shift:* singles → pairs (L3); pairs restricted to
     subtlety ≥3 combinations (threshold+tax, threshold+member).
  2. *Shown-set pressure:* reduce the shown cap below 8 (task
     builder parameter; family machinery — weaker shown signal,
     same defects).
  3. *Case-grid extension:* add subtotal probes (e.g.
     threshold±2, mid-bracket values) to the family generator —
     changes holdout resolution; the generator's digest changes
     and must be re-frozen.
  4. *Defect-catalog extension:* new transforms — changes the
     family itself; last resort, and arguably a new family
     definition for preregistration purposes.
  Note what is **not** a lever: L4's adversarial spec dressing.
  The discovery solver never reads the spec, so poisoned text
  cannot harden anything for this mechanism; counting L4 as
  "harder" here would be a labelling error.
- **Termination:** at most **two** hardening rounds. If the
  threshold still fails, calibration reports FAIL and the
  decision returns to the coordinator — per ratified D6, the
  shipping substitution may then be considered, as a
  pre-preregistration amendment only.
- **Calibration report artifact:** seed range, task ids +
  normalized-form digests, per-class and pooled baseline
  fractions, lever used per round, final decision
  (PROCEED / FAIL). It is an input to the preregistration, and
  the preregistration records the calibration report's digest.

## 5. Risks and ambiguities (named, not resolved)

- **P2-R1 — Finite-universe exhaustion.** ≤216 unique programs
  bound every set: Task 02's sample sizes (pool 12, evaluation
  ≥45 singles + 18 composed, control ≥30, plus calibration)
  must be re-checked as *unique-program* counts at
  preregistration; if the singles population cannot supply
  them, sizes shrink by amendment **before** preregistration,
  never by quietly reusing programs across sets.
- **P2-R2 — "Holdout" means three things.** The lab's
  `split_of` (task-level train/holdout by normalized form), the
  within-task holdout *cases*, and the dossier's held-out
  *evaluation tasks*. The preregistration must use three
  distinct terms; conflating them is how leakage enters.
- **P2-R3 — Baseline authorship (B-3) is the soft spot.** A
  substrate written by the same hands that later claim transfer
  invites a straw-man baseline. Mitigations available to the
  program: substrate built as an independent stage with its
  own measured results (as Stage C was), frozen before the
  dossier design is finalised, author and runner not the same
  brain where avoidable.
- **P2-R4 — Born-climbable tasks.** Gradient-path enforcement
  guarantees a shown-score path exists for the *true* fix
  sequence; it also means a strong baseline faces no
  signal-starved tasks. Calibration (§4) is the only honest
  answer; do not weaken `_select_shown` to manufacture
  headroom — that would change what a task *is*.
- **P2-R5 — exec surface.** Adapter scoring executes
  AST-edited descendants of lab code. The lab's discipline
  (fresh namespace, own generated code only, exceptions =
  failure) plus the core's time guards are the fence; the
  adapter must not grow a path that executes code from outside
  the task pipeline.
- **P2-R6 — Parameter-combination coverage.** With 36
  combinations, a seed range can silently cover only part of
  the parameter space (e.g. never draw tax_pct=11 pairs).
  Calibration and preregistration reports should include the
  parameter-combination histogram per set, so coverage is
  auditable.
- **P2-R7 — `member_basis` transform naming.** Source names the
  function `defect_member_order` while the catalog key is
  `member_basis`; an implementer wiring defects by function
  name will mislabel classes. Use catalog keys; note it in the
  adapter's tests.

— End of design note. Decisions flagged (B-3 vs B-1;
calibration thresholds as written) belong to the coordinator
at P2's turn, not to this note.
