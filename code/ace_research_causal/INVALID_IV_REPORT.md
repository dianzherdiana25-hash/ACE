# R5 — Instrument invalidity, heterogeneous compliance and decision costs

**Status:** exploratory, public synthetic, not independently accepted. No general causal discovery or OAIE result. All changes are confined to `code/ace_research_causal/` and PR #42 stays a draft.

## Reproduce

Python 3.10+ standard library only:

```bash
PYTHONPATH=code python -m unittest ace_research_causal.test_invalid_iv ace_research_causal.test_verify_invalid_iv -v
PYTHONPATH=code python -m ace_research_causal.verify_invalid_iv
PYTHONPATH=code python -m ace_research_causal.invalid_iv --worlds 100 --output /tmp/r5_invalid_iv.json
```

The archived result is lossless Base64(zlib(UTF-8 JSON)) in `invalid_iv_results.json.zlib.b64`. Raw 500-world JSON SHA-256:

`fe50505bbb126f5ce32f609baef3e51df1c1aab42cd364f9af3385353864c3d9`.

The local verification executed 16 instrument/policy tests + 5 adversarial replay tests (21/21 PASS). The independent simulation of population do(X) ATE under heterogeneous U, analytic countermodel, cost utility invariants, weak first-stage abstention, forgery detection and byte-identical fresh replay are covered. GitHub blob hashes for source, tests, archive and verifier match locally executed bytes. This is **not** independent peer review, a clean checkout, or exact-head CI.

Public [prescore protocol](INVALID_IV_PROTOCOL.md) was committed before the primary 100-world/group run. A small 2-world/group development smoke test preceded the lock. All worlds and assumptions are authored by the researcher.

## Structural assumptions, interventions and controls

The hidden U influences the baseline treatment X and outcome Y. A randomized binary Z encourages treatment with compliance probability logistic(logit(p0)+sU); otherwise baseline X is U-correlated. Outcome is Y=(tau+hU)X+dU+lambda Z+noise. True population do(X=+1) vs do(X=-1) contrast is 2*tau since E[U]=0; direct do(X) sets Z=0.

Groups (100 deterministic worlds each): `valid` (no direct Z effect, no compliance selection, homogeneous treatment), `direct_exclusion` (lambda≠0), `selected_compliance` (h and s nonzero), `both_invalid`, and `weak_first_stage` (compliance 8%). Treatments are randomized in the encouragement and direct-do arms. Learners see Z,X,Y only, never U, tau or structural parameters.

Equal 160 evaluator rows per learned arm. **Caveat:** the direct-do control has stronger experimental access than the IV arm and must not be mistaken for a fair capability-matched comparator. The random baseline receives zero training rows. IV bootstrap policy uses 64 in-memory resamples, so compute cost is unequal.

Policies select +1 intervention, -1 intervention, or abstention at fixed action costs 0, 0.5, 1.0. True utility is action*tau-cost for an action, zero for abstention; regret is maximum achievable utility minus chosen utility. The IV bootstrap gate rejects weak first stages or estimates whose signed bootstrap lower quantile does not exceed action cost. It is **not calibrated**, cannot certify exclusion validity and does not learn mechanisms beyond the supplied family.

## Main results (cost = 0.5; mean regret; lower is better)

| Cohort | IV point-cost | IV bootstrap-cost gate | Passive OLS point-cost | Direct-do point-cost | Always abstain |
| --- | ---: | ---: | ---: | ---: | ---: |
| Valid | **0.010847** | 0.047375 | 0.228478 | 0.006525 | 0.119498 |
| Direct exclusion violation | 0.579247 | 0.343090 | **0.283229** | 0.012509 | 0.127774 |
| Selected compliance, heterogeneous effects | 0.139281 | **0.072073** | 0.294081 | 0.023292 | 0.138049 |
| Both assumptions violated | 0.594720 | 0.466744 | **0.382464** | 0.015964 | 0.134154 |
| Weak instrument | 0.255863 | **0.125762** | 0.286425 | 0.010786 | 0.125762 |

**Abstention and error:**
- Direct-exclusion cohort: gate accepts 21 of 100 worlds at cost .5, **21/21 accepted actions have the wrong sign**.
- Both-invalid cohort: 31 accepted and **31/31 wrong sign**.
- Selection cohort: 51 accepted, 0 wrong sign, but cost-aware regret still exceeds privileged direct-do control.
- Weak-first-stage cohort: 0 accepted; error conditional on acceptance is **undefined**, not zero.
- Valid cohort: 38 accepted, 0 wrong, but IV point-cost regret is lower than cautious gated IV.

The gate reduces regret compared with always acting in every invalid cohort, but still performs *worse than always abstaining* in direct-exclusion and both-invalid worlds. It **must not** be considered a reliable instrument-validity detector.

## Falsification criteria — all five descriptive triggers observed, not scientific acceptance

- F1: valid IV improves on passive OLS at cost=.5 by **0.217631** mean regret, above declared 0.1 threshold.
- F2: direct-exclusion IV ATE MSE is **1.270526**, versus **0.018581** under valid instruments (failure of causal robustness).
- F3: selection-world IV regret **0.139281** vs privileged direct-do **0.023292**, gap 0.115989 > 0.1.
- F4: gated IV improves vs always-acting IV regret in three invalid cohorts, but still has catastrophic conditional wrong-sign decisions on direct-exclusion and both-invalid worlds.
- F5: both-invalid IV ATE MSE **1.745192** vs direct-do **0.025538**.

For direct-exclusion, bootstrap gate minus IV point-cost regret is -0.236157 (paired descriptive percentile 95% interval [-0.328836,-0.155788]); for both-invalid it is -0.127975 ([-0.207963,-0.060287]). These represent simulation-world variation, not outside-the-study confidence guarantees.

## Constructive identification obstruction

With perfect compliance X=Z, outcome Y=tau X+lambda Z+epsilon. Models (tau=+0.4, lambda=-0.8) and (tau=-0.4, lambda=0) induce exactly the same joint distribution (Z,X,Y) but **different outcomes under do(X)**. No estimator using only those variables can distinguish the models by infinite encouragement data without additional identifying assumptions. More bootstrap resamples cannot resolve structural non-identifiability.

## Decision and limitations

**Scientific gate = NOT_ASSESSED; no merge.** This benchmark tests one researcher-designed IV family with parametric forms and hand-chosen failure magnitudes. It does not show autonomous recovery from invalidity, nonlinear graph discovery, general causal reasoning, externally validated calibration or efficient information acquisition under real intervention costs.

Next stage should study adaptive requests for a small number of directly randomized do(X) samples *at explicit higher cost*, and require prespecified detectability/uncertainty thresholds. Include countermodels where no intervention is available and refusing action is the only defensible behavior. Any claim of robust causal intelligence must survive an independently designed, family-disjoint evaluator and exact-head CI.
