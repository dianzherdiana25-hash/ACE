# ACE Research R5 — ACQ2: EVPI as a conservative purchase upper bound

**Scientific gate: NOT ASSESSED / no OAIE claim.** This is public synthetic development, not an independent, blinded benchmark. ACQ2 is an isolated addition to `code/ace_research_causal/` in draft PR #42. Do not merge or deploy.

## Evidence and reproducibility

The prescore public protocol is `ACQ2_PROTOCOL.md`, committed at `b8d5919d8cc2e3d17f5cb395ceb322d76168ad3d` **before** the full 100-world/cohort run. The researcher saw the synthetic model family, wrote the priors and policy rules, and ran a two-world smoke check. No hidden-task or preregistered scientific acceptance is claimed.

From the repository root (Python 3.10+, standard library only):

```bash
PYTHONPATH=code python -m unittest ace_research_causal.test_acq2 ace_research_causal.test_verify_acq2 -v
PYTHONPATH=code python -m ace_research_causal.verify_acq2
PYTHONPATH=code python -m ace_research_causal.acq2 --worlds 100 --output /tmp/ace_acq2_replay.json
```

- 17 ACQ2 invariants and 7 verifier/adversarial tests passed locally (**24/24**).
- Additional available legacy ACQ1 tests plus ACQ2 tests: **47/47 PASS** locally. The old `test_invalid_iv.py` suite was unavailable in the local workspace and was NOT run in that regression, so this is not an entire historical ACE suite.
- Full 500-world deterministic replay across all three prices produced a **67,890-byte JSON**, SHA-256 `c5cc9245aae3d7017adafef526eae2cb4d0d41c5ef4d98ad6573817819ebea84`. Stored losslessly as Base64(zlib(JSON)) in `acq2_results.json.zlib.b64`; `verify_acq2.py` checks digest, accounting and fresh byte-identical replay. Independent tamper tests reject manipulated digests, mismatched spend, false conditional-error denominators, and unmatched random-control budgets.
- GitHub blob SHAs of the locally executed `acq2.py`, tests, verifier and compressed result have been read back and compared, **but independent full clean exact-head checkout/CI is still open**.

## Design and identification caveats

Five cohorts, 100 new world seeds each: valid (810000+), exclusion violation (820000+), selected compliance (830000+), both invalid (840000+), and weak instrument (850000+). All use the **same author-specified SCM family** and data-generating functions as previous R5 studies, not out-of-family evidence. Every policy sees identical 80 randomized-encouragement rows plus 80 passive observation rows. Direct interventions cost 0.0025, 0.0125, or 0.025 utility units per sample; queries are capped at 32, in deterministic balanced batches. Action cost is 0.5.

Heuristic candidate interval: `tau ∈ [-1.5, 1.5] ∩ [IV ± 1.2/|first_stage|]` if usable; otherwise fall back to the whole prior range. The 1.2 factor combines an **assumed** upper bound 1.0 on direct instrument effects and ad hoc 0.2 sampling tolerance. It is **not a confidence interval or a rigorously identified set**, especially under U-selected compliance. An analytic uniform-on-interval working belief defines EVPI: the optimistic difference between perfect-information expected utility and optimal current expected utility. A 32-row purchase is rejected whenever EVPI ≤ its total cost. **Passing the EVPI gate is never a promise that finite samples will improve utility.**

Compared arms: IV no-buy, uniform-belief no-buy, maximin robust no-buy, EVPI-triggered 8-row and 32-row direct interventions, always-buy-32, ACQ1 disagreement-triggered 32, offline random-matched-32 at identical cohort label spend, and always-abstain. The offline random control is not deployable (its selection count depends on cohort-wide observable trigger counts). An outcome evaluator privately uses true tau **only after all purchase and action decisions** to compute net regret and interval coverage.

## Measured mean net regret (smaller better)

