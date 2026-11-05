# ACE R7.6 — preregistration: adaptive diagnostics, fresh certification, bounded cost

**PRE-SCORE LOCK: 2026-11-06**. This preregistration precedes R7.6 implementation and any R7.6 final scoring. Author-visible synthetic development, **not** an independent sealed scientific evaluation.

## Hypothesis
A two-stage six-group diagnostic selector buys fewer labels than uniform two-per-group diagnostics, while retaining coverage of groups 2/3 and not increasing harmful capability acceptance under a fresh conditional anytime-valid e-process. This is a trade-off test, not a claimed solution.

## New worlds, frozen in advance
- New RNG namespace `r76-new-world`, labels `r76-purchase`, evaluator scoring `r76-score`. Source/validation/final IDs disjoint from R7.1–7.5.
- Six groups, Bernoulli true reliability p. Truth: p≥0.80. Each family base with independent U[-0.09,+0.09] jitter, clipped [0.01,0.99].
- Families: stable [0.18,0.42,0.63,0.78,0.91,0.97], swap [0.91,0.19,0.36,0.54,0.33,0.72], reverse [0.90,0.79,0.29,0.39,0.17,0.12], new01 [0.86,0.94,0.22,0.68,0.14,0.24], new23 [0.21,0.34,0.96,0.91,0.27,0.11], all_null [0.55,0.62,0.70,0.73,0.75,0.77] clipped ≤0.799, correlated same stable base but acquisitions copied in within-group pairs (violates i.i.d. premise). **Additional new** near_boundary [0.77,0.79,0.80,0.81,0.82,0.78], tests sensitivity to boundary.
- Offline source fit: 18 stable train worlds, 12 purchased labels per group/world = 1296 labels charged separately. Validation 12 disjoint stable worlds.
- Final **four** predetermined seeds 20261112/13/14/15, 20 worlds per seed per family, 8 families => **640 final worlds**, scored exactly once after implementation freeze. All families are author-designed; four seeds are bounded replications, not truly independent scientific holdout.
- Per-world acquisition budgets [0,6,12,18,24], 64 independent evaluator-only scoring probes per group. No purchased labels from scoring, no paid evaluator.
- Deterministic SHA256-derived RNG. All policies see only purchased outcome (group,label), group IDs, a source-trained prior. Latent p, outcome probes and privileged oracle ceiling never enter policy.

## Frozen algorithms
Each policy makes **at most one capability acceptance decision per world**, with other groups counted as abstentions. Candidate selection is independent from fresh certification evidence (no diagnostic label reuse).
- `narrow6` control: diagnostic groups [0,4,5] twice in that order, 6 purchased labels, choose highest hit count (tie by source prior, then lower ID).
- `full12` control: [0..5] twice, 12 purchased, choose highest hit count with same ties.
- `broad6` control: [0..5] once, 6 purchased, choose highest hit count (tie by source prior).
- `adaptive10` proposal: [0..5] once, then choose top **two** groups by (first observed success, source prior, negative group ID). Buy two further labels for each shortlisted group, in round-robin top-two order (4 more labels). Choose final candidate from this shortlist by (observed success fraction, source prior, negative group ID). The four extra diagnostics are charged. No OOD-specific heuristics, no hidden-world inference.
- `random6` control: buy one label/group then select group via independent seeded random pick.
- `abstain6` negative control: one label/group, always abstain.
- If cap is below required diagnostic count, buy only available prefix and abstain. If no remaining budget for certification, abstain.
- Fresh certificates use per-outcome likelihood ratio `p1/p0` for success and `(1-p1)/(1-p0)` for failure, null p0=0.80, fixed p1=0.99. Accept when E≥10 after ≥3 fresh certificate outcomes, stop early on accept or at cap. The conditional null p≤0.8 one-candidate Ville bound applies only under independent stationary Bernoulli assumptions; not guaranteed for correlated family or across multiple tasks.
- All methods get **same** task budget and same potential acquired-outcome stream for each (world, group, occurrence). Diagnostics can change which occurrence goes to certification but not the underlying stream.

## Metrics and decision gate locked before scoring
For every method/family/seed/budget: correct accepts, wrong accepts, abstentions, purchases, ECE, Brier, false-acceptance rate (null when zero acceptances), correct accepts per 100 purchased labels, total utility `20×correct − 60×wrong − 2×abstained − purchases`, selected group histogram, oracle upper bound, per-seed breakdown. Report training + validation selection cost separately. Report confidence intervals or pooled variability only as descriptive across 4 seeds, not a population guarantee.

**R7.6 PASS requires all** at budget 24:
1. `adaptive10` true accepts on new23 **strictly greater** than `narrow6`.
2. Correct acceptance on stable **≥80%** of `full12`, and no increase in stable wrong accepts.
3. Total wrong accepts across stable + four shifted + all_null + near_boundary **≤ full12**.
4. Total predeclared utility over stable + four shifted **≥ full12** AND **≥ broad6**, counting every purchased label.
5. All online budgets obey cap; no multiple certificates, no oracle leakage. Correlated family is **stress only** and must be reported, without applying i.i.d. safety claims.

Any failure => HOLD, no promotion or merge. Full-suite exact-head CI and independent evaluator custody are separate acceptance gates and are not assumed.

## Sequence
Commit this protocol; write self-contained source and unit tests; run validation-only smoke; commit final code and tests; read back Git blobs; run test suite; run the new final bank **once** with stdout saved and hashed; perform separate result-only arithmetic audit; record both positive and negative outcomes; retain draft PR #43. Do not modify main, E1.4 frozen research, other-team folders, paid evaluators or Tod.
