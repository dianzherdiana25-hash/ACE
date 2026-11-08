# ACE Fase 6 — Automated Typed Structural Abstraction Discovery & Cross-Family Relational Transfer (PRE-SCORE PROTOCOL v1)

**Date:** 2026-11-07  
**Branch:** `research/ace-novel-reptransfer-v1-20261107` (parent `main` `80104ce50ecbcea21080bed8c0eabce88d47ccb5`)  
**Mandatory Custody Gate:** This pre-registration document MUST be committed to Git **before** any `.py` implementation file in `code/ace_research_discovery/`, any test execution, or any scored result exists. Post-score threshold or task edits are prohibited; all positive, partial, and negative outcomes must be preserved verbatim.

---

## 1. Scientific Question & Advance Beyond Prior Pilots

Prior public ACE pilots established:
1. **R1 / v0.1 (`primitive_discovery.py`):** RPNI state-merging DFA induction on bounded `{a, b}` strings.
2. **v0.2 (`structural.py`) & v0.3 (`compositional.py`) & `ace_runtime` v1:** Selection and persistence over a researcher-authored 7-slope flat symbol-counter grammar (`w_a * #a + w_b * #b == 0`) conjoined with DFAs/fixed guards.
3. **Prior representation transfer baselines (R9-class):** Hand-curated source pools aligned to target predicates within flat `{a, b}` string families.

**Fase 6 Question:** Can a bounded, pure-typed learner—given **only** elementary stack/frame/scan combinators over `{a, b}` and an **uncurated mixed source pool (`S_mixed`)** where 50% of tasks are flat surface distractors and **zero task-relevance metadata** is provided—automatically:
1. Synthesize typed source programs from labeled examples alone;
2. Extract reusable **sub-program integer/boolean structural projections** via a domain-agnostic Minimum Description Length (MDL) + unlabeled probe-entropy criterion (filtering out 1-bit surface distractors without human curation);
3. Lift unary structural projections $\phi: \text{Frame} \to \mathbb{Z} \cup \mathbb{B}$ across a **genuinely distinct target problem family** (paired-tree relational tasks `(T1, T2)` encoded as concatenated `{a, b}` prime Dyck frames of unseen longer lengths) via a general typed pair-frame functor $\mathcal{F}_{\text{pair}}$; and
4. Achieve higher sample efficiency, higher out-of-length accuracy, lower amortized AST evaluation work than 4× fresh DSL synthesis, and low false-admission rates on non-expressible relational tasks via unlabeled probe-agreement gating—while honestly exposing unobservable semantic drift?

---

## 2. Frozen Upstream Custody & Isolation Boundaries

- All 25 files pinned in `docs/UPSTREAM_SOURCES.json` and all files in `code/ace_runtime/` remain **100% unmodified** (verified offline by `tools/verify_sources.py`).
- New implementation lives exclusively in `code/ace_research_discovery/` (`__init__.py`, `dsl.py`, `sampling.py`, `discovery.py`, `arms.py`, `tasks.py`, `evaluator.py`, `runner.py`, `verify.py`, `test_discovery.py`).
- **Strict Evaluator AST Isolation:** `evaluator.py` implements an independent recursive-descent ordered-tree parser (`TreeNode`) and ground-truth task semantics. Static Python `ast` verification in `verify.py` and `test_discovery.py` asserts that `dsl.py`, `discovery.py`, and `arms.py` **never** import `evaluator` or `tasks`, never inspect task names/strata, and never call `eval`, `exec`, `compile`, or `__import__`.

---

## 3. Canonical `{a, b}` Encoding & Deterministic SHA-256 Sampling

