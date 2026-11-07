# ACE P4: Cross-Generation Capability Growth (G0 -> G1 -> G2 Continuation) — Pre-Score Commit

**Date:** 2026-11-07  
**Author:** Lead Research Engineer & Autonomous Development Coordinator  
**Branch:** `research/ace-generations-growth-20261107`  
**Target:** dianzherdiana25-hash/ACE Issue #70 (P4)  
**Status:** `PRE_REGISTERED` (Commitment locked prior to empirical data generation)  

---

## 1. Research Question & Epistemic Boundaries

Fase 7 demonstrated recursive generational development where $G_0 \rightarrow G_1 \rightarrow G_2$ achieved $51.1\% \rightarrow 68.8\% \rightarrow 96.2\%$ on the $U_{\text{gen}}$ task bank ($B=32$).

The goal of P4 is to test whether the accumulated inductive biases of $G_2$ (split-frame relational comparison, probe agreement gating, and MDL program ranking) represent genuine capability growth on an **unseen secondary task distribution** ($U_{\text{growth}}$), or whether $G_2$'s advantage degrades when faced with composite cross-relational structures.

### Non-Claim & Negative Findings Charter
1. Benchmark improvements are **NOT** evidence of Open-Ended Autonomous Intelligence Evolution (OAIE).
2. `scientific_status` remains `NOT_ASSESSED`.
3. `release_status` remains `BLOCK_RELEASE`.
4. `oaie_established` remains `False`.
5. Negative controls (unobservable semantic drift $D_{\text{drift}}$) are pre-registered to honestly demonstrate the limits of passive inductive bias.

---

## 2. Pre-Registered Hypotheses & Falsification Criteria

### Hypothesis H1 — Cross-Generation Generalization Advantage
- **Statement:** On the held-out $U_{\text{growth}}$ evaluation stratum (length 16–28 balanced terminal tests), promoted generation $G_2$ achieves mean accuracy $M(G_2) \ge 0.80$ and outperforms baseline $G_0$ by $\ge 0.20$ and $G_1$ by $\ge 0.10$.
- **Falsification Criterion:** Falsified if $M(G_2) < 0.80$ or $(M(G_2) - M(G_0)) < 0.20$.

### Hypothesis H2 — Compute Amortization over Search Scale
- **Statement:** The structural inductive bias of $G_2$ ($K=256$) cannot be replicated by simply scaling raw evaluation budget on $G_0$ ($B_{\text{extra\_compute}}$ with $K=1024$, $4\times$ compute). $M(G_2) - M(B_{\text{extra\_compute}}) \ge 0.15$.
- **Falsification Criterion:** Falsified if $M(G_2) - M(B_{\text{extra\_compute}}) < 0.15$.

### Hypothesis H3 — Unobservable Semantic Drift Honesty (Negative Control)
- **Statement:** When terminal classification boundaries invert relative to invariant training/validation samples ($D_{\text{drift}}$), all passive generational mechanisms ($G_0, G_1, G_2$) will fail terminal accuracy ($M(D) \le 0.10$).
- **Falsification Criterion:** Falsified if any passive arm achieves $M(D) > 0.50$ (which would indicate label leakage or non-rigorous holdout).

### Hypothesis H4 — Lineage Auditability & Evaluator Isolation
- **Statement:** All mechanism candidates are evaluated under AST isolation (`ImmutableCoreGuard`), staged under `STAGED_FOR_REVIEW` in `Autonomy`, and verified via HMAC signatures without modifying evaluator or promotion policies.
- **Falsification Criterion:** Falsified if any core SHA-256 changes or evaluator AST isolation is breached.

---

## 3. Pre-Committed Task Stratum ($U_{\text{growth}}$)

The $U_{\text{growth}}$ bank consists of 6 novel task families disjoint from $M_1$, $M_2$, and original $U_{\text{gen}}$:
1. `UG1`: Quarter-frame parity invariance (left quarter vs right quarter parity match).
2. `UG2`: Alternating 3-stride modular match ($w[0::3]$ vs $w[1::3]$).
3. `UG3`: Split-half block count symmetry ($\text{block2\_aa}(\text{left}) \equiv \text{block2\_aa}(\text{right}) \pmod 2$).
4. `UG4`: Relational length-parity coupling with suffix condition.
5. `UG5`: Cross-modular parity comparison ($a$-count in left half mod 3 vs $b$-count in right half mod 3).
6. `UG6`: Double-stride composite conjunction.

Drift controls:
- `DG1`: `UG1` inverted terminal labels.
- `DG2`: `UG3` inverted terminal labels.

Each task is evaluated across 5 deterministic seeds (1..5) with $N=128$ balanced terminal test strings (length 16–28).
