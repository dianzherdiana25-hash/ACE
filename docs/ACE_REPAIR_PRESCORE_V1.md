# ACE Autonomous Software Repair v1 — Pre-Registered Experimental Protocol (PRE-SCORE)

**Date:** 2026-11-07  
**Branch:** `research/ace-software-repair-v1-20261107`  
**Parent Baseline Commit (`main`):** `80104ce50ecbcea21080bed8c0eabce88d47ccb5`  
**Classification:** PUBLIC SYNTHETIC / CURATED STAGED BENCHMARK — PRE-SCORE FREEZE  
**Governance Flags:** `scientific_decision = "NOT_ASSESSED"`, `release_gate = "BLOCK_RELEASE"`, `oaie_established = False`, `candidate_deployed = False`

> **Mandatory Pre-Score Custody Rule:** This protocol is committed *before* any `code/ace_research_repair/*.py` implementation, benchmark execution, or terminal scoring exists. All subsequent commits on this branch are strictly additive against this frozen specification. Neither `code/ace_runtime/` nor any of the 25 pinned files in `docs/UPSTREAM_SOURCES.json` may be modified.

---

## 1. Research Question

Can ACE **inspect, reproduce, diagnose, represent, patch, test, verify, and remember** software bug repairs in isolated staging across four distinct Python bug families (`boundary_index`, `parsing`, `state_invariant`, `data_dependency`), and does learned typed fault-representation plus durable repair experience memory (`R_ace`) improve terminal-verified repair accuracy, candidate evaluation efficiency, and anti-overfitting safety over `R_rule`, `R_fixed`, and `R_fresh` under a matched candidate-evaluation budget?

---

## 2. Scope, Isolation, and Safety Boundaries

1. **Staging-Only Execution (`sandbox.py`):** Every candidate module execution occurs inside an isolated child Python process rooted in a fresh `tempfile.TemporaryDirectory`, written via `O_NOFOLLOW` file descriptors with a scrubbed environment (`PATH`, `PYTHONNOUSERSITE=1`, `PYTHONDONTWRITEBYTECODE=1`), hard `resource.RLIMIT_CPU = 2` seconds, and parent wall-clock timeout `3.0s`. Repository files are never modified.
2. **Strict Evaluator Custody (`evaluator.py`):** Terminal property and edge-case test suites live exclusively in `code/ace_research_repair/evaluator.py`. AST static import analysis enforces that `evaluator.py` is **never** imported by `corpus.py`, `sandbox.py`, `operators.py`, `represent.py`, `memory.py`, or `engine.py`. Only `runner.py`, `verify.py`, and `test_repair.py` may invoke `evaluator.py` *after* repair decisions and candidate selection are frozen.
3. **Closed Typed AST Operator Grammar (`operators.py`):** Candidate synthesis uses pure stdlib `ast` transformations from a fixed, researcher-authored operator catalog; no LLM calls, network requests, external packages, or unconstrained arbitrary string synthesis are used.

---

## 3. Disjoint Source and Target Bug Banks (`corpus.py`)

### 3.1 Four Bug Families

| Family ID | Structural Fault Class | Typed Repair Operator Sub-Grammar |
|---|---|---|
| `boundary_index` | Off-by-one `range`/slice bounds, inclusive vs. strict comparisons, missing empty-sequence guards | `OP_EMPTY_GUARD_INSERT`, `OP_RANGE_STOP_ADJUST`, `OP_CMP_BOUNDARY_FLIP`, `OP_SLICE_BOUND_ADJUST` |
| `parsing` | Unstripped outer whitespace, unbounded delimiter `split`, unsigned-only `isdigit` guards | `OP_STR_STRIP_NORMALIZE`, `OP_SPLIT_MAXSPLIT_ONE`, `OP_SIGN_GUARD_EXPAND` |
| `state_invariant` | Missing accumulator reset on flush, inverted state-update statement order, missing post-loop tail flush | `OP_STATE_RESET_ON_FLUSH`, `OP_SWAP_ADJACENT_STATE_STMTS`, `OP_LOOP_TAIL_FLUSH` |
| `data_dependency` | Mutable container aliasing without `.copy()`, shared mutable default arguments, stale local variable binding | `OP_MUTABLE_COPY_WRAP`, `OP_DEFAULT_NONE_INIT`, `OP_RHS_VAR_REBIND` |

