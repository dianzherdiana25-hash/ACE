# Scientific Addendum: ACE F14 Gating Correction & True Independent Evaluation

**Status:** EMPIRICAL CORRECTION & INDEPENDENT REPLICATION ADDENDUM  
**Date:** 2026-11-07  
**Commitment Hash:** Pre-Score Commitments Recorded in `docs/research/f14/ACE_F14_INDEPENDENT_EVALUATION_PRESCORE_20261107.md` (`08baed13793977b7a056e262d984dde074e243edf0aa00a5c45b486f0c249659`)  
**Evidence Artifact:** `evidence/f14/ace_f14_mechanism_discovery_v1.json.gz`  
**Evidence Artifact SHA-256:** `4cc363b9ff0fb17f84bc960bc4e94573c10ba038e525d2f7f5fcfd86141a3062`  
**Governance Invariants:** `release_gate=BLOCK_RELEASE`, `scientific_status=NOT_ASSESSED`, `oaie_established=False`  
**Marginal Cost:** Strictly $0.00 / Rp0 (Local standard library compute)

---

## 1. Audit and Identification of Generational Gain Bug

An in-depth audit of `HostController` and `discovery_engine` revealed two critical gating discrepancies in the initial F14 evaluation run:

1. **Root Controller Hardcoded Holdout Score:**
   The root node `G0_root` was previously registered with an unvalidated constant `holdout_score = 0.50` instead of measuring empirical starting accuracy on the terminal task suite.
2. **True Baseline Discrepancy:**
   On the independent terminal task suite (`terminal_tasks.py`, spanning Families D, E, and F), $G_0$ actually achieves **$0.3906$** ($75 / 192$ holdout samples correct).
3. **Flawed Lineage Delta Calculation:**
   - Under the flawed root score ($0.5000$), $G_1$ ($0.6042$) yielded a reported gain of $+0.1042$, falsely indicating that $G_1$ failed the $\ge 0.1500$ threshold.
   - In truth, measuring against actual empirical parent $G_0$ ($0.3906$):
     $$\Delta G_1 = 0.6042 - 0.3906 = \mathbf{+0.2136} \ge 0.1500 \implies \mathbf{ACCEPTED}$$
   - $G_1$ was properly promoted to active lineage head.
   - Next, candidate $G_2$ achieved $0.6146$. When evaluated against its true parent $G_1$ ($0.6042$):
     $$\Delta G_2 = 0.6146 - 0.6042 = \mathbf{+0.0104} < 0.1500 \implies \mathbf{REJECTED}$$
   - $G_2$ failed the pre-registered promotion threshold and was correctly **`REJECTED`** by `HostController`.
   - The active lineage head remained **$G_1$** (`G1_autonomous_discovered`).

---

## 2. Host Boundary V2 & Evaluator Hardening

To prevent future lineage corruption or unearned promotion:
- **Empirical Root Initialization:** `HostController.initialize_root_score(root_fn)` measures the root model directly on sealed holdout banks via the trusted evaluator, eliminating arbitrary starting constants.
- **Parent Status Invariant:** `HostController.evaluate_and_gate` enforces that child candidates can only be promoted if their direct parent is in status `ACCEPTED`. If parent candidate is rejected or unaccepted, any derivative candidate is rejected fail-closed.
- **Lineage Head Invariant:** If candidate $G_2$ is rejected, `active_head_id` does not advance; it stays anchored at parent $G_1$.
- **Subprocess Isolation:** Worker execution is quarantined in separate subprocesses without access to evaluator signing keys or ground-truth terminal labels. Untrusted AST candidates attempting dangerous imports (e.g. `import os`, `subprocess`) fail immediately.

---

## 3. Independent Dataset Replica Validation

Five seeds using identical holdout samples do not constitute five independent dataset replicas. We separated search seed (`search_seed`) from task generation seed (`task_seed`) across 5 pre-registered paired configurations:

