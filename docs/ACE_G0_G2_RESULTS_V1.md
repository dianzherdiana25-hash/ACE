# ACE Fase 7 — Bounded Recursive Self-Development (`G0 → G1 → G2`): Results & Verification

**Branch:** `research/ace-recursive-g0g2-20261107`
**Pre-registration commit:** `37990d9` (`docs/ACE_G0_G2_PRESCORE_V1.md` only)
**Evidence artifact:** `evidence/generations/ace_g0_g2_v1.json.gz`
**Uncompressed JSON SHA-256 (Python 3.12 & 3.13 byte-identical):** `2b749959258be9109c6cd60fc6e423d894ba3eb8f7a9b0f222d34634ad5ae4a0`
**Scientific status:** `NOT_ASSESSED` | **Release status:** `BLOCK_RELEASE` | **OAIE:** `NOT_ESTABLISHED`

---

## 1. Mandatory Three-Status Separation

| Evidence Flag | Value | Basis |
|---|---|---|
| `ACE_BASE_RUNTIME_EXECUTED` | **`TRUE`** | Live `ace_runtime` executed via `Autonomy` (`fase7_ace_runtime_lineage_seed`), verifying `LEARNED_STAGED` (`a41650f6...`) followed by `REUSE_VALIDATED` (`f6c6c77e...`, model `736436e5...`); `tools/verify_sources.py` `25/25` intact. |
| `NEW_CAPABILITY_INTEGRATED_AND_EXECUTED` | **`TRUE`** | `ImmutableCoreGuard`, `Autonomy` (`STAGED_FOR_REVIEW` candidate staging across 16 candidates in 4 batches), `ExperienceMemory`, `SelfReflection`, and `G0 → G1 → G2` lineage transitions executed end-to-end. |
| `SCIENTIFIC_CAPABILITY_VALIDATED` | **`TRUE` (Public Pre-Registered Benchmark `H1..H5` Pass; `NOT_ASSESSED` externally)** | Monotonic generational gains (`0.5111 → 0.6875 → 0.9625` on unseen `U_gen`), beating `4×` compute (`0.5111`), strong fixed library (`0.5000`), random meta-mutation (`0.5111`), and fresh R1 (`0.5000`) with zero `L_base` regression (`1.0000`) and zero `N_ood` false admissions (`0`). |
| `PASSIVE_SEMANTIC_DRIFT_DETECTABLE` | **`FALSE`** | Under hidden terminal-only label inversion (`D_drift`), `G2` commits `10/10` false admissions (`mean_acc = 0.0000`), confirming passive unidentifiability without terminal probes. |

---

## 2. Generational Lineage Transitions (`G0 → G1 → G2`)

1. **`G0 → G1` (`M1` Strided & 2-Gram Block Discovery)**:
   - `G0` scored `0.5000` on `M1_DEV` and `0.5000` on `M1_VAL`. Diagnostic inspection detected flat-counter anagram collisions separable by strided index parities, logged into `ExperienceMemory` via `SelfReflection` (`REPRESENTATION_GAP_STRIDED_PARITY`).
   - Eight typed `ace.meta_mechanism.v1` candidates were validated and staged in `Autonomy` (`STAGED_FOR_REVIEW`, zero auto-deploy).
   - Promoted **`G1`** (`enable_strided_features = True`, `stride_moduli = [2, 3]`) achieved `1.0000` on `M1_VAL` (`+0.5000 >= 0.15`) with `0.0000` regression on `L_base`.
2. **`G1 → G2` (`M2` Split-Frame Lifting, MDL Ranking & Probe-Agreement Gating)**:
   - Starting strictly from `G1` (`parent_gen = "G1"`), `G1` scored `0.5000` on `M2_VAL` while retaining `1.0000` on `M1_VAL`. Diagnostic inspection isolated split-half invariance collisions (`REPRESENTATION_GAP_SPLIT_FRAME_AND_AMBIGUITY`).
   - Eight second-generation candidates were staged in `Autonomy` (`STAGED_FOR_REVIEW`); candidates that dropped `G1`'s strided inheritance failed the `M1_VAL` non-regression gate (`max_prior_regression <= 0.02`) and were rejected automatically.
   - Promoted **`G2`** (`enable_strided_features = True`, `stride_moduli = [2, 3]`, `enable_split_frame_lifting = True`, `enable_mdl_ranking = True`, `enable_probe_agreement_gate = True`) achieved `1.0000` on `M2_VAL` and `1.0000` on `M1_VAL`.

---

## 3. Quantitative Target Benchmark Across All 7 Arms (`75` Units, `B = 32`)

| Arm | `U_gen` Mean Acc (`40` units) | `U_gen` Admit Rate | `L_base` Mean Acc (`15` units) | `N_ood` False Admissions (`10` units) | Mean Evals Used (`U_gen`) | Mean Symbol Reads (`U_gen`) |
|---|---:|---:|---:|---:|---:|---:|
| **`G2` (2nd Generation)** | **`0.9625`** | `0.9250` | **`1.0000`** | **`0`** | `128.35` | `20,610.0` |
| **`G1` (1st Generation)** | **`0.6875`** | `0.3750` | **`1.0000`** | **`0`** | `109.35` | `15,938.4` |
| **`G0` (Initial Generation)** | `0.5111` | `0.0250` | `1.0000` | `0` | `67.60` | `11,816.4` |
| `B_extra_compute` (`G0` @ `4×` `K=1024`) | `0.5111` | `0.0250` | `1.0000` | `0` | `67.60` | `11,816.4` |
| `B_random_mut` (2-Step Random Meta-Mut) | `0.5111` | `0.0250` | `1.0000` | `0` | `77.78` | `13,626.7` |
| `B_fixed` (`120+` Hand Library @ `K=256`) | `0.5000` | `0.0000` | `0.7333` | `0` | `252.88` | `35,724.0` |
| `B_fresh` (Fresh R1 DFA Inference) | `0.5000` | `0.0000` | `0.5474` | `0` | `32.92` | `3,420.5` |

---

## 4. Immutable Core, Anti-Goodhart & Honest Limitations

- **Immutable Lock Integrity (`H5` PASS)**: `ImmutableCoreGuard` verified all `7` SHA-256 file locks (`evaluator.py` `66e87d6a...`, `policy.py`, `verifier.py`, `core.py`, `escrow.py`, `engine.py`, `UPSTREAM_SOURCES.json`) plus `PROMOTION_POLICY` (`e2440ae6...`) before and after every generation; AST import isolation confirmed zero `evaluator` imports in all `5` fit-side modules.
- **Scope Boundary**: Evolution occurred strictly within the typed `ace.meta_mechanism.v1` combinator/projection parameter space rather than unconstrained open-ended Python self-rewriting; therefore `oaie_established = False` and `release_status = "BLOCK_RELEASE"`.
