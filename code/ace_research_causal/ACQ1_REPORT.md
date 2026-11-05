# ACE Research R5 — ACQ1 active causal identification (costed direct-do queries)

**Status:** exploratory / development-only, negative results preserved. This is a fully synthetic causal economics test, **not** a successful general-causal-intelligence result. No merge or deployment.

## Locked protocol and provenance

- [ACQ1_PROTOCOL.md](ACQ1_PROTOCOL.md) committed on branch `research/chat-r5-causal` at `9589bfbba16a9c29c884210fa6dfd436d3b832f0` **before the primary 100-world-per-cohort evaluation**. The researcher authored the world family and policy triggers. Small implementation smoke tests used 2–3 worlds; not blind preregistration.
- `acq1.py`: bounded acquisition policies, separate per-arm direct-do ledger, cost-sensitive action utility and cohort-budget-matched random control.
- `test_acq1.py`: 17/17 local tests passed, including strict 32-query cap, balanced batches, identical requested do-row prefix across arms, equal initial 160 rows, cost accounting, null accepted-case error when no actions, deterministic replay.
- `test_verify_acq1.py`: 6/6 additional tests passed for archive manipulation, byte-replay disagreement, underestimated query costs and mismatched randomized acquisition budgets.
- [acq1_results.json.zlib.b64](acq1_results.json.zlib.b64): 19,010-byte raw JSON losslessly archived via zlib+base64. Raw SHA-256 = `3a0dd2d04d3737377f5f9e50fa9df4f77534747c8ef01c0a2b12171721e9d4d8`.
- `verify_acq1.py`: fail-closed archive digest and **full byte-identical 500-world replay**, and independent cost/accounting checks.

Execute with Python standard library only, from repository root:

```sh
PYTHONPATH=code python -m unittest ace_research_causal.test_acq1 ace_research_causal.test_verify_acq1 -v
PYTHONPATH=code python -m ace_research_causal.verify_acq1
PYTHONPATH=code python -m ace_research_causal.acq1 --worlds 100 --output /tmp/acq1_replay.json
```

The committed ACQ1 source and test Git blob checksums match the tested local files exactly. Local validation was rerun with **byte-exact GitHub `invalid_iv.py`**, blob SHA `c27bd617496044a7f00b27d21e837523f0a54b89`, plus a local copy of the `stress.ols` function checked against its GitHub source. The **23/23 tests and byte-identical 500-world replay PASS** in this arrangement. However, this is still **not a complete clean exact-HEAD checkout, exact-head Actions CI, or independent reviewer execution**; reproduce independently before accepting any scientific claim.

## Identification & matched controls

Every world begins with the same **80 encouragement + 80 passive observational** rows. Both IV and OLS are estimated from these data, with latent U and true tau inaccessible to the policies. Conditional purchases of directly randomized `do(X)` rows bypass the compliance mechanism. If bought, 8-row balanced packets are issued, up to 32 rows, at **0.0125 utility per direct sample**. Taking a nonzero action costs an additional **0.50 utility**. Total net regret = optimal utility - realized action utility + paid direct query cost. This differs from comparing pure predictive accuracy, and prevents free-oracle advantages.

Policies: never buy, always buy 32, IV uncertainty trigger, IV/OLS discrepancy trigger, staged discrepancy-triggered 8+24, and offline **random matched 32** with exactly the same per-cohort total direct-label spend as the discrepancy policy. Random budget matching uses only the count of initial-row triggers, not ground-truth outcomes, but it is cohort-level and **not a deployable world-local control**. Shared sample prefixes ensure inter-policy paired stochastic comparisons.

Five new non-overlapping public world seed ranges, each 100 worlds: valid 710000–710099, direct exclusion 720000–720099, U-selected compliance 730000–730099, both invalid 740000–740099, and weak first-stage 750000–750099. The underlying world generator is the **same researcher-specified family** as previous R5 study, not new out-of-family generalization or learned causal structure.

## Results: mean net regret per world (lower is better)

