# ACE Independent Host Controller & Evaluation Architecture Specification

**Status:** APPROVED ARCHITECTURAL SPECIFICATION & HARNESS  
**Release Gate:** `BLOCK_RELEASE`  
**Scientific Status:** `NOT_ASSESSED`  
**OAIE Established:** `False`  
**Date:** 2026-11-07  
**Module:** `code/ace_host_controller`  
**Authors:** Lead Research Engineer & Autonomous Development Coordinator (Gemini Argon)

---

## 1. Executive Summary: The Principle of Separation of Powers

In open-ended autonomous intelligence research, self-modifying agents or search algorithms cannot be allowed to evaluate, grade, or promote themselves. Allowing an evolutionary agent to inspect test holdouts, modify evaluation thresholds, or bypass environment sandboxes leads to deceptive alignment, benchmark contamination, and unchecked capability regression.

The **ACE Independent Host Controller** implements an external, authoritative supervisory layer. It decouples:
1. **The Candidate Generator (Untrusted Explorer):** The research agent (e.g. F10, F11, F12, ACE Runtime) that formulates hypotheses, queries training samples, and synthesizes candidate mechanisms.
2. **The Host Controller (Trusted Supervisor):** The external governor that tracks candidate lineage, enforces compute and query budgets, seals evaluation holdouts, audits code safety, detects data leakage, issues cryptographically signed receipts, and executes automated rollbacks.

```
+---------------------------------------------------------------------------------+
|                         INDEPENDENT HOST CONTROLLER                             |
|                                                                                 |
|   +---------------------+   +---------------------+   +---------------------+   |
|   |    LineageGraph     |   |   ExecutionBudget   |   |   HostSandboxGate   |   |
|   |  - Parent / SHA     |   |  - Wall-clock time  |   |  - AST validation   |   |
|   |  - G0 -> G1 -> G2   |   |  - Query count      |   |  - BLOCKED_ENV      |   |
|   +----------+----------+   +----------+----------+   +----------+----------+   |
|              |                         |                         |              |
|              +-------------------------+-------------------------+              |
|                                        |                                        |
|   +------------------------------------+------------------------------------+   |
|   |                                                                         |   |
|   |   +---------------------+                     +---------------------+   |   |
|   |   |   ExposureLedger    |                     |   Sealed Evaluator  |   |   |
|   |   | - Query journal     |                     | - Secret holdouts   |   |   |
|   |   | - Contamination     |                     | - Manifest SHA-256  |   |   |
|   |   |   verification      |                     | - HMAC Receipts     |   |   |
|   |   +----------+----------+                     +----------+----------+   |   |
|   |              |                                           |              |   |
|   +--------------+-------------------------------------------+--------------+   |
|                  |                                           |                  |
|                  v                                           v                  |
|         [ Non-Contamination ]                      [ Acceptance Gate ]          |
|                  |                                           |                  |
|                  +---------------------+---------------------+                  |
|                                        |                                        |
|                                        v                                        |
|                          Promotion / Rollback Engine                            |
+----------------------------------------+----------------------------------------+
                                         |
                       Evaluates & Gates Candidates Blindly
                                         |
                                         v
+---------------------------------------------------------------------------------+
|                    ACE AUTONOMOUS RESEARCH GENERATOR / RUNTIME                  |
|  - Causal Gap Identification (F12)                                              |
|  - Epistemic Querying (F11 metered budget)                                      |
|  - Candidate Synthesis & Representation Transfer (R9)                           |
+---------------------------------------------------------------------------------+
```

---

## 2. Core Governance Modules

### 2.1 Lineage Graph (`lineage.py`)
- Tracks each candidate as a discrete node with:
  - `candidate_id` and immutable `parent_id`
  - `source_sha`: Cryptographic SHA-256 digest of candidate specification or code
  - `generation`: Generational tier ($G_0, G_1, G_2, \dots$)
  - `lineage_depth`: Depth from root
  - `status`: Lifecycle state (`REGISTERED`, `EVALUATING`, `ACCEPTED`, `REJECTED`, `ROLLED_BACK`)