To test realistic generate-and-validate overfitting vulnerability, the shared candidate generator also includes two naive generate-and-validate overfit probe operators (`overfit_probe`):
- `OP_OVERFIT_CONSTANT_RETURN`: replaces a function return expression with a constant literal observed in public dev assertions.
- `OP_OVERFIT_DEV_INPUT_GUARD`: prepends an early input-equality special-case return matching a failing public dev assertion `(args -> expected)`.

### 3.2 Source Training Bank (`8` Bugs: 2 per Family)

Used *exclusively* during `R_ace` source acquisition to induce binary fault-trace capabilities in `ace_runtime.engine.Runtime` and populate `RepairMemory` (`(fault_signature, runtime_model_id, ast_schema) -> operator_family`):

- `S01_sliding_window_sums` (`boundary_index`): sliding window sum omitting final window index.
- `S02_safe_head_ratio` (`boundary_index`): empty-list subscript crash before ratio calculation.
- `S03_kv_header_parse` (`parsing`): colon header splitter failing when value contains colons.
- `S04_csv_int_sum` (`parsing`): comma token summer skipping signed `+`/`-` integer tokens.
- `S05_run_length_max` (`state_invariant`): threshold streak tracker updating maximum before incrementing streak.
- `S06_batch_packet_accumulator` (`state_invariant`): packet batcher failing to reset item count upon capacity flush.
- `S07_snapshot_ledger` (`data_dependency`): checkpoint recorder appending aliased mutable state dict without `.copy()`.
- `S08_tag_collector` (`data_dependency`): tag accumulator mutating a shared default list argument across calls.

### 3.3 Unseen Target Evaluation Bank (`18` Units Total)

Implemented in completely distinct modules and algorithms from the source bank:

1. **Nominal Target Bugs (`12` units: 3 per family):**
   - `boundary_index`: `T01_binary_search_index` (`<` vs `<=` convergence bound), `T02_interior_local_maxima` (`range` stop off-by-one), `T03_trimmed_floor_mean` (missing empty-sample guard).
   - `parsing`: `T04_parse_env_entries` (`=` assignment `maxsplit=1`), `T05_parse_version_triple` (unstripped raw version string), `T06_replay_stock_deltas` (signed delta token validation).
   - `state_invariant`: `T07_run_length_counts` (missing run counter reset on symbol transition), `T08_step_differences` (previous-value update ordered before difference emission), `T09_session_durations` (missing post-loop active session flush).
   - `data_dependency`: `T10_apply_row_mask` (in-place mutation of caller template list), `T11_register_route` (shared mutable default route dictionary), `T12_compute_net_total` (tax computed on stale `subtotal` instead of `discounted` local variable).
2. **Out-of-Class Negative Controls (`OOD_abstain`: `4` units):**
   Multi-fault or algorithmic-redesign defects outside bounded single-schema repair:
   - `T13_ood_greedy_coin_change`: greedy coin selection instead of dynamic programming on non-canonical denominations.
   - `T14_ood_nested_expr_eval`: flat parenthesis-stripping scanner instead of sign-stack / recursive-descent evaluation.
   - `T15_ood_weighted_shortest_hops`: unweighted FIFO BFS instead of Dijkstra edge-weight relaxation.
   - `T16_ood_triple_fault_ledger`: simultaneous three-fault ledger bug combining input aliasing, delimiter misparse, and inverted transfer arithmetic.
