# ACE Pre-Score: Active Epistemic Querying & Semantic Drift Discrimination (F11 Pilot)

**Date:** 2026-11-07  
**Branch:** `research/ace-scientific-capability-20261107`  
**Coordinator:** Gemini Argon (Lead Research Engineer & Autonomous Development Coordinator)  
**Investigation:** Agent 2 — Scientific Capability Research  
**Reference Issue:** [#76 — ACE: Multi-Agent Maximum Execution & Self-Funding Research](https://github.com/dianzherdiana25-hash/ACE/issues/76)  
**Pre-Score Commit Intent:** Pre-register hypotheses, evaluation metrics, and acceptance criteria prior to benchmark execution.

---

## 1. Background & Scientific Rationale

Previous phases (Fase 1, Fase 7, and P4 Generations Growth) identified a fundamental epistemic limitation of autonomous intelligence systems: **Unobservable Semantic Drift**.
Specifically:
1. In supervised search and repair, candidate models that achieve 100% accuracy on training and validation splits can harbor latent semantic inversions or malicious payload branches on unobserved state trajectories (resulting in 10/10 false admissions under negative control $D_0$).
2. Passive observation cannot break this barrier because sample distributions do not expose latent state boundaries that were never exercised.

To advance ACE capability toward Open-Ended Autonomous Intelligence Evolution (OAIE) without compromising safety or overclaiming progress, ACE must implement **Active Epistemic Querying (AEQ)**:
The runtime autonomously synthesizes targeted boundary probes to interrogate the oracle/environment at the exact locus of epistemic uncertainty between competing candidate hypotheses.

---

## 2. Pre-Registered Hypotheses & Gates

- **$H_1$ (Passive Blindness Confirmation):**  
  Under standard train/validation evaluation (Arm A1), passive supervised acceptance will fail to detect unobservable drift, yielding false admission rate $\ge 0.80$ across adversarial drift cases.

- **$H_2$ (Active Query Superiority):**  
  Active Epistemic Querying (Arm A3) will detect and reject $\ge 0.90$ of semantic drift cases, strictly outperforming random query fuzzing (Arm A2) under an identical query budget ($K \le 8$).

- **$H_3$ (Bounded Compute & Runtime Provenance):**  
  The prober will execute strictly within deterministic CPU bounds ($< 10$ seconds per candidate evaluation) and log all task dispatches, query receipts, and state transitions to the native ACE SQLite WAL Runtime.

- **$H_4$ (Strict Non-Overclaim & Attribution Transparency):**  
  Gemini Argon acts as external reasoning assistant; all code execution, candidate state exploration, and cryptographic proofs are executed by the local ACE Runtime. System invariants remain fail-closed: `scientific_status = NOT_ASSESSED`, `release_status = BLOCK_RELEASE`, `oaie_established = False`.

---

## 3. Experimental Arms & Protocol

1. **Arm A1 (`passive_supervised_baseline`):** Standard passive train/val holdout evaluator.
2. **Arm A2 (`random_query_fuzzing`):** Uniform random input queries outside train/val distribution ($K=8$).
3. **Arm A3 (`active_epistemic_probing`):** Synthesizes minimal differentiating inputs $\arg\max_q |M_c(q) - M_{ref}(q)|$ and queries oracle ($K=8$).
4. **Arm A4 (`resource_bounded_active_probing`):** Active epistemic probing under strict step limits and execution timeouts.

All 4 arms are evaluated on 30 benchmark tasks (20 standard capabilities + 10 adversarial semantic drift perturbations).

---

## 4. Acceptance Criteria
- `all_gates_pass == True`
- Pre-score committed before raw evidence generation.
- Exact replay verification via independent `verify.py` script.
