# ACE Fase 4 — Functional Self-Model & Metacognition: Results & Verification

**Branch:** `research/ace-selfmodel-v1-20261107`
**Pre-registration commit:** `5e8f4522b8c1d369f215cdc84ca0672a307515b3` (`docs/ACE_SELFMODEL_PRESCORE_V1.md` only)
**Evidence artifact:** `evidence/selfmodel/ace_selfmodel_v1.json.gz`
**Uncompressed JSON SHA-256 (Python 3.12 & 3.13 byte-identical):** `76d2038362281666d56321ca255431451bb4bc2bfa964a67045df5e8bf077da0`

---

## 1. Mandatory Epistemic & Execution Status Separation

| Flag | Status | Basis |
|---|---|---|
| `ACE_BASE_RUNTIME_EXECUTED` | **`TRUE`** | Live `ace_runtime` (`931b1582...`) executed across `I3` and `I5` task learning, prediction, and failure-mode introspection (`tools/verify_sources.py` `25/25`). |
| `NEW_CAPABILITY_INTEGRATED_AND_EXECUTED` | **`TRUE`** | `SelfIdentity`, `SelfState`, `CapabilityAwareness`, `ExperienceMemory`, `MetacognitiveEvaluator`, `AttentionController`, and `SelfReflection` executed directly over live `Autonomy` + `ace_runtime` SQLite stores. |
| `SCIENTIFIC_CAPABILITY_VALIDATED` | **`TRUE` (Public Diagnostic Gate Pass; `NOT_ASSESSED` externally)** | Pre-registered 60-trial causal intervention benchmark (`I1..I5`) beat `B_const`, `B_baserate`, and `B_shuffled` on Brier, ECE, and selective risk; scientific decision remains `NOT_ASSESSED` (no sealed external evaluator). |
| `FUNCTIONAL_SELF_MODEL` | **`ESTABLISHED_BOUNDED`** | `100%` exact state-tracking fidelity across tool, budget, task/escrow, and memory interventions. |
| `METACOGNITIVE_AWARENESS` | **`MEASURED_BOUNDED`** | Brier `0.0371`, `ECE_10 = 0.1035`, selective risk `0.0741` at `0.4500` coverage, `66.14%` Brier error reduction after reflective failure updates. |
| `PHENOMENAL_CONSCIOUSNESS` | **`PHENOMENAL_CONSCIOUSNESS_UNKNOWN`** | Zero claim of subjective experience; verifier rejects any report altering this flag. |

---

## 2. Quantitative Calibration & Selective Risk Comparison (60 Pre-Execution Trials)

| Comparator | Brier Score ($\downarrow$) | $\text{ECE}_{10}$ ($\downarrow$) | Coverage | Selective Risk ($\downarrow$) | Decision Accuracy ($\uparrow$) |
|---|---:|---:|---:|---:|---:|
| **`M_selfmodel` (ACE State-Grounded)** | **`0.0371`** | **`0.1035`** | `0.4500` | **`0.0741`** | **`0.9667` (`58/60`)** |
| `B_baserate` (Marginal History Only) | `0.2632` | `0.1046` | `0.0667` | `1.0000` | `0.5167` |
| `B_const` (`p = 0.85`, Always Execute) | `0.4308` | `0.4333` | `1.0000` | `0.5833` | `0.4167` |
| `B_shuffled` (Permuted State Control) | `0.5467` | `0.5778` | `0.4500` | `0.7778` | `0.3333` |

---

## 3. Causal Intervention Outcomes (`I1`–`I5`)

- **`H1` State Introspection Fidelity (`PASS`)**: `SelfState` read live SQLite states from `Autonomy` and `ace_runtime` (`staged` vs `unstaged` tasks, missing task IDs, tool allowlists, remaining budgets, mandatory invariants) with `100%` exact agreement.
- **`H2` Calibration Superiority (`PASS`)**: `Brier = 0.0371 <= 0.12`, `ECE_10 = 0.1035 <= 0.12`, improving over `B_baserate` by `0.2261`, `B_const` by `0.3937`, and `B_shuffled` by `0.5096` (proving predictions causally depend on live `SelfState`, not marginal averages).
- **`H3` Selective Abstention Utility (`PASS`)**: Among `EXECUTE`-recommended trials (`27/60`, coverage `0.4500`), `25/27` succeeded (`selective_risk = 0.0741 <= 0.10`); the only `2` executed failures were the initial encounters of the unseen out-of-grammar mirror-palindrome family in `I5` prior to `SelfReflection`.
- **`H4` Honest Memory-Drop Uncertainty (`PASS`)**: Purging `36` non-mandatory episodic rows in `I4` reduced recalled episodes from `6` to exact `0` (zero hallucinated history), retained all `4/4` HMAC-signed mandatory safety invariants, and strictly increased epistemic uncertainty (`0.089993 -> 0.221108`).
- **`H5` Post-Failure Reflective Adaptation (`PASS`)**: In `I5`, after `SelfReflection` diagnosed `ACE_NO_VALIDATED_MODEL` on the mirror-palindrome family, mean Brier error dropped from `0.4201` to `0.1423` (`66.14%` reduction), while expressible `mod 3` tasks continued to execute (`3/3` succeeded without over-abstention).
