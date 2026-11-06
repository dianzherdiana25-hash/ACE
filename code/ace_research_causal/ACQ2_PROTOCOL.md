# R5 ACQ2 — Robust value-of-information upper bounds (prescore public protocol)

Date: 2026-11-06. Commit this protocol **before** the primary evaluation and preserve outcome-negative results. The module is independent and confined to `code/ace_research_causal/` on `research/chat-r5-causal`, stacked on draft PR #42. Do not modify main, E1.4, other teams, or merge.

## Hypothesis and falsifiers
Can a conservative policy use *expected value of perfect information* (EVPI) as an upper bound to refuse direct intervention purchases that cannot pay for themselves, without erroneously treating this upper bound as achieved value-of-sample-information?

Precommitted public evaluation: 100 new seed values in each of five R5 SCM cohorts, `valid` 810000–810099, `direct_exclusion` 820000–820099, `selected_compliance` 830000–830099, `both_invalid` 840000–840099, and `weak_first_stage` 850000–850099. Reuse `invalid_iv.world`, `invalid_iv.one`, and equal 80 encouragement + 80 passive observations from `acq1.initial_rows`, never the true tau inside a policy. These are **new seed ranges within the same author-specified SCM family**, NOT independent new families. Sealed external confirmation remains open.

Prices for a new balanced direct `do(X)` sample: `0.0025`, `0.0125`, and `0.025` utility per row, action cost `0.5`. Maximum 32 do rows, purchased in 8-row balanced batches, with deterministic shared-prefix sampling and per-policy query accounting. No interpolation of free samples. Evaluation utility: action*tau-action_cost, zero for abstain. Net regret: oracle-optimal action utility minus policy utility + per-row purchase price.

## Identification assumptions and declared approximation
The IV coefficient is approximately `tau + lambda / first_stage` under homogeneous effects and valid random encouragement. Assume *externally imposed*, unverified bounds `tau in [-1.5, 1.5]` and `|lambda| <=1.0`. To account heuristically for estimation noise, use `radius = (1.0+0.2)/abs(first_stage)`, capped by the prior range. The candidate interval is `[-1.5,1.5] intersect [IV-radius, IV+radius]`. If the intersection is empty, if IV/first-stage is not finite, or if `|first_stage|<0.12`, **fall back to the full prior interval** (fail open in uncertainty, not artificial certainty). These intervals are not calibrated frequentist confidence sets; under U-selected compliance/heterogeneous effects, even their structural bound can be invalid. This limitation must be reported.

For a uniform distribution on the interval (a **researcher-imposed working belief, not a learned posterior**), compute exactly: 
- `V_current = max(0, E[tau]-0.5, -E[tau]-0.5)`
- `EVPI = E[max(0, |tau|-0.5)] - V_current`
using analytic integrals, no Monte Carlo approximation in the gate. This is an optimistic bound on value of *any* information under that working belief, not an estimate of 32-row information gain. If `EVPI <= 32*row_price`, a 32-row experiment cannot pay its price under that assumption; otherwise it **may still be wasteful**.
- `evpi32`: buy all 32 direct rows only if EVPI exceeds their price, otherwise use belief-optimal action; after buying use direct-do linear estimate and action threshold, not the true tau.
- `evpi8`: buy 8 do rows if EVPI exceeds 8-row cost; after buying use direct-do estimate and act, with no further purchases (a deliberately cheap but noisy control).
- `robust_no_buy`: maximin action over interval, which selects action only if its worst-case utility is positive; no purchase.
- `bayes_no_buy`: use uniform-belief optimal action; no purchase.
- Comparators `iv_no_buy`, `always32`, and `disagreement32` from ACQ1; `random_matched32` is an *offline* fixed-count-per-cohort random purchase schedule matched to `evpi32` direct-row budget, not a deployable real-time policy; `abstain` always takes no action.

## Declared test criteria
F1 (cost-accounting): for all worlds and policies, query cost equals actual do rows × price; total direct rows <=32 and evaluation uses no true tau to set purchase decisions.
F2 (matched control): evpi32 and random_matched32 buy exactly the same total rows **per cohort and price**.
F3 (generalization): evpi32 mean net regret improves by >=0.02 vs matched random in **both** direct_exclusion and both_invalid at price 0.0025. If not, evidence of targeting skill is **rejected**.
F4 (no unnecessary information): at standard price 0.0125, evpi32 mean net regret on valid worlds must not exceed iv_no_buy by more than 0.05; otherwise it is not a useful fallback.
F5 (price sensitivity): within each world, the evpi32 purchase decision must be nonincreasing as price increases; the **observed net regret need not** be monotonic and must be reported separately.
F6 (adversarial near-null and unknown structure): winning against simple baselines is not scientific acceptance. No generic causal reasoning/OAIE claim without independent family-disjoint evaluator, identification coverage, and independent exact-head runtime.

Report negative results, accepted wrong-sign rates with denominators, acquisition coverage, intervals and out-of-scope identifiability. Bootstrap 1,000 paired world resamples on major contrasts is *descriptive* only. Save a canonical JSON report, digest and deterministic verifier; no live provider calls or payment.
