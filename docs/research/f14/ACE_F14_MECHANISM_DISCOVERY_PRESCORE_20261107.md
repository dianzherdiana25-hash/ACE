# Pre-Score Commitment: ACE F14 Autonomous Mechanism Discovery Benchmark

**Status:** PRE-REGISTERED EXPERIMENTAL COMMITMENT  
**Date:** 2026-11-07  
**Commitment Scope:** F14 Autonomous Mechanism Discovery (Eliminating Hardcoded Feature Inductive Biases)  
**Release Gate:** `BLOCK_RELEASE`  
**Scientific Status:** `NOT_ASSESSED`  
**OAIE Established:** `False`  
**Coordinator:** Gemini Argon (Lead Research Engineer & Autonomous Development Coordinator)  
**Target Environment:** Local Autonomous Runtime & Independent Host Controller (`code/ace_host_controller`)  
**Cost Constraint:** Strictly $0.00 / Rp0 (Standard library Python CPU execution only)

---

## 1. Scientific Background & Rationale

In F12 (`generational_growth.py`), cross-generation growth ($G_0 \to G_1 \to G_2$) relied on hardcoded feature lists:
- $G_0$: `allowed_features = ["flat_parity"]` with hardcoded starting accuracy $0.50$.
- $G_1$: `allowed_features = ["flat_parity", "strided_mod", "dyck_bounded"]`.
- $G_2$: `allowed_features = ["flat_parity", "strided_mod", "dyck_bounded", "split_mod"]`.

While this demonstrated the Host Controller's regression gating and lineage tracking, the mechanism proposals were not autonomously synthesized by ACE; rather, they were pre-selected by the human engineer.

F14 establishes genuine **Autonomous Mechanism Discovery**:
1. **Compositional Mechanism Grammar ($\mathcal{G}_{\text{mech}}$):** Defines an infinite expressive space of candidate structural extractors over string sequences (slicing, counting, prefix/suffix bounds, Dyck depth, relational equality, and modular congruence).
2. **Autonomous Error Diagnosis:** ACE inspects training errors of the current generation model without human hints, identifies empirical error correlations (e.g., positional alternation or bracket depth), and constructs targeted candidate search expressions.
3. **Empirical Baseline Evaluation:** $G_0$ baseline accuracy is measured strictly on data via the exact same search and evaluation protocol, eliminating all hardcoded starting accuracies.
4. **Host Controller Submission:** Candidate ASTs are compiled into pure Python callables and submitted to the Host Controller for independent sealed holdout validation ($O_{\text{term}}$).

---

## 2. Core Hypotheses

> **Hypothesis F14-A (Autonomous Mechanism Discovery):**  
> ACE can autonomously diagnose structural error patterns and synthesize novel mechanism ASTs from $\mathcal{G}_{\text{mech}}$ that achieve validated holdout gain $\ge 0.15$ over prior generation without human-injected feature lists.

> **Hypothesis F14-B (Recursive Generalization to Unseen Families):**  
> Synthesized mechanisms will successfully generalize across generations ($G_0 \to G_1 \to G_2$) to unseen structural families (Family C Relational Split-Frame) while satisfying the Host Controller regression invariant ($\text{regression} \le 0.02$).

> **Hypothesis F14-C (Baseline Dominance):**  
> Autonomous grammar discovery will significantly outperform Random Search, Static Feature Selection, and Cold-Start baselines, and achieve $\ge 85\%$ of the performance of the Researcher-Engineered Upper Bound.

---

## 3. Matched Baselines

All baselines are evaluated on the exact same task suites and budget constraints:

| Baseline ID | Name | Description | Search Budget |
| :--- | :--- | :--- | :--- |
| **B1** | **Researcher Upper Bound** | Human hand-engineered features from F12 (`strided_mod`, `dyck_bounded`, `split_mod`) | Reference |
| **B2** | **Random AST Search** | Random uniform sampling from $\mathcal{G}_{\text{mech}}$ without error diagnosis | $N=50$ candidates |
| **B3** | **Static Feature Selection** | Standard fixed regex / n-gram patterns ($n \in \{1, 2, 3\}$) | Exhaustive |
| **B4** | **Compute-Matched Search** | Brute-force exhaustive search over $\mathcal{G}_{\text{mech}}$ with $3.0\times$ budget ($N=150$) | $N=150$ candidates |
| **B5** | **Cold-Start (G0)** | Baseline classifier without mechanism discovery | None |
| **Primary** | **ACE F14 Discovery Engine** | Error-driven diagnosis + guided grammar search from $\mathcal{G}_{\text{mech}}$ | $N=50$ candidates |

---

## 4. Pre-Registered Success Criteria

To accept Hypothesis F14:
1. **Zero Hardcoded Features:** No pre-defined domain feature lists (`strided_mod`, `dyck_bounded`, `split_mod`) in the agent loop.
2. **Empirical G0 Baseline:** $G_0$ starting accuracy measured empirically on data, not set to arbitrary constants.
3. **Generational Holdout Gain:** $G_1$ and $G_2$ must each achieve holdout accuracy gain $\Delta \ge +0.15$ over parent generation on Host Controller holdouts.
4. **Regression Safety:** Regression on previously mastered families $\le 0.02$.
5. **Dominance over Random & Static:** ACE Discovery Engine holdout accuracy $>$ Random Search (B2) and Static Features (B3) by $\ge +0.10$.
6. **Host Controller Verification:** Passed through `SubprocessSealedEvaluator` or `DualOracleHarness`, zero Merkle exposure contamination, signed receipts.
7. **Falsification Rule:** If ACE fails to synthesize valid mechanisms from $\mathcal{G}_{\text{mech}}$ or fails the holdout gain threshold, declare autonomous mechanism discovery **UNRESOLVED / FALSIFIED**.

---

## 5. Governance Invariants

- `release_gate = "BLOCK_RELEASE"`
- `scientific_status = "NOT_ASSESSED"`
- `oaie_established = False`
- No overclaiming of open-ended evolution or unrestricted code generation.
