# ACE Research R4 v5 — directional meta-adaptation (PUBLIC DEVELOPMENT, NEGATIVE)

**Scientific verdict: H5 REJECTED. Not an independently sealed evaluation. No OAIE/AGI claim or candidate promotion.**

## Immutable-before-score provenance

- Base branch `research/chat-r4-metalearning`, draft PR #39. No main, E1.4 or other teams changed.
- Pre-score GitHub commit `ce5bde20af27924c65a3718804a2e1b1d9bafc58`; v5 source, tests, protocol, frozen fitted parameters and bank SHA256 digests were committed and Git blob re-read before OOD scoring.
- Prescore JSON SHA256 (file bytes): `38e9b04c7b6336457bd0fe366d7a4c9a3fcabdd6f968fc8ea00907632414a760`.
- Prescore canonical JSON-data SHA256: `a4701fd854177fa166b6e028ed76c98afbd48e362d200c56b8d44033bb643e06`.
- Original full OOD results SHA256 (file bytes): `448cd4498b88e450c70e3d5f712473c961b63ee7cffa0b5bbd2be1897a61c8a9`.
- Full OOD results are preserved losslessly in `v5_results.json.gz.b64` (gzip mtime zero; base64). Do not hand-edit historical results.

## Protocol and actually executed commands

- Four fixed seeds: `1301, 1423, 1559, 1697`; per seed 66 source tasks, 32 validation tasks, 48 OOD tasks (12 in each of four novel composition families). 192 total OOD tasks; 32 binary domain points/task.
- Seven arms, matched *target* eight label purchases per task (1,536 labels/arm over all seeds). k=0,1,2,4,8. Full-domain balanced accuracy at k4 is primary; unqueried Brier is supplementary.
- `node --test v5_test.mjs v5_audit_test.mjs`: **16/16 PASS** on Node.js 22.16.0 local CPU.
- `node v5_study.mjs score v5_prescore.json v5_results.json` executed **only after prescore GitHub commit/readback**.
- `node v5_study.mjs verify v5_prescore.json v5_results.json`: **PASS semantic replay**.
- `node v5_audit.mjs v5_prescore.json v5_results.json`: **PASS**, independent aggregation and fail-closed tamper tests.

## Primary result

| Arm | Balanced k4 | Unqueried accuracy k4 | Unqueried Brier k4 |
|---|---:|---:|---:|
| joint | 56.935% | 52.381% | 0.30188 |
| reptile | 56.777% | 52.716% | 0.27798 |
| random_route | 56.282% | 52.958% | 0.25375 |
| nearest | 56.098% | 53.497% | 0.45754 |
| scratch | 55.397% | 52.623% | 0.25473 |
| learned_static_route | 55.397% | 52.623% | 0.25474 |
| learned_conditional_route | 55.397% | 52.623% | 0.25473 |

- Learned conditional `55.397%` versus strongest control joint `56.935%`: **−1.538 percentage points**. The prespecified gate required **+5 points**, at least 3/4 seed wins, logical target work ≤1.5× scratch, and Brier no worse than +0.01 over best control.
- Observed seed wins **0/4**; target compute proxy **1.596× scratch**, exceeding cap. Brier is **0.04715 lower** than joint, which alone cannot rescue the hypothesis.
- Pre-specified H5 is **REJECTED**, and no independent significance/superiority claim is made.

## Per-family falsification against strongest control at k=4

| OOD family | learned conditional | joint | learned − joint |
|---|---:|---:|---:|
| rotating_stencil | 53.205% | 54.790% | -1.585 pp |
| change_point_parity | 50.959% | 52.522% | -1.563 pp |
| cyclic_xor_intervals | 65.809% | 64.217% | +1.592 pp |
| piecewise_modulo | 51.616% | 56.212% | -4.596 pp |

## Mechanism diagnostics and honest limits

- Learned conditional routing coefficients are almost zero (typical magnitudes 1e-5 to 1e-4; the largest selected absolute coefficient across seeds is under 0.001). Learned **static** routing coefficients are also small (under 0.004). As fitted, routing does not produce a substantial direction change; conditional k4 accuracy matches scratch to displayed precision.
- A controlled unit test confirms the implementation **can** make non-diagonal updates when deliberately assigned nonzero off-diagonal weights. This is an engineering check, not evidence that optimization discovered useful routing.
- Fitting both static and conditional candidates used **1,152** objective evaluations, **2,433,024** source label-scoring exposures (reuses included), and **390,804,480** counted logical feature/route operations across four seeds. Comparisons match target-label budgets but **not all-in training compute**. End-to-end compute efficiency is therefore not established.
- There is no hidden, evaluator-custodied OOD bank, task-naturalism, large-seed confidence interval, real-world task transfer, full repository regression, or exact-HEAD GitHub Actions verification.
- Out-of-distribution family labels are generator-distinct and not fed to the target learner, but share compositional programming building blocks with training features. They are not proof of general open-world shift.
- Negative outcome and all failure cases preserved. Do not cherry-pick cyclic_xor_intervals or retune frozen v5 using this outcome.

## Reproduction

```bash
cd code/ace_research_metalearning
node --test v5_test.mjs v5_audit_test.mjs
node v5_study.mjs test
base64 -d v5_results.json.gz.b64 | gzip -dc > /tmp/r4v5_results.json
node v5_study.mjs verify v5_prescore.json /tmp/r4v5_results.json
node v5_audit.mjs v5_prescore.json /tmp/r4v5_results.json
```

Next gate: independent holdout and whole-repository exact-HEAD CI. Draft remains unmerged; no promotion.
