# ACE P4: Cross-Generation Capability Growth (G0 -> G1 -> G2 Continuation) — Empirical Results

**Date:** 2026-11-07  
**Author:** Lead Research Engineer & Autonomous Development Coordinator  
**Branch:** `research/ace-generations-growth-20261107`  
**Commit Pre-Score:** `e6a20b2` (`ACE_P4_GENERATIONS_GROWTH_PRESCORE_20261107.md`)  
**Evidence Artifact:** `evidence/generations/ace_generations_growth_v1.json.gz`  
**Uncompressed SHA-256:** `4ecb63792d7382f17136dda9496efdf9fef03363712a88593efca253e6a8c92d`  
**Deterministic Replay:** `VERIFIED_PASS` (`verify_growth.py`)  

---

## 1. Executive Summary

In response to Issue #70 (P4), we extended the recursive generation research ($G_0 \rightarrow G_1 \rightarrow G_2$) to a novel, disjoint evaluation stratum ($U_{\text{growth}}$) consisting of 6 cross-relational tasks (`UG1`..`UG6`) evaluated across 5 random seeds ($N=40$ total units, 30 nominal + 10 drift controls) with length 16–28 balanced terminal tests ($N=128$ strings per test).

### Key Empirical Findings
1. **$G_2$ Superiority on Novel Invariants ($H_1$ PASS):**
   - $G_2$ achieved **$99.69\%$** mean terminal accuracy on $U_{\text{growth}}$ ($29/30$ units solved at $\ge 0.95$).
   - $G_0$ and $G_1$ both achieved **$50.00\%$** (chance level), yielding a margin $\Delta(G_2 - G_0) = +0.4969$, comfortably exceeding the pre-registered threshold $+0.20$.
2. **Compute Amortization ($H_2$ PASS):**
   - Scaling search compute on base generation $G_0$ by $4\times$ ($B_{\text{extra\_compute}}$ with $K=1024$ candidates) remained stuck at **$50.00\%$** accuracy ($0/30$ solved).
   - This empirically falsifies the compute-scaling hypothesis: raw search scale cannot compensate for missing relational inductive bias ($\Delta = +0.4969 \ge 0.15$).
3. **Semantic Drift Negative Control ($H_3$ PASS):**
   - Under hidden terminal label inversion ($D_{\text{drift}}$), $G_2$ scored **$0.00\%$** terminal accuracy ($0/10$ solved), faithfully proving that passive inductive bias cannot detect unobservable semantic drift without active interactive probes.
   - $G_0$ abstained and remained at $50.00\%$, with zero false discoveries.
4. **Lineage Audit & Core Immutability ($H_4$ PASS):**
   - `ImmutableCoreGuard` verified 7/7 core hashes intact.
   - AST isolation verified with zero forbidden imports.
   - All mechanisms staged in `Autonomy` under `STAGED_FOR_REVIEW` with receipts in SQLite WAL.

---

## 2. Quantitative Summary Table

| Evaluation Arm | Feature Set | Budget $K$ | Mean Acc ($U_{\text{growth}}$) | Solve Rate ($U_{\text{growth}}$) | Drift Acc ($D_{\text{drift}}$) |
|---|---|---|---|---|---|
| **$G_2$ (Promoted)** | Strided + Split-Frame Relational | 256 | **99.69%** | **96.67%** (29/30) | **0.00%** (10/10 drift refutations) |
| **$G_1$ (Intermediate)**| Strided Features Only | 256 | 50.00% | 0.00% (0/30) | 50.00% (Abstained) |
| **$G_0$ (Base)** | Surface Counts Only | 256 | 50.00% | 0.00% (0/30) | 50.00% (Abstained) |
| **$B_{\text{extra\_compute}}$** | Surface Counts Only | 1024 ($4\times$) | 50.00% | 0.00% (0/30) | 50.00% (Abstained) |
| **$B_{\text{fixed}}$** | 100 R1 Fixed Predicates | 256 | 50.00% | 0.00% (0/30) | 50.00% (Abstained) |
| **$B_{\text{random\_mut}}$** | Random Mechanism Mutation | $\le 256$ | 50.00% | 0.00% (0/30) | 50.00% (Abstained) |
| **$B_{\text{fresh}}$** | Fresh R1 DFA Learner | Dynamic | 50.00% | 0.00% (0/30) | 50.00% (Abstained) |

---

## 3. Pre-Registered Hypotheses Verdicts

- **$H_1$ (Growth Advantage):** `PASSED` ($M(G_2) = 0.9969 \ge 0.80$; $\Delta = +0.4969 \ge 0.20$).
- **$H_2$ (Compute Amortization):** `PASSED` ($\Delta(G_2 - B_{\text{extra\_compute}}) = +0.4969 \ge 0.15$).
- **$H_3$ (Semantic Drift Honesty):** `PASSED` ($M(G_2 \mid D_{\text{drift}}) = 0.00 \le 0.10$; no arm $> 0.50$).
- **$H_4$ (Lineage Audit & AST Isolation):** `PASSED` (`ast_isolated = True`).
- **All Gates Pass:** `TRUE`.

---

## 4. Release Status & Scientific Governance

As required by the Project Charter:
- `scientific_status`: `NOT_ASSESSED` (requires sealed external holdouts and independent audit)
- `release_status`: `BLOCK_RELEASE`
- `oaie_established`: `False` (isolated synthetic grammar domains do not establish general open-ended evolution)
- `SCIENTIFIC_CAPABILITY_VALIDATED`: `False`
- `PASSIVE_SEMANTIC_DRIFT_DETECTABLE`: `False`
