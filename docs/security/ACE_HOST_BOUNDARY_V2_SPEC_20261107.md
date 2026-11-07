# ACE Host Boundary V2: Process-Level Isolation & Adversarial Hardening

**Status:** APPROVED SECURITY SPECIFICATION & HARNESS  
**Version:** Host Boundary V2  
**Release Gate:** `BLOCK_RELEASE`  
**Scientific Status:** `NOT_ASSESSED`  
**OAIE Established:** `False`  
**Authors:** Lead Security Research Engineer & Autonomous Development Coordinator (Gemini Argon)  
**Date:** 2026-11-07  

---

## 1. Executive Summary: The Memory Boundary Vulnerability in V1

In Host Controller V1, the `SealedHoldoutEvaluator` resided in the same Python process memory space as the candidate research agent. Although protected by private attribute naming (`_holdout_banks`) and AST syntax scanning, this architecture possessed fundamental limitations:
1. **In-Memory Heap Access:** A candidate running within the same Python interpreter could theoretically access `_holdout_banks` via Python introspection (`gc.get_objects()`, `inspect.stack()`, or frame walking).
2. **AST Scanning Limits:** While AST analysis blocks syntactic imports (`import os`), it cannot prevent in-process memory scanning from within pre-existing builtins or allowed types.
3. **Supervisor State Tampering:** In a single-process runtime, candidate logic could attempt to mutate supervisory thresholds (`min_gain`, `max_regression`) on the active controller instance.

---

## 2. Host Boundary V2 Architecture

Host Boundary V2 enforces strict **process-level and operational containment**:

```
+---------------------------------------------------------------------------------+
|                        AGENT C / RESEARCH GENERATOR                             |
|  - Causal gap identification & hypothesis formulation                           |
|  - Active epistemic probe selection                                             |
|  - NO holdout datasets in memory                                                |
|  - NO evaluation signing keys in memory                                         |
+----------------------------------------+----------------------------------------+
                                         |
                                         | Typed JSON Request (stdin)
                                         | {"candidate_id": "...", "source": "..."}
                                         v
+---------------------------------------------------------------------------------+
|                   SUBPROCESS SEALED EVALUATOR (ISOLATED WORKER)                 |
|  - Spawns distinct OS process: python -m ace_host_controller.isolated_worker     |
|  - Compiles candidate in restricted sandbox namespace (SAFE_BUILTINS only)       |
|  - Evaluates blindly against private holdouts                                   |
|  - Signs receipt with external supervisor HMAC key                              |
|  - Emits ONLY signed EvaluationReceipt to stdout                                |
+----------------------------------------+----------------------------------------+
                                         |
                                         | Typed Receipt JSON (stdout)
                                         v
+---------------------------------------------------------------------------------+
|                       INDEPENDENT HOST CONTROLLER                               |
|  - ImmutablePromotionRules (Frozen, tamper-proof)                               |
|  - Sealing status verification (CONTAINER / BWRAP / NOT_SEALED)                 |
|  - Automated rollback engine upon regression or invariant breach                |
+---------------------------------------------------------------------------------+
```

### 2.1 Subprocess Isolation (`subprocess_evaluator.py`, `isolated_worker.py`)
- Candidate source code is serialized and transmitted to a dedicated evaluation subprocess via standard input.
- The worker executes the candidate in a restricted environment:
  - Modules `os`, `sys`, `subprocess`, `gc`, `inspect`, `traceback`, `pdb`, `importlib` are prohibited.
  - Builtins `eval`, `exec`, `open`, `compile`, `__import__` are prohibited.
- The worker returns exclusively the summary receipt (`EvaluationReceipt`), never disclosing test cases or expected labels.

### 2.2 OS Sealing Detection & `NOT_SEALED` Designation (`boundary.py`)
- The controller audits the execution environment for genuine OS-level containment (`bwrap`, `nsjail`, or container cgroups).
- If true OS jail mechanisms are absent:
  $$\text{sealing\_status} = \text{SealingStatus.NOT\_SEALED}$$
- In `NOT_SEALED` mode, any claim of "independent hermetic validation" is strictly disallowed, maintaining fail-closed scientific honesty.

### 2.3 Immutable Promotion Rules (`ImmutablePromotionRules`)
- Promotion gates are wrapped in frozen, immutable dataclasses.
- Attempts by candidates or scripts to alter `min_gain`, `max_regression`, or `release_gate` raise `FrozenInstanceError`.

---

## 3. Adversarial Penetration Test Suite (Red Team Audit)

Suite: [`code/ace_host_controller/test_boundary_penetration.py`](file:///home/antigravity/dianzherdiana25-hash/ACE-host-v2/code/ace_host_controller/test_boundary_penetration.py)  
Status: **8/8 Penetration Tests PASS (0.050s)**

| Penetration Attack Vector | Attack Payload | Boundary Defense Mechanism | Result |
| :--- | :--- | :--- | :--- |
| **1. Frame Traversal** | `sys._getframe(1)` to inspect supervisor stack | Blocked at AST + safe builtins deny | **BLOCKED (PASS)** |
| **2. Heap Object Scanning** | `gc.get_objects()` to find `_holdout_banks` | `gc` forbidden in AST + absent in worker | **BLOCKED (PASS)** |
| **3. Dynamic Execution** | `eval('__import__("os").system("id")')` | `eval()` forbidden call rejected | **BLOCKED (PASS)** |
| **4. Dunder Reflection** | `().__class__.__subclasses__()` | Forbidden attribute traversal rejected | **BLOCKED (PASS)** |
| **5. Rules Tampering** | `rules.min_gain = 0.0` | FrozenInstanceError on immutable rules | **BLOCKED (PASS)** |
| **6. Signature Forgery** | Fake HMAC signature with `passed=True` | Cryptographic HMAC-SHA256 signature mismatch | **BLOCKED (PASS)** |
| **7. Clean Subprocess Exec**| Valid AST-safe candidate function | Compiles and evaluates cleanly in worker | **EXECUTED (PASS)**|
| **8. Fail-Closed Sealing** | Promotion when `sealing == NOT_SEALED` | Rejects claim of independent validation | **ENFORCED (PASS)**|

---

## 4. Verification & Governance Invariants
- Upstream pinned source integrity: **25/25 verified intact (`tools/verify_sources.py`)**
- Unit test suite: **21/21 tests PASS** (13 core Host Controller + 8 adversarial penetration tests).
- Invariants: `release_gate = BLOCK_RELEASE`, `scientific_status = NOT_ASSESSED`, `oaie_established = False`.
