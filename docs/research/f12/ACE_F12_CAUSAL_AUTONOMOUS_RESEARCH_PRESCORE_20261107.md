# Pre-Score Commitment: ACE F12 Causal Autonomous Research Benchmark

**Status:** PRE-REGISTERED EXPERIMENTAL COMMITMENT  
**Date:** 2026-11-07  
**Commitment Hash:** Pre-registered before running benchmark  
**Release Gate:** `BLOCK_RELEASE`  
**Scientific Status:** `NOT_ASSESSED`  
**OAIE Established:** `False`  
**Lead Coordinator:** Gemini Argon (Lead Research Engineer & Autonomous Development Coordinator)  
**Execution Runtime:** Native ACE Autonomous Runtime (`code/ace_runtime`) & Independent Host Controller (`code/ace_host_controller`)

---

## 1. Core Hypothesis

> **Hypothesis F12:**  
> Under independent Host Controller supervision and metered environment access, an autonomous research agent utilizing **causal gap identification** and **active information-gain experiment selection** will:
> 1. Formulate typed, falsifiable hypotheses that explain observed performance bottlenecks;
> 2. Synthesize highly informative discriminating experiments without oracle leakage;
> 3. Produce successor mechanisms achieving validated cross-generation capability growth ($G_0 \to G_1 \to G_2$) on family-disjoint holdout tasks ($\ge 0.15$ accuracy gain, $\le 0.02$ regression);
> 4. Strictly outperform matched controls (fixed templates, random exploration, passive evaluation, extra compute, and memory ablations).

---

## 2. Experimental Arms & Controls

The benchmark evaluates 6 matched experimental arms under identical Host Controller budget constraints ($K \le 20$ metered oracle queries, max execution seconds $30.0$s per task):

| Arm ID | Name | Hypothesis Synthesis | Query Policy | Memory Conditioning |
| :--- | :--- | :--- | :--- | :--- |
| **Arm 1** | Fixed Template Control | Fixed static heuristic rules | Static 1-edit probe | Standard evidence history |
| **Arm 2** | Random Exploration Control | Random uniform mutation | Random probe selection | Standard evidence history |
| **Arm 3** | Passive Evaluation Control | Supervised MLE fit | Zero active queries ($K=0$) | Standard evidence history |
| **Arm 4** | **Active F12 Causal Agent** | **Causal gap-driven synthesis** | **Max Mutual Information / Info-Gain** | **Structured causal memory DAG** |
| **Arm 5** | Extra-Compute Control | Search over 5x candidates | Passive / Random selection | Standard evidence history |
| **Arm 6a** | Ablation: No-Memory | Causal synthesis | Active Info-Gain | Zero memory (cold start) |
| **Arm 6b** | Ablation: Shuffled-Memory| Causal synthesis | Active Info-Gain | Permuted evidence history |

---

## 3. Disjoint Task Families

Tasks are partitioned into 3 mathematically disjoint structural families:
1. **Family A: Strided Modular Parity:**
   - Invariants over interleaved symbol sequences ($w[0::2].\text{count}('a') \pmod m == r$).
2. **Family B: Dyck Nested Balance & Depth Bounds:**
   - Context-free bracket/prefix balance and prefix non-negativity ($\forall i, \text{depth}(w[:i]) \ge 0 \land \text{depth}(w) == 0$).
3. **Family C: Relational Split-Frame Equivalence:**
   - Structural equality/inequality between left and right halves ($w[:h].\text{count}('a') \pmod m == w[h:].\text{count}('a') \pmod m$).

---

## 4. Pre-Registered Success Criteria

To accept Hypothesis F12, the empirical results must satisfy ALL of the following criteria:
1. **Holdout Gain:** Active F12 ($G_1$ and $G_2$) achieves mean holdout accuracy gain $\Delta \ge +0.15$ over $G_0$ baseline across held-out families.
2. **Regression Bound:** Prior task regression $\le 0.02$ across all generational promotions.
3. **Control Dominance:** Active F12 statistically outperforms Fixed Templates, Random Policy, Passive Evaluation, and Extra-Compute on holdout accuracy and query efficiency.
4. **Memory Dependency:** Active F12 outperforms No-Memory (Arm 6a) and Shuffled-Memory (Arm 6b) by $\Delta \ge 0.10$, proving non-trivial dependence on accumulated causal evidence.
5. **Host Controller Verification:** All candidates evaluated through `SealedHoldoutEvaluator`, logged in `ExposureLedger` with zero holdout contamination, and issued valid HMAC receipts.
6. **Governance Preservation:** `release_gate = BLOCK_RELEASE`, `oaie_established = False`, `scientific_status = NOT_ASSESSED`.
