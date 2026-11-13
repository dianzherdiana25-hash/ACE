# ANTIGRAVITY TASK 04 — DESIGN NOTE: P1, decoupling `run_discovery` from the grid family

Status: **DESIGN ONLY.** No code is changed by this note, and it
authorises no refactor. It is material for Ian when the G3
application stage arrives (precondition P1 of the ratified
Task 02 dossier draft). Author: Antigravity bench room,
2026-11-13 (no Gemini; quota exhausted).

Source pinned for this note: `operator_discovery.py` in the
**composition-discovery lineage** (`wt-compdisc`, the version
with pair + chain discovery that produced
`evidence/operator_discovery_v4.json`). The copy in `wt-g3design`
is the older pre-chain version (353 lines) — see ambiguity R7
before touching anything.

---

## 1. Coupling map (from the source, as it stands)

The discovery mechanism is *conceptually* family-neutral, but
the module reaches into the grid family at six points:

| # | Site | Grid dependency | Kind |
|---|---|---|---|
| K1 | Module imports (top of file) | `from .grid_generalization import _budget_for, _passes` | scorer + budget factory |
| K2 | Module imports | `from .grid_substrate import _OPERATORS` | baseline catalog identity |
| K3 | `run_discovery.solve_with.extended_variants` | deferred `from .grid_substrate import grid_variants` — the baseline arm's variant generator, imported *inside* the solver so import-time greps miss it | baseline variant generator |
| K4 | `_budget_for(task)` calls in `_scored_variants`, `discover_pairs_for_task`, `discover_chain_for_task`, `solve_with` | Builds `Budget(1_000_000, entrypoint="navigate", shown_cases, shown_truth)` — grid entrypoint name and a BFS-sized step budget are hardcoded in the factory | per-task budget |
| K5 | `run_discovery.solved` | `_passes(code, holdout_cases, holdout_truth)` executes the candidate against grid cases/truth under a 5 s guard | holdout scoring |
| K6 | `_string_candidates` | Seeds the string-literal candidate set with `"#"` — the grid wall character — inside what is otherwise the generic schema space. The comment is honest about it ("the task family's spec fixes '#'"), but it is a family literal living in the core | hidden literal leak |

Implicit couplings, not imports:

- **Task dict contract.** Everything assumes keys `buggy_code`,
  `shown_cases`, `shown_truth` (via K4), `holdout_cases`,
  `holdout_truth`, `defects`. Nothing validates or documents
  this contract; a second family must reverse-engineer it.
- **Score semantics.** `budget.score(code)` returns a *count*
  of passed shown cases; `_safe_score` wraps it with a 0.5 s
  SIGALRM guard (timeout = −1). "Shown-perfect" everywhere means
  `score >= len(shown_cases)`. Any family scorer must reproduce
  count semantics exactly.
- **Solver duplication.** `solve_with`'s greedy loop (≤6 rounds,
  frontier ≤4, score-sorted) is a hand-mirror of `solve_grid`'s
  loop with an injected generator. It lives in the discovery
  module, but its shape is the grid solver's.
- **Single-function programs.** `_function_of` takes the first
  `FunctionDef` in the module; schema application is defined
  over that one function. (Pricing's `total()` satisfies this
  today; the contract must say so.)
- **Platform.** SIGALRM guards ⇒ main-thread, Unix-only
  execution, for every family.

What is already family-neutral and must not change behaviour:
the schema space and `enumerate_variants` (except the K6 seed),
`apply_operator` / `_apply_key_direct` / `apply_chain`,
discovery + pair + chain discovery, the admission rule
(≥ `min_pool_fixes` pool fixes, pair/chain credits included),
and the greedy loop's shape.

## 2. Adapter interface design

One explicit adapter object per family, passed into
`run_discovery(..., adapter=...)`. No global registry, no
auto-discovery: the caller names the family machinery, so the
preregistration can name it too.

```python
class FamilyAdapter(Protocol):
    family_id: str                      # "grid", "pricing", ...

    def make_budget(self, task) -> BudgetLike:
        """Object with .score(code) -> int = COUNT of passed
        shown cases, under the family's own execution limits
        (step/time). Carries the family entrypoint internally
        (grid: 'navigate', 1_000_000 steps; pricing: 'total',
        limits set by the pricing adapter's own design)."""

    def passes(self, code, cases, truth) -> int:
        """Count of holdout cases passed (K5's replacement)."""

    def baseline_variants(self, code) -> list[str]:
        """The family's PRE-improvement variant generator
        (grid: grid_variants(code, _OPERATORS)). This defines
        the baseline arm; the extended arm is baseline_variants
        + admitted operators/chains, assembled by the core."""

    def baseline_catalog_id(self) -> str:
        """Stable identifier/digest of the baseline catalog
        (grid: the _OPERATORS tuple), for the artifact
        manifest's baseline reference."""

    def extra_string_candidates(self, code) -> set[str]:
        """Family literals seeded into string candidates
        (grid: {'#'}; pricing: empty set). Removes K6 from
        the core."""
```

Design rules:

- The **core imports no family module** after the refactor —
  verifiable by grep (see §4, step 4). The deferred import (K3)
  is the first thing to go; hidden coupling is worse than
  visible coupling.
- The core assembles the extended variant generator itself
  (baseline variants from the adapter ∪ admitted operator/chain
  applications, as `extended_variants` does today), so the
  arms-differ-only-by-the-catalog property stays in one place
  and stays auditable.
