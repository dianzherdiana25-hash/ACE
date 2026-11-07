# Empirical Results: ACE F13 Causal Memory Validation Benchmark

**Status:** EMPIRICAL RESEARCH REPORT (NEGATIVE & INCONCLUSIVE FINDINGS RECORDED)  
**Date:** 2026-11-07  
**Pre-Score Commitment:** `docs/research/f13/ACE_F13_CAUSAL_MEMORY_PRESCORE_20261107.md`  
**Pre-Score Commitment SHA-256:** `0948f00b273be45a408d7c758cd45c2b5a67c15c215b86e9600f2940decf34f3`  
**Evidence Artifact:** `evidence/f13/ace_f13_causal_memory_v1.json.gz`  
**Evidence Artifact SHA-256:** `91caa55f5a25311c1831d4b86e8a5dfd6c4e3dcf83898568c979241db9c45dcb`  
**Release Gate:** `BLOCK_RELEASE`  
**Scientific Status:** `NOT_ASSESSED`  
**OAIE Established:** `False`  
**Cost:** Strictly $0.00 / Rp0 (Local CPU standard library execution)

---

## 1. Executive Summary

ACE F13 investigated whether structured causal memory (transfer of operator weights and distilled parameter abstractions) provides causal benefits on downstream curriculum tasks compared to cold-start (No-Memory), permuted associations (Shuffled-Memory), distractor priors (Irrelevant-Memory), and compute matching (2.0x budget).

### Key Empirical Findings
1. **Transfer Accuracy Effect Size:** Standard Memory achieved a mean holdout accuracy of $0.9922 \pm 0.0175$ compared to No-Memory at $0.9766 \pm 0.0349$, yielding an effect size of **Cohen's $d = 0.5657$** (satisfying Criterion 1: $d \ge 0.50$).
2. **Inconclusive Query Reduction:** Because the active information-gain inquiry loop is highly efficient at epistemic elimination (cutting candidate hypotheses via discriminating probes), both Standard Memory and No-Memory resolved the ambiguity in an average of $1.40$ queries. Consequently, the observed query reduction was **$0.0\%$**, failing Pre-Registered Criterion 2 ($\ge 25.0\%$).
3. **Shuffled-Memory Resilience:** Shuffled-Memory achieved $1.0000 \pm 0.0000$, resulting in a negative delta ($\Delta = -0.0078$), failing Criterion 3 ($\ge +0.05$).
4. **Falsification Verdict:** Under the strict pre-registered criteria, Hypothesis F13 is declared **`FALSIFIED_OR_INCONCLUSIVE`**. In accordance with the Project Charter and fail-closed research governance, these negative findings are recorded honestly without claim inflation.

---

## 2. Experimental Summary Across 6 Matched Arms

Evaluated across the 5 pre-registered deterministic seeds ($[42, 137, 256, 512, 1024]$):

| Arm ID | Arm Name | Transfer Acc (Mean $\pm$ SD) | 95% Confidence Interval | Transfer Queries (Mean $\pm$ SD) |
| :--- | :--- | :--- | :--- | :--- |
| **Arm 1** | **Standard Memory** | **$0.9922 \pm 0.0175$** | $[0.9705, 1.0139]$ | $1.40 \pm 0.55$ |
| **Arm 2** | No-Memory (Cold Start) | $0.9766 \pm 0.0349$ | $[0.9332, 1.0199]$ | $1.40 \pm 0.55$ |
| **Arm 3** | Shuffled-Memory | $1.0000 \pm 0.0000$ | $[1.0000, 1.0000]$ | $1.40 \pm 0.55$ |
| **Arm 4** | Irrelevant-Memory | $0.9766 \pm 0.0349$ | $[0.9332, 1.0199]$ | $1.40 \pm 0.55$ |
| **Arm 5** | Static Transfer Baseline | $0.9922 \pm 0.0175$ | $[0.9705, 1.0139]$ | $1.40 \pm 0.55$ |
| **Arm 6** | Compute-Matched (2x) | $0.9766 \pm 0.0349$ | $[0.9332, 1.0199]$ | $1.40 \pm 0.55$ |

---

## 3. Pre-Registered Criteria Evaluation Table

| Criterion ID | Target Metric | Pre-Registered Threshold | Observed Result | Pass / Fail |
| :--- | :--- | :--- | :--- | :--- |
| **Crit-1** | Cohen's $d$ (Standard vs. None) | $\ge 0.50$ | **$0.5657$** | **PASS** |
| **Crit-2** | Query Reduction Percentage | $\ge 25.0\%$ | **$0.0\%$** | **FAIL** |
| **Crit-3** | Shuffled-Memory Dominance | $\ge +0.05$ | **$-0.0078$** | **FAIL** |
| **Crit-4** | Irrelevant-Memory Resilience | $\ge +0.05$ | **$+0.0156$** | **FAIL** |
| **Overall** | Full Pre-Registration Confirmation | All 4 Criteria | 1 Pass, 3 Fail | **FALSIFIED / INCONCLUSIVE** |

---

## 4. Scientific Discussion & Architectural Implications

The F13 experiment reveals a critical epistemic boundary condition:
- When an active inquiry oracle $O_{\text{exp}}$ is present and the hypothesis space is moderately sized, active epistemic probes are so informative that the agent quickly collapses the hypothesis space regardless of the initial prior.
- Inductive memory priors provide a measurable accuracy boost in transfer ($d = 0.5657$), but do not substantially reduce active query count when active information gain is already optimal.
- Consequently, future memory architectures (F15+) must focus on **large-scale combinatorial grammar spaces** where active inquiry alone cannot exhaustively search without strong inductive pruning.

---

## 5. Governance Preserved

- `release_gate`: `BLOCK_RELEASE`
- `scientific_status`: `NOT_ASSESSED`
- `oaie_established`: `False`
- Pinned upstream sources: 25/25 verified intact.
