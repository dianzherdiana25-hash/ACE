# Pre-Score Commitment: ACE F14 Independent Terminal Evaluation Protocol

**Status:** PRE-REGISTERED EXPERIMENTAL COMMITMENT (DEDICATED PRE-EVALUATION COMMIT)  
**Date:** 2026-11-07  
**Commitment Scope:** Independent Terminal Benchmark for ACE F14 Autonomous Mechanism Discovery  
**Task Suite:** `code/ace_research_f14/terminal_tasks.py` (Disjoint Family D, E, F)  
**Release Gate:** `BLOCK_RELEASE`  
**Scientific Status:** `NOT_ASSESSED`  
**OAIE Established:** `False`  
**Coordinator:** Gemini Argon (Lead Research Engineer & Autonomous Development Coordinator)  
**Target Environment:** Local Autonomous Runtime & Independent Host Controller (`code/ace_host_controller`)  
**Cost Constraint:** Strictly $0.00 / Rp0 (Standard library Python CPU execution only)

---

## 1. Experimental Rationale & Decontamination Safeguard

The original exploratory F14 evaluation reused the F12 task suite (Family A: strided parity, Family B: Dyck balance, Family C: split-mod relational). Because the compositional grammar $\mathcal{G}_{\text{mech}}$ was designed with primitive operators directly corresponding to those families, evaluating on F12 tasks risked circular validation. Furthermore, the exploratory baseline $B_1$ was manually assigned $1.00$ without empirical execution.

This protocol institutes an **independent, sealed terminal evaluation**:
1. **Completely Disjoint Task Families:** Six new tasks across three structural families never used during grammar formulation:
   - **Family D (Run-Length & Alternation):** $D_1$ (Even Runs of 'a'), $D_2$ (Bounded Alternation $\le 2$).
   - **Family E (Hierarchical Prefix & Symmetry):** $E_1$ (Prefix Depth Mod 3), $E_2$ (Mirror Parity Palindrome).
   - **Family F (Modular Cross-Stride Invariants):** $F_1$ (Stride 2 vs Stride 3 Cross-Parity), $F_2$ (Triplet Parity).
2. **Empirical Baseline Execution:** All baselines ($B_1$ through $B_5$) are executed empirically sample-by-sample on actual holdout pools. No manual constants are permitted.
3. **Paired Multi-Seed Replications:** Evaluated across 5 deterministic seeds: $[42, 137, 256, 512, 1024]$.
4. **Distinction of Mechanism Search vs Primitive Creation:** F14 operates via grammar-guided search and compositional synthesis over $\mathcal{G}_{\text{mech}}$. It does **not** create arbitrary new Turing-complete primitive instructions from scratch. Claims of open-ended evolution (OAIE) are strictly forbidden.

---

## 2. Experimental Hypotheses

> **Hypothesis F14-Indep-A (Autonomous Compositional Synthesis):**  
> Guided by training error diagnosis, ACE F14 will compose valid AST predictors from $\mathcal{G}_{\text{mech}}$ on previously unseen families ($D, E, F$) that achieve statistically significant accuracy gains ($\Delta \ge +0.15$) over cold-start baseline $G_0$.

> **Hypothesis F14-Indep-B (Generational Progress without Regression):**  
> Advancing from $G_1$ (Families $D, E$) to $G_2$ (incorporating Family $F$) will achieve incremental holdout gain ($\Delta \ge +0.15$) while maintaining regression on prior families $\le 0.02$.

> **Hypothesis F14-Indep-C (Empirical Baseline Dominance):**  
> Autonomous discovery will achieve holdout accuracy superior to Random AST Search ($B_2$) and Static Feature Selection ($B_3$) by at least $+0.10$.

---

## 3. Matched Experimental Arms

| Arm ID | Description | Compute / Search Budget |
| :--- | :--- | :--- |
| **B1** | Empirical Domain Reference (direct domain oracle evaluation) | Reference model execution |
| **B2** | Random AST Search (uniform sampling from $\mathcal{G}_{\text{mech}}$ without diagnosis) | $N=50$ candidates |
| **B3** | Static Feature Selection (fixed character counting / parity heuristics) | Fixed heuristics |
| **B4** | Compute-Matched Search (brute-force search with $3\times$ budget) | $N=150$ candidates |
| **B5** | Cold-Start ($G_0$ default baseline) | None |
| **Primary** | ACE F14 Autonomous Discovery Engine ($G_0 \to G_1 \to G_2$) | $N=50$ candidates per task |

---

## 4. Pre-Registered Confirmation Criteria

All criteria must be satisfied to declare positive validation:
1. **Zero Hardcoded Features:** No domain-specific feature lists injected into the discovery loop.
2. **Empirical $G_0$ Baseline:** Starting accuracy computed strictly from data.
3. **$G_1$ Holdout Gain:** Mean holdout accuracy gain $\Delta(G_1 - G_0) \ge 0.1500$.
4. **$G_2$ Holdout Gain:** Mean holdout accuracy gain $\Delta(G_2 - G_1) \ge 0.1500$.
5. **$G_2$ Prior Regression:** Regression on $G_1$ tasks $\le 0.0200$.
6. **Dominance over Random Search ($B_2$):** Holdout advantage $\ge +0.1000$.
7. **Dominance over Static Features ($B_3$):** Holdout advantage $\ge +0.1000$.
8. **Empirical Reference Ratio ($B_1$):** Achieves $\ge 80.0\%$ of empirical reference accuracy.

**Falsification Clause:** If any criterion fails across the 5 paired seeds, the outcome is designated **`HOLD / REJECT`** or **`FALSIFIED_OR_INCONCLUSIVE`**. No post-hoc modification of criteria or task suites is allowed.

---

## 5. Governance Invariants

- `release_gate`: `BLOCK_RELEASE`
- `scientific_status`: `NOT_ASSESSED`
- `oaie_established`: `False`
- Marginal Cost: Strictly $0.00 / Rp0.