- The task contract is written down as part of the adapter
  spec: producers (family task builders) emit `buggy_code`,
  `shown_cases`, `shown_truth`, `holdout_cases`,
  `holdout_truth`, `defects`, `task_id`; single-entry-function
  programs only.
- `_safe_score` and the 5 s holdout guard stay in the core,
  unchanged; adapters supply the budget/scorer they guard.

## 3. Migration shape (for the future implementer; not now)

1. Introduce the adapter + a `GridAdapter` that delegates to
   the existing functions byte-for-byte (`_budget_for`,
   `_passes`, `grid_variants`, `_OPERATORS`, `{"#"}`).
2. Rewire `run_discovery` and the discovery helpers to the
   adapter; delete K1–K3 imports from the core.
3. Move the `"#"` seed behind `extra_string_candidates` (K6).
4. Run the replication guard (§4). Only a green guard makes
   the refactor *done*; then, and only then, can a digest be
   frozen over the refactored core for preregistration.
5. Build the `PricingAdapter` as a separate, later step (P2 of
   the dossier) against `curriculum_lab._pricing_family`.

Explicitly out of scope for P1: unifying `solve_with`'s loop
with `solve_grid` (that changes the mechanism, not just its
wiring), adding schemas, or touching admission/chain logic.

## 4. Replication guard — reproduce v4 exactly before any freeze

Universe and split, copied from the v4 driver
(`opdisc_run_v4.py`): `build_universe()` (default seed
20261112); pool = first 3 single-defect `new_only` tasks per
class; pair/chain pool = first 6 mixed tasks; evaluation = the
remaining `new_only` tasks minus the pair pool; control =
`catalog_control` tasks. Same `min_pool_fixes=2`.

Numbers that must reproduce **exactly** (zero tolerance on
counts and on admitted sets; wall time excluded), from
`evidence/operator_discovery_v4.json`:

| Check | Expected |
|---|---|
| pool_tasks / evaluation_tasks | 12 / 29 |
| bounds_off_by_one | pool 3 · candidates 3 · admitted 3 operators + 1 chain · eval 8 · baseline 0 → extended 4 |
| dist_step_2 | pool 3 · candidates 1 · admitted 1 + 0 chains · eval 11 · 0 → 3 |
| returns_start_distance | pool 3 · candidates 1 · admitted 1 + 1 chain · eval 13 · 0 → 5 |
| wall_char_x | pool 3 · candidates 55 · admitted 1 + 0 chains · eval 15 · 0 → 3 |
| pair pool | 6 tasks · 0 solved by pairs |
| chain pool | 6 tasks · 3 solved by chains |
| mixed evaluation | 18 · baseline 0 → extended 18 |
| control | 34 · 34 → 34 (no regression) |

Plus: the admitted operator/chain **key strings per class must
match the evidence file as sets** (counts alone could hide a
substituted operator), and the existing
`test_operator_discovery.py` suite passes unchanged.

Mismatch procedure: stop; do not freeze any digest; bisect
which migration step diverged; if a difference traces to the
SIGALRM guard flipping a borderline candidate under load,
record it as a named finding with the task/key identified —
never waive it silently, and never re-run until it matches
without understanding why.

## 5. Risks and ambiguities (named, not resolved)

- **R1 — Where does `"#"` belong?** Moving it behind the
  adapter keeps grid behaviour identical, but the artifact
  manifest must state that the string-candidate seed is family
  machinery, not frozen artifact — otherwise a future family
  could smuggle advantage in through its seed set. The seed
  set is visible in the adapter, hence auditable; the dossier
  preregistration should record each family's seed set.
- **R2 — Budget incomparability.** Grid's 1,000,000-step BFS
  budget and any pricing execution limit are family machinery;
  effects are only ever compared *within* a family (Δ vs that
  family's baseline), so incomparability is sound — but the
  preregistration must record each family's budget/limits, or
  the margin call is unauditable.
- **R3 — Timeout sensitivity.** The 0.5 s candidate guard
  makes borderline scores load-dependent in principle. v4's
  margins were wide (0 vs solved), so the guard is unlikely to
  be load-bearing today; the replication guard's mismatch
  procedure exists for the day it is.
- **R4 — `return_indices` is grid-shaped.** It is coded
  generically (any 2-deep name-sliced subscript return chain)
  but only grid code exercises it. It stays in the frozen
  schema space: removing it would change the artifact to make
  the pricing run look cleaner — exactly the kind of silent
  edit the digest freeze exists to prevent.
- **R5 — First-function contract.** `_function_of` silently
  picks the first function. If a future family's reference
  program grows a helper, discovery would edit the wrong
  function without error. Adapter spec must require the
  entrypoint to be the first (or only) function, and task
  builders must assert it.
- **R6 — SIGALRM portability.** All family runs inherit the
  main-thread/Unix constraint. Acceptable for this program's
  VM; recorded so nobody schedules a threaded runner.
- **R7 — Canonical tree.** The mechanism's newest version
  lives in the composition-discovery lineage (draft PR #140),
  not in the wt-g3design lineage the G3 work branched from.
  Before any refactor, the program must settle which tree is
  the mechanism's canonical home and land the chain version
  there; refactoring the stale copy would fork the artifact.
- **R8 — Driver-side split logic.** The pool/evaluation split
  lives in the run driver, not the module. For the G3 dossier
  runs, split logic is part of the preregistered protocol; the
  refactor should not bury it inside the adapter, where it
  would escape the protocol hash.

— End of design note. Prepared for Ian's use at the G3
application stage; questions of ratification belong to the
coordinator, not to this note.
