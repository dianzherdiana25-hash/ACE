# ACE E1.4c-v2 — Corrective pool-independence PRELOCK

**PRE-SCORING corrective development protocol.** The previous E1.4c-v1 result was `HOLD` and revealed that the shared PRNG could indirectly couple the unlabeled question pool to the hidden rule through word-dependent rejection of demonstration traces. We preserve the v1 result, preregister this correction independently **before running v2 scores**, and distinguish it from a confirmatory replication.

## Fixed scope

- **Hypothesis unchanged:** the learned family-specific query-policy heuristic transfers from six source episodes to six disjoint target episodes in each family better than sham, task-local max-partition, exact one-label uniform expectation and no-label, in **each** of S/G x related/unrelated strata (three target tasks per stratum). All existing v1 query heuristics, selector tie-break rules, policy scoring, label budgets, aggregation and GO/HOLD rule remain untouched.
- **Motifs unchanged:** reuse v1's four-event *rule words* (already public), but allocate completely new input-level tasks, pools, demonstrations and probes. New bank inputs may not overlap v1 or earlier public banks; the new bank builder must include v1 inputs in its used-set before producing v2 cases. Any unexpected overlap is a blocking integrity failure, not a numerical score.
- **Specific correction:** before constructing ANY word-conditioned demonstrations or probes, allocate all **24 unlabeled query pools** of eight questions using independent per `(family, pair_id, role)` PRNG seeds beginning at `141711`. Pool construction must not access the hidden rule, oracle, candidate or outputs. Afterwards reserve all pool inputs so separate demo/probe PRNG streams (seed `141712` plus slot) cannot reuse them. `preallocate_pools()` must yield identical pools when supplied arbitrary altered secret words.
- Source-to-target policy selection is performed using sources only; the target evaluator must not choose the inherited heuristic after target outcomes are known. Source training requires eight oracle-labeled interventions per source, i.e. 96 labels, and counterfactual target evaluation requires eight interventions per target, i.e. 96 more calls. Deployment arms each consume one label but overall amortized cost is **not equal** to local controls.
- Candidate/evaluator share a process and known four-event grammar; isolation of E1.3 worker is NOT inherited. Cross-process security and class-informed strong independent reference remain future gates. Do not claim AGI or open-ended autonomous evolution.
- Decision threshold: **strictly higher** inherited than every comparator in all 4 strata → `GO_CROSS_EPISODE_TRANSFER_DEVELOPMENT_ONLY`; otherwise `HOLD_CROSS_EPISODE_TRANSFER_HYPOTHESIS`. Resource/integrity failures → `HOLD_RESOURCE_INTEGRITY`. Do not posthoc tune these rules.
- The v1-to-v2 comparison is descriptive and **not independent**: the correction followed an audit of scored v1 results. Keep all negative and contradictory outcomes.

## Technical proof requirements

1. Tests demonstrate counterfactual pool invariance under changed rule words, no pool oracle calls, no overlap with earlier public inputs **including v1**, and distinct source/target roles.
2. Frozen exact-source commit and bank SHA recorded. Run under a bounded, visible terminal command. Preserve both raw report and deterministic replay; record actual failure if it occurs.
3. An independent report arithmetic verifier recalculates source utilities, selected policy mapping, stratum summaries and decision; no hidden oracle claimed verified by report arithmetic.
4. Only ACE research branch; no main/Tod changes, no paid usage, no sealed E1.3 evaluation.
