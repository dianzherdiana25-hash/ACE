# Scientific Validation Results: ACE F14 V3 Independent Evaluation

**Report ID:** `ACE_F14_V3_SCIENTIFIC_VALIDATION_REPORT_20261107`  
**Evaluation Date:** 2026-11-07  
**Commitment Preregistration Hash:** `2c287b5702244010afde9d8ac5ecfbe3d80c6a18b860c7916f7f9e34e8f98a9a`  
**Evidence Artifact SHA-256:** `6eb79e93d9fcd892476735853739d7d0cbfafbc9c64afb0cdb557604837f359d`  
**Artifact File:** `evidence/f14/ace_f14_v3_scientific_validation.json.gz`  
**Marginal Financial Cost:** Strictly $0.00 / Rp0 (Local standard library compute)

---

## 1. Executive Summary & Epistemic Separation

| Dimension | Evaluation Status | Empirical Verdict |
|---|---|---|
| **ENGINEERING_TESTED** | **PASS** | 257/257 unit & system tests pass; Host Controller lineage, fail-closed gates, and budget enforcement verified. |
| **SCIENTIFICALLY_VALIDATED** | **FALSIFIED / NEGATIVE** | Hypotheses H1, H2, and H3 are all falsified on previously unexposed task families (G, H, I). |
| **OAIE_ESTABLISHED** | **FALSE** | Autonomous capability evolution is bounded by fixed template combinations and fails on non-regular formal languages. |

```json
{
  "release_gate": "BLOCK_RELEASE",
  "scientific_status": "NOT_ASSESSED",
  "oaie_established": false
}
```

---

## 2. Experimental Protocol & Commitments

Following the frozen pre-score protocol `docs/research/f14/ACE_F14_V3_PREREGISTRATION_20261107.md` (hash `2c287b5702244010afde9d8ac5ecfbe3d80c6a18b860c7916f7f9e34e8f98a9a`), the evaluation executed across 5 pre-registered paired configurations:
1. `task_seed=42, search_seed=42`
2. `task_seed=101, search_seed=137`
3. `task_seed=202, search_seed=256`
4. `task_seed=303, search_seed=512`
5. `task_seed=404, search_seed=1024`

### Benchmark Suite: Three Completely Disjoint Families
The benchmark tasks in `code/ace_research_f14/terminal_tasks_v3.py` are strictly disjoint from F12 training tasks (A, B, C) and F14-V1 tasks (D, E, F):
- **Family G (Context-Sensitive & Sequential Constraint):**
  - $G_1$ (`task_g1_an_bn`): Exact $a^n b^n$ balance for $n \ge 1$ (non-regular formal language).
  - $G_2$ (`task_g2_sandwich_parity`): Sandwich prefix-suffix equality ($w[:2] == w[-2:]$) with odd 'a' parity.
- **Family H (Block State-Machine & Sliding Window):**
  - $H_1$ (`task_h1_chunk_alternation`): Contiguous character run length parity alternation.
  - $H_2$ (`task_h2_sliding_window_atleast2`): Sliding 4-gram density invariant ($\ge 2$ 'a's per 4-gram window).
- **Family I (Hierarchical Depth & Center Symmetry):**
  - $I_1$ (`task_i1_nested_bracket_mod`): Nested Dyck bracket depth even-modulo invariant.
  - $I_2$ (`task_i2_mirror_center_invariant`): Mirror palindrome with fixed center character invariant.

### Strict Three-Tier Data Partitioning
- **`train_pool` (45 samples, lengths 1..6):** Exposed to error diagnosis and heuristic search.
- **`validation_pool` (32 samples, lengths 6..9, 16 pos / 16 neg):** Exposed for Pareto selection and generalization gap measurement.
- **`terminal_holdout_pool` (32 samples, lengths 8..15, 16 pos / 16 neg):** SEALED within `HostController` and `SealedHoldoutEvaluator`. Zero search engine read access.

---

## 3. Quantitative Results Across 5 Paired Seeds

### Primary Discovery vs. Matched Baselines

| Model / Baseline | Mean Holdout Acc | 95% Confidence Interval | Gain over Parent / Root | Promotion Status |
|---|---|---|---|---|
| **B1 (Domain Reference Oracle)** | **1.0000** | [1.0000, 1.0000] | — | Upper Bound |
| **B2 (Random AST Search, N=50)** | **0.6281** | [0.5759, 0.6803] | — | Matched Budget Control |
| **B3 (Static Feature Selection)** | **0.5385** | [0.5057, 0.5713] | — | Naive Parity Heuristic |
| **B4 (Compute-Matched Search, N=150)** | **0.6094** | [0.5694, 0.6494] | — | $3\times$ Compute Control |
| **B5 / G0 (Cold-Start Root)** | **0.6250** | [0.6250, 0.6250] | Reference Root | **ACTIVE HEAD** |
| **Primary G1 (Autonomous Guided)** | **0.6333** | [0.6275, 0.6391] | $+0.0083$ | **REJECTED** ($\Delta < 0.1500$) |
| **Primary G2 (Autonomous Guided)** | **0.5604** | [0.5546, 0.5662] | $-0.0646$ | **REJECTED** ($\Delta < 0.1500$) |

### Paired Differences & Statistical Testing

| Comparison | Mean Delta ($\Delta$) | 95% Confidence Interval | Pre-registered Threshold | Verdict |
|---|---|---|---|---|
| $G_1$ vs. $G_0$ Root | $+0.0083$ | $[+0.0025, +0.0141]$ | $\ge +0.1500$ | **FAILED** (Insufficient Gain) |
| $G_2$ vs. $G_0$ Root | $-0.0646$ | $[-0.0704, -0.0588]$ | $\ge +0.1500$ | **FAILED** (Performance Regression) |
| $G_1$ vs. B2 (Random Search) | $+0.0052$ | $[-0.0826, +0.0930]$ | $\ge +0.1000$ | **FAILED** (No Significant Dominance) |
| $G_2$ vs. B2 (Random Search) | $-0.0677$ | $[-0.1555, +0.0201]$ | $\ge +0.1000$ | **FAILED** (Random Outperforms Guided) |
| $G_2$ vs. B3 (Static Features) | $+0.0219$ | $[-0.0223, +0.0661]$ | $\ge +0.1000$ | **FAILED** (No Dominance) |

---

## 4. Evaluation of Pre-Registered Hypotheses

### Hypothesis H1: Genuine Computational Primitive Discovery
- **Pre-registered Question:** Does ACE synthesize computational operations outside its initial template catalog $\mathcal{G}_{\text{mech}}$?
- **Empirical Test:** Programmatic AST structural audit via `audit_primitive_novelty()`.
- **Finding:** Across all 5 seeds and all 6 tasks, **0 novel computational primitives were discovered**.
  Every candidate AST produced was a combinatorial composition of predefined catalog templates (`CountOp`, `SliceOp`, `ModEqPred`, `DyckBalanceOp`, `HalfSplitOp`, `RelationalEqPred`).
- **Verdict:** **FALSIFIED / NOT CONFIRMED** (`FALSIFIED_COMBINATORIAL_SEARCH_ONLY`).
  The discovery engine performs bounded template search, not open-ended primitive discovery.

### Hypothesis H2: Cross-Family Representation Transfer
- **Pre-registered Question:** Does diagnostic error guidance transfer representations across structurally disjoint families without per-task tuning?
- **Empirical Test:** Guided search dominance over matched random search ($\Delta \ge +0.1000$) and generalization gap $\le 0.0500$.
- **Finding:**
  - $G_2$ vs. Random B2 mean delta was $-0.0677$ (guided search was inferior to random search).
  - $G_1$ validation-to-holdout generalization gap was $0.1823$ (exceeding the $0.0500$ threshold).
