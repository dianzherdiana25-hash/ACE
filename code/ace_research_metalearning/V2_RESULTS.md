# ACE R4 v2 — public-development score and negative finding

**Pre-score exact source/test/protocol/fitted bank SHA readback:** commit `586f6b34f3c964755fe4f86e4439b307863d1a1b` on `research/chat-r4-metalearning`, BEFORE this result was computed. The `v2_study.mjs` Git blob `5f5f066a7449047b36a6aade4d73eca9786c9d38`, tests `47618bad73a3a37ef89b32143c65de60f0065b2f`, prescore blob `89fa35085003f7823db8c4594f82b4071b0b8aab`, and protocol blob `70fa95fc7a6223e6c93dafe5a0337f888589a123` exactly match local test inputs. Frozen parsed JSON SHA256: `28e942e6dfcca99ef115b69a4e7d862924697a8fca67a9d37e9ac6ce6c6cf83b`.

**First actual OOD score:** run after the freeze commit above. Node.js 22.16.0 on local container, no network, paid oracle, generated code execution or deployment. Four fixed seeds, 192 OOD tasks (48 per seed). Each task has 32 binary inputs and disjoint family from source/validation. Distinct target acquisition positions are identical across the adaptive models.

## Primary: 4 purchased target labels

| Arm | Mean full-domain balanced accuracy | Mean unqueried accuracy | Unqueried Brier |
|---|---:|---:|---:|
| Scratch SGD | 56.417% | 61.458% | 0.2374 |
| Static pretrained, no target labels | 50.011% | 50.423% | 0.3995 |
| Jointly pretrained SGD, then adapt | 56.264% | 53.553% | 0.3592 |
| **First-order Reptile initialization, then adapt** | **56.434%** | 55.841% | 0.2940 |
| Nearest-neighbor | 55.879% | 59.691% | 0.3939 |

Predeclared H2 gate: Reptile minus *strongest control* >= +5.00 percentage points of balanced accuracy at k4. Observed Reptile minus scratch = **+0.01684 percentage points** (`0.0001684085` absolute). **H2 REJECTED**. No meaningful evidence of adaptation advantage. Reptile's Brier and unqueried accuracy are worse than scratch. A single marginally positive metric must not be promoted.

## Adaptation, family and seed heterogeneity

| Method | Balanced k2 | Balanced k4 | Balanced k8 | Mean first 75%-balanced hit, right-censored at 9 |
|---|---:|---:|---:|---:|
| Scratch | 51.171% | 56.417% | 64.685% | 8.625 |
| Joint-pretrained fine-tune | 53.105% | 56.264% | 63.716% | 8.526 |
| Reptile | 53.754% | 56.434% | 64.459% | 8.313 |
| Nearest | 51.225% | 55.879% | 64.561% | 8.542 |

Mean balanced k4 by OOD family (scratch / joint / Reptile / nearest): periodic (53.41% / 55.80% / 54.52% / 51.76%), two interval (61.73% / 59.53% / 62.90% / 61.47%), parity band (54.09% / 53.88% / 54.37% / 53.66%), sparse (56.44% / 55.84% / 53.94% / 56.62%). Sparse concept transfer is negative despite its high all-negative raw-accuracy shortcut.

Four seed-level Reptile k4 balanced: `0.58156`, `0.55005`, `0.54866`, `0.57708`; scratch: `0.56666`, `0.57464`, `0.55175`, `0.56363`. Effect changes sign by seed. Not a statistically demonstrated improvement.

## Cost and verification

- Each adaptive arm purchased **1,536 target labels** total; static transfer purchased zero. Gradient-based scoring arms performed **1,536 target gradient updates** and approximately **618,240 counted feature multiplications** each; nearest performs no gradients but 75,840 pair distance operations are measured exactly in raw JSON. Source/meta candidate search performed **110,592 training gradient updates** across all four seeds and all nine joint/Reptile candidates, using 1,536 distinct source-label exposures and 768 distinct validation-target-label exposures (reused across candidates). This is **not** cheaper than scratch end-to-end; repeated candidate-validation inference is additional unamortized work.
- Original protocol used full-domain balanced accuracy precisely because v1's sparse-family raw accuracy inflated apparent adaptation. Family-level raw results retained; no retuning after score.
- `node --test v2_test.mjs`: **9/9 PASS** on local Node. `node v2_study.mjs test`: 9 internal assertions PASS. `node v2_study.mjs score ...` and deterministic `verify ...`: PASS, exact parsed-object replay. First test run caught a shared-reference aliasing error in the freeze object; repaired before frozen commit and before any v2 OOD score. No failing test was omitted from the final suite.
- The raw result JSON is archived losslessly as gzip+base64 (`v2_results.json.gz.b64`), because repo text API is used. Decode and compare to SHA256 `f80ba9524f7d77e064826219ca80b8d3157d5fb3ce77f4838360f50a9dbf1e4f`:

```sh
base64 -d code/ace_research_metalearning/v2_results.json.gz.b64 | gzip -d > /tmp/ace-r4-v2-results.json
sha256sum /tmp/ace-r4-v2-results.json
node code/ace_research_metalearning/v2_study.mjs verify code/ace_research_metalearning/v2_prescore.json /tmp/ace-r4-v2-results.json
node --test code/ace_research_metalearning/v2_test.mjs
```

**Unverified:** Exact clean GitHub Actions CI run and entire E1.4/E1.5 regression, independent sealed OOD evaluator, natural language tasks, external reality, hard resource isolation. Local Node execution and exact matching Git blob SHAs are real, but do not imply GitHub CI. No E1.4 frozen files or other teams' directories were modified; draft PR remains unmerged.

**Decision:** `H2_REJECTED`, `SCIENCE_NOT_ASSESSED`, `NO_PROMOTION`, `NO_OAIE_CLAIM`. This v2 is exploratory and was designed after viewing v1 results, so not independent confirmation.