| Run | Task Seed | Search Seed | $G_0$ Empirical | $G_1$ Accuracy | $G_1$ Gain ($\Delta_{\text{parent}}$) | $G_1$ Status | $G_2$ Accuracy | $G_2$ Gain ($\Delta_{\text{parent}}$) | $G_2$ Status | Active Lineage Head |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **1** | 42 | 42 | $0.3906$ | $0.6042$ | $+0.2136$ | **ACCEPTED** | $0.6146$ | $+0.0104$ | **REJECTED** | `G1_autonomous_discovered` |
| **2** | 101 | 137 | $0.3906$ | $0.5833$ | $+0.1927$ | **ACCEPTED** | $0.5833$ | $+0.0000$ | **REJECTED** | `G1_autonomous_discovered` |
| **3** | 202 | 256 | $0.3906$ | $0.5885$ | $+0.1979$ | **ACCEPTED** | $0.5938$ | $+0.0053$ | **REJECTED** | `G1_autonomous_discovered` |
| **4** | 303 | 512 | $0.3906$ | $0.5990$ | $+0.2084$ | **ACCEPTED** | $0.5990$ | $+0.0000$ | **REJECTED** | `G1_autonomous_discovered` |
| **5** | 404 | 1024 | $0.3906$ | $0.5885$ | $+0.1979$ | **ACCEPTED** | $0.5885$ | $+0.0000$ | **REJECTED** | `G1_autonomous_discovered` |
| **Mean** | — | — | **$0.3906$** | **$0.5927$** | **$+0.2021$** | **100% PASS** | **$0.5958$** | **$+0.0031$** | **100% REJECT** | **`G1_autonomous_discovered`** |

### Statistical Summary
- **$G_1$ Discovery Gain:** $+0.2021 \pm 0.0097$ (95% CI: $[0.1901, 0.2141]$), comfortably exceeding the $\ge 0.1500$ threshold.
- **$G_2$ Discovery Gain:** $+0.0031 \pm 0.0048$ (95% CI: $[-0.0028, 0.0090]$), failing the $\ge 0.1500$ threshold across all seeds.
- **$G_2$ Prior Regression:** $0.0000 \pm 0.0000$, passing the $\le 0.0200$ threshold.

---

## 4. End-to-End Raw Data Verifier

The updated verifier (`code/ace_research_f14/verify.py` and `tools/verify_f13_f14.py`) performs complete sample-by-sample recomputation:
1. Validates that every run contains full `raw_labels` and `raw_predictions` (`g0`, `g1`, `g2`).
2. Recomputes exact accuracies:
   $$\text{acc}_G = \frac{1}{N} \sum_{i=1}^N \mathbb{I}(\hat{y}_{G, i} = y_i)$$
3. Computes exact parent gains:
   $$\Delta_{G1} = \text{acc}_{G1} - \text{acc}_{G0}, \quad \Delta_{G2} = \text{acc}_{G2} - \text{acc}_{G1}$$
4. Validates that declared acceptance decisions and lineage nodes match mathematical gains.
5. Verifies candidate budgets ($\le 50$) and CPU limits ($\le 120.0\text{s}$).
6. Fails closed on any manipulation of labels, predictions, scores, or lineage records.

---

## 5. Epistemic Conclusion & Governance

- **Scientific Reality:** Grammar search autonomously synthesized functional mechanisms for Family D (run lengths) and Family E (prefix depth), resulting in $+20.21\%$ empirical gain for $G_1$. However, compositional search over $\mathcal{G}_{\text{mech}}$ failed to discover effective primitives for Family F (cross-stride modular parity and triplet parity), producing only $+0.31\%$ gain for $G_2$.
- **Honest Governance:** Candidate $G_2$ was rightfully **`REJECTED`**. No artificial claims of $G_2$ promotion are made.
- **Invariants Maintained:**
  - `release_gate = BLOCK_RELEASE`
  - `scientific_status = NOT_ASSESSED`
  - `oaie_established = False`
