# Empirical Results: ACE F14 Autonomous Mechanism Discovery Benchmark

**Status:** EMPIRICAL RESEARCH REPORT (INDEPENDENT TERMINAL EVALUATION — NEGATIVE & FALSIFIED FINDINGS RECORDED)  
**Date:** 2026-11-07  
**Pre-Score Commitment:** `docs/research/f14/ACE_F14_INDEPENDENT_EVALUATION_PRESCORE_20261107.md`  
**Pre-Score Commitment SHA-256:** `08baed13793977b7a056e262d984dde074e243edf0aa00a5c45b486f0c249659`  
**Evidence Artifact:** `evidence/f14/ace_f14_mechanism_discovery_v1.json.gz`  
**Evidence Artifact SHA-256:** `3d97c401131d9335860bbd1d587945a248214b69ccacea3d428c33d70cb783fc`  
**Release Gate:** `BLOCK_RELEASE`  
**Scientific Status:** `NOT_ASSESSED`  
**OAIE Established:** `False`  
**Cost:** Strictly $0.00 / Rp0 (Local CPU standard library execution)

---

## 1. Executive Summary

ACE F14 tested autonomous mechanism discovery without hardcoded domain feature lists across generations ($G_0 \to G_1 \to G_2$).

While early exploratory benchmarks evaluated on F12 tasks (Family A, B, C) showed high accuracy, that setup suffered from circularity because the compositional grammar $\mathcal{G}_{\text{mech}}$ was designed with primitive operators targeting those specific families. Furthermore, the exploratory baseline $B_1$ was manually assigned $1.00$ without empirical execution.

Under the independent, pre-registered terminal benchmark (`terminal_tasks.py`), ACE was evaluated on three completely new, disjoint structural families:
- **Family D (Alternating & Run-Length Structure):** $D_1$ (Even Runs of 'a'), $D_2$ (Bounded Alternation $\le 2$).
- **Family E (Hierarchical Prefix & Symmetry):** $E_1$ (Prefix Depth Mod 3), $E_2$ (Mirror Parity Palindrome).
- **Family F (Modular Cross-Stride Invariants):** $F_1$ (Stride 2 vs Stride 3 Cross-Parity), $F_2$ (Triplet Parity).

### Key Empirical Findings:
1. **Real Empirical Baselines:** All baselines were computed from sample-by-sample execution:
   - Reference Model ($B_1$): $1.0000 \pm 0.0000$.
   - Random AST Search ($B_2$): $0.6323 \pm 0.0175$.
   - Static Feature Selection ($B_3$): $0.6042 \pm 0.0000$.
   - Compute-Matched Search ($B_4$, $3\times$ budget): $0.6417 \pm 0.0150$.
   - Cold-Start ($B_5$, $G_0$): $0.3906 \pm 0.0000$.
2. **Autonomous Discovery Performance:**
   - $G_0$ starting accuracy: $0.3906 \pm 0.0000$.
   - $G_1$ discovered accuracy: $0.6042 \pm 0.0000$ (gain: $+0.1042$, failing the pre-registered threshold $\ge 0.1500$).
   - $G_2$ discovered accuracy: $0.6146 \pm 0.0000$ (gain: $+0.1146$, failing the pre-registered threshold $\ge 0.1500$).
   - $G_2$ regression on $G_1$ tasks: $0.0000 \pm 0.0000$ (passing $\le 0.0200$).
3. **No Advantage Over Random Search:** Random AST Search ($B_2 = 0.6323$) achieved slightly higher holdout accuracy than guided discovery ($G_2 = 0.6146$, delta $-0.0177$).
4. **Falsification Verdict:** Under the strict pre-registered confirmation criteria, Hypothesis F14 is declared **`FALSIFIED_OR_INCONCLUSIVE`** on the independent terminal benchmark (Decision: **`HOLD / REJECT`**).

---

## 2. Generational Growth Decisions & Lineage Tracking

Evaluated under `HostController` with `SealedHoldoutEvaluator` across 5 paired seeds ($[42, 137, 256, 512, 1024]$):

