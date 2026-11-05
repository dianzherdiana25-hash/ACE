# R7.3 — Locked shift-aware selective prediction protocol

**Lock status: PRE-FINAL-SCORING**. This is a NEW bounded public-development experiment. R7.1/R7.2 results have been inspected and are excluded from confirmatory evidence. Their code may be used as baselines only. No sealed/independently custodied holdout is claimed.

## Hypothesis (falsifiable)
Can a fixed-cost, observation-only prior-shift test before acceptance reduce false capability claims relative to the R7.2 certificate selector on *new* shifted tasks while retaining useful stable coverage, under a budget of at most 24 synthetic labels per task?

## Precommitted tasks
Seed 20261107, distinct namespace `r73-new-world` and IDs prefixed by split. Six observable strata. Each world jitters base probabilities independently by uniform [-0.09,+0.09] with clipping to [0.01,0.99].
- source/stable: (0.18, 0.42, 0.63, 0.78, 0.91, 0.97);
- shift-A/reliability swap: (0.91, 0.19, 0.36, 0.54, 0.33, 0.72);
- shift-B/inversion: (0.90, 0.79, 0.29, 0.39, 0.17, 0.12).
Training 30 new stable worlds; validation 12 new stable worlds. Final: 24 new stable test, 24 shifted-A, 24 shifted-B. Split namespace and RNG are disjoint from R7.1 and R7.2. The shift mechanisms are publicly constructed, so this remains PUBLIC DEVELOPMENT.

## Algorithms — fixed before final evaluation
All methods use R7 original `Evaluator` for purchases and separate deterministic 64 probes/group for offline scoring. Policies NEVER receive latent probabilities.
- Random+LCB: random query allocation, fixed `Config(strength=12,z=1.0)`, >=3 observations/accepted group.
- R7.2 certificate: existing unmodified `next_certificate_group` and same fixed prior; early stopping permitted.
- Sentinel control: buy a fixed prefix of [group 4, group 5] repeated three times (6 labels), then R7.2 certificate selection with **no** shift rejection. This isolates prefix cost and exploration effects.
- Shift-aware: buy the same six sentinel labels; compute sequential posterior predictive log likelihood under the train-fitted Beta prior versus an uninformative Beta(1,1) model on precisely those same labels. Trigger `shift_detected` iff accumulated log Bayes factor (uninformative/source) **>= 2.0**. No unseen label or true probability can enter this check.
  - If no shift: continue the same R7.2 certificate selector using existing observations.
  - If shift: discard the source prior, replay the six purchased sentinel labels into Beta(1,1) for all strata. Buy 1 label for each of the four unvisited groups 0..3 while budget remains. Allocate residual labels greedily to the group with largest observed Beta posterior mean, breaking ties by seeded task-local group order; stop queries to a group once its LCB acceptance rule is met. Use LCB z=1.0 and min 3 target labels. If no viable uncertified group can be selected, abstain.
- At budget <6, sentinel-control and shift-aware acquire only the deterministic prefix and MUST NOT accept uninspected groups.
- No free labels for shift detection; diagnostic observations count against the same cap, including when a policy abstains. Online caps: 0,6,12,24.
- Oracle ceiling uses latent probabilities solely AFTER scoring, never as policy input.

## Precommitted metrics and success gate
At 24 label cap, compare **shift-aware vs R7.2 certificate**, and report random-LCB and sentinel-control. Report all budgets 0,6,12,24; true/wrong accepted, abstained, total purchases, per-decision false acceptance rate (null when no accepted decisions), per-label utility, ECE/Brier, how many tasks shift detector flagged, and oracle theoretical ceiling. Utility = 20*true accepts - 60*wrong accepts - 2*abstains - purchased labels.

**PASS gate (all required):**
1. On both OOD-A and OOD-B: wrong accepts no greater than certificate and at least one OOD exhibits strictly fewer wrong accepts.
2. On stable test: true accepts >=80% of certificate (same number of worlds) and wrong accepts no greater than certificate.
3. On at least one shifted family: true accepts >0 (prevent trivial always-abstain safety), and utility improved versus certificate on BOTH OOD families.
4. Total online labels never exceed 24*task count; report realized vs matched cap distinctly.

Any failed condition -> HOLD, regardless of calibration improvement. No post-final hyperparameter changes or split reruns for claiming success. Separate future unseen seeds + independently custodied evaluator needed before scientific acceptance.

## Required tests and audit
Tests must cover no oracle leakage, hard budget cap, deterministic replay, per-task shift diagnostics based on purchased labels, correct prior-reset replay, no re-reading score probes, no false-acceptance rate 0/0, and split separation. Run validation smoke first, then final scoring exactly once; record run command, Python version, SHA256 receipts, and all negative results.

Not authorization to merge PR, modify main/E1.4, run paid evaluation, or deploy candidate policies.
