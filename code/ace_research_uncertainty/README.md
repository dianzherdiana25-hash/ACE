# ACE Research R7 — Uncertainty & Active Learning (public pilot)

**Scientific decision: HOLD / negative.** This is an isolated local research
pilot, not an ACE deployment gate. No E1.4/E1.5 change, paid evaluator,
external oracle, source rewrite, network access, or OAIE claim.

## Hypothesis and comparisons

Can uncertainty-based query selection prevent false capability acceptance
at bounded evaluation cost without sacrificing all useful coverage?

There are six observable strata per task with hidden Bernoulli success
probabilities. A stratum is truly acceptable when p >= 0.80. The selector
sees only group identifiers and purchased binary outcomes. Private hidden
truth is used by evaluator scoring and a privileged oracle ceiling, not
by any acquisition policy.

- fixed: round-robin acquisition, posterior mean >= 0.80 after three labels;
- random: random acquisition, same posterior-mean gate;
- random_lcb: the same random query sequence as random, source prior and
  posterior lower confidence bound for acceptance;
- active_lcb: highest posterior-SD/proximity-to-target query priority,
  same prior and LCB rule as random_lcb;
- oracle_upper_bound: ground-truth ceiling (evaluation only), not a
  deployable policy or fair label-cost baseline.

LCB = posterior mean - z × posterior SD; each stratum requires >=3 target
observations before acceptance. Strength candidates {0,2,6,12} and z
{1.0,1.64,2.33} selected by validation asymmetric utility, then ECE tie
break. This is NOT a formal coverage-guaranteed confidence interval.

## Data isolation, budgets and cost accounting

- 30 stable train tasks, 2,160 offline source-training labels;
- 12 separate stable validation tasks, 12 candidate configurations;
- 20 distinct stable test tasks; 20 distinct shifted-mechanism OOD tasks;
- online per-task budgets 0, 6, 12 or 24 purchased synthetic labels;
- identical, evaluator-only 64 probe outcomes per stratum for scoring;
- no evaluator probes reused as purchased labels, no test/OOD tuning;
- Python stdlib only, deterministic seed 20261105, no external calls.

This is a public synthetic simulation; its in-process evaluator is NOT a
security barrier for a real private evaluator. Source-training and validation
tuning labels must not be confused with target acquisition costs.

## Observed local pilot, 24 purchased labels per task

Each split has 120 stratum decisions; each non-oracle method spent 480 labels.

| Split | Method | Correct accepted | Wrong accepted | Abstain | ECE | Brier |
|---|---|---:|---:|---:|---:|---:|
| test | fixed | 30 | 8 | 82 | 0.056467 | 0.178429 |
| test | random | 20 | 5 | 95 | 0.048228 | 0.187431 |
| test | random_lcb | 20 | 0 | 100 | 0.034333 | 0.156140 |
| test | active_lcb | **0** | **0** | **120** | 0.029380 | 0.156096 |
| ood | fixed | 12 | 8 | 100 | 0.034549 | 0.211791 |
| ood | random | 10 | 7 | 103 | 0.046067 | 0.216890 |
| ood | random_lcb | 1 | 5 | 114 | 0.200243 | 0.287742 |
| ood | active_lcb | **0** | **0** | **120** | 0.279584 | 0.307476 |

Oracle ceiling: 48 truly good test strata; 21 OOD. At both 6 and 12
labels, active_lcb likewise accepted 0 of 120 test strata. Validation
gave all 12 active candidate configs equal utility (-144), so the chosen
strength=12, z=1.0 arose from ECE tie-breaks, not verified utility gain.

**Negative finding:** active uncertainty sampling has no demonstrated
sample-efficiency gain: it abstained on every evaluated stratum. Its zero
false accepts are trivial zero-coverage outcomes, and its false-acceptance
RATE is undefined (0/0), not 0% risk. Shifted OOD caused high ECE and
Brier error in source-prior LCB policies. In contrast, matched random_lcb
accepted 20 true/0 false on test, but 1 true/5 false on OOD.

## Reproduction and integrity

From a compatible checkout of the branch, Python 3.10+:

    PYTHONPATH=code python3 -m unittest ace_research_uncertainty.test_experiment -q
    PYTHONPATH=code python3 -m ace_research_uncertainty.experiment > /tmp/ace_r7_result.json
    sha256sum /tmp/ace_r7_result.json

Observed compatible local run: **11/11 PASS**, deterministic repeated run.
Full pretty-printed stdout SHA-256:
6add3863c4d1f080baadc3486dee5052cd37206704446ea75e07e4d0654d564e

Local code/test blob SHA matches the bytes read back from GitHub after upload.
This is NOT an exact-head GitHub Actions pass, independent audit or a sealed
holdout test. Existing E1.5 workflow triggers only for ace_loop changes,
not this owned research directory.

## Limits and next falsification

The active heuristic prioritizes uncertainty rather than safety-adjusted
expected acceptance value, and wastes labels on strata it cannot certify.
Under shifted hidden probabilities, stable source priors become misleading.
Six visible fixed strata, one deterministic seed, synthetic predictions and
in-process scoring do not establish real ACE generalization. These public
test/OOD results have already been inspected; further tuning must use NEW,
precommitted independent splits, not re-use this bank as fresh confirmation.
Future work must evaluate utility-per-label, risk-vs-coverage curves, shift
detection and direct ACE semantic-aliasing counterexamples under an
independently custodied scorer.

Decision remains **HOLD; no promotion, no merge**.
