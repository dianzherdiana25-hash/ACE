# ACE R4 v6 — meta-learning failure attribution (PUBLIC EXPLORATORY)

Project: `dianzherdiana25-hash/ACE`; isolated to `code/ace_research_metalearning/` on `research/chat-r4-metalearning`. Existing R4 v1–v5 results are immutable; **do not revise their decisions or thresholds**. No changes to `main`, frozen E1.4, other agents' files, or services. No merge.

## Motivation and questions — frozen before evaluation

Five successive R4 studies failed their prespecified OOD balanced-accuracy gates, with v5 learned directional coefficients close to zero. V6 is **an attribution study**, not a new promotion hypothesis or a statistical claim of independent generalization.

We will report, without a new performance acceptance gate:

1. **Optimization collapse:** exact magnitude of v5 learned cross-feature routing coefficients, and prediction-label flip rate against identical scratch SGD at k=4 with matched learning rates, initial state, targets, and query positions.
2. **Acquisition confounding:** compare scratch SGD under an index-only family-blind schedule versus the inherited v5 schedule that hashes `task.family`; both buy eight labels. This tests dependence on the evaluation procedure, not target policy efficacy.
3. **Sample ambiguity:** evaluate an **evaluator-only, task-distribution-aware candidate-pool posterior** over public synthetics, including the evaluated task itself. Report candidate counts, fraction of ambiguous unqueried positions and candidate-posterior prediction accuracy at k4 and k8. This is not a deployable learner, statistically valid information bound, or fair comparison to blind baselines; it only characterizes ambiguity relative to the constructed finite pool.
4. **Representation / optimization diagnostic:** fit the same 20-dimensional v2 feature map to all 32 labeled points for 96 epochs and record *training* balanced accuracy. This is not a mathematical representational ceiling and must not be called a generalization result.
5. **Nonzero-direction control:** frozen fixed beta `[0.4,-0.4,0.4,-0.4,-0.4,0.4]` checks whether visibly nonzero routing changes performance. No parameter tuning using the v6 target data.

## Bank, experimental allocation, and leakage policy

- Four **new** deterministic target seeds `[2009,2063,2137,2221]`; each produces 48 v5-generator tasks from four OOD families, total 192; generated task masks are unique within each seed's partitions by the underlying v5 bank constructor. These are **new public synthetic instances of already author-visible families**, not an independently sealed novel family distribution.
- Four frozen pre-v6 v5 fits from seeds `[1301,1423,1559,1697]` provide learning rates and gradient-routing beta; there is **no refitting or model selection on new targets**.
- Each learner has identical 0,2,4,8 target-label budget, using input positions determined only by new seed and integer task ID, **not family or labels**. Additional scratch arm uses original family-dependent scheduling as a confound diagnostic.
- Evaluator-only reference set is the union of the target seed's OOD concepts and eight predetermined extra public-bank seeds `[2333,2401,2503,2609,2707,2803,2909,3011]`; it is disallowed as a trainable feature or selection tool.
- Balanced accuracy and unqueried Brier are reported at k4 and k8, with per-seed/family raw receipts and explicit source provenance.
- Frozen constants: 32-point binary domain, 20 features, max 8 target acquisitions, 96 full-label training epochs, LR 0.12 for full-label fitting; beta and target seeds fixed above. A separate test checks the family-blind schedule is the same for two families sharing a task ID.
- Precommit source, tests, protocol, and SHA256-locked prescore containing only generator bank digests, v5 source fit, configuration and task seeds. Commit these **before** scoring targets. Later commit immutable scored evidence, verification, and results. Never overwrite prescore or source after scoring.

## Failure handling / interpretation

If new source or test fails before first scoring, fix and re-freeze as a new prescore checkpoint; retain failure log. If replay after scoring differs, flag FAIL and do not claim valid evidence. Do not inflate candidate-pool/post-hoc full-label diagnostic into an IQ, OAIE, transfer, or adaptation-gain claim. No independent evaluator or externally custody-held test set is claimed. Main scientific conclusion remains **NO VALIDATED GAIN** until a separate pre-registered study with an independent untouched evaluator is passed.

## Reproduction

```sh
node --test code/ace_research_metalearning/v6_test.mjs
node code/ace_research_metalearning/v6_diagnostic.mjs test
node code/ace_research_metalearning/v6_diagnostic.mjs freeze /tmp/r4_v6_prescore.json
node code/ace_research_metalearning/v6_diagnostic.mjs score /tmp/r4_v6_prescore.json /tmp/r4_v6_results.json
node code/ace_research_metalearning/v6_diagnostic.mjs verify /tmp/r4_v6_prescore.json /tmp/r4_v6_results.json
```

Node >=20, standard library only. Required existing sibling files: `v2_study.mjs`, `v3_study.mjs`, `v5_study.mjs`, `v5_prescore.json` (exact Git blobs verified before evaluation). The result archive is public-development research evidence only.
