# ACE R2 v5 — PRE-SCORE public development protocol

Owner: `code/ace_research_lifelong/`; branch `research/chat-r2-lifelong`. No E1.4, main, or other-agent edits. This protocol is committed **before** v5 code execution and results. Scientific status remains unassessed; not OAIE.

## Scope: memory preservation under unknown tasks

R2-v4 showed support-conditioned expert retrieval works on aliased contexts, but rejects only 20% of unseen fifth-task blocks. R2-v5 evaluates *novelty gating of a learned memory archive* separately from task-ID inference and parameter-transfer effects. Model weights must be frozen throughout calibration and novelty evaluation: detecting unknown tasks must not overwrite known memories. **No task identifier** is passed into inference; IDs are used only by the generator and scoring ledger. This is *not* R7's generic uncertainty/active-learning research: the specific intervention is archive protection during lifelong skill routing.

## Fixed design and budgets

- 5 precommitted seeds `[5,17,31,53,79]`; 12 real-valued input dimensions, 4 independent known sparse signed linear teacher functions with 4 nonzero weights and 2% flipped training/evaluation labels.
- Sequential schedule `[0,1,2,0,3,1,2,0]`, 64 labeled train examples per episode, 12 of which are used for pre-update expert routing. Maximum 4 specialist heads, each 12 weights. **No parameter-transfer initialization** (v4 matched-capacity ablation showed no advantage).
- Support-conditioned specialist learning: reuse head with lowest 12-sample log loss when <= .61, otherwise allocate a zero-initialized head if capacity remains. At capacity, reuse best head. Every observed example receives one online sigmoid update to its assigned head. Fixed source grammar; no generated code executes.
- Freeze archive after 512 observed training labels per seed. Separate `cal` known-task support blocks, 12 per known task; `known` evaluation blocks, 12 per known task; `unrelated` unknown teachers 4–7, 12 blocks each; `near` teacher variants 8–11 formed by flipping the largest-magnitude weight of corresponding known task, 12 blocks each; and `shift` known task teachers with an irrelevant context-coordinate reversal, 12 blocks each. Every support block has 16 labeled examples. Query banks of 96 items per known task are reserved for measuring accepted known-skill correctness. No support/evaluation sample sharing or teacher-seed substitution. All splits drawn by disjoint deterministic PRNG streams. The near-known condition is a deliberately hard, partially identifiable negative challenge; score labels aren't available for threshold choice.
- Score each support block with *all* stored specialists (identical inference computation for all detectors). Candidate novelty score is the **minimum mean cross-entropy** across heads. Thresholds computed ONLY from `cal` known-task blocks, never from novelty, shifted, or known evaluation blocks. Quantile index: `ceil(0.90*N)-1`, sorted ascending; accept when score <= threshold.
- Detectors: `always_reuse` (no reject), `fixed61` (historical v4 threshold 0.61), `global_q90` (single 90th percentile of all calibrated known scores), `slot_q90` (90th percentile of calibration rows whose best head matches chosen head; if fewer than four rows use global threshold), `global_q90_margin` (global threshold and loss margin top-two < 0.02 triggers rejection); all use the same archive and support labels. The margin detector tests whether ambiguity helps novelty gating; it is not allowed new model capacity.

## Metrics, quality gates, and interpretation

Counts per seed: 48 calibration support blocks, 48 known, 48 unrelated unknown, 48 near-known unknown, 48 same-teacher context-shift controls; 16 support-label accesses/block, plus 96 query examples ×4 for known-task retained accuracy (query labels are evaluator-only, not provided to detector). Report known false rejection, unrelated and near true rejection, shifted false rejection, accepted known accuracy with abstentions counted wrong, and number of heads, gradient updates, support labels, and per-head score operations.

**All gates are required for claim of useful R2 memory protection:**
1. `global_q90` unrelated-task TPR improves on `fixed61` by >= 0.10 **and** known FPR <= 0.15.
2. `global_q90` near-known TPR >= 0.50.
3. `global_q90` shifted known-task FPR <= 0.15.
4. `global_q90` known-task accuracy with abstention scored as wrong >= 0.75.
5. `slot_q90` unknown-task (unrelated+near) TPR beats `global_q90` by >= 0.03 while known FPR <= 0.15.

Quantiles and thresholds above are frozen by this protocol. Do not tune after seeing scores. Cross-seed intervals are descriptive only; evaluator data and code are author-visible, not independent custody. No claim of scientific confirmation even if gates pass.

**Precommitted failure canaries:** (a) a frozen archive must have byte-identical weights before and after all calibration and evaluation; (b) `shift` labels match the same teacher functions as known and must not be counted as genuinely novel capabilities; (c) `near` teacher has a different true weight signature; (d) no training or detector ever accesses unknown teacher ID for routing; (e) labels and observations must be accounted separately to avoid inflating unique sample counts. 
