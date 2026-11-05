# ACE R2 v6 — pre-score protocol: learn newly admitted skill without losing older skills

**Ownership:** only `code/ace_research_lifelong/`, branch `research/chat-r2-lifelong`. **Research classification:** author-visible public development; no independent evaluator, OAIE or production promotion.

## Falsifiable hypothesis and distinction from v5
R2-v5 calibrated novelty rejection on a **frozen** archive. R2-v6 tests whether **admitting and training** a fifth task can preserve four old capabilities when the archive has a hard four-head memory limit. The candidate combines bounded archive compression (merge two similar old weight vectors) with support-label novelty detection, then trains a new head. Hypothesis H6: **similarity-selected merging** maintains better old/new joint correctness than an equally sized oldest-head eviction and random-pair merging. This is not generic uncertainty calibration (R7), meta-learning (R4), or architecture evolution (R3); it is memory consolidation under continual acquisition.

## Generation and split isolation (frozen before run)
Seeds `[11,23,47,89,131]`. Known task families `related_pair` (two related 12-feature signed-linear teachers, two independent) and `orthogonal` (four disjoint three-feature sparse teachers). Novel task types `unrelated` (independent sparse signed teacher 4) and `near` (task 3's largest-magnitude weight flipped; truly distinct but similar). This gives 5×2×2 = 20 paired scenarios per method. Inputs uniform continuous [-1,1]^12, deterministic flipped labels at 2%, features and teacher coefficients identical across splits for each task, different PRNG streams for every role. Context is aliased (no useful context), with 16 labeled support examples **per inference block**, 128 independent query examples per task. No test query labels are supplied to training/inference.

**Initial four-head archive**: each known task has a separately supervised 256-label stage (four stages in order [0,1,2,3]) and an independent 32-sample post-training calibration set per known task. Task IDs are disclosed only for *initial supervised archive construction*—this fact MUST be stated in claims. During new-task detection, inference retrieval, and updates the non-privileged methods get **only** labeled support sets and stored model weights, not task ID. Four existing heads each have exactly 12 trainable weights = 48 weight scalars, no label replay for expert methods. One 16-label novel training support block is used to score the four old heads before updating; the remaining 176 novel labels complete a **192-label novel episode** including the initial 16. Calibration q90 threshold uses only 128 known calibration labels and was not fitted on novelty/evaluation data. Same new-task support, labels, and calibration are reused across paired methods; detection occurs before any changes.

## Fixed methods, fairness, and ablations
- `frozen4`: preserve all four experts, never update on new task; old-skill control, poor new learning expected.
- `evict_first`: if novel score exceeds q90, replace first old head with a zero-initialized head; otherwise reuse best head for training. Four-head cap, 192 novel SGD updates.
- `merge_random`: if novel, uniformly choose an unordered old-expert pair using a deterministic seed/weight-independent RNG; replace them by their averaged weights and add zero-head; if not novel, reuse best. Four-head cap and 192 updates.
- **`merge_closest` candidate**: identical to merge_random except choose the pair with smallest squared Euclidean weight distance; merge arithmetic mean, then add zero-head. No private task ID, no extra stored training examples.
- `expand5`: same detector and updates, but allocate fifth head instead of replacing/merging (extra 12 weight scalars; upper bound for capacity tradeoffs, not fair memory comparator).
- `oracle_merge`: privileged oracle *forces a novel admission*, even if detector rejects; uses the **same closest-pair compression**. Upper bound on detection errors, not a deployable control.
- `shared_sgd`: single 12-weight SGD model, sequentially trained on all four known stages (256 each) and the novel stage (192).
- `shared_replay`: shared model, bounded reservoir of 48 labeled examples from all seen stages, one extra replay gradient update per incoming training example when buffer nonempty. Additional updates and example memory are **charged**, and replay RNG never uses hidden task ID.

**Capacity metrics:** expert baselines fixed at 48 trainable weight scalars pre/post (except expand5=60), no stored label replay; shared baseline 12 scalars, replay 12 plus 48 stored examples. All samples for each scenario and evaluation support are identical across arms. Candidate and two four-head admission controls exactly match training labels and update counts. No gradient updates are allowed during evaluation.

## Evaluation and predeclared acceptance gates
Measure old four-task block-query mean accuracy **before** fifth-task admission (using disjoint labeled retrieval support); after novel training score four old tasks again on their frozen evaluation sets and the novel task on its independent support/query. Inference chooses the head with minimum 16-support mean log loss; no ID. Report terminal old accuracy, old drop (pre minus post), new accuracy, 5-task **joint mean** (4×old + new)/5, decision to admit novel, compression-pair identity (head index only), recovery across related versus orthogonal families, gradient updates, score-probe calls, stored scalars, and novice labels. 'No task creation' on false novelty must remain visible as a failure. Query accuracy counts every case (no abstention).

**ALL gates required for H6 development success**, comparisons paired by seed×family×novelty mode:
1. `merge_closest` joint accuracy exceeds `evict_first` by >= .025 **and** `merge_random` by >= .015.
2. Candidate terminal old accuracy >= .72, and mean old retention drop <= .10.
3. Candidate new-task accuracy >= .78.
4. Candidate novel admission rate >= .65 on both `unrelated` and `near` modes.
5. Candidate joint performance on `orthogonal` family is within .05 of `related_pair`; failure means merge depends excessively on hand-designed task similarity.

Diagnostic oracle and expand5 are never used as fair memory-matched comparators. No threshold, architecture or task coefficients may be retuned after scoring. If a code defect invalidates a run, publish erratum and rerun **all** arms, never silently patch scores. Descriptive seed bootstrap is not a confirmatory confidence interval.

## Reproduction once committed
```bash
cd code/ace_research_lifelong
node r2_v6.js > R2_V6_REPLAY.json
node audit_v6.js R2_V6_REPLAY.json
```
No CI job outside owned path, no writes to main, E1.4 frozen, or other agents.