| Cohort | IV no-buy | Uniform-belief no-buy | EVPI-32 at 0.0025 | Matched random at 0.0025 | EVPI-32 at 0.0125 | Robust maximin no-buy |
|---|---:|---:|---:|---:|---:|---:|
| Valid | **0.024835** | 0.117143 | 0.103764 | 0.103764 | 0.117143 | 0.123558 |
| Exclusion invalid | 0.604602 | 0.156579 | **0.119587** | 0.119587 | 0.156579 | 0.138596 |
| Selected compliance | 0.146780 | **0.077787** | 0.107005 | 0.107005 | 0.077787 | 0.112002 |
| Both assumptions invalid | 0.639426 | 0.319884 | 0.183122 | **0.153152** | 0.319884 | **0.123654** |
| Weak first stage | 0.333919 | 0.116885 | 0.109242 | 0.109242 | 0.116885 | 0.116885 |

At the standard 0.0125 price, EVPI-32 buys **zero** samples in every cohort; the resulting performance reflects **the chosen uniform-belief no-buy action**, not evidence that purchase targeting improved. At cheap 0.0025, it buys 100/100 valid, 100/100 exclusion, 97/100 selected, 92/100 both-invalid and 100/100 weak worlds, so there is essentially **no useful selectivity**.

At cheap price, evpi32 minus equal-budget random net regret:
- Exclusion: 0.000000, descriptive bootstrap interval [0,0] (both always buy).
- Both invalid: **+0.029970**, interval [-0.044984,+0.109944]. The proposed EVPI heuristic is worse on average, with uncertainty crossing zero; no targeting improvement is established.
- Selected compliance: 0.000000; nearly all worlds buy.
- Valid and weak first stage: 0.000000; all worlds buy.

The researcher-imposed candidate interval covers true tau in 100/100 valid, selected and weak worlds, 96/100 exclusion worlds and only **78/100 both-invalid worlds**. It should never be advertised as a valid 95% confidence region or a general partial-identification guarantee. The maximin no-buy policy largely abstains in ambiguous worlds; low regret can follow from **avoiding actions**, not discovery of true mechanisms.

### Prescored criteria

- F1 cost accounting: **PASS**, independent verifier checks query cost and capped acquisition.
- F2 budget-matched random control: **PASS**, exact total direct rows matched per cohort/price.
- F3 EVPI targeting improves by ≥0.02 over matched random in *both* invalid cohorts at cheapest price: **FAIL**. Exclusion difference 0; both-invalid policy worse by 0.02997.
- F4 standard-price valid-world regret penalty ≤0.05 vs IV no-buy: **FAIL**, penalty **+0.092308**, descriptive 95% interval [+0.066479,+0.118228].
- F5 nonincreasing 32-row purchase counts as price rises: **PASS** (price response, not an intelligence result).
- F6 general causal intelligence: **REJECTED/NOT IDENTIFIED**.

## Critical methodological conclusions

1. EVPI is a sound *upper-bound concept* **conditional on a specified belief**, but the data-derived belief itself is not validated. Here it largely becomes an all-or-nothing purchasing rule.
2. Abstaining under model ambiguity is often safer, but broad abstention is not proof of learned causal intelligence, and it sacrifices utility when the valid IV estimate already supports effective action.
3. Candidate sets derived from a known bound on exclusion-direct effect can miss the truth under selected compliance and heterogeneity. More bootstrap or sample queries cannot repair assumption failure automatically.
4. At standard prices, EVPI32 versus matched-random comparisons are not pure acquisition-policy comparisons: both purchase zero, but their **no-purchase action rules differ** (uniform-belief vs IV). Interpret such differences as policy effects, not evidence of query targeting.
5. No real-world causal mechanism recovery, learned interval calibration, independently designed holdout, exact-head CI, or positive OAIE result has been demonstrated.

**Next falsifier:** explicitly construct alternative plausible SCMs with the *same observable training likelihood* and different interventional outcomes. Evaluate the value of *8-row actual noisy samples* (expected value of sample information, EVSI), not EVPI, with independently calibrated observation noise and mandatory cost accounting. A new model-family-disjoint holdout should remain sealed from research-policy authors until selection is frozen.
