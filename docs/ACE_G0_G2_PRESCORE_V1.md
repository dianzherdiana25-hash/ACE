# ACE Fase 7 — Bounded Recursive Self-Development (`G0 → G1 → G2`): PRE-REGISTRATION

**Status when committed:** Pre-registration only (**no `code/ace_research_generations/` code, no scored results**).
**Branch:** `research/ace-recursive-g0g2-20261107` (based on `920305e`).
**Scientific status:** `NOT_ASSESSED` | **Release status:** `BLOCK_RELEASE` | **OAIE:** `NOT_ESTABLISHED`

---

## 1. Research Question

Can an autonomous ACE lineage (`G0 → G1 → G2`) inspect its own empirical search bottlenecks on development task families, synthesize and stage **bounded meta-mechanism improvements** via `Autonomy` (`STAGED_FOR_REVIEW`), validate generational transitions on disjoint meta-validation banks without ever touching evaluators, holdout data, security policies, or promotion rules, and produce measurable transfer/efficiency gains on **unseen family-disjoint target tasks** relative to `G0`, `G1`, a strong fixed library (`B_fixed`), random meta-mutation (`B_random_mut`), a `4×` extra-compute `G0` baseline (`B_extra_compute`), and a fresh learner (`B_fresh`)?

---

## 2. Immutable Security & Anti-Goodhart Boundary

Candidates in `G0 → G1` and `G1 → G2` operate strictly inside a typed, closed **Meta-Mechanism Configuration & Combinator Schema** (`ace.meta_mechanism.v1`) controlling ONLY:
1. Sub-automaton / window-projection feature induction depth and deduplication horizon,
2. MDL-weighted candidate hypothesis ranking priors over unary/binary/ternary typed combinators,
3. Version-space probe-disambiguation filter thresholds.

Cryptographically locked and **strictly forbidden** from candidate read/write access (enforced by `immutable_guard.py` SHA-256 locks + AST import isolation):
- `code/ace_research_generations/evaluator.py` and all terminal holdout banks,
- `code/ace_autonomy/{policy.py, verifier.py, core.py, escrow.py}` and HMAC journals,
- `code/ace_runtime/engine.py` and all 25 pinned `docs/UPSTREAM_SOURCES.json` files,
- Generational promotion criteria (`zero regression on prior validation + >= 0.10 validation gain`).

---

## 3. Generational Protocol (`G0 → G1 → G2`)

All inputs are binary `{a, b}` strings (compatible with real `ace_runtime`), sampled deterministically via SHA-256 ranking (`B = 32` target labels: `16` train len `0..6`, `16` val len `7..13`; terminal `128` strings len `16..28` in isolated `evaluator.py`, seeds `1..5`):

1. **`G0` (Initial Generation)**:
   - Base surface + R1 prefix/suffix/mod-2,3 feature learner + breadth-first pair search (`K = 256` candidate hypothesis evaluations cap per target unit) + live `ace_runtime` exact-reuse check.
2. **`G0 → G1` Transition (on Disjoint Meta-Bank 1: `M1_dev` 6 tasks, `M1_val` 4 tasks)**:
   - `M1` tasks involve **periodic block-parity & strided position invariants** (`even_pos_a%2`, `odd_pos_b%2`, `block2_aa_count%3`) where `G0` flat counters fail.
   - `G0` diagnoses residual validation errors via `SelfReflection`, proposes `8` typed meta-mechanisms in staging (`Autonomy` `stage_candidate`), evaluates on `M1_val` (zero terminal access), and promotes `G1` iff `M1_val` mean accuracy improves by `>= 0.15` with zero regression on `G0` base sanity tasks.
3. **`G1 → G2` Transition (on Disjoint Meta-Bank 2: `M2_dev` 6 tasks, `M2_val` 4 tasks)**:
   - Starting strictly from `G1` (inheriting `G1`'s strided/block projection discovery), `M2` tasks require **compositional cross-half / split-register invariants** (`first_half` vs `second_half` structural projections + high-ambiguity conjuncts).
   - `G1` diagnoses remaining search-budget exhaustion and spurious low-budget ambiguity, proposes `8` second-generation meta-mechanisms (adding MDL motif compression + split-window lifting + unlabeled probe-agreement pruning), validates on `M2_val` + regression check on `M1_val`, and promotes `G2`.

---

## 4. Unseen Family-Disjoint Target Benchmark & Comparators

Evaluated on **15 unseen target tasks** across `5` seeds (`75` units total at `B = 32`, never touched during `G0→G1` or `G1→G2`):
- **`U_gen` (`8` unseen cross-family tasks)**: Novel **strided-register × split-frame relational invariants** (e.g., comparing even-index parity of left half vs odd-index parity of right half, block-transition counts across split frames, and XOR-gated periodic invariants — disjoint from every `M1` and `M2` rule!).
- **`L_base` (`3` base tasks)**: Expressible by `G0` and `B_fixed` (non-regression check).
- **`N_ood` (`2` unbounded non-regular tasks)**: Exact `ca == cb` and `a^n b^n c-encoded` balance (abstention safety check).
- **`D_drift` (`2` hidden terminal-inversion drift controls)**: Observational-equivalence negative controls (expected FAIL on passive labels).

All 7 arms evaluated on identical `(train, val)` labels per unit:
1. `G0` (`K = 256` eval budget)
2. `G1` (`K = 256` eval budget)
3. `G2` (`K = 256` eval budget)
4. `B_fixed` (Strong fixed 120-predicate hand library, `K = 256` eval budget)
5. `B_random_mut` (2-generation random meta-mutation lineage without diagnostic selection, `K = 256`)
6. `B_extra_compute` (`G0` with `4×` candidate evaluation budget `K = 1024`)
7. `B_fresh` (Fresh R1 DFA target learner via real `ace_runtime` / `r1.infer`)

---

## 5. Pre-Registered Hypotheses (`B = 32`)

- **H1 (Monotonic Generational Progress on `U_gen`)**: `M(G2) >= M(G1) + 0.15` AND `M(G1) >= M(G0) + 0.15`.
- **H2 (Beats Extra-Compute & Fixed Baseline on `U_gen`)**: `M(G2) - max(M(B_extra_compute), M(B_fixed), M(B_fresh)) >= 0.15` (proving structural mechanism evolution rather than brute-force search).
- **H3 (Beats Random Meta-Mutation on `U_gen`)**: `M(G2) - M(B_random_mut) >= 0.15` (proving causal contribution of diagnostic self-reflection + meta-validation).
- **H4 (Zero Regression on `L_base` & Admission Safety on `N_ood`)**: `M(G2) >= M(G0) - 0.05` on `L_base`, and `false_admissions(G2) <= false_admissions(G0)` on `N_ood`.
- **H5 (Immutable Evaluator & Policy Integrity)**: `100%` SHA-256 lock verification before/after every generation; negative drift controls (`D_drift`) reported honestly without claiming unobservable drift detection.
