# R4 v2 protocol — first-order meta-initialization, PUBLIC DEVELOPMENT

**Scope:** Additional, explicitly exploratory experiment motivated by the R4 v1 failure (PR #39). This is NOT a new independent sealed holdout or revision of v1's failed hypothesis. Changes only in `code/ace_research_metalearning/` on `research/chat-r4-metalearning`. The v1 negative result, prescore, and posthoc audit remain immutable.

## Falsifiable H2 (fixed before v2 OOD score)

Across four fixed seeds `101,211,307,401` and 48 OOD tasks per seed, a first-order Reptile-learned **initialization** for a 20-dimensional logistic learner achieves **at least +0.05 absolute** mean full-domain balanced accuracy at 4 target labels versus the strongest of (a) scratch SGD, (b) ordinary jointly pretrained SGD with adaptation and (c) nearest-neighbor. Each adaptive arm queries the same eight predetermined target positions, using identical budgets k=0/1/2/4/8. **Reject H2** when this criterion fails; do not revise based on postscore results.

## Distinct task families

- Meta-train: monotone threshold (24 tasks), one contiguous interval (24 tasks).
- Model/hyperparameter selection only: inverse threshold (12 tasks), outside interval (12 tasks).
- OOD test: modular periodic, two intervals, parity-modulated band, four-point sparse (12 each).
- Every task has 32 binary inputs. Masks are unique across all splits within each seed. Family identifiers are never supplied as a learner input. Four seeds × 48 OOD tasks = 192 targets.
- The OOD generators and seeds are author-visible public synthetics; this is **not** external independent confirmation. The split-family names and mechanisms are distinct, although structural similarity may remain.

## Compared learning procedures and allocation

All gradient-based arms use the same frozen 20-dimensional feature map (bias, low-order polynomial, Fourier terms and fixed triangular bumps) and logistic SGD. Scratch learns weights from zero; joint pretraining learns fixed starting weights by ordinary online cross-task SGD; Reptile performs eight outer passes with eight support labels per source task and learned first-order initialization; static transfer uses joint weights without target purchases; nearest-neighbor is a nonparametric baseline. Reptile and joint candidates each use **8 epochs × 48 tasks × 8 source steps**, and **384 unique source labels** per seed reused across epochs. Both methods undergo validation-only hyperparameter selection: Reptile 3 learning rates × 2 outer rates, joint 3 learning rates; scratch 3 learning rates. All candidate validation exposures/gradient work count toward total cost; no claim of end-to-end equal budget between search and baselines. Target arms query identical positions independent of reward, not active acquisition.

## Evidence and outcome rules

- Main estimand: full-domain balanced accuracy at k=4, where a purchased label is credited as known. This avoids the v1 sparse-class raw-accuracy trap.
- Secondary: k=0/1/2/8 balanced accuracy, unqueried-only accuracy and Brier, right-censored first k to 75% balanced accuracy (9 means never by k=8), target purchases, gradient updates and feature multiplications.
- Freeze code/protocol/tests/fitted parameters and full SHA256 per-split bank digests in GitHub **before** v2 OOD evaluation. Freeze includes no scored OOD outcomes. Refit from train/validation during deterministic replay to reject changed learned weights. No source or result may be overwritten after scoring; changes require a new version.
- Fixed decision threshold H2 +0.05; track negative and heterogeneous family results, with no benchmark cherry-picking, science GO, real-world generalization or OAIE claim.

## Commands

```bash
node --test code/ace_research_metalearning/v2_test.mjs
node code/ace_research_metalearning/v2_study.mjs test
node code/ace_research_metalearning/v2_study.mjs freeze /tmp/v2_frozen.json
node code/ace_research_metalearning/v2_study.mjs score /tmp/v2_frozen.json /tmp/v2_score.json
node code/ace_research_metalearning/v2_study.mjs verify /tmp/v2_frozen.json /tmp/v2_score.json
```

`node --test` and `freeze` must pass before the first OOD scoring. The frozen JSON is referenced by exact prescore commit and SHA256 in the outcome report.