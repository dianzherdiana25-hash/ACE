# Preregistration: ACE F14 V3 Scientific Validation Protocol

**Protocol ID:** `ACE_F14_V3_SCIENTIFIC_VALIDATION_PRESCORE_20261107`  
**Registration Date:** 2026-11-07  
**Status:** FROZEN PRE-SCORE PROTOCOL COMMITMENT  
**Release Gate:** `BLOCK_RELEASE`  
**Scientific Status:** `NOT_ASSESSED`  
**OAIE Established:** `False`  
**Marginal Cost:** Strictly $0.00 / Rp0 (Local standard library compute)

---

## 1. Epistemic Background & Motivation

Previous evaluations (F12, F14-V1) demonstrated:
1. $G_1$ can achieve holdout gains ($+20.21\%$) on regular alternating/depth tasks (Families D, E).
2. However, $G_2$ achieved only $+0.31\%$ gain on cross-stride modular parity (Family F), failing promotion.
3. The grammar pool $\mathcal{G}_{\text{mech}}$ was composed of human-curated AST templates rather than genuinely discovered primitives.
4. Families D, E, and F have become research-contaminated through iterative optimization.

Protocol V3 introduces a clean, unexposed terminal task suite (Families G, H, I) and establishes pre-registered hypotheses, strict three-tier data splits, budget controls, and structural novelty verification.

---

## 2. Core Hypotheses & Confirmation Thresholds

### Hypothesis H1: Genuine Computational Primitive Discovery
- **Question:** Does ACE synthesize computational operations outside its initial template catalog $\mathcal{G}_{\text{mech}}$?
- **Operational Test:** Programmatic AST structural audit. A candidate is classified as a *novel primitive* if and only if it introduces a new control-flow or state-accumulation node not present in $\mathcal{G}_{\text{mech}}$ and achieves $\Delta_{\text{gain}} \ge 0.1500$.
- **Falsification Condition:** If candidate ASTs consist solely of predefined catalog operators (`CountOp`, `SliceOp`, `ModEqPred`, `DyckBalanceOp`, `HalfSplitOp`, `RelationalEqPred`), H1 is declared **FALSIFIED** (classified as combinatorial template search).

### Hypothesis H2: Cross-Family Representation Transfer
- **Question:** Does diagnostic error guidance transfer representations across structurally disjoint families without per-task tuning?
- **Operational Test:** Comparison of primary guided search against matched random search (B2).
- **Confirmation Threshold:** Mean advantage $\Delta_{\text{guided - random}} \ge +0.1000$ and generalization gap between validation pool and unexposed terminal holdout $\le 0.0500$.
- **Falsification Condition:** If random search achieves comparable or superior holdout accuracy ($\Delta_{\text{guided - random}} < +0.1000$), H2 is declared **FALSIFIED**.

### Hypothesis H3: Recursive Capability Growth ($G_0 \to G_1 \to G_2$)
- **Question:** Does generational succession produce monotonic, regression-bounded capability improvements under Host Controller governance?
- **Confirmation Thresholds:**
  1. $G_1$ holdout gain over empirical $G_0$: $\Delta G_1 \ge 0.1500$.
  2. $G_2$ holdout gain over parent $G_1$: $\Delta G_2 \ge 0.1500$.
  3. $G_2$ backward regression on $G_1$ tasks: $\le 0.0200$.
- **Falsification Condition:** If $\Delta G_2 < 0.1500$, candidate $G_2$ MUST be **REJECTED**, active lineage head must remain $G_1$, and H3 is declared **INCONCLUSIVE / FALSIFIED**.

---

## 3. Experimental Design & Task Suite V3

The evaluation benchmark is implemented in `code/ace_research_f14/terminal_tasks_v3.py`:
- **Family G (Context-Sensitive & Sequential Constraint):**
  - $G_1$: Strict $a^n b^n$ formal language ($n \ge 1$).
  - $G_2$: Sandwich prefix-suffix equality ($w[:2] == w[-2:]$) with odd 'a' parity.
- **Family H (Block State-Machine & Sliding Window):**
  - $H_1$: Contiguous run length parity alternation (strict even/odd alternation).
  - $H_2$: Sliding 4-gram density invariant ($\ge 2$ 'a's per window).
- **Family I (Hierarchical Depth & Center Symmetry):**
  - $I_1$: Dyck bracket balance with even max prefix depth modulo constraint.
  - $I_2$: Mirror palindrome with fixed center character constraint.

### Three-Tier Data Partitioning
Every task contains three strictly isolated partitions:
1. `train_pool`: 45 short strings (lengths $1 \dots 6$) for error diagnosis and candidate generation.
2. `validation_pool`: 32 intermediate strings (lengths $6 \dots 9$, balanced 16 positive / 16 negative) for search selection and Pareto scoring.
3. `terminal_holdout_pool`: 32 long strings (lengths $8 \dots 15$, balanced 16 positive / 16 negative) SEALED within `HostController`; evaluated ONLY once during terminal gating.

---

## 4. Pre-Registered Paired Configurations & Compute Budgets

Evaluation will execute across 5 pre-registered paired configurations:
- Run 1: `task_seed = 42, search_seed = 42`
- Run 2: `task_seed = 101, search_seed = 137`
- Run 3: `task_seed = 202, search_seed = 256`
- Run 4: `task_seed = 303, search_seed = 512`
- Run 5: `task_seed = 404, search_seed = 1024`

### Budget Constraints
- **Search Budget:** Strictly $N=50$ candidates evaluated per task for Primary Guided Search and Random Baseline (B2).
- **Compute-Matched Baseline (B4):** Strictly $N=150$ candidates ($3\times$ search budget).
- **Execution Time:** Maximum $120.0$s CPU time per run.
- **Financial Cost:** Strictly $\$0.00$ / Rp0.

---

## 5. Matched Baselines
- **B1 (Domain Reference Oracle):** Sample-by-sample execution of ground-truth oracles.
- **B2 (Random AST Search):** Uniform sampling from $\mathcal{G}_{\text{mech}}$ without diagnostic guidance ($N=50$).
- **B3 (Static Feature Selection):** Fixed heuristics (character counts and parity).
- **B4 (Compute-Matched Search):** $3\times$ budget ($N=150$) random search.
- **B5 (Cold-Start $G_0$):** Default root model measured empirically on sealed holdout.

---

## 6. Immutable Governance Policies
```json
{
  "release_gate": "BLOCK_RELEASE",
  "scientific_status": "NOT_ASSESSED",
  "oaie_established": false
}
```
All experimental results will be recorded faithfully, including all negative results, failed promotions, and rejected hypotheses.
