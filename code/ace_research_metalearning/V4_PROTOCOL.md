# ACE Research R4 v4 — gradient-conditioned inner-loop update (public development)

Owner: `code/ace_research_metalearning/` exclusively; branch `research/chat-r4-metalearning`; parent baseline v3 at `a1a65fe2c3119c0f186c4abfc3d348e8a8afa4c5`. No source, data, or decisions from E1.4 may be altered. Prior negative R4 v1/v2/v3 results and prescore remain immutable. No merge or OAIE claim.

## Precommitted hypothesis H4 (before first v4 OOD score)

A learned diagonal update transformation, whose step scale varies with within-task **accumulated signed-gradient coherence** at each feature, will improve **full-domain balanced accuracy after four purchased target labels** by **>= +0.05 absolute** relative to the **strongest** of scratch SGD, fixed diagonal preconditioner, ordinary joint pretraining+finetuning, first-order Reptile, no-learning nearest-neighbor, and untrained gradient-conditioner controls, over four seeds. All adapted arms have the same target query order and 8-label budget, and no arm receives target family identity as a feature. H4 additionally requires positive gain on >= 3/4 seeds, noninferior unqueried Brier loss against strongest control at k=4, and <= 1.40x the scratch target **logical feature-multiply plus conditioner-operation** count. Failure of *any* criterion rejects H4. Compute ratio is a proxy, **not wall CPU equivalence**; full source meta-learning compute is reported separately, not declared matched.

## Generalization split and negative controls

- Four preregistered seeds: `907, 1009, 1103, 1217`; per seed 66 meta-train tasks from threshold/interval/alternating families, 32 validation tasks from reverse-threshold/outside-interval/block-xor, and 48 OOD tasks from **prime-affine**, **palindromic-bands**, **bitcount-gate**, and **modular-intersection**, 12 each. 32 binary inputs/task, 192 OOD tasks overall, min five positives and min five negatives per task. Complete task masks are unique across train/validation/OOD within a seed. The OOD families/seeds are PUBLIC, not independent evaluator-custodied.
- Target observations at k=0,1,2,4,8 use the same deterministic **seed-only** blind position order across every task and every arm (no task ID, mask, family or labels enter query order). Purchased labels are credited as known for the primary full-domain balanced metric. Secondary measures: unqueried accuracy/Brier, mean first k to >=75% balanced accuracy censored at 9, label purchases, gradient steps, feature multiplies and conditioning operations.
- 20-dimensional fixed polynomial/Fourier/bump feature map, logistic model, identical 8 target SGD steps for gradient learners. Source gradient transformation uses `coherence_j = abs(sum past+new gradients)_j / sum abs(past+new gradients)_j`, and `scale_j = clip(exp(beta_group*(2*coherence_j-1)), 0.25, 4)`. Group beta coefficients for polynomial/Fourier/bump groups are meta-learned using finite-difference gradients of source-task k4+k8 unqueried Brier loss; two outer rates, three SGD rates, six bounded outer steps. Validation selects candidate with best balanced k4, Brier tiebreaker. No OOD outcome determines weights, architecture, hyperparameters or selection.
- Controls: SGD from zero; validation-selected *fixed* three-group diagonal rates; untrained conditional scales with validation-selected fixed beta; joint-pretrained finetune; Reptile with validation-picked inner/outer rates; nearest. All adaptive competitors purchase identical target labels. Full source/validation data for meta-objective are allowed and explicitly billed; this is not equal all-in cost.

## Tamper and freeze gates

1. Run `node --test code/ace_research_metalearning/v4_test.mjs` and `node code/ace_research_metalearning/v4_study.mjs test` before freeze. Any failure stops evaluation. Examine no OOD outcomes before freeze.
2. Create `v4_prescore.json`, storing all fitted coefficients, individual source/validation/holdout split SHA256 **digests** and the protocol/gate config. Commit source, tests, protocol, prescore on GitHub before scoring OOD, and record that prescore Git commit. The digest alone is not secure custody; test-family mechanisms are author-visible.
3. Score exactly once at this checkpoint using immutable source. Then commit complete raw OOD evidence, experiment summary, and verification. Replay the raw score with exact GitHub source and committed prescore; compare canonical SHA256. No postscore retuning, no reinterpretation of H4, no cherry-picking.
4. Keep PR draft, do not merge. Hold scientific acceptance until independent evaluator and prospective family-shift replication are performed.

## Commands

```bash
node --test code/ace_research_metalearning/v4_test.mjs
node code/ace_research_metalearning/v4_study.mjs test
node code/ace_research_metalearning/v4_study.mjs freeze /tmp/v4_prescore.json
node code/ace_research_metalearning/v4_study.mjs score /tmp/v4_prescore.json /tmp/v4_results.json
node code/ace_research_metalearning/v4_study.mjs verify /tmp/v4_prescore.json /tmp/v4_results.json
```

One-world synthetic 1D binary task families, manually authored meta-rule, and standard-library deterministic simulation do not demonstrate open-ended intelligence or real-world transfer. Even a positive exploratory result is NOT a confirmatory science GO.