Every example across all source and target tasks is a valid binary string over `{"a", "b"}` with `len(x) <= 40` (strictly within `ace_runtime`'s `<= 100` character contract), allowing `ace_runtime.engine.Runtime` and `r1.fixed_predicates()` to process identical raw inputs on equal footing:

- **Single Ordered Rooted Tree (`enc(T)`):** Recursively encoded as a prime balanced Dyck word:
  $$\text{enc}(\text{Node}([c_1, \dots, c_k])) = \text{"a"} + \text{enc}(c_1) + \dots + \text{enc}(c_k) + \text{"b"}$$
  A tree with $v \ge 1$ vertices has length $2v$, `#a == #b == v` (rendering all 7 flat counter slopes in `ace_runtime` trivial constants on valid trees), and returns stack height to `0` exclusively at indices `0` and `2v`.
- **Paired Relational Frame (`enc(T1, T2) = enc(T1) + enc(T2)`):** Concatenation of two independent prime Dyck trees $T_1, T_2$ (potentially of unequal sizes $v_1 \ne v_2$). Because `enc(T1)` is prime Dyck, the boundary between $T_1$ and $T_2$ varies dynamically with $T_1$'s structure and is uniquely defined by the first positive index where nesting depth returns to `0`.
- **Python-Version-Independent Sampling:** All candidate pools and splits are ordered exclusively via FIPS 180-4 SHA-256 hex digests `sha256(f"{tag}:{seed}:{word}".encode("ascii")).hexdigest()`, guaranteeing bit-for-bit identical splits across Python 3.12 and Python 3.13 without `random.Random` state sensitivity.

### Split Regimes & Length Separation
- **Seeds:** `SEEDS = (1, 2, 3, 4, 5)`.
- **Source Pool (`S_mixed`, 12 single-tree tasks):** Sampled from prime Dyck trees with $v \in \{2, \dots, 9\}$ vertices (lengths `4..18`). Each source task provides `64` balanced labeled examples (`32` train = `16` pos + `16` neg; `32` validation = `16` pos + `16` neg, strictly disjoint).
- **Target Strata (15 paired-tree tasks):**
  - **Development (`train`, `validation`):** Sampled from paired trees `(T1, T2)` with $v_1 + v_2 \in \{5, \dots, 14\}$ (lengths `10..28`). Matched total target label budgets `B in (16, 32, 64)` (`n_train = B // 2`, `n_val = B // 2`, each class-balanced `B // 4` pos + `B // 4` neg, `train ∩ validation = ∅`, nested across budgets). **Primary budget: `B = 32` (`16 train + 16 val`).**
  - **Terminal Holdout (`terminal`):** `128` balanced examples (`64` pos + `64` neg) sampled from **strictly longer** unseen paired trees with $v_1 + v_2 \in \{15, \dots, 20\}$ (lengths `30..40`), ensuring `(train ∪ validation) ∩ terminal = ∅` and testing genuine structural length generalization.

---

## 4. Uncurated Mixed Source Pool & Family-Disjoint Target Strata

### 4.1 Uncurated Mixed Source Pool (`S_mixed`, 12 Single-Tree Tasks)
Presented to discovery learners in deterministic hash-interleaved order with **no** structural/distractor flag:

**6 Single-Tree Structural Tasks:**
1. `s_struct_depth_odd`: `max_depth(T) % 2 == 1` (even edge-height)
2. `s_struct_leaves_mod3`: `leaves(T) % 3 == 0`
3. `s_struct_root_deg_eq2`: `root_deg(T) == 2`
4. `s_struct_bipartite_zero`: `bipartite_diff(T) == 0` (`#odd_depth_nodes(T) == #even_depth_nodes(T)`)
5. `s_struct_max_outdeg_le2`: `max_outdeg(T) <= 2` (at-most-binary Motzkin tree)
6. `s_struct_branching_ge2`: `branching_nodes(T) >= 2` (at least two internal nodes with out-degree $\ge 2$)

**6 Single-Tree Surface String Distractor Tasks (evaluated on the identical single-tree string domain):**
7. `s_surf_starts_aaa`: `x.startswith("aaa")`
8. `s_surf_ends_abb`: `x.endswith("abb")`
9. `s_surf_contains_bba`: `"bba" in x`
10. `s_surf_count_a_mod3`: `x.count("a") % 3 == 0`
11. `s_surf_char3_is_a`: `len(x) >= 4 and x[3] == "a"`
12. `s_surf_aab_and_bbb`: `x.startswith("aab") and x.endswith("bbb")`

### 4.2 Strictly Family-Disjoint Target Strata (15 Paired-Tree Tasks `(T1, T2)`)
Unit-tested to ensure zero target task equals any source task, and `U_cross` alters moduli/thresholds/relational arity so even reusing boolean outputs of the 12 source tasks cannot solve `U_cross` without extracting underlying `Int` structural projections:

- **`U_cross` (6 Cross-Family Paired-Tree Relational Tasks — Primary Transfer Stratum):**
  1. `u1_leaves_mod4_rel`: `leaves(T1) % 4 == leaves(T2) % 4` (source had mod 3 unary; target requires mod 4 binary relation)
  2. `u2_rootdeg_eq_and_deep`: `root_deg(T1) == root_deg(T2) and max_depth(T1) >= 3` (source only tested `root_deg == 2` and depth parity)
  3. `u3_bipartite_diff_rel`: `bipartite_diff(T1) == bipartite_diff(T2)` (source only tested `== 0`; target matches arbitrary signed differences)
  4. `u4_branching_mod3_rel`: `branching_nodes(T1) % 3 == branching_nodes(T2) % 3` (source only tested `>= 2`)
  5. `u5_depth_parity_and_motzkin`: `(max_depth(T1) % 2 == max_depth(T2) % 2) and max_outdeg(T1) <= 2 and max_outdeg(T2) <= 2`
  6. `u6_max_depth_eq`: `max_depth(T1) == max_depth(T2)`
- **`L_surface` (3 Surface Compositional Tasks — No-Regression Stratum):**
  1. `l1_starts_aaa_ends_abb`: `x.startswith("aaa") and x.endswith("abb")`
  2. `l2_total_a_mod4_eq0`: `x.count("a") % 4 == 0`
  3. `l3_starts_aab_even_a`: `x.startswith("aab") and (x.count("a") % 2 == 0)`
- **`N_abstain` (3 Non-Expressible Relational Tasks — Admission-Safety / Abstention Stratum):**
  1. `n1_ordered_tree_identity`: exact ordered isomorphism `T1 == T2`, with negatives drawn from sibling-mirrored asymmetric pairs `(T, mirror(T))` that preserve the exact multiset of `(depth, out_degree)` across all vertices.
  2. `n2_mirror_tree_duality`: exact ordered mirror `T2 == mirror(T1)`, with negatives drawn from asymmetric `(T, T)` pairs sharing identical `(depth, out_degree)` multisets.
  3. `n3_ordered_leaf_hash_eq`: ordered left-to-right leaf-depth polynomial signature match `sum((i+1)*d_i(T1)) % 5 == sum((i+1)*d_i(T2)) % 5`.
- **`D_drift` (3 Unobservable Semantic-Shift Controls — Epistemic Boundary Stratum):**
  1. `d1_leaves_mod4_late_invert`: identical `train` + `validation` + `terminal` inputs to `u1_leaves_mod4_rel`, with inverted `terminal` truth.
  2. `d2_bipartite_late_invert`: identical `train` + `validation` + `terminal` inputs to `u3_bipartite_diff_rel`, with inverted `terminal` truth.
  3. `d3_surface_late_invert`: identical `train` + `validation` + `terminal` inputs to `l1_starts_aaa_ends_abb`, with inverted `terminal` truth.

---

## 5. Typed Combinator DSL, Discovery Mechanism & Capability Arms

### 5.1 Base Typed Stack/Frame/Scan DSL (`dsl.py`)
Elementary typed combinators over `{a, b}` (zero named tree invariants):
- **Frame selectors (`Frame`):** `Whole`, `LeftF` (first prime Dyck component), `RightF` (second prime Dyck component).
- **Dyck stack trace semantics:** A single linear scan pushes an open record on `'a'` (incrementing parent child counter) and pops `(depth, deg)` on `'b'`.
- **Node-level terms (`NInt`, `NPred`):** `NDepth`, `NDeg`; `NEq(n, c)` ($c \in \{0,1,2,3\}$), `NGe(n, c)` ($c \in \{1,2,3,4\}$), `NModEq(n, m, r)` ($(m,r) \in \{(2,0),(2,1),(3,0),(3,1),(3,2)\}$).
- **Frame aggregators & surface ops:** `MaxNodes(F, n)`, `CountNodes(F, np)`, `SignedBalance(F, np)`, `CharCount(F, ch)`, `StrLen(F)`, `IsSingleTree(Whole)`, `IsPairedTrees(Whole)`, `StartsWith(F, pat)`, `EndsWith(F, pat)`, `Contains(F, pat)` (patterns length `1..3`), `CharAtEq(F, idx, ch)` ($idx \in \{0..3\}$).
- **Arithmetic & Boolean combinators:** `Mod(e, m)` ($m \in \{2,3,4\}$), `IntEqConst(e, c)`, `IntGeConst(e, c)`, `IntLeConst(e, c)`, `IntEq(e1, e2)`, `IntGe(e1, e2)`, `BoolNot`, `BoolAnd`, `BoolOr`, `BoolEq`.

### 5.2 Automated Source Abstraction Discovery & Pair Functor (`discovery.py`)
1. **Source Synthesis (`C_source = 2000`):** Bottom-up observational-equivalence enumerative synthesis over unary `Whole` expressions on each of the 12 `S_mixed` tasks using source `(train, val)` only. Tasks achieving exact `64/64` source fit are admitted.
2. **MDL + Unlabeled Entropy Compression (`K_max = 7`):** Every unary frame-parameterized sub-expression $\phi(F)$ (`ast_size >= 3`) from admitted source solutions is evaluated on `64` unlabeled single-tree probes (`sampling.py`). Trivial near-constants (`non_mode_rate < 0.10`) and behavioral duplicates are pruned; candidates are ranked by:
   $$U(\phi) = H_{\text{probe}}(\phi) + 0.25 \cdot (\text{source\_reuse\_count}(\phi) - 1) - 0.12 \cdot |\text{AST}(\phi)|$$
   where $H_{\text{probe}}(\phi)$ is unlabeled empirical Shannon entropy in bits. Multi-valued `Int` structural projections naturally carry $1.8\text{--}2.8$ bits of entropy versus $\le 1.0$ bit for surface `Bool` distractors, selecting up to `K_max = 7` distinct unary abstractions $\Phi$.
3. **Typed Pair-Frame Functor $\mathcal{F}_{\text{pair}}$:** Maps each unary $\phi \in \Phi$ to paired frame projections $(\phi(\text{LeftF}), \phi(\text{RightF}))$ and standard relational readouts ($\phi(L) == \phi(R)$, $\phi(L) \bmod m == \phi(R) \bmod m$ for $m \in \{2,3,4\}$, unary thresholds $\phi(F) \in \{==c, \ge c, \le c, \bmod m == r\}$), combined with compact surface atoms in a depth-2 boolean adapter (`atom`, `NOT atom`, `a1 AND a2`, `a1 OR a2`).
4. **Admission & Unlabeled Probe-Agreement Gate:** A target candidate is staged (`admitted = True`) iff (a) `train_correct == len(train)` and `val_correct == len(val)`, AND (b) across all exact-fit candidates within `+2` complexity units of the minimum-complexity exact candidate, minimum pairwise prediction agreement on `64` deterministic unlabeled paired-tree probes (lengths `30..40`) is `>= 0.90`.

### 5.3 Explicit Capability Arms + Separate Upper Bound
1. **`M0_memorize` (*Memorization*):** Exact `train + validation` lookup with deterministic minimum-Hamming nearest-neighbor fallback.
2. **`M1_exact_reuse` (*Exact Model Reuse*):** Real `ace_runtime.engine.Runtime` SQLite instance seeded with all 12 `S_mixed` tasks (partitioning development labels into `train_rt, val_rt` so `prefixes(train_rt) <= 63` without adding or dropping any label) and evaluated on each target task (`REUSE_VALIDATED` / `LEARNED_STAGED` / `NO_VALIDATED_MODEL`, calling `runtime.evaluate` whenever staged).
3. **`M2_strong_fixed` (*Strong Fixed Feature Library*):** All `100` predicates from `r1.fixed_predicates()` plus `44` generic flat string/length/modulo/ratio/index/4-gram predicates (`144` fixed features total), fitted with the **identical** depth-2 boolean adapter and admission gate.
4. **`M3_fresh_dsl` & `M3_fresh_4x` (*Composition of Supplied Base Operators*):** Bottom-up observational-equivalence synthesis directly on target `(train, val)` over the full paired-frame base DSL without source abstractions, at `C_fresh = 600` (`1×`) and `C_fresh_4x = 2400` (`4×` compute control), with the identical admission gate.
5. **`M4_random_abs` (*Random Transfer Control*):** Exact matched count $K = |\Phi|$ of non-constant, behaviorally distinct random unary DSL abstractions (`ast_size in 3..6`) lifted via the identical pair functor $\mathcal{F}_{\text{pair}}$, adapter, and gate.
6. **`M5_ace_discovery` & `M5_ace_ungated` (*ACE Discovered Typed Abstractions*):** Full automated discovery from uncurated `S_mixed` with (`M5_ace_discovery`) and without (`M5_ace_ungated`: unfiltered sub-expressions up to cap and unconditional target staging) MDL filtering and validation/probe gating.
7. **`U_native_oracle` (*Separately Reported Native Solver Upper Bound*):** Hand-authored exact tree-invariant oracle features fitted with the same adapter, stored exclusively under `upper_bound_oracle` (never inside `arms`).

---

## 6. Pre-Registered Quantitative Hypotheses & Falsification Gates (Primary `B = 32`, Seeds `1..5`)

- **H1 (Cross-Family Transfer vs Reuse, Memorization & Strong Fixed Library):** On `U_cross` at `B = 32`, `M5_ace_discovery` achieves mean terminal accuracy `>= 0.85` and beats `M0_memorize`, `M1_exact_reuse`, and `M2_strong_fixed` each by `>= +0.20` (`20.0` pp) absolute.
- **H2 (Gain & Compute Efficiency vs Fresh Target Synthesis & 4× Budget Control):** On `U_cross` at `B = 32`, `M5_ace_discovery` beats `M3_fresh_dsl` by `>= +0.15` (`15.0` pp) absolute AND beats `M3_fresh_4x` by `>= +0.10` (`10.0` pp) absolute, while expending **strictly fewer amortized AST node evaluations per target task** than `M3_fresh_4x` (including 100% of `S_mixed` source synthesis + MDL extraction AST evaluations amortized across the 15 target tasks).
- **H3 (Discovered Abstractions vs Matched Random Abstractions):** On `U_cross` at `B = 32`, `M5_ace_discovery` beats `M4_random_abs` by `>= +0.20` (`20.0` pp) absolute.
- **H4 (Automated Uncurated Source Filtering):** Across all 5 seeds, `M5_ace_discovery` automatically extracts `>= 5` of the `6` structural integer equivalence classes from the uncurated 12-task `S_mixed` pool within `K_max = 7` without task-relevance labels, with `< 50%` of selected slots occupied by 1-bit surface distractors.
- **H5 (No Surface Regression):** On `L_surface` at `B = 32`, `M5_ace_discovery` achieves mean terminal accuracy `>= 0.90` and is within `0.05` (`5.0` pp) of `M2_strong_fixed`.
- **H6 (Admission Safety / Abstention on Non-Expressible Tasks):** On `N_abstain` at `B = 32`, `M5_ace_discovery` achieves false-admission rate `<= 0.20`, reducing false admissions relative to `M5_ace_ungated` by `>= 0.75` absolute.
- **H7 (Epistemic Drift Witness & Cross-Python Determinism):**
  - **H7a (Expected Negative Safety Control):** On `D_drift` at `B = 32`, `M5_ace_discovery` stages the development-consistent model and scores `<= 0.20` terminal accuracy, witnessing that observational validation + unlabeled probe agreement **cannot** detect unobservable post-validation semantic inversion (`open_world_safe = False`, `release_decision = BLOCK_RELEASE`).
  - **H7b (Bit-Identical Reproducibility):** `runner.py` and `verify.py` produce bit-for-bit identical uncompressed canonical JSON (identical SHA-256) under both `python3.12` and `python3.13`, pass static AST isolation checks, and preserve `25/25` upstream blob hashes in `tools/verify_sources.py`.

---

## 7. Interpretation Boundaries

Passing nominal gates `H1..H6` + `H7b` while witnessing expected drift failure `H7a` establishes **bounded automated sub-program representation discovery from an uncurated mixed pool and functorial cross-family transfer within a researcher-authored base stack/scan combinator DSL**. It does **not** establish invention of the underlying stack machine itself, open-world semantic safety (`open_world_safe = False`), autonomous research-agenda generation, production readiness (`BLOCK_RELEASE`), or OAIE (`oaie_established = False`).
