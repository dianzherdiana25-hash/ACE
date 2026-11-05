# ACE R2 v4 — support-conditioned memory retrieval: exploratory result

**Date:** 2026-11-05. **Status:** `HOLD_NO_VALIDATED_LIFELONG_GAIN`. **Public synthetic development only.** Pre-score commitment: `R2_V4_PRESCORE_PROTOCOL.md`, Git commit `f8bd61813a6359000b3b0fea6b18123dd7ef3b97` predating scoring. Full source, raw results, and separate arithmetic audit are checked in under this R2 directory.

## Experiment execution and correction history

- 5 seeds × 3 context regimes × 9 methods = **135 paired method/regime/seed runs**. Underlying x/y teachers and draw seeds are intentionally shared across regimes, so these are **not 135 independent teacher samples**.
- Each run processes 8 sequential episodes, 64 training labels each = 512 logical observed training labels; 12 task-identification support examples per episode are included within those 64, not additional training purchases.
- After each episode, the evaluator makes 4 task-block queries, each with 12 support labels and 96 evaluation labels, and a final unknown-task block with 12 support labels. **396 support-label access events** and 3072 query-label scores per run (repeating identical evaluation-support examples over checkpoints; 60 unique support items per run, not 396 independent samples).
- During the first exact-GitHub-blob V8 run, we found a **task-ID dependency in replay reservoir RNG seeding**, even though the predictive policy did not use the task ID directly. We removed it and reran all 135 cases before persisting official results. Historical initial run should not be used as conclusive replay evidence. Post-fix source blob `7a0e3a7b9011bfc8ce60e7de5e766517b1c54afb`.
- The post-fix source was read directly from GitHub and executed in a V8 isolate; same-source deterministic replay and 20 invariant categories returned PASS. This is **not** Node exact-head CI, independent code custody, or a fully blinded scientific evaluation.

## Corrected terminal scores (mean across five seeds)

| Method | Distinct context | Aliased context | Context-shifted | Aliased avg forgetting | Training updates/run | Eval updates/run |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Frozen first-task only | .5896 | .5896 | .5896 | .0000 (trivial) | 64 | 0 |
| SGD shared | .6177 | .6177 | .6177 | .2000 | 512 | 0 |
| Diagonal EWC | .6260 | .6260 | .6260 | .0557 | 512 (+ Fisher/penalty) | 0 |
| Reservoir replay | .5953 | .5953 | .5953 | .1630 | 1023 (+ 48 stored examples) | 0 |
| Context-only 4-expert cap | .8896 | .6177 | .8255 | .2000 | 512 | 0 |
| **Evidence retrieval + transfer candidate** | **.8260** | **.8260** | **.8260** | **.0615** | **512** | **0** |
| Matched evidence retrieval, **no transfer** | .8266 | .8266 | .8266 | .0604 | 512 | 0 |
| Shared-head support fine-tuning | .6531 | .6531 | .6531 | .1734 | 512 | 384 |
| Task-ID oracle (privileged) | .8896 | .8896 | .8896 | .0042 | 512 | 0 |

The selective candidate has **5% final known-task rejection** (abstention counted incorrect) but rejects only **20% of unseen fifth-task diagnostic blocks**. On the aliased context condition, evidence-vs-context improvement = +.20833 absolute accuracy, but evidence-vs-identical-no-transfer effect = -.000521. On distinct contexts, evidence retrieval *loses* to context-only routing (.8260 vs .8896).

## Pre-score gates (all required)

| Criterion | Outcome |
| --- | --- |
| Aliased evidence beats context by >= .15 | PASS: +.20833 |
| Candidate transfer beats equal-capacity evidence_zero by >= .025 | **FAIL: -.000521** |
| Reject >= .65 unseen fifth-task blocks | **FAIL: .20** |
| Falsely reject <= .20 familiar task blocks | PASS: .05 |
| Evidence beats support-finetune by >= .03 on alias | PASS: +.17292 |
| Aliased evidence accuracy >= .75 | PASS: .82604 |

Decision: **4/6 gates PASS, 2/6 FAIL ⇒ HOLD_NO_VALIDATED_LIFELONG_GAIN**. Do not promote mechanism or infer autonomous learning capability.

## Separate arithmetic audit

The `audit_v4.js` module independently reads `R2_V4_RESULTS.json`, does not invoke a learner or generator, recomputes all group means, 135 distinct run identities, split-rule signatures, 8-episode trajectories, final accuracy, rejection, forgetting, BWT/support-conditioned FWT, exact label/update budgets and gates, then performs a paired five-seed descriptive bootstrap. `R2_V4_AUDIT.json` reports PASS. Across the repeated arms: 69,120 logical training-label accesses, 53,460 evaluation-support access events, 414,720 evaluation query-label scores, and 75,825 gradient updates including evaluation adaptation steps. These are logical work units, **not** unique independent labels or hardware time.

Five-seed paired, descriptive-only resampling of aliased score differences:

| Contrast | Mean Δ | Five-seed descriptive resampling interval |
| --- | ---: | ---: |
| Evidence − Context | +.20833 | +.07083 to +.31771 |
| Evidence − Evidence-zero | -.000521 | -.00729 to +.00625 |
| Evidence − Fast adaptation | +.17292 | +.02865 to +.29219 |

These are **not confirmatory confidence intervals** and should not be used as causal proof outside this author-visible synthetic benchmark.

## Costs, fairness, and limitations

The evidence candidate evaluates every available specialist on support labels, adding about 1296 router prediction calls per run and up to 56 persistent numeric scalars (four 12-weight heads plus metadata). Context-only uses no labeled-support computations beyond the same charged label access events. Comparing evidence vs context therefore tests the **value of spending label-conditioned routing compute**, not cost-free superiority. The causal parameter-transfer ablation (`evidence_zero`) has the same head count, threshold, 12-support budget, training updates, router work, model architecture and storage. It slightly **outperforms** the proposed transfer, showing no incremental gain.

The fifth novelty task is sampled by the author-visible generator and scored with one 12-example support block per seed. The metric measures detecting an unknown function, not solving it. When input contexts are aliased, task identity must come from the supplied labeled support; without it, task routing can be information-theoretically impossible. Repeated checkpoint diagnostics use the same support labels, but models do **not** train on those evaluation supports. Fixed synthetic task-family weights, small seeds, no hardware-time measurement, no blinded evaluator and no real-world lifelong skill learning prevent OAIE claims.

## Exact reproduction and next independent gates

```bash
cd code/ace_research_lifelong
node r2_v4.js > R2_V4_REPLAY.json
node audit_v4.js R2_V4_REPLAY.json
```

Next experiment should precommit a *new task-family generator*, consider memory-aware context inference with matched label-conditioned routing budget, evaluate switch-detection and unknown-task abstention as distinct objectives, and require clean exact-GitHub-HEAD Node CI plus separately held confirmatory tasks. Do not tune v4 thresholds after seeing the current result.
