# Preregistration: ACE Autonomous Self-Development Loop V0.1

**Protocol ID:** `ACE_SELF_DEV_V01_PRESCORE_20261107`  
**Registration Date:** 2026-11-07  
**Status:** FROZEN PRE-SCORE PROTOCOL COMMITMENT  
**Release Gate:** `BLOCK_RELEASE`  
**Scientific Status:** `NOT_ASSESSED`  
**OAIE Established:** `False`  
**Marginal Financial Cost:** Strictly $0.00 / Rp0 (Local standard library compute)

---

## 1. Epistemic Background & Objectives

The Autonomous Self-Development Loop V0.1 unifies:
1. **System Diagnosis & Weakness Identification:** Programmatic analysis of current baseline model performance against structured tasks.
2. **Falsifiable Research Hypothesis Selection:** Automatic formulation of concrete, refutable hypotheses targeting diagnosed weaknesses.
3. **Typed AST Source Evolution (E1.6-V2):** Generation of verified, strongly-typed Python source code using bounded mathematical genes and strict AST whitelisting (rejecting unauthorized imports, builtins, and system calls).
4. **Independent Sealed Holdout Evaluation:** Evaluation against a brand new Confirmation Task Suite (Families J, K) disjoint from F12 (A, B, C), F14-V1 (D, E, F), and F14-V3 (G, H, I).
5. **Fail-Closed Lineage Governance:** Gating under Host Controller. Candidates with holdout gain $< 0.1500$ or regression $> 0.0200$ MUST be rejected; the baseline model is strictly retained.
6. **Durable Checkpointing & Crash Resumption:** State is persisted across all 8 phases to guarantee restartability.
7. **Transparent Author Provenance:** Explicit attribution to `ACE_AUTONOMOUS_V01`, `GEMINI`, `CODEX`, or `HUMAN`.
8. **ChatGPT / GitHub Actions Entrypoint:** Verifiable, data-only task envelopes via GitHub Actions emitting HMAC receipts.

---

## 2. Confirmation Benchmark Suite (Families J, K)

Implemented in `code/ace_self_dev/confirmation_suite.py`:
- **Family J (Multi-Scale Run-Length Invariants):**
  - $J_1$ (`task_j1_multiscale_run_parity`): Contiguous character run lengths alternate strictly between even and odd lengths.
  - $J_2$ (`task_j2_symmetric_run_boundary`): First contiguous character run length equals last run length with even 'a' parity.
- **Family K (Relational Substring Parity & Center Pivot):**
  - $K_1$ (`task_k1_center_pivot_density`): Center character determines left-half vs right-half 'a' density equality.
  - $K_2$ (`task_k2_modular_stride_shift`): Even-index character count equals odd-index character count modulo 3.

### Three-Tier Data Partitioning
1. `train_pool`: 40 short strings (lengths $1 \dots 6$) for error diagnosis and candidate generation.
2. `validation_pool`: 32 intermediate strings (lengths $6 \dots 9$, balanced 16 positive / 16 negative).
3. `sealed_confirmation_holdout`: 32 long strings (lengths $8 \dots 15$, balanced 16 positive / 16 negative) SEALED within Host Controller.

---

## 3. Pre-Registered Confirmation Criteria

1. **Promotion Threshold:** $\Delta_{\text{holdout\_gain}} \ge 0.1500$ over parent baseline.
2. **Regression Tolerance:** Prior task performance regression $\le 0.0200$.
3. **Falsification & Rejection Rule:** If $\Delta_{\text{gain}} < 0.1500$, candidate MUST be rejected; active head must remain at parent baseline.
4. **Zero Marginal Financial Cost:** All search, generation, and evaluation operations must cost exactly $0.00.
5. **Author Provenance Invariant:** Every proposed candidate must explicitly record `author_type`.

---

## 4. Immutable Governance Commitment
```json
{
  "release_gate": "BLOCK_RELEASE",
  "scientific_status": "NOT_ASSESSED",
  "oaie_established": false
}
```
Operational workflow execution (even across multiple cycles) does not constitute proof of recursive self-improvement or open-ended intelligence evolution.
