# ACE Research R2 v5 — Calibrated novelty gating for lifelong memory protection

**Research lane:** R2 Continual & Lifelong Learning.
**Protocol before source/scoring:** `R2_V5_PRESCORE_PROTOCOL.md`, commit `9a6aa661f4a6046bd7fc94fe5bb0877679107dc3`.
**Scientific state:** `HOLD_NO_VALIDATED_MEMORY_PROTECTION`, public deterministic development; no OAIE claim.

## Research question

R2 v4 achieved ~82.6% accuracy for known aliased-context tasks using 12 labeled routing examples, but rejected only 20% of unknown fifth-task supports. To avoid catastrophic forgetting through accidental new-task updates, v5 tests whether known-task-only calibration of the *minimum specialist log loss* improves the ability to distinguish unseen functions from previously stored skills. Archive weights stay unchanged across calibration and evaluation; in that sense v5 tests admission/protection, **not new-skill acquisition**.

## Dataset and controls

Five fixed seeds; four synthetic 12D sparse signed-linear teachers, sequence [0,1,2,0,3,1,2,0], 64 observed training examples per episode, first 12 used for routing, up to four independent heads (no parameter-transfer initialization after v4 negative result). After 512 train labels the archive is frozen. For each seed: 48 labeled calibration support blocks (known tasks), 48 independently sampled known evaluation blocks, 48 new unrelated teacher blocks, 48 new near-known teacher blocks (largest weight sign flip) and 48 same-known-rule context-shift controls. Each block has 16 support labels. Evaluation known-task predictive accuracy uses a separately generated 96-item query set per task; same query set is re-used across support blocks **and must not be counted as independent labels**.

Models and methods share the *same trained archive*, support examples, and per-block specialist-loss evaluation. Methods: accept-all, fixed 0.61 threshold, global known-calibration q90, per-slot q90, and global q90 with two-specialist margin rejection. Threshold calibration uses known calibration blocks only; no unseen-task labels in selection. No task ID is supplied to specialist inference.

## Actually observed results — means across five author-visible seeds

| Gate | Fixed .61 | Global q90 | Per-slot q90 | Global + margin |
| --- | ---: | ---: | ---: | ---: |
| False reject on known tasks | .10833 | .08333 | .09167 | .11667 |
| False reject on same-rule context shift | .08333 | .07917 | .07917 | .11250 |
| True reject on unrelated new tasks | .68750 | .69583 | **.77083** | .71250 |
| True reject on near-known new tasks | .69167 | .64167 | **.72083** | .66250 |
| Combined unknown true rejection | .68958 | .66875 | **.74583** | .68750 |
| Known accuracy with abstention counted wrong | .75195 | **.76467** | .75508 | .74123 |

Always-accept known accuracy = .81897 but never rejects novel tasks (TPR 0). This accuracy comparison is not an equal-coverage measure because abstentions count wrong. The leading slot-q90 novelty result trades a slightly higher known false-rejection rate for improved novelty sensitivity, with a 4-expert maximum and the same labeled support budget.

**Paired descriptive seed contrasts:** slot q90 minus global q90 combined TPR +.07708 (five-seed exact resampling range +.03750 to +.11667), global q90 minus fixed .61 unrelated TPR +.00833 (range -.09583 to +.14583). These intervals are *descriptive only*, not independent inferential confidence intervals. No non-synthetic trial family was used.

## Precommitted gate disposition: 4/5 pass, 1/5 fail

1. Global calibration improves unrelated TPR over fixed .61 by >= .10 and has known FPR <= .15 — **FAIL** (+.00833, FPR .08333).
2. Global calibration near-known TPR >= .50 — **PASS** (.64167).
3. Global calibration shifted same-rule false-reject <= .15 — **PASS** (.07917).
4. Global calibration known-task accuracy counting abstentions as wrong >= .75 — **PASS** (.76467).
5. Per-slot calibration combined unknown TPR >= global by .03 with known FPR <= .15 — **PASS** (gain .07708, known FPR .09167).

The compound scientific gate remains **HOLD**. The result suggests **memory-specific threshold calibration** is worth an independent follow-up, *not* an accepted continual-learning or autonomous novelty-discovery result. Parameter-transfer superiority was previously falsified in v3/v4; this study does not reverse that finding.

## Evidence and accounting

`r2_v5.js` source was committed before execution and then read back directly from GitHub blob `5087c8606575acecb78cffa746617fd3f89ae4cc`. Source-level deterministic checks (18 invariant families) passed; all five seed runs and 240 block groups per seed were computed with fixed non-network random generators. Full result, including all calibration thresholds, per-block decisions, support scores, teacher signatures, and per-seed archive hashes: `R2_V5_RESULTS.json`.

A separate **output-only arithmetic audit** (`audit_v5.js`, `R2_V5_AUDIT.json`) recomputed the q90 thresholds, slot-wise fallback rules, every method's accept/reject decision, group rates, predictive accuracy arithmetic, teacher-signature consistency and frozen-head equality. It passed. Logical accesses across five seeds: 2,560 observed training labels; 3,840 calibration support labels; 15,360 evaluation support labels; 70,260 specialist prediction calls including training routing. This is not 19,200 independent real-world examples or CPU-time profiling.

## Known limits

- Synthetic sparse sign tasks and manually created near-known rules may make novelty recognition easier than natural tasks. Five seeds give weak coverage and cannot support broad generalization claims.
- Novelty detection is **support-supervised**: 16 labels per block are supplied to make the detection decision. It is not zero-shot.
- The per-slot gain measures selection among existing frozen specialist heads; it **does not demonstrate learning unknown tasks**. Memory preservation is mechanistically guaranteed by no parameter updates during test, rather than empirically demonstrating long-horizon resistance to forgetting while acquiring a new skill.
- The same stored heads and support blocks underlie all detectors; aggregate treatment arms and their confidence intervals are correlated.
- The separate auditor is independent *arithmetic code* evaluating the author's data, not an independent evaluator, held-out natural task family or threat-model isolation audit.
- There is no verified clean-checkout Node.js / GitHub Actions CI at R2 HEAD, nor sealed independent confirmatory evaluation.

## Reproduction

```bash
cd code/ace_research_lifelong
node r2_v5.js > R2_V5_REPLAY.json
node audit_v5.js R2_V5_REPLAY.json
```

The code requires Node.js and the standard library only; no external paid evaluator. Exact bytes of output should match `R2_V5_RESULTS.json` from the same source; if not, stop without changing claims.

## Next falsifiable work

Commit a *new* task family before looking at labels; evaluate novelty under nonstationary rule drift, unknown-task online admission/update, retention measured both before and after new-task learning, with matched-capacity heads and support-label budgets. Require independent task generation and exact-HEAD Node clean-checkout CI before scientific promotion. Keep PR draft and no main or frozen E1.4 modifications.
