# R7.2 pre-evaluation protocol lock — utility-weighted information acquisition

Status: **PRE-SCORE DESIGN**. The R7.1 public test and OOD results are development-only and must never be relabeled independent holdout.

## Falsifiable hypothesis
Under equal maximum online label budget, a utility-weighted certificate-seeking selection policy using *only observed labels and source prior* will achieve greater **safe coverage** (true accepted strata) than matched random acquisition with the same confidence acceptance rule, without higher false acceptance counts, both on newly generated stable test worlds and on a hidden mechanism-shift OOD family.

A result where all methods abstain, or the active method just buys more labels, does **not** count as improvement.

## Locked public benchmark and access
- Implement exclusively within code/ace_research_uncertainty; no ACE core changes.
- Lock seed **20261106**; 6 observable groups, hidden group Bernoulli reliability. Train 30, validation 12, stable test 24, shifted OOD 24 tasks. Unique split-prefixed world IDs. Test/OOD data generated only after policy code and unit tests are finalized.
- Stable success probabilities: (0.18,0.42,0.63,0.78,0.91,0.97).
- Shifted: (0.91,0.19,0.36,0.54,0.33,0.72). Each probability jittered U(-0.09,+0.09), clipped [0.01,0.99].
- Latent target reliability ≥0.80 defines true safe acceptance; 64 deterministic evaluator-side scoring probes/group from a namespace separate from acquired-label stream.
- A source prior is fitted only on source train; no update or hyperparameter selection using test or OOD. 12 validation tasks may be used for debugging and deciding whether to stop, NOT to select among many adaptive variants after inspection of final splits.
- Fixed prior strength **12**, normal-LCB z **1.0**, minimum **3 acquired target labels per accepted group**, identical for utility-guided and random-LCB; report limitations of normal approximation and prior shift.
- Label budgets **0,6,12,24** per task, local deterministic seed. Maximum is a cap; early stopping permitted but all realized purchases explicitly counted.
- Baselines: no-activity zero-budget, round-robin posterior-mean fixed threshold, uniformly random query with posterior mean, uniformly random + same LCB rule as active. Privileged oracle truth is **evaluation-only ceiling** and never called by any policy.
- Query selector computes expected probability of eventual acceptance in next 1..8 labels from Beta-binomial posterior predictive with positive expected correct/false utility; score per query horizon. It prioritizes groups with credible paths to certify, not uncertainty alone. It does not read ground-truth success probability. Stopped if no positive eligible score. Exclude already accepted groups.
- Safety-adjusted utility for risk comparison: **20 × true accepts - 60 × false accepts - 2 × abstentions - 1 × online purchased labels**, with online label budget separately reported. Report true/false accepts, abstentions, false accept rate (undefined when zero accepted), ECE, Brier, buys, and value per 100 labels.
- Strict success requires active's mean true accepts ≥ random-LCB *and* false accepts ≤ random-LCB on BOTH stable test and OOD; at least one strict improvement; positive safe utility at nonzero coverage. Failed/undecidable gates retained. If methods differ in purchase counts, report both matched-budget and realized-cost versions.
- The OOD family is author-known and only tests specific reliability swaps, not generic uncertainty awareness. No significance or generalization claims without independent seeds.
- No external tool/evaluator charges; no dynamic candidate code execution; no test/OOD retuning; record negative results and counterexamples.

## Evaluation sequence
1. Commit this protocol BEFORE implementing and running the R7.2 benchmark.
2. Implement separate module with tests for budget exhaustion, oracle isolation, no-target-label abstention, no OOD tuning, deterministic replay, early stopping, and invariant that model sees no hidden probabilities.
3. Run validation-only smoke check; freeze implementation. Run stable test/OOD exactly once. Save full JSON, SHA256, command, stdout/stderr, environment notes.
4. Do not merge PR, do not promote R7 to an accepted ACE gate.
