# ACE Research R4 v4: gradient-conditioned learning-to-learn — negative result

**Scientific conclusion: H4 REJECTED.** This is a single author-visible public synthetic development study, **NOT** independent confirmation, not OAIE, and not evidence of successful open-world learning to learn. Previous v1/v2/v3 hypotheses remain REJECTED. No deployment or merge.

## Immutable experiment provenance

- R4 branch `research/chat-r4-metalearning`, base v3 checkpoint `a1a65fe2c3119c0f186c4abfc3d348e8a8afa4c5`.
- **Pre-OOD commit:** `d0ec6548d3b06a856b8a88a87bdb28af251aff8d` contains byte-matched `v4_study.mjs`, `v4_test.mjs`, `V4_PROTOCOL.md`, and `v4_prescore.json` (4/4 local Git blob IDs match GitHub readback). Source was **not changed after OOD scoring**.
- Frozen JSON SHA256 (raw file bytes): `76f5d73b5f444b39e318044597fdf4aa5c6dffcee1980e555d99b88b5b161286`; canonical parsed-object SHA256: `150862984d9345c9f6bfa73485b61c8e594947ce488e3d5097be496d1ed2df7c`.
- Frozen four seeds `907,1009,1103,1217`; per seed 66 train, 32 validation, 48 OOD tasks. Four OOD families: prime-affine, palindromic-bands, bitcount-gate and modular-intersection. **192 OOD tasks**. All seven target methods acquire the same eight seed-only predetermined labels/task, except nearest has no gradient steps. Six gradient-based arms each take the same eight label purchases and eight target gradient steps/task.
- Committed full raw OOD results as `v4_results.json.gz.b64` losslessly compressed with gzip; raw JSON SHA256 `069a8e387373a622bf1782c362b00f3deb592507e57a37d652c13ffa55b02475`, gzip base64 text SHA256 `145d84435c710bc9e45d8d66d36061ebbcf2d564327c16f210087903fbbb2405`. The archive includes per-seed and per-family scores, per-stage metrics and logical work.

## Primary precommitted result: full-domain balanced accuracy after k=4 acquired labels

| Arm | Balanced accuracy | Unqueried accuracy | Unqueried Brier |
| --- | ---: | ---: | ---: |
| Scratch SGD | 55.166% | 56.771% | 0.2573 |
| Reptile | 55.731% | 56.641% | 0.2869 |
| Nearest neighbor | 54.365% | 55.785% | 0.4342 |
| Validation-selected fixed diagonal | 55.298% | 56.603% | 0.2790 |
| **Ordinary joint pretraining + finetuning** | **55.915%** | 53.664% | 0.3351 |
| Untrained gradient-conditioned rule | 55.166% | 56.771% | 0.2658 |
| **R4 learned gradient-conditioned rule** | **55.175%** | 56.771% | 0.2577 |

**Meta minus strongest control:** −0.740465 percentage points, versus precommitted criterion **+5 pp**. Of four paired seeds, R4 learned method beat joint finetuning at k4 in **1/4** (seed 907), losing in seeds 1009, 1103, 1217. H4 failed the accuracy and 3/4 seed-win gates. OOD results were not used to reselect parameters.

### Paired per-seed difference: learned minus joint control

| Seed | Learned | Joint | Difference (percentage points) |
| --- | ---: | ---: | ---: |
| 907 | 55.829% | 55.594% | +0.235 |
| 1009 | 53.220% | 53.773% | −0.553 |
| 1103 | 55.710% | 56.456% | −0.746 |
| 1217 | 55.940% | 57.838% | −1.898 |

### By OOD family: learned vs joint

| Family | Learned | Joint |
| --- | ---: | ---: |
| prime-affine | 54.042% | 52.999% |
| palindromic-bands | 59.015% | 59.998% |
| bitcount-gate | 52.736% | 55.258% |
| modular-intersection | 54.906% | 55.406% |

The advantage on prime-affine alone is **postscore subgroup evidence**, insufficient to rescue H4. Generalization losses were largest on bitcount-gate.

## Compute, budget, and limitations

- Target purchases: 192 tasks × 8 labels = **1,536 label purchases per arm** (including nearest); all non-nearest arms perform **1,536 target gradient updates**. The learned method adds 184,320 logical conditioner operations to the 618,240 feature multiplications charged to scratch and learned methods; reported target-work ratio = **1.2981× scratch**, under the prespecified 1.40× cap. This **does not** imply equivalent CPU, equal overhead or equal total training cost.
- Meta-fitting across seeds used **864 complete source-loss evaluations**, **1,824,768 nominal source-example scoring exposures** (labels reused), and **183,617,280 tracked source feature multiplications** for learned candidate fitting, plus source training for Reptile/joint controls and validation scoring. These are *logical* costs, not independent measurements of full CPU/memory/I/O. Original unique source labels = **8,448** across four distinct source banks; validation full-label exposure = 4,096.
- Learned beta coefficients were small for all four seeds (roughly −0.008 to +0.052); this nearly-identity update is a **failure mode**, not evidence of a novel effective gradient optimizer. Only researcher-specified three-group scaling rule is learned. Meta-parameters did change from zero, but not enough to improve transfer.
- H4's Brier noninferiority vs the strongest **balanced-accuracy** control passed because the learned model Brier is 0.2577 vs joint 0.3351; this is **not** superiority to the scratch Brier of 0.2573. Passing a secondary gate does not change the H4 rejection.
- All task generators are synthetic, author-visible; no independent evaluator custody, no sealed future tasks, no real-world adaptation, no statistical superiority claim, no completed exact GitHub Actions CI or historical ACE regression. Features and primitive update rule were supplied manually. Full-domain balanced accuracy credits already purchased target labels as known; interpret alongside unqueried metrics.

## Verification actually executed

Node.js 22.16.0 in local workspace using byte-exact GitHub source snapshots for prerequisites. `node --test v4_test.mjs v4_audit_test.mjs` **11/11 PASS**. `node v4_study.mjs test` PASS (6 guardrail groups). `node v4_study.mjs score v4_prescore.json v4_results.json` and `node v4_study.mjs verify v4_prescore.json v4_results.json` PASS. `node v4_audit.mjs v4_prescore.json v4_results.json.gz.b64` PASS, including independent arithmetic checks on family macro averages, per-seed aggregates, label limits, gradient steps, deterministic replay and tampered primary decision refusal. Audit is same-author code, not an independent scientific evaluator.

**Decision:** KEEP draft PR, DO NOT merge/promo. Next research should test gradient-direction transformations learned with held-out-source meta-objectives, held-out-domain variation and cost-aware competitor controls; no modification of H4 based on postscore evidence. Potential pilot v5 requires a new prescore protocol and genuinely new family bank.
