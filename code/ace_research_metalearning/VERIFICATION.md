# ACE R4 — execution/readback verification

## Tested source and evidence
- Private GitHub source re-fetched at blob `e1ba03a5e9e78690393317449bc1aefbaafb9cf3` for `study.mjs` (12,412 source characters).
- Prescore JSON was durably committed at `e20246b74002e98e1b6be08ed5a1fb3caff0583c` **before** running any OOD task scoring in this study.
- Original OOD result JSON committed in later commit `de7306d0388dd6614b405e25d51d68f383729114`.
- After source readback, 10 guardrail checks returned PASS, and **4/4 OOD seeds** were deterministically recomputed with the GitHub source's unmodified research function bodies and matched every archived per-seed JSON byte-structure after parse/stringify.
- CLI line-ending bug was detected by source readback and corrected at commit `3ece26a24d3a7ffae65b66e1e0dd998e027ad9bd` before exact readback replay.
- Post-hoc diagnostic from `posthoc_balanced.mjs` blob `3ba0612d5c3d8a90b0616dad4e39efae79f86179` was re-executed from GitHub source in the same isolated JavaScript executor; **4/4 seeds** exactly match `posthoc_balanced_results.json`.

## Research findings and negative controls
- Original H1 k4 unqueried accuracy: meta 67.81%, strongest comparator static-finetune 69.58%, **−1.77 percentage points** against the strongest comparator. H1 fails the prespecified +5 pp gate.
- Post-hoc balanced k4 full-domain accuracy: meta **55.44%** versus scratch **57.80%** and static-finetune **57.66%**. No rescue by class balancing.
- Sparse concepts have 3 positives among 24 inputs: an all-negative model gets **87.5% raw accuracy without adaptation**. Consequently the 80% raw-accuracy adaptation-speed metric is potentially misleading. Post-hoc audit is explicitly nonconfirmatory.
- Meta-fitting consumed 2,466,192 evidence-pair operations and 5,568 exposed source/validation labels across four repeated seeds, not counting target-stage work.

## Explicit unverified gates
- Exact Node.js ESM CLI and `node --test` have **not** been executed on a clean local checkout.
- GitHub Actions exact-head integration is **not** evidenced; existing ACE E1.5 workflow does not match this new directory.
- The JavaScript executor executed the source's research function bodies; it did not import the full Node entrypoint, measure real CPU/memory in a controlled runner or provide OS sandboxing.
- No independent evaluator-owned hidden holdout, confidence interval, production task, or verified OAIE gain.

This file is engineering evidence only; no merge authorization.
