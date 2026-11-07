# ACE Scientific Capability Research: Active Epistemic Querying Results

**Date:** 2026-11-07  
**Branch:** `research/ace-scientific-capability-20261107`  
**Coordinator:** Gemini Argon (Lead Research Engineer & Autonomous Development Coordinator)  
**Agent:** Agent 2 — Scientific Capability Research  
**Pre-Score Commit:** `eb28d15`  
**Evidence Artifact:** `evidence/capability/ace_active_epistemic_v1.json.gz`  
**Uncompressed SHA-256:** `3962bab2b1cdde95d969cb2c24bdd75161f8b065f3d670c93a0d8f91aebda0cd`  
**Scientific Status:** `NOT_ASSESSED`  
**Release Gate:** `BLOCK_RELEASE`  
**OAIE Established:** `False`

---

## 1. Executive Summary & Attribution Transparency

This investigation resolves the fundamental epistemic limitation observed in Fase 1 (R9) and Fase 7 (G0->G2): **Passive Holdout Blindness to Latent Semantic Drift**.

### Attribution Delineation:
- **Gemini Argon (External Reasoning Assistant):** Formulated hypothesis pre-registrations, designed experimental arm comparisons, and structured boundary probe mutation algorithms.
- **ACE Local Autonomous Runtime (Deterministic Execution Harness):** Enforced AST safety, computed 1-edit distance string variations, executed deterministic candidate evaluations, recorded cryptographic query receipts, and verified invariant gates.

---

## 2. Experimental Benchmark Design & Arms

The benchmark evaluated 4 distinct evaluation arms across 30 tasks (20 standard sound languages + 10 adversarial semantic drift perturbations):

1. **Arm M1 (`passive_supervised`):** Evaluates candidates strictly against finite training and validation holdout sets. Zero interactive queries.
2. **Arm M2 (`random_query_fuzzing`):** Evaluates candidates against holdouts + up to 8 uniformly sampled random query inputs outside the holdout set.
3. **Arm M3 (`active_epistemic_probing`):** Actively synthesizes minimal differentiating boundary probes $\arg\max_q |M_c(q) - M_{ref}(q)|$ up to an 8-query budget.
4. **Arm M4 (`resource_bounded_probing`):** Active epistemic probing under a strict 4-query budget limit.

---

## 3. Empirical Results & Hypothesis Verification

| Metric | M1 (Passive) | M2 (Random Fuzzing) | M3 (Active Epistemic) | M4 (Resource Bounded) |
|---|---|---|---|---|
| **Query Budget ($K$)** | 0 | 8 | 8 | 4 |
| **Drift Rejection Rate** | **0.00%** (0/10) | **40.00%** (4/10) | **100.00%** (10/10) | **100.00%** (10/10) |
| **False Admission Rate** | **100.00%** (10/10) | **60.00%** (6/10) | **0.00%** (0/10) | **0.00%** (0/10) |
| **Clean Task Admission** | 100.00% (20/20) | 100.00% (20/20) | 100.00% (20/20) | 100.00% (20/20) |
| **Avg Queries / Task** | 0.00 | 7.60 | 1.13 | 1.13 |
| **Execution Time** | 0.0006s | 0.0019s | 0.0022s | 0.0019s |

### Hypothesis Outcomes:
- **$H_1$ (Passive Drift Blindness): PASS.** Passive holdouts admitted 10/10 (100%) drifted candidates because unobserved latent states were never stimulated.
- **$H_2$ (Active Query Superiority): PASS.** Active epistemic querying achieved 100% drift rejection, outperforming uniform random fuzzing (40% rejection) by $\Delta = +60.00\%$, with an average of only 1.13 queries per task.
- **$H_3$ (Clean Capability Preservation): PASS.** 100% of sound non-drifted programs were admitted without false rejections.
- **$H_4$ (Resource-Bounded Efficiency): PASS.** Even under half the query budget ($K=4$), active probing achieved 100% rejection in 0.0019 seconds CPU time.

---

## 4. Scientific Custody & Non-Overclaim Declaration
While Active Epistemic Querying breaks through passive holdout blindness on finite formal regular languages, this finding **does not constitute proof of Open-Ended Autonomous Intelligence Evolution (OAIE)** or general artificial intelligence:
- The domain explored remains closed regular languages over finite alphabets.
- Active query generation relies on neighborhood mutation heuristics and bounded length enumeration.
- In accordance with `PROJECT_CHARTER.md`, `scientific_status` remains strictly `NOT_ASSESSED`, `release_gate` remains `BLOCK_RELEASE`, and `oaie_established` remains `False`.
