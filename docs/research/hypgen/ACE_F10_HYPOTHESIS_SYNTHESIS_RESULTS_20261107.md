# ACE Fase 10 (F10) — Autonomous Structural Hypothesis Synthesis Empirical Results (2026-11-07)

**Execution Lane:** `research/ace-f10-hypothesis-synthesis-20261107` (Issue #70 Priority C / P2)  
**Parent HEAD SHA:** `a8efd9bfc9a9633bcd1a8b815bc7d7f725cffeb7`  
**Preregistration Protocol:** `docs/research/hypgen/ACE_F10_HYPOTHESIS_SYNTHESIS_PRESCORE_20261107.md`  
**Evidence Artifact:** `evidence/hypgen/f10_hypothesis_synthesis_v1.json.gz`  
**Scientific Status:** `SCIENTIFIC_NOT_ASSESSED` | **Release Gate:** `BLOCK_RELEASE`  
**OAIE Status:** `OAIE_NOT_ESTABLISHED`  

---

## 1. Summary of Comparative Benchmark Arms

| Arm ID | Generator | Hypotheses Generated | Falsifiable Rate | Evaluator Calls | Mean Task Solve Rate | F10 Threshold Decision |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Arm A** | `M1_fixed_catalog` | 2 | 100% | 31 | 0.0000 | Baseline |
| **Arm B** | `M2_random_grammar` | 4 | 100% | 32 | 0.7500 | Matched Control |
| **Arm C** | `M3_novelty_only` | 4 | 100% | 32 | 0.7500 | Matched Control |
| **Arm D** | `M4_extra_compute` | 2 | 100% | 31 | 0.0000 | Extra Compute |
| **Arm E** | `M5_f10_structural` | 4 | 100% | 39 | 0.0000 | **THRESHOLD_REJECTED** |

---

## 2. Empirical Findings & Negative Outcome Transparency

1. **Gate 1 (Syntactic & Falsification Integrity):** **PASSED**  
   - 100% of generated hypotheses in all arms possess typed mathematical falsification criteria.
   - 100% of goal specs successfully dispatched to and executed by the real operational `ace_runtime.engine.Runtime`.

2. **Gate 2 (Empirical Value vs Matched Controls):** **FALSIFIED / THRESHOLD_REJECTED**  
   - Precommitted threshold required $\Delta_{\text{vs\_random}} \ge +0.05$ and $\Delta_{\text{vs\_novelty}} \ge +0.05$.
   - Actual observed performance: $\Delta_{\text{vs\_random}} = -0.7500$ and $\Delta_{\text{vs\_novelty}} = -0.7500$.
   - **Reason for Failure**: Grounded structural synthesis correctly targeted real, challenging capability gaps (such as non-regular mirror palindromes and unobservable semantic drift), where bounded $\le 63$-node state merging honestly failed or abstained (`NO_VALIDATED_MODEL`). Conversely, random sampling drew nominal trivial string tasks that easily passed validation.
   - S1 finding (`PR #34`) corroborated: Unconstrained or naive hypothesis discovery without domain-specific representation expansion cannot outperform matched controls without genuine representation primitives.

3. **Gate 3 (Negative Drift Honesty):** **PASSED**  
   - Arm E correctly abstained on unobservable semantic drift without false claims of generalization.

4. **Gate 4 (Real Runtime Execution Integration):** **PASSED**  
   - Real SQLite WAL runtime events, task IDs, and SHA-256 receipts generated and archived in evidence.