| Generation | Candidate ID | Parent ID | Discovered AST Type | Mean Holdout Acc | 95% Confidence Interval | Mean Gain ($\Delta$) | Mean Regression | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **$G_0$** | `G0_root` | Root | `ModEqPred(LengthOp, 3, 0)` | $0.3906$ | $[0.3906, 0.3906]$ | Baseline | N/A | ROOT |
| **$G_1$** | `G1_discovered` | $G_0$ | AST Composition ($D, E$) | $0.6042$ | $[0.6042, 0.6042]$ | $+0.1042$ | $0.0000$ | **BELOW THRESHOLD** |
| **$G_2$** | `G2_discovered` | $G_1$ | AST Composition ($D, E, F$) | $0.6146$ | $[0.6146, 0.6146]$ | $+0.1146$ | $0.0000$ | **BELOW THRESHOLD** |

---

## 3. Matched Baselines Comparison

| Baseline ID | Baseline Name | Mean Holdout Accuracy | Performance Ratio to Reference | Search Budget |
| :--- | :--- | :--- | :--- | :--- |
| **B1** | Empirical Domain Reference | $1.0000 \pm 0.0000$ | $100.0\%$ | Exact Oracle Execution |
| **B2** | Random AST Search (Uniform sampling) | $0.6323 \pm 0.0175$ | $63.2\%$ | $N=50$ candidates |
| **B3** | Static Feature Selection (Parity / Counts) | $0.6042 \pm 0.0000$ | $60.4\%$ | Fixed catalog |
| **B4** | Compute-Matched Search ($3\times$ budget) | $0.6417 \pm 0.0150$ | $64.2\%$ | $N=150$ candidates |
| **B5** | Cold-Start ($G_0$ baseline) | $0.3906 \pm 0.0000$ | $39.1\%$ | Zero discovery |
| **Primary** | **ACE F14 Autonomous Discovery Engine ($G_2$)** | **$0.6146 \pm 0.0000$** | **$61.5\%$** | **$N=50$ candidates / task** |

---

## 4. Pre-Registered Criteria Evaluation Table

| Criterion ID | Target Metric | Pre-Registered Threshold | Observed Result | Pass / Fail |
| :--- | :--- | :--- | :--- | :--- |
| **Crit-1** | Zero Hardcoded Feature Lists | True | **True** (synthesized from $\mathcal{G}_{\text{mech}}$) | **PASS** |
| **Crit-2** | Empirical $G_0$ Baseline | Data-driven | **$0.3906$** | **PASS** |
| **Crit-3** | $G_1$ Holdout Gain | $\ge 0.1500$ | **$+0.1042$** | **FAIL** |
| **Crit-4** | $G_2$ Holdout Gain | $\ge 0.1500$ | **$+0.1146$** | **FAIL** |
| **Crit-5** | $G_2$ Prior Regression | $\le 0.0200$ | **$0.0000$** | **PASS** |
| **Crit-6** | Dominance over Random AST Search | $\ge +0.1000$ | **$-0.0177$** | **FAIL** |
| **Crit-7** | Dominance over Static Features | $\ge +0.1000$ | **$+0.0104$** | **FAIL** |
| **Crit-8** | Ratio to Empirical Reference ($B_1$) | $\ge 80.0\%$ | **$61.5\%$** | **FAIL** |
| **Overall** | Full Pre-Registration Confirmation | All 8 Criteria | 3 Pass, 5 Fail | **FALSIFIED / INCONCLUSIVE** |

---

## 5. Epistemic Assessment & Claim Boundaries

1. **Composition vs. Creation:** F14 operates via grammar search and AST composition within the predefined catalog of $\mathcal{G}_{\text{mech}}$. It does **not** invent new computational primitives (such as general run-length iterators or arbitrary recursive stack machines) when presented with families that require them.
2. **No Overclaiming:** We do not claim Open-Ended Autonomous Intelligence Evolution (OAIE). The scientific status remains strictly `NOT_ASSESSED`.
3. **Fail-Closed Governance:**
   - `release_gate`: `BLOCK_RELEASE`
   - `scientific_status`: `NOT_ASSESSED`
   - `oaie_established`: `False`
