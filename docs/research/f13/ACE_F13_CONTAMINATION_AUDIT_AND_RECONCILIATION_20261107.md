# ACE F13 Causal Memory: Contamination Audit and Reconciliation Report

**Date:** 2026-11-07  
**Status:** AUDIT & SCIENTIFIC RECONCILIATION COMPLETE  
**Repository:** `dianzherdiana25-hash/ACE`  
**Branch:** `agent-c-discovery` (PR #84)  
**Evidence Artifact:** `evidence/f13/ace_f13_causal_memory_v1.json.gz`  
**Evidence SHA-256:** `efa00a78db2d6ab43f1635f6402adaa7049c82be59146268f91e29266324dd03`  
**Pre-Score Doc:** `docs/research/f13/ACE_F13_CAUSAL_MEMORY_PRESCORE_20261107.md`  
**Pre-Score SHA-256:** `0948f00b273be45a408d7c758cd45c2b5a67c15c215b86e9600f2940decf34f3`  
**Governance Invariants:**  
- `release_gate`: `BLOCK_RELEASE`  
- `scientific_status`: `NOT_ASSESSED`  
- `oaie_established`: `False`  
- Marginal Cost: Strictly $0.00 / Rp0

---

## 1. Root Cause Analysis: Holdout Pool Leakage

During the initial F13 exploratory phase, an audit revealed that `code/ace_research_f13/agent.py` accessed `task.holdout_pool` directly:
```python
# Contaminated logic previously in agent.py:
holdout_hits = sum(1 for w, lbl in task.holdout_pool if cand_fn(w) == lbl)
holdout_acc = holdout_hits / max(1, len(task.holdout_pool))
if holdout_acc >= 0.85:
    self.memory.record_solution(task.cluster, best_cand.family_name, best_cand.params)
```
This violated the strict separation between training/development feedback and terminal evaluation. Memory storage decisions were being gated on terminal holdout performance.

### Corrective Action Implemented:
1. **Total Decoupling:** Completely eliminated all references to `task.holdout_pool` from `F13CausalAgent`. Memory updates are now exclusively determined by training feedback (`train_acc >= 0.85` on `task.train_pool`).
2. **Independent Sealed Evaluation:** Terminal holdout evaluation is executed solely by the benchmark evaluator harness post-search on `task.holdout_pool`.
3. **Automated Non-Interference Proof:** Added `test_terminal_label_noninterference` in `code/ace_research_f13/test_f13_memory.py`. When terminal holdout labels are adversarially inverted:
   - Agent proposals are bit-for-bit identical.
   - Selected family and parameters are identical.
   - Queries consumed and training accuracies are identical.
   - Predictions on arbitrary input strings are 100% invariant.
4. **Exposure & Budget Accounting:** Oracle calls are metered through `host.budget.consume_queries(1)` and logged to `host.ledger`.

---

## 2. Reconciled Empirical Results (Paired-Seed Analysis)

Five deterministic seeds ($[42, 137, 256, 512, 1024]$) were evaluated across 6 matched arms:

### Summary by Arm
| Arm | Transfer Acc (Mean $\pm$ SD) | 95% Confidence Interval | Transfer Queries (Mean $\pm$ SD) |
| :--- | :--- | :--- | :--- |
| **Standard Memory** | $0.9922 \pm 0.0175$ | $[0.9705, 1.0139]$ | $1.40 \pm 0.55$ |
| **No-Memory (Cold Start)** | $0.9766 \pm 0.0349$ | $[0.9332, 1.0199]$ | $1.40 \pm 0.55$ |
| **Shuffled-Memory** | $1.0000 \pm 0.0000$ | $[1.0000, 1.0000]$ | $1.40 \pm 0.55$ |
| **Irrelevant-Memory** | $0.9766 \pm 0.0349$ | $[0.9332, 1.0199]$ | $1.40 \pm 0.55$ |
| **Static Transfer** | $0.9922 \pm 0.0175$ | $[0.9705, 1.0139]$ | $1.40 \pm 0.55$ |
| **Compute-Matched (2x)** | $0.9766 \pm 0.0349$ | $[0.9332, 1.0199]$ | $1.40 \pm 0.55$ |

### Paired-Seed Breakdown ($n=5$)
| Seed | Standard | No-Memory | Shuffled | Irrelevant | Diff (Std - None) | Diff (Std - Shuffled) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **42** | 1.0000 | 1.0000 | 1.0000 | 1.0000 | +0.0000 | +0.0000 |
| **137** | 1.0000 | 1.0000 | 1.0000 | 1.0000 | +0.0000 | +0.0000 |
| **256** | 0.9609 | 0.9219 | 1.0000 | 0.9219 | +0.0391 | -0.0391 |
| **512** | 1.0000 | 0.9609 | 1.0000 | 0.9609 | +0.0391 | +0.0000 |
| **1024** | 1.0000 | 1.0000 | 1.0000 | 1.0000 | +0.0000 | +0.0000 |

### Statistical Inference (Paired Difference Tests)
- **Standard vs. No-Memory:**
  - Mean paired difference $\bar{\Delta} = +0.0156$ ($s_{\Delta} = 0.0214$)
  - Paired $t$-statistic: $t(4) = 1.633$ ($p > 0.10$, two-tailed critical value $t_{0.025, 4} = 2.776$)
  - 95% CI of Difference: $[-0.0109, +0.0422]$ (crosses zero; not statistically significant).
- **Standard vs. Shuffled-Memory:**
  - Mean paired difference $\bar{\Delta} = -0.0078$ ($s_{\Delta} = 0.0175$)
  - Paired $t$-statistic: $t(4) = -1.000$ ($p > 0.30$)
  - 95% CI of Difference: $[-0.0295, +0.0139]$ (crosses zero; shuffled memory achieves higher empirical accuracy on seed 256).

---

## 3. Scientific Verdict and Falsification

Under the pre-registered protocol (`docs/research/f13/ACE_F13_CAUSAL_MEMORY_PRESCORE_20261107.md`), an empirical claim of causal memory transfer requires satisfying all 4 criteria:
1. Cohen's $d \ge 0.50$: **PASS** ($d = 0.5657$).
2. Query reduction $\ge 25.0\%$: **FAIL** ($0.0\%$ reduction; active query count is saturated at 1.40 across both arms).
3. Shuffled memory dominance $\Delta \ge +0.05$: **FAIL** ($\Delta = -0.0078$).
4. Irrelevant memory resilience $\Delta \ge +0.05$: **FAIL** ($\Delta = +0.0156$).

**Final Determination:** **`FALSIFIED_OR_INCONCLUSIVE`** (Decision: **HOLD / REJECT**).  
The hypothesis that Causal Memory V2 delivers autonomous causal advantage on this task suite is not supported by rigorous decontaminated evidence.