3. **Adversarial Test-Weakness Traps (`TRAP_overfit`: `2` units):**
   Algorithmic defects paired with weak 3-case public dev suites where naive special-case or constant-return patches pass 100% of dev tests but fail held-out property tests:
   - `T17_trap_constant_collapse`: `min_swaps_to_group_ones` where all non-empty dev cases expect `1`, tempting `OP_OVERFIT_CONSTANT_RETURN`.
   - `T18_trap_special_case_guard`: `longest_zero_sum_span` where only one dev case tests an interior span, tempting `OP_OVERFIT_DEV_INPUT_GUARD`.

---

## 4. Matched Budget and Experimental Arms

### 4.1 Matched Candidate-Evaluation Budget

- **Maximum candidate sandbox executions per target unit:** `K = 16` subprocess runs (`timeout = 3.0s`, `RLIMIT_CPU = 2s`).
- **Strict accounting:** Every candidate execution in `sandbox.py` counts toward `K = 16` — including **both** `Test` (public dev suite execution) and `Verify` (unlabeled perturbation suite execution) in `R_ace`. Initial fault reproduction (`Reproduce`, 1 run on the unmodified buggy module) is logged separately for every arm that executes dynamic reproduction (`R_fresh` and `R_ace`).

### 4.2 Four Experimental Arms

All four arms draw from the **identical** `generate_candidates` AST patch pool per unit and operate under the **identical** `K = 16` sandbox execution limit:

1. **`R_rule` (Deterministic Static Rule-Order Patcher):**
   Orders candidates statically by `(target_lineno, fixed_family_order, operator_name, patch_id)` without dynamic trace localization, learned representations, or `Verify` perturbation checks. Admits the first candidate passing all public dev tests.
2. **`R_fixed` (Hand-Authored Static AST Feature Ranker):**
   Scores candidates using fixed syntactic heuristics (preferring edits inside the target entrypoint function, smaller AST edit complexity, and exception-adjacent AST constructs) without dynamic trace spectrum, `ace_runtime`, `RepairMemory`, or `Verify`. Admits the first candidate passing all public dev tests.
3. **`R_fresh` (Target-Only Spectrum Localization + Enumerative AST Search):**
   Executes `Reproduce` with `sys.settrace` to compute Ochiai line suspiciousness on the target unit and ranks candidates by `(-ochiai_score, fixed_family_order, target_lineno, patch_id)`, with **zero** source-learned representation or `RepairMemory`, and no `Verify` perturbation gate. Admits the first candidate passing all public dev tests.
4. **`R_ace` (Full 8-Stage ACE Software Repair Pipeline):**
   Executes the explicit 8-stage loop:
   `Goal -> Inspect -> Reproduce -> Diagnose -> Represent -> Patch -> Test -> Verify -> Remember`:
   - **`Inspect`:** Parses module AST, enumerates function scopes, control-flow boundaries, mutable defaults, and call sites.
   - **`Reproduce`:** Runs public dev tests in `sandbox.py` with `sys.settrace` line, exception, and container-aliasing instrumentation.
   - **`Diagnose`:** Computes Ochiai line suspiciousness spectrum and failure mode (`IndexError`, `ValueError`, `AssertionMismatch`, cross-call/arg mutation).
   - **`Represent`:** Encodes observed dynamic fault traces into bounded binary `{a, b}` trace words, executes capability learning/reuse and `predict` queries inside real `ace_runtime.engine.Runtime` (`ace.sqlite3`), and queries `RepairMemory` (`repair_memory.sqlite3`) for source-learned `(runtime_model_id, fault_signature) -> operator_family` priors.
   - **`Patch`:** Ranks the shared AST candidate pool by combining Ochiai line localization with learned `ace_runtime` + `RepairMemory` operator-family log-priors (demoting unremembered `overfit_probe` operators).
   - **`Test`:** Evaluates top-ranked candidates on public dev tests in `sandbox.py` within `K = 16`.
   - **`Verify`:** Before admitting any dev-passing candidate, executes the candidate in `sandbox.py` (charged against `K = 16`) on **unlabeled synthesized perturbation probes** from `corpus.py`, requiring: (a) zero crashes/timeouts, (b) non-degenerate output variation across diverse unlabeled inputs where variation is expected, (c) caller-argument immutability and cross-call isolation, and (d) exact agreement `f(x) == f(x')` on unlabeled symmetry/equivalence input pairs. Candidates failing `Verify` are rejected and search continues if budget remains; otherwise `R_ace` safely abstains.
   - **`Remember`:** Atomically commits validated `(fault_signature, runtime_model_id, ast_schema, operator_family, operator_name, patch_sha256)` repair schemas into SQLite WAL `RepairMemory` with a SHA-256 hash-chained event ledger.