- Enforces DAG acyclicity and single active HEAD pointer.

### 2.2 Execution Budgets & Capability Permits (`budget_permits.py`)
- Enforces hard compute bounds:
  - Max wall-clock execution seconds (e.g. 300.0s)
  - Max epistemic/evaluation queries (e.g. 1,000 queries)
  - Max candidates evaluated (e.g. 50 candidates)
- Enforces least-privilege capability permits:
  - Disallows raw network access (`allow_network = False`)
  - Disallows unconstrained filesystem writes (`allow_filesystem_write = False`)
  - Disallows direct shell/subprocess execution (`allow_shell_exec = False`)

### 2.3 Host Sandbox Gate (`sandbox_gate.py`)
- Inspects candidate Python code AST before execution:
  - Rejects forbidden modules: `os`, `sys`, `subprocess`, `socket`, `urllib`, `requests`, `ctypes`, `pty`, `multiprocessing`.
  - Rejects forbidden builtins: `eval`, `exec`, `__import__`, `open`, `compile`, `globals`, `locals`.
  - Rejects reflection escape vectors: `__subclasses__`, `__bases__`, `__mro__`, `__globals__`.
- Enforces fail-closed `BLOCKED_ENVIRONMENT` if OS-level isolation (bwrap/seccomp/container) is absent when executing untrusted dynamic processes.

### 2.4 Sealed Holdout Evaluator (`sealed_evaluator.py`)
- Holdout test sets and ground-truth predicates are sealed in private memory.
- An `EvaluatorManifest` publishes SHA-256 digests of all test banks without disclosing test cases.
- Evaluates candidate callables blindly under budget limits.
- Emits cryptographically signed `EvaluationReceipt` (HMAC SHA-256) containing:
  - Overall holdout accuracy
  - Prior regression against baseline tasks
  - Evaluator manifest digest
  - Wall-clock execution duration
  - Binary pass/fail assertion

### 2.5 Exposure Ledger & Non-Contamination Verification (`exposure_ledger.py`)
- An append-only journal logs every sample, probe, query, or feedback item received by the research agent during training and search.
- Before promotion, the controller computes the intersection between the exposure journal and the sealed holdout inputs:
  $$\text{Contamination} = \left( \mathcal{E}_{\text{exposed}} \cap \mathcal{H}_{\text{holdout}} \neq \emptyset \right)$$
- If contamination is detected, promotion is rejected immediately (`ContaminationError`).

### 2.6 Acceptance Gate & Automated Rollback (`controller.py`)
- Promotion to `ACCEPTED` requires ALL criteria:
  1. Holdout accuracy gain over parent $\ge \text{min\_gain}$ (default: $0.15$).
  2. Max regression on prior tasks $\le \text{max\_regression}$ (default: $0.02$).
  3. Exposure ledger verified non-contaminated (`contamination == False`).
  4. Sandbox AST audit passed cleanly.
  5. Evaluation receipt signed and verified.
- **Automated Rollback:** If an accepted candidate triggers regression or safety invariant violations post-promotion, `controller.rollback()` restores the previous verified ancestor checkpoint and marks the regressed head as `ROLLED_BACK`.

---

## 3. Cryptographic Governance Invariants

All governance artifacts produced by `HostController.get_governance_report()` adhere to:
```json
{
  "schema": "ace.host_controller_governance.v1",
  "release_gate": "BLOCK_RELEASE",
  "scientific_status": "NOT_ASSESSED",
  "oaie_established": false
}
```

Independent verification is supported via CLI:
```bash
PYTHONPATH=code python3 -m ace_host_controller.verify --artifact <path/to/report.json[.gz]>
```

---

## 4. Empirical Test Suite Results

Test suite: `code/ace_host_controller/test_host_controller.py`  
Status: **13/13 unit tests PASS (0.004s)**  
Upstream Pins: **25/25 verified intact (`tools/verify_sources.py`)**