- **Verdict:** **FALSIFIED / NOT CONFIRMED** (`FALSIFIED_NO_REPRESENTATION_TRANSFER`).
  Diagnostic signals developed on F12/F14-V1 do not transfer to context-sensitive and sliding-window languages in Families G, H, I.

### Hypothesis H3: Recursive Capability Growth ($G_0 \to G_1 \to G_2$)
- **Pre-registered Question:** Does generational succession produce monotonic, regression-bounded capability improvements under Host Controller governance?
- **Empirical Test:** $\Delta G_1 \ge 0.1500$, $\Delta G_2 \ge 0.1500$, regression $\le 0.0200$.
- **Finding:**
  - $\Delta G_1 = +0.0083$ (Threshold $\ge 0.1500 \implies$ **REJECTED**).
  - $\Delta G_2 = -0.0646$ (Threshold $\ge 0.1500 \implies$ **REJECTED**).
  - Active lineage head remained strictly at $G_0$ (`G0_v3_root`).
- **Verdict:** **FALSIFIED / NOT CONFIRMED** (`FALSIFIED_GROWTH_HALTED`).
  Recursive evolution completely halted at $G_0$ under unexposed task families.

---

## 5. Host Controller Lineage & Security Governance

1. **Empirical Root Invariant:** $G_0$ holdout accuracy ($0.6250$) was initialized dynamically by `SealedHoldoutEvaluator` on sealed holdout samples, not through hardcoded assumptions.
2. **Fail-Closed Lineage Retention:** Because $G_1$ failed promotion ($\Delta = +0.0083 < 0.1500$), $G_1$ was marked `REJECTED`. The active head remained $G_0$.
3. **Parent Score Invariance:** When $G_2$ was evaluated, its parent score was correctly derived from the active head ($G_0$). When $G_2$ also failed ($\Delta = -0.0646$), it was marked `REJECTED`, and the active head remained $G_0$.
4. **Zero Holdout Leakage:** Search engines evaluated candidates strictly against `train_pool` (45 samples) and `validation_pool` (32 samples). The terminal holdouts were held exclusively within the `HostController` process boundary.
5. **Enforced Containment:** Sandbox gate enforced fail-closed isolation (`BLOCKED_ENVIRONMENT` under uncontained OS environments).

---

## 6. Resource Profiling & Search Budget Enforcement

- **Budget Per Task:** Strictly enforced at $N=50$ candidates evaluated for Primary Guided Search and B2 Random Search.
- **Compute-Matched Baseline B4:** Strictly enforced at $N=150$ candidates ($3\times$).
- **Unique Candidates Evaluated:** 50 per task (no duplicate evaluation waste).
- **Average CPU Time Per 5-Seed Run:** $\sim 0.35$ seconds.
- **Maximum Resident Memory:** $\sim 28.5$ MB.
- **Marginal Financial Cost:** Strictly **$0.00** / Rp0.

---

## 7. Epistemic Implications for OAIE

The rigorous failure of H1, H2, and H3 on Task Suite V3 provides crucial negative evidence regarding the boundaries of autonomous evolution:
1. **Combinatorial Search is Not Evolution:** Expanding $\mathcal{G}_{\text{mech}}$ by enumerating human-specified AST templates yields apparent progress on training distributions (F12, F14-V1) but collapses when tested against context-sensitive languages ($a^n b^n$) and sliding-window invariants.
2. **Need for True Primitive Synthesis:** Open-ended intelligence evolution cannot occur without mechanisms that invent new state-accumulating primitives (e.g. counters, stacks, memory arrays) rather than merely permuting fixed AST nodes.
3. **Scientific Value of Negative Proof:** By proving fail-closed governance, eliminating holdout leakage, and establishing pre-registered commitments before unblinding results, the ACE architecture demonstrates complete experimental integrity.

---

## 8. Final Status Commitment

```json
{
  "release_gate": "BLOCK_RELEASE",
  "scientific_status": "NOT_ASSESSED",
  "oaie_established": false
}
```
All research findings, evidence artifacts, and negative proofs are preserved in the permanent project record.
