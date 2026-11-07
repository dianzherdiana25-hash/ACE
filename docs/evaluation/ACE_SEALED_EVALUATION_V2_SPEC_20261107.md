# ACE Sealed Evaluation V2: Dual-Oracle Decoupling & Merkle Exposure Auditing

**Status:** APPROVED EVALUATION SPECIFICATION & HARNESS  
**Version:** Sealed Evaluation V2  
**Release Gate:** `BLOCK_RELEASE`  
**Scientific Status:** `NOT_ASSESSED`  
**OAIE Established:** `False`  
**Authors:** Lead Scientific Evaluator & Autonomous Development Coordinator (Gemini Argon)  
**Date:** 2026-11-07  

---

## 1. Executive Summary: Epistemic Distinctions in Autonomous Evaluation

In empirical AI safety and autonomous capability research, **cryptographic signatures (HMAC/SHA256) prove data custody and integrity, but they do NOT by themselves prove independent scientific evaluation.** If an evaluation harness allows active epistemic probes to query the terminal test set or share internal state with the candidate generator, cryptographic signing merely certifies a contaminated benchmark.

**Sealed Evaluation V2** introduces three fundamental scientific controls:
1. **Dual-Oracle Separation:** Active epistemic inquiries ($O_{\text{exp}}$) are mathematically and physically decoupled from terminal holdouts ($O_{\text{term}}$).
2. **Merkle-Chained Exposure Ledger:** Every sample or feedback exposed to the agent is committed to an append-only hash chain with multi-tier contamination auditing.
3. **Pre-Registration Commitment Protocol:** Evaluation thresholds and holdout manifests are committed to a cryptographic hash before opening terminal evaluations.

```
+---------------------------------------------------------------------------------+
|                        AGENT C / RESEARCH GENERATOR                             |
|  - Causal Gap Diagnosis                                                         |
|  - Active Epistemic Querying (under metered budget K)                           |
+----------------------------------------+----------------------------------------+
                                         |
                       Active Inquiries  | (Length 1..6 strings only)
                                         v
+---------------------------------------------------------------------------------+
|                           EXPERIMENT ORACLE (O_exp)                             |
|  - Answers active probes within training domain                                 |
|  - Strictly metered: budget.consume_queries(1)                                  |
|  - Logs every query into MerkleExposureLedger                                   |
|  - ZERO access to terminal holdouts                                             |
+---------------------------------------------------------------------------------+

                      [ COMPLETE SEPARATION OF ORACLES ]

+---------------------------------------------------------------------------------+
|                          TERMINAL EVALUATOR (O_term)                            |
|  - Evaluates final candidate mechanisms only                                    |
|  - Evaluates on length 8..24 disjoint holdouts                                 |
|  - NEVER accessible via epistemic query interface                              |
|  - Audits MerkleExposureLedger for exact and n-gram substring contamination     |
|  - Validates PreRegistrationCommitment before emitting EvaluationReceipt        |
+---------------------------------------------------------------------------------+
```

---

## 2. Core Modules in Evaluator V2 (`code/ace_host_controller/evaluator_v2.py`)

### 2.1 Dual-Oracle Decoupling (`DualOracleHarness`)
- **Experiment Oracle Registry (`_experiment_oracles`):**
  Exposed exclusively via `query_experiment_oracle(candidate_id, task_id, input_str, budget)`. An attempt to target tasks not registered for active inquiry raises `KeyError`.
- **Terminal Holdout Registry (`_terminal_holdouts`):**
  Private holdout test cases (length 8..24, balanced classes). Any attempt by a research agent to query terminal holdout instances directly raises `OracleBoundaryViolation`.

### 2.2 Tamper-Resistant Merkle Exposure Ledger (`MerkleExposureLedger`)
- Uses an append-only cryptographic hash chain:
  $$H_i = \text{SHA256}(i \parallel \text{candidate\_id} \parallel \text{query\_type} \parallel \text{content} \parallel H_{i-1})$$
- Modifying, deleting, or reordering any past query breaks `verify_chain_integrity()` and raises `LedgerTamperError`.
- **Multi-Tier Contamination Defense:**
  - **Tier 1 (Exact Match):** $\mathcal{E}_{\text{exposed}} \cap \mathcal{H}_{\text{terminal}} == \emptyset$
  - **Tier 2 (N-Gram Substring Leakage):** Verifies that no long substrings (length $\ge 8$) from terminal test inputs appeared in epistemic probes.

### 2.3 Pre-Registration Commitment (`PreRegistrationCommitment`)
- Before opening terminal holdouts, the supervisor records:
  $$\text{CommitmentHash} = \text{SHA256}(\text{manifest\_digest} \parallel \text{min\_gain} \parallel \text{max\_regression} \parallel \text{target\_tasks})$$
- Post-hoc threshold tampering is cryptographically detectable.

---

## 3. Unit Test Suite Results

Test Suite: [`code/ace_host_controller/test_evaluator_v2.py`](file:///home/antigravity/dianzherdiana25-hash/ACE-eval-v2/code/ace_host_controller/test_evaluator_v2.py)  
Status: **5/5 tests PASS (0.001s)**

1. `test_dual_oracle_querying_and_budget`: Active queries answer via experiment oracle and decrement budget correctly.
2. `test_merkle_exposure_ledger_chain_and_tamper`: Verifies hash chain and catches in-memory tampering.
3. `test_multitier_contamination_detection`: Successfully catches exact matches and n-gram substring leaks.
4. `test_terminal_evaluation_and_gating`: Evaluates candidate cleanly, checks prior regression, and signs HMAC receipt.
5. `test_preregistration_commitment_hash`: Confirms hash determinism and threshold sensitivity.

---

## 4. Verification & Fail-Closed Invariants
- Upstream pinned source integrity: **25/25 verified intact (`tools/verify_sources.py`)**
- Invariants: `release_gate = BLOCK_RELEASE`, `scientific_status = NOT_ASSESSED`, `oaie_established = False`.