| Cohort | No buy | Always 32 | Uncertainty 32 | Disagreement 32 | Staged 8+24 | Budget-matched random 32 |
|---|---:|---:|---:|---:|---:|---:|
| Valid | **0.0201** | 0.4252 | 0.2321 | 0.3810 | 0.3177 | 0.3815 |
| Direct exclusion broken | 0.6190 | 0.4287 | 0.5336 | 0.5431 | 0.5505 | **0.5080** |
| U-selected compliance | **0.1085** | 0.4452 | 0.1516 | 0.3284 | 0.2769 | 0.3586 |
| Both invalid | 0.6858 | **0.4290** | 0.6852 | 0.4799 | 0.4803 | 0.4788 |
| Weak first stage | **0.3211** | 0.4355 | 0.3572 | 0.3950 | 0.3487 | 0.3837 |

This is a **failed acquisition heuristic**, not a success report. No single policy wins across all five cohorts; the cost-sensitive decision must depend on correctly anticipating whether direct intervention access is valuable, and the current IV/OLS disagreement trigger cannot do that reliably.

### Prespecified falsifiers

- **F1 FAIL.** Under direct exclusion, disagreement improves on no buy by only **0.075866** (declared >=0.10). Paired bootstrap discrepancy minus no-buy = -0.075866, percentile interval [-0.144629,-0.002094]; statistically favorable on this synthetic distribution, but short of the **prespecified magnitude**.
- **F2 FAIL.** Disagreement vs cost-matched random = **+0.035068** net regret under direct exclusion (CI [-0.034980,+0.111394]) and **+0.001098** under both invalid (CI [-0.060327,+0.061895]). The heuristic does not demonstrate better allocation of direct experimental samples.
- **F3 FAIL.** With valid instruments, discrepancy raises net regret by **+0.360889** (CI [+0.330036,+0.389237]); 89 of 100 worlds unnecessarily buy 32 do rows. Sampling cost dominates.
- **F4 PASS but weak.** Under both-invalid, staged buys **2,520 instead of 2,688 direct rows** across 100 worlds and increases mean net regret by **+0.000318** (CI [-0.021235,+0.025115]); small savings without evidence of greater causal identification.
- **F5 PASS as a method-failure warning.** Under direct-exclusion violation, uncertainty-only trigger still suffers **0.5336** net regret (>0.20), because an invalid instrument can yield a precise but biased estimate.
- **F6 REJECTED by design.** The two observationally equivalent exclusion-violation SCMs from the previous R5 study remain nonidentifiable without direct interventions or other assumptions. This experiment does not prove general causal intelligence; `scientific_acceptance = NOT_ASSESSED`.

### Other negative outcomes

Under selected compliance, discrepancy-triggered acquisition raises net regret from **0.1085** (no buy) to **0.3284**; adding information hurts when the prior actionable estimate is already good enough relative to the acquisition price. Under weak instruments, full 32-row direct purchasing lowers action-regret from 0.3211 to 0.0355 but **adds 0.40 sample cost**, yielding a worse 0.4355 net regret. Purchased information cannot be judged only by prediction gains.

Break-even direct-row price (net regret of acquisition equals no buy, holding observed sample/action outcomes fixed): discrepancy trigger costs become competitive at about **0.01706** in direct exclusion and **0.02016** in both-invalid, but only **0.00239** in selected-compliance and **negative** in valid worlds. Current price 0.0125 is unfavorable in most cohorts. These are postscore *descriptive sensitivity calculations*, not a tuned or prespecified new policy.

## Research gates

**Engineering within local tested scope:** PASS (23 focused tests + deterministic 500-world replay). **Independent full HEAD:** NOT RUN; GitHub Actions status must be inspected, and merged-branch regressions have not been run. **Scientific claim:** NO GO / NOT ASSESSED. Do not modify main, frozen E1.4, or agents' folders, and do not merge this PR.

Next falsification should compare **robust value-of-information bounds under ambiguous SCM sets** against naive confidence thresholds, under a separately authored unseen mechanism family and action/payoff prices. A defensible system should be able to decline purchasing further data when it cannot establish that information is decision-relevant. Never treat longer search or more oracle queries as intelligence by itself.
