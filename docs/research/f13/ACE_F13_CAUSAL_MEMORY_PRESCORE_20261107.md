# Pre-Score Commitment: ACE F13 Causal Memory Validation Benchmark

**Status:** PRE-REGISTERED EXPERIMENTAL COMMITMENT  
**Date:** 2026-11-07  
**Commitment Scope:** F13 Causal Memory Validation (Resolving F12 Inconclusive Memory Ablation)  
**Release Gate:** `BLOCK_RELEASE`  
**Scientific Status:** `NOT_ASSESSED`  
**OAIE Established:** `False`  
**Coordinator:** Gemini Argon (Lead Research Engineer & Autonomous Development Coordinator)  
**Target Environment:** Local Autonomous Runtime & Independent Host Controller (`code/ace_host_controller`)  
**Cost Constraint:** Strictly $0.00 / Rp0 (Standard library Python CPU execution only)

---

## 1. Background & Scientific Rationale

In ACE F12 (`docs/research/f12/ACE_F12_CAUSAL_AUTONOMOUS_RESEARCH_RESULTS_20261107.md`), the memory ablation yielded identical holdout performance across active, no-memory, and shuffled-memory arms ($\text{acc} = 0.5825$). Diagnosis revealed two structural flaws in the F12 setup:
1. **Lack of Curriculum Structure:** Tasks in F12 were evaluated independently in random batches without structural prerequisites.
2. **Passive Memory Recording:** The F12 agent appended finding dictionaries to memory but did not condition hypothesis proposal probabilities or operator weights on accumulated causal evidence.

F13 redesigns the investigation from the ground up:
- We formulate a **Curriculum Task Sequence** with explicit transfer hierarchies (Modular/Periodic Family and Balanced/Symmetric Family).
- The causal memory actively distills **structural inductive abstractions** (promoted operator weights, parameter priors, and hypothesis templates).
- Downstream tasks leverage these abstractions to prioritize candidate exploration.

---

## 2. Core Hypotheses

> **Hypothesis F13-A (Transfer Accuracy):**  
> An autonomous agent with structured causal memory (`Standard Memory`) will achieve higher holdout generalization accuracy on downstream curriculum transfer tasks than an agent with zero memory (`No-Memory`) or distractor memory (`Irrelevant-Memory`), with an effect size of Cohen's $d \ge 0.50$.

> **Hypothesis F13-B (Active Inquiry Efficiency):**  
> On downstream transfer tasks, `Standard Memory` will reduce the number of active environment queries ($O_{\text{exp}}$) required to reach task criterion by at least $25.0\%$ compared to `No-Memory` and `Irrelevant-Memory`.

> **Hypothesis F13-C (Structural Alignment vs Permutation):**  
> `Standard Memory` will significantly outperform `Shuffled-Memory` (permuted operator-domain associations), proving that transfer benefit derives from aligned structural relationships rather than mere history volume.

---

## 3. Matched Experimental Arms

All arms operate under identical Host Controller budget constraints ($K \le 20$ metered oracle queries per task, max execution time $30.0$s):

| Arm ID | Arm Name | Description | Memory Content |
| :--- | :--- | :--- | :--- |
| **Arm 1** | **Standard Memory** | Dynamic causal memory updating operator priors from successful tasks | Distilled hypothesis templates & operator weights |
| **Arm 2** | **No-Memory (Cold Start)** | Resets to uniform priors before each curriculum task | None (wiped at every task transition) |
| **Arm 3** | **Shuffled-Memory** | Retains learned templates but randomly shuffles operator-domain links | Permuted operator associations |
| **Arm 4** | **Irrelevant-Memory** | Injected with distractor priors from an unrelated domain (sorting / lex) | Distractor domain invariants |
| **Arm 5** | **Static Transfer Baseline** | Fixed hand-engineered prior without learning from task experience | Immutable prior distribution |
| **Arm 6** | **Compute-Matched Baseline** | No-Memory, but granted $2.0\times$ search & inquiry budget ($K \le 40$) | None (compensated with brute-force compute) |

---

## 4. Evaluation Seeds & Task Curriculum

### 4.1 Evaluation Seeds
Experiments are evaluated across 5 pre-registered deterministic seeds:
$$\text{Seeds} = [42, 137, 256, 512, 1024]$$

### 4.2 Curriculum Task Sequence
1. **Cluster 1: Periodic & Strided Invariants**
   - $T_0$ (Warmup): Binary parity of `'a'` (`count('a') % 2 == 0`)
   - $T_1$ (Transfer Target 1): Strided even-index parity (`w[0::2].count('a') % 2 == 0`)
   - $T_2$ (Transfer Target 2): Stride-3 modular match (`w[1::3].count('b') % 2 == 1`)
2. **Cluster 2: Nested Balance & Relational Symmetry**
   - $T_3$ (Warmup): Dyck-1 balanced brackets (`prefix_balance >= 0 and total_balance == 0`)
   - $T_4$ (Transfer Target 3): Depth-bounded Dyck with length constraint (`depth in [0, 4]`)
   - $T_5$ (Transfer Target 4): Relational half-split balance (`w[:len//2].count('a') == w[len//2:].count('a')`)

Transfer evaluation is evaluated strictly on held-out tasks $\{T_1, T_2, T_4, T_5\}$.

---

## 5. Pre-Registered Acceptance Criteria & Falsification Thresholds

To confirm Hypothesis F13, empirical results must meet ALL criteria:
1. **Cohen's $d \ge 0.50$:** Standard Memory vs. No-Memory on curriculum transfer tasks.
2. **Query Reduction $\ge 25.0\%$:** Standard Memory vs. No-Memory query consumption.
3. **Shuffled-Memory Dominance:** Standard Memory holdout accuracy $>$ Shuffled-Memory holdout accuracy ($\Delta \ge +0.05$).
4. **Irrelevant-Memory Resilience:** Standard Memory holdout accuracy $>$ Irrelevant-Memory holdout accuracy ($\Delta \ge +0.05$).
5. **Compute-Matched Non-Triviality:** Standard Memory query efficiency $\ge 1.30\times$ Compute-Matched baseline per unit query.
6. **Host Controller Verification:** Evaluated via sealed terminal oracles $O_{\text{term}}$, zero exposure ledger contamination, signed receipts.
7. **Falsification Rule:** If $d < 0.50$ or query reduction $< 25\%$, the hypothesis of causal memory transfer is declared **FALSIFIED / NOT SUPPORTED**, and recorded honestly.

---

## 6. Governance Invariants

- `release_gate = "BLOCK_RELEASE"`
- `scientific_status = "NOT_ASSESSED"`
- `oaie_established = False`
- No claim of OAIE or intrinsic general intelligence.
