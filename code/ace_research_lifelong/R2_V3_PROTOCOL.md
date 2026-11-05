# ACE R2 v3 — adversarial lifelong learning across multiple synthetic families

**Status: exploratory public development; not independent confirmation; not OAIE.**

## Research question and decision contract

Does novelty-triggered expert consolidation with partial parameter transfer retain old capabilities and adapt to recurring tasks better than capacity-matched no-transfer and fixed-slot experts, EWC, replay, and a frozen policy? The accepted exploratory gate requires *every* criterion: mean final >= 0.68; average forgetting <= 0.10; candidate final minus strongest capacity-matched alternative >= 0.025; candidate minus reservoir replay >= 0.025; final minus shifted-context OOD <= 0.05. Record both failed and passed criteria. The task-ID oracle is a diagnostic upper bound, NEVER a fair comparator. These thresholds are development-only and authored in the benchmark source, not independent preregistration.

## Public task design

Three deterministic families: sparse-linear, compositional features with pairwise XOR-like products, and rotating linear rules. Features are 10 binary inputs plus six pair-products (16 total), with deterministic seeded sparse teacher weights and 3% deterministic label flips. Four tasks are encountered in sequence [0,1,2,0,3,1,2,0]. Four seeds [7,19,43,91] and two context regimes: separated contexts with small jitter or overlapping contexts with broad jitter. Each of eight episodes supplies 64 new labels, totaling 512. Evaluation uses 96 independently generated public examples per task and OOD uses context offset +0.16, both drawn from distinct RNG streams and never passed to the optimizer. Evaluation is diagnostic after every episode, never used for model selection. No private task bank.

## Comparison and resource accounting

- Frozen: train only first 64 labels, then stop updating while retaining a shared logistic model.
- Online SGD: logistic model with 16 features and interactions with context and squared context (48 weights).
- Diagonal EWC: same shared model plus diagonal Fisher and anchor (144 scalars), penalty and Fisher work counted.
- Replay: shared model with a 48-example uniform reservoir; replay one older example per new label when available (1023 gradient updates vs 512).
- Selective: 4-expert cap; route by closest context prototype; grow on novelty distance >.21; initialize new expert with 0.2× closest expert; consolidate prior experts by training only the routed one. 16 weights per expert.
- No-transfer: identical architecture and gating/cap, initialize new expert at zero. This is the essential equal-capacity ablation.
- Fixed slots: four experts with **privileged public context centroid priors**, no task ID at inference.
- Task-ID oracle: privileged task identifier, only to estimate upper bound; not a fair competitor.

Report end accuracy, intermediate accuracy trajectories, per-task first-learning accuracy, mean positive forgetting (max historical post-training accuracy minus final), backward transfer (final minus immediately after first learned), forward transfer (pre-first task accuracy minus .5), shifted-context OOD accuracy, training-label total, weight-update and coordinate-operation counts, Fisher and penalty work, buffer entries, expert and storage scalar count. Scalar counts exclude JS object/heap overhead and are not actual memory-byte profiling. Replay uses 2× gradient updates and extra stored examples; no compute-matched downsampling inference is allowed.

## Reproducibility

From `code/ace_research_lifelong/` run:

```bash
node r2_v3.js > R2_V3_REPLAY.json
node -e 'const {runV3,testV3}=require("./r2_v3.js"); console.log(testV3(runV3))'
```

Compare regenerated JSON against `R2_V3_RESULTS.json` byte-for-byte. Both are public development, not a sealed confirmation. `testV3` verifies paired seeds, deterministic replay, 192-row matrix, explicit label/compute caps, nonnegative metrics, full trajectories, exact Fisher workload, and group aggregations. The script was executed in a V8 isolate and test assertions passed; Node clean-checkout exact-head CI remains a separate gate.

## Interpretation limitations

Only synthetic discrete labels, no continual real-world perception or semantic tasks. Context jitter and task-specific teacher construction are researcher-controlled. The fixed-slot comparator knows test-context centers; the oracle uses task ID. Models have different persistent states and compute, so claims are restricted to **matched capacity selective-vs-no_transfer/fixed_slots comparisons**, not global model-class superiority. Overlap creates routing ambiguity; accuracy under shifted contexts may reflect different expert choice, not learned invariance. Failure to pass a gate stays HOLD. Results must not be tuned after looking at these public test values. Future confirmatory tasks need separate generation/custody and independent code-path review.
