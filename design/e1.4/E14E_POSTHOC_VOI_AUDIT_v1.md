# ACE E1.4e — post-score value-of-information (VOI) identifiability audit

**Classification: POST-HOC DIAGNOSTIC, not prescoring evidence and not a new experiment.** Analysis reads the already-scored fixed E1.4e target bank from [raw data](../../evidence/e14/e14e_public_development_v1.json.gz), frozen science report at [E1.4e result](E14E_META_VALIDATED_QUERY_RESULT_v1.md). The original decision remains exactly `HOLD_META_VALIDATED_QUERY_TRANSFER`; this note does not change the prescoring decision gate, seed or score.

The report's `hindsight_ceiling` is the best score after trying all **eight** one-label question interventions, chosen retrospectively by an oracle with knowledge of final probe scores. This is an **unattainable diagnostic upper bound** for deployed unlabeled selectors on the same pool and fixed five-event candidate grammar. Its advantage over no-label measures whether a positive one-label opportunity even exists in each task.

| Family / regime | Tasks with any strict one-label improvement | No label correct | Best hindsight one-label correct | Upper possible gain |
| --- | ---: | ---: | ---: | ---: |
| Symbol / related | **0/3** | 19/24 | 19/24 | +0 |
| Symbol / unrelated | **0/3** | 21/24 | 21/24 | +0 |
| Graph / related | **1/3** | 20/24 | 22/24 | +2 |
| Graph / unrelated | **0/3** | 21/24 | 21/24 | +0 |
| **All target tasks** | **1/12** | **81/96** | **83/96** | **+2** |

Thus on this fixed scored bank, **three of four required strata cannot strictly beat no-label, even using an oracle hindsight one-label selector.** The frozen primary four-stratum GO gate (inherited strictly greater than no-label and all other controls in every stratum) was therefore **mathematically unattainable**, regardless of the source-trained strategy. This is a fundamental *benchmark identifiability / task opportunity* defect, not evidence that no learning algorithm could ever exploit query choice.

Extra source/meta training consumed 324 distinct label events for a benchmark whose best observed one-query target policy could produce only +2 total probe-correct across 12 targets, even with hindsight choices. This does not establish a useful amortized value-of-information return. The 636 actual oracle invocations include 96 duplicated target eight-label-reference calls; 540 independent label inputs were measured.

## Interpretation and next scientific gate

1. Preserve all E1.4e frozen artifacts and HOLD unchanged. Do not tune seeds, threshold, penalty or policy to rescue an impossible gate on this sample.
2. Start **E1.4f** as an independent public *benchmark-opportunity study*, rather than another transfer-policy pilot. Freeze a fresh task distribution, candidate grammar, probe prevalence, negative/both-wrong/out-of-basis stress cases and opportunity acceptance thresholds **before** scoring. Quantify the fraction of tasks where the *best* one-query policy actually beats no-label; report across families and source-target regimes.
3. Verify whether a policy using *unlabeled inputs* (no oracle access) can recognize opportunity under matched label budget; assess expected one-label random and strong informed references. If opportunity prevalence is too low to identify learning, stop using this bank as a GO criterion and redesign representation or task distribution rather than declare an intelligence-capability NO-GO.
4. Full E1.4-wide regression status remains unresolved (earlier run interrupted with partial `E`), and official Bubblewrap worker isolation was not validated. Neither gate can be silently treated as passed.

This audit was produced after seeing the E1.4e scores; treat every recommendation as a hypothesis for a **new preregistered** bank, never as retroactive confirmation.
