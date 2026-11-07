# Forensic Baseline Audit: ACE V3 Scientific Validation

**Status:** BASELINE FORENSIC AUDIT REPORT  
**Date:** 2026-11-07  
**Repository:** `dianzherdiana25-hash/ACE`  
**Base Commit:** `3bfa3bf38ed3bd299fbffd82ff1e0a7a1f328a77` (`integration/ace-f13-f14-stack-20261107`)  
**Main Reference:** `80104ce50ecbcea21080bed8c0eabce88d47ccb5` (`origin/main`)  
**Associated PRs:**  
- PR #82: `engineering/ace-host-boundary-v2-20261107` (`3ab7371`)
- PR #83: `engineering/ace-sealed-evaluator-v2-20261107` (`c835baf`)
- PR #84: `research/ace-f13-f14-discovery-20261107` (`ceb4b90`)
**New V3 Integration Branch:** `integration/ace-v3-validation-20261107`  

---

## 1. Tri-State Status Separation

In accordance with scientific rigor, the project explicitly separates three operational and epistemic states:

| Status Axis | Current State | Operational Definition | Evidence Base |
| :--- | :---: | :--- | :--- |
| **`ENGINEERING_TESTED`** | **PASS** | Software components compile, pass unit tests, satisfy API contracts, execute without unhandled exceptions, and pass exact-HEAD CI matrix. | 257 tests passing across 22 suites on Python 3.11, 3.12, 3.13; GitHub Actions Run `42383587268` SUCCESS. |
| **`SCIENTIFICALLY_VALIDATED`** | **INCONCLUSIVE / NEGATIVE** | Hypothesized causal mechanisms (causal memory transfer, autonomous primitive discovery) demonstrate statistically significant, non-circular effect over matched controls on unexposed terminal holdouts. | F13 causal memory showed $0.00\%$ effect over controls ($0.5825 \pm 0.0000$ across all conditions). F14 G1 achieved $+20.21\%$ on D/E, but G2 achieved only $+0.31\%$ on F ($< 0.1500$) and was rightfully rejected by Host Controller. |
| **`OAIE_ESTABLISHED`** | **FALSE** | Open-Ended Autonomous Intelligence Evolution: self-directed expansion of representational power, task distribution, and recursive capability improvement without human intervention or ceiling saturation. | Under no interpretation has OAIE been established. The system is bounded by fixed grammar templates and discrete heuristic search. |

---

## 2. Forensic Discrepancy & Vulnerability Analysis

A comprehensive forensic audit of the integrated baseline identified five critical vulnerabilities and discrepancies that must be resolved in V3:

### Discrepancy A: Search Budget Non-Enforcement in Guided Mode
- **Location:** `code/ace_research_f14/discovery_engine.py:200-241` (`GrammarSearchEngine.search_candidates`)
- **Finding:** In `search_mode == "guided"`, the method executed `candidates = self.get_grammar_pool(...)`, which enumerates the entire static catalog (~60 AST candidates) regardless of the `budget` argument. Meanwhile, `search_mode == "random"` strictly sampled `budget` candidates.
- **Impact:** Guided search was granted an unfair, uncalibrated evaluation budget relative to random baselines. Candidate generation counts, evaluation calls, CPU time, and memory were untracked.

### Discrepancy B: Conflation of Template Search with Primitive Discovery
- **Location:** `code/ace_research_f14/discovery_engine.py:155-198` (`get_grammar_pool`)
- **Finding:** The grammar pool contains hand-crafted template operators (`DyckBalanceOp`, `SliceOp` + `CountOp`, `HalfSplitOp` + `RelationalEqPred`). The discovery engine merely samples combinations from this predefined human catalog.
- **Impact:** The report's criterion `zero_hardcoded_features` was declared `True` without structural inspection. True primitive discovery (synthesizing a new computational operation not representable in the initial primitive set) did not occur; it was template selection.

### Discrepancy C: Terminal Holdout Boundary Leakage via G1 Prior Baseline Calculation
- **Location:** `code/ace_research_f14/discovery_engine.py:368-370`
- **Finding:** Following G1 acceptance, `discovery_engine` computed `baseline_map` by directly iterating over `task_suites[tid].holdout_pool`!
- **Impact:** The search process had direct read access to terminal holdout labels and samples. Even though not used for direct parameter fitting, exposing `holdout_pool` to candidate generator code violates sealed evaluator integrity.

### Discrepancy D: Host Process Isolation and Environment Verification
- **Location:** `code/ace_host_controller/sandbox_gate.py:108-125`
- **Finding:** When `enforce_os_containment=False` was passed, untrusted candidate execution bypassed OS checks. In standard container environments, true user-namespace process sandboxing (`bwrap`/`nsjail`) is absent, relying primarily on AST filters.
- **Impact:** Malicious candidate ASTs bypassing AST filters could theoretically inspect local files. A fail-closed `BLOCKED_ENVIRONMENT` designation must be strictly enforced when evaluating unverified external code.

### Discrepancy E: Exposure of Task Families D, E, F
- **Location:** `code/ace_research_f14/terminal_tasks.py`
- **Finding:** Task families D (run lengths), E (prefix depth), and F (cross-stride modular parity) have now been repeatedly executed and analyzed during F14 development.
- **Impact:** Under strict preregistration standards, Families D, E, F are "contaminated by research exposure". V3 requires genuinely new, unexposed task families (Families G, H, I) under a dedicated pre-score protocol.

---

## 3. Mandatory Governance Locks
- `release_gate`: `BLOCK_RELEASE`
- `scientific_status`: `NOT_ASSESSED`
- `oaie_established`: `False`
- `marginal_cost`: `$0.00 / Rp0`
