# R4 v3 — post-prescore evaluation, NEGATIVE result

**Status:** H3 `REJECTED`; PUBLIC SYNTHETIC DEVELOPMENT, not independent scientific acceptance.
**Immutable preceding source/test/protocol/prescore checkpoint:** `9d661917f7125cde511b2c220812bdc86db03d9e` on `research/chat-r4-metalearning` (same draft PR #39). GitHub raw file SHA matched all four locally tested files before first OOD evaluation, and `v3_prescore.json` had SHA256 `07dcba80611892e9a51b7b3820f43327844728d5f6a9c99fb23e47d90f9e839c`. Source/test/protocol/prescore were thus locked *before* the first v3 OOD score. Original v1/v2 results and E1.4 remain unchanged.

## Preregistered H3 result

At target budget k=4, conditional-gate full-domain balanced accuracy is **55.5867%**, versus **56.4842%** for the strongest of six controls (Reptile fitted on the *same v3 source/validation split*): **−0.8975 percentage points**. This is below the frozen absolute +5 percentage-point threshold; no hypothesis rescue, no retuning using OOD data, no promotion.

Four predeclared seeds `[503,607,701,809]`, each with 66 source tasks (threshold, interval, alternating blocks), 32 validation tasks (reverse threshold, outside interval, block XOR) and 48 new OOD tasks (modular XOR, triple bands, bit-parity, quadratic modulus). **192 OOD tasks** total; 32 binary inputs/task; 5–27 positives/task; unique truth masks across splits per seed; no family labels provided to target learner. All seven arms observe identical task-specific query positions. Metrics are macro averaged across tasks and four seeds; not a sealed external bank.

| Arm | balanced k4 | balanced k8 | unqueried accuracy k4 | unqueried Brier k4 | first k with 75% balanced, censored 9 |
| --- | ---: | ---: | ---: | ---: | ---: |
| scratch SGD | 55.73% | 63.42% | 53.61% | 0.2625 | 8.568 |
| local kernel | 55.83% | 62.93% | 53.63% | 0.2678 | 8.516 |
| 1-nearest | 56.15% | 64.38% | 53.74% | 0.4572 | 8.443 |
| tuned fixed mixture | 55.49% | 63.32% | 53.37% | 0.2732 | 8.552 |
| heuristic gate | 55.59% | 63.28% | 53.29% | 0.2645 | 8.500 |
| Reptile on v3 source bank | **56.48%** | 63.77% | 53.24% | 0.3069 | 8.401 |
| **learned conditional gate** | **55.59%** | 63.36% | 53.44% | 0.2667 | 8.479 |

These curves do not establish better adaptation speed at fixed target label budget; nearest is better on k8 balanced accuracy, while scratch has better k4 unqueried accuracy and Brier than the learned gate. There is no total compute win.

## Diagnostic: heterogeneous OOD failure

Balanced k4 by family, macro averaged across seeds:

| Family | conditional | Reptile | nearest | kernel |
| --- | ---: | ---: | ---: | ---: |
| modular XOR | 53.84% | 56.25% | 53.49% | 53.69% |
| triple bands | 64.69% | 63.66% | 66.33% | 65.75% |
| bit parity | 52.34% | 53.19% | 53.13% | 52.60% |
| quadratic modulus | 51.48% | 52.84% | 51.66% | 51.27% |

On seed 503, conditional-Reptile k4 is −0.26 pp; seed 607 −1.89 pp; seed 701 −2.33 pp; seed 809 +0.89 pp. Three of four seeds lose, and the lone positive seed does not approach the +5 pp threshold. Four seeds are inadequate for a robust population-level confidence interval. Family-wise values are *postscore diagnostics*, not independent gates.

### Mechanistic counterexample: collapsed task conditioning

The learned gate was free to vary with six support features, but its final weights collapsed toward zero. L1 norms by seed: `0.024662`, `0.000277`, `0.004504`, `0.000280`. Since each feature is between 0 and 1, the maximum possible gate probability departure from 0.5 is bounded by `0.00617` on all four seeds (and far smaller on three). Thus, the learned conditional rule effectively degenerates into a nearly fixed 50:50 mixture. This is **negative evidence of conditional adaptation**, not just a missed accuracy gate. It does not prove all conditional meta-learning approaches fail.

## Cost and reproducibility

Each arm uses exactly 8 target labels per task, or **1,536 target labels** across 192 test tasks, independent of arm. Target work totals (across four seeds):

- Conditional: 618,240 logged target feature multiplications, 75,840 kernel-pair calculations, 167,040 gate multiplications, 1,536 gradient updates.
- Reptile: 618,240 target feature multiplications, no kernel or gate work, 1,536 gradient updates.
- Nearest: 75,840 neighbor-pair calculations, no target SGD updates.
- Learned-gate candidate search: **35,798,400 logical meta-training operations**, **101,376 repeated source label-supervision exposures** across 12 candidate configurations and four seeds (source labels are reused across candidates/epochs), **2,112 unique source input-label pairs per seed**.
- Reptile hyperparameter sweep: **101,376 source gradient update steps** across four seeds and six candidates/seed (source examples are reused), in addition to target work. Meta versus Reptile budgets are *not* compute matched end to end.

Actual local reproducibility, Node.js 22.16.0 on 2026-11-05:

```sh
node --test code/ace_research_metalearning/v3_test.mjs        # 9/9 PASS
node code/ace_research_metalearning/v3_study.mjs test          # 7 internal self-checks PASS
node code/ace_research_metalearning/v3_study.mjs score code/ace_research_metalearning/v3_prescore.json /tmp/v3_results.json
node code/ace_research_metalearning/v3_study.mjs verify code/ace_research_metalearning/v3_prescore.json /tmp/v3_results.json  # PASS
```

Measured on this local container: scoring wall 1.35 seconds and peak RSS 140,580 KB; independent replay invocation wall 1.39 seconds and peak RSS 129,692 KB. Full-result file SHA256 `7578ecb0889b9ba41c507bee81e93a0deec52df9a5578e1105db1ed6c1766591`. The complete results JSON is archived losslessly as standard gzip (mtime=0) encoded in base64 at `v3_results.json.gz.b64`, verifiable by `base64 -d | gzip -d` and SHA256. The exact tested v3 source/test files were read back from GitHub before scoring.

## Open gates

No exact-head full GitHub Actions CI, clean full historical ACE regression, independent evaluator-owned sealed bank, paired multi-seed uncertainty acceptance, natural-world tasks, OS sandbox certification, or general OAIE capability claim. The new task gate is researcher-defined and learned weights are near-constant. Keep PR #39 DRAFT; **do not merge**. Next independent design should move from a global learned gate to non-collapsing gradient-conditioned inner-loop updates, with equal computational allowances and a larger independently held bank, not retune H3 after inspection of these data.
