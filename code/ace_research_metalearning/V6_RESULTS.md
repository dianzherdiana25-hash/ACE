# ACE R4 v6 — Diagnostic result: inherited learning rule collapses to scratch

**Status: PUBLIC_EXPLORATORY_DIAGNOSTIC_NOT_CONFIRMATORY. NO VALIDATED OOD META-LEARNING GAIN.**

## Provenance

- Baseline branch: `research/chat-r4-metalearning`; PR #39; prior HEAD `dee09c99d8acc7410ce8761a512c380c281d7207`.
- Before target scoring, `v6_diagnostic.mjs`, `v6_test.mjs`, `V6_PROTOCOL.md`, and `v6_prescore.json` were committed. Exact checkpoint: `dff5cd01712d2014b959a726885991025ad6d095`. Readback confirmed **4/4 Git blob SHAs** match the locally tested bytes.
- Frozen prescore semantic SHA256: `a1b1453dcbbf51ef50a085cf46ffa8acb96c0305f24bf6808e833cbf2acaeb39` (`SHA256(JSON.stringify(parsed_prescore))`, different from raw-file digest).
- Four new deterministic public synthetic seeds `[2009,2063,2137,2221]`; 48 targets/seed, 192 total, 4 v5-generator OOD families, same 8 target labels/arm. These are new *instances* of previously author-visible families, not an independent sealed generalization test.
- Historical v5 fit source `v5_prescore.json` and dependencies preserved byte-for-byte. The previous v1–v5 hypotheses remain rejected and are not rescored or rewritten.

## k=4 and k=8 full-domain balanced accuracy

| Arm | k=4 | k=8 | k4 unqueried Brier |
| --- | ---: | ---: | ---: |
| Scratch SGD, family-blind schedule | **55.083%** | 61.999% | 0.250162 |
| Inherited v5 learned directional routing, same schedule | **55.083%** | 61.999% | 0.250162 |
| Frozen nonzero off-diagonal stress routing | 55.630% | 62.224% | 0.249539 |
| Scratch SGD, legacy family-conditioned schedule | 55.309% | 62.434% | 0.252672 |

These are not candidates selected on v6 outcomes. The stress routing's +0.547 pp diagnostic difference from scratch is not a meta-learning gain or a successful preregistered promotion. The two acquisition schedules differ, and legacy uses the family string in its pseudorandom seed. This is an **experimental-design confound**, not demonstrated label leakage or causal proof of performance inflation.

## Failure attribution

1. **Learned routing is behaviorally inert:** inherited beta RMS `0.0002103`, maximum absolute coefficient `0.00062495`. Across 192 targets × 32 positions, **zero learned-vs-scratch predicted class flips** at k4 with identical LR and query schedule. It therefore learned a barely detectable perturbation instead of a new decision rule. Minor probability-level differences exist in Brier; not literally identical floating-point predictions.
2. **Representation/optimization and data limitations coexist:** fitting the same 20-D logistic features for 96 epochs on **all 32 true labels** per task yields **74.878% in-sample balanced accuracy**. This is a training diagnostic, *not* a representational upper bound or out-of-sample generalization result. The large difference from 4-label performance is consistent with limited evidence and/or optimizer issues; it cannot uniquely attribute causality.
3. **Finite-pool ambiguity remains high:** evaluator-only reference pool contained 395–399 distinct synthetic concepts per seed, **including the target**. At four known labels the mean compatible hypothesis count was `27.677`; about **99.89%** of unqueried positions admitted conflicting labels among compatible hypotheses. At eight labels 3.563 hypotheses remained on average, with **49.72%** ambiguous unqueried positions. This is ambiguity **only for this engineered candidate pool**, not an information-theoretic lower bound on possible learners.
4. **Evaluator-only candidate posterior:** unqueried accuracy 64.211% at k4 and 82.096% at k8. This reference knows the evaluation pool, including the target. It is a diagnostic, not a valid comparable learner and cannot establish a true oracle upper bound.

## Per-family k4 balanced accuracy (scratch / legacy schedule / full-label in-sample fit)

- Rotating stencil: 50.56% / 52.40% / 64.14%.
- Change-point parity: 48.81% / 49.98% / 58.38%.
- Cyclic XOR intervals: 67.35% / 64.53% / 99.45%.
- Piecewise modulo: 53.61% / 54.33% / 77.55%.

## Label and computational accounting

- Each of four adaptive arms buys exactly eight labels/task, **1,536 target purchases** in aggregate. All curves use k0/2/4/8; no paid or external evaluator calls.
- Counted inner-loop gradient steps are equal across arms: 1,536. The inherited routing additionally incurs **368,640 recorded route operations** vs scratch's zero, with 61,440 recorded feature multiplications per arm. This counter omits predictions needed for periodic scoring, so no end-to-end compute ratio is claimed. Full-label fit uses far more data/compute and is not a budget-matched competitor.
- Python/Node host CPU and OS sandbox certification were not performed; Node 22.16.0 local execution and reproducible logical counters are the evidence.

## Tests, preservation, and receipts

- Before scoring: seven `node --test v6_test.mjs` PASS, seven internal guardrails PASS; exact GitHub prescore 4/4 blob SHA readback PASS.
- After scoring: `node v6_diagnostic.mjs verify v6_prescore.json v6_results.json` **PASS deterministic semantic replay**. Independent recomputation of task-level aggregates in `v6_audit.mjs` plus full replay PASS. **12/12 Node unit tests PASS** across source and audit suites, including four adversarial tamper checks.
- Raw result `v6_results.json` raw-file SHA256 `018257fd46f7d625f207295a6de8863490b09bc56d1ca571ba8461c2705603b5`; lossless archive `v6_results.json.gz.b64` SHA256 `f81b6aaec523322014c5551a91970c176940edec698f72a0d1ad9fb4e7c1100b`.
- No changes to original R4 v1–v5 files, frozen E1.4 research, `main`, other agent-owned folders or Tod. All v6 files remain in R4's owned folder.

## Decision

**H6 is an attribution exercise, not a success hypothesis.** The evidence supports *gradient-route collapse under the inherited v5 optimization and these public synthetic concepts*, with a substantial acquisition-schedule sensitivity and finite-pool ambiguity. It **does not** show an impossibility result for meta-learning, identify one uniquely causal failure mechanism, or demonstrate OAIE capability growth.

Next research should isolate the gradient landscape with known-operator diagnostic positive controls and validate acquisition-blind protocols **before** any further OOD claims. Do not tune to these v6 results and relabel the same bank confirmatory. Exact-head GitHub CI, complete ACE historical regression, independent sealed holdout, and independent scientific acceptance remain OPEN. PR stays draft; NO MERGE / NO PROMOTION.