---

## 5. Pre-Registered Hypotheses and Falsification Criteria

- **`H1` (Nominal Repair Accuracy & Family Coverage vs. Static Baselines):**
  On the 12 unseen nominal target bugs (`T01`–`T12`), `R_ace` achieves strictly more terminal-verified repairs than both `R_rule` and `R_fixed`, solving `>= 9/12` nominal units overall and `>= 2/3` units in every one of the four bug families.
- **`H2` (Candidate-Budget Efficiency / Transfer Gain vs. `R_fresh`):**
  Under the matched `K = 16` sandbox execution cap (including `Verify` sandbox runs charged to `R_ace`), `R_ace` either achieves strictly higher terminal-verified nominal repair count than `R_fresh`, or ties/exceeds `R_fresh` while reducing mean sandbox candidate evaluations per solved nominal bug by `>= 20%`.
- **`H3` (Anti-Overfitting Rejection on `TRAP_overfit` and Abstention on `OOD_abstain`):**
  1. At least one unverified baseline (`R_rule`, `R_fixed`, or `R_fresh`) commits `>= 1` overfitting false admission on `TRAP_overfit` (`T17`, `T18`), confirming non-vacuous trap difficulty;
  2. `R_ace` rejects `2/2` `TRAP_overfit` overfit candidates in `Verify` (`0` overfitting false admissions);
  3. `R_ace` safely abstains on `4/4` `OOD_abstain` units (`T13`–`T16`), yielding `0/6` false admissions across all negative/trap controls and `100%` terminal holdout pass rate across all admitted `R_ace` patches.
- **`H4` (Durable Cross-Restart Retention in `Remember`):**
  Closing and re-instantiating `RepairEngine` on an existing workspace without re-running source training verifies both `ace_runtime` and `RepairMemory` SQLite integrity chains, exercises `REUSE_VALIDATED` capability inheritance in `ace_runtime.engine.Runtime`, and reproduces byte-identical nominal target patch selections.

---

## 6. Determinism, Negative-Result Commitment, and Interpretation Limits

1. **Cross-Version Canonical Replay:** Wall-clock durations are excluded from canonical hashed evidence payloads (`evidence/repair/ace_repair_v1.json.gz`), and RFC 1952 gzip headers use fixed `mtime = 0` and `OS = 0xff` so both `python3.12` and `python3.13` produce byte-identical canonical JSON SHA-256 digests verified by `verify.py`.
2. **Honest Negative-Result Commitment:** All four arms, candidate budgets consumed, dev-vs-terminal discrepancies, false admissions, abstentions, and any failed hypotheses (`H1`–`H4`) must be reported verbatim without post-score protocol or threshold modification.
3. **Interpretation Limits:** All bug families, typed AST mutation operators, binary trace encoders, and unlabeled metamorphic perturbation generators are researcher-authored. Passing engineering tests or local hypotheses demonstrates bounded staged repair integration and typed representation reuse within curated Python bug classes — **not** open-ended operator invention, unconstrained real-world repository repair, open-world semantic safety, or OAIE. Accordingly, `scientific_decision = "NOT_ASSESSED"`, `release_gate = "BLOCK_RELEASE"`, `oaie_established = False`, and `candidate_deployed = False` remain unconditionally enforced.
