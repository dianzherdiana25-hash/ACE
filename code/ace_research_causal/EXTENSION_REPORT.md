# ACE Research R5 — nonlinear / unknown direction / rewiring extension

**Research classification:** EXPLORATORY (author-visible public synthetic worlds). **No OAIE, general causal discovery, or independent scientific acceptance claim.** This is a follow-on to R5's separate linear study, not an E1.4 replay. Everything remains inside code/ace_research_causal/.

## Run and verify

Python 3.10+ standard library only, no network, paid evaluator, arbitrary source execution or external data:

```sh
PYTHONPATH=code python -m unittest ace_research_causal.test_extension -v
PYTHONPATH=code python -m ace_research_causal.extension --worlds 80 --output /tmp/extension_replay.json
cmp /tmp/extension_replay.json code/ace_research_causal/extension_results.json
sha256sum /tmp/extension_replay.json
```

Local execution: Python 3.13.5; **15/15 tests PASS**; a separate rerun of all 240 worlds generated **byte-identical JSON**, SHA-256 `7dea5fa002aba8661f0013ea8b11f7f39d3f474a390d0767ef30fc77e2d1ba00`. Exact Git blob readbacks for extension.py, test_extension.py, and extension_results.json matched locally executed files. This does **not** constitute independent third-party review, GitHub Actions CI, or a fully clean exact-head checkout.

## Predefined structural family

For each world, hidden U ~ N(0,1). The causal parent/root (either X or M) is U + Gaussian noise (sd .25). Child = a*root + q*root^2 + h*root^3 + Gaussian noise (sd .2). Outcome Y = b X + c M + t X M + p X^2 + r M^2 + d U + Gaussian noise (sd .25).

The direction X→M vs M→X is hidden **from the causal learner**. World generation uses balanced alternating directions. Signed coefficients have bounded magnitudes; no zero-strength parent-to-child mechanism is sampled. The cubic coefficient h is zero in the first two cohorts and nonzero in the third; all fitted mediator models remain quadratic. d=0 is the unconfounded negative-control cohort.

Training world IDs are 600000–600079 (nonlinear with confounding), 700000–700079 (nonlinear no confounding) and 800000–800079 (cubic model misspecification, confounded). Each *world* is independently generated and fitted; there is **no meta-training across worlds**. These ID bands separate public development cohorts; they are NOT a sealed split against the researcher.

Each learned arm receives exactly 120 training oracle rows. Causal: 30 randomized do(X), 30 randomized do(M), 60 randomized do(X,M). From single-variable randomized responses, compare fitted quadratic effects to infer direction, fit the child mechanism from the inferred parent intervention, and fit Y on 60 joint rows **plus** 30 rows from the intervention judged to randomize the causal parent (90 Y rows). Ablation `causal_joint_only` consumes the **same 120 query rows** but fits Y on 60 joint rows only. If inferred direction is wrong, pooling can incorporate confounded samples; this failure is deliberately not masked.

Observational control: 120 passive samples, fitted quadratic mediator/outcome. `observational_oracle_direction` is **given the true direction**, an *unfair advantage* in its favor to isolate coefficient/causal-effect identification. `observational_fixed_direction` always assumes X→M and is the naive observational arm. Random coefficients require zero evaluator rows; not cost-matched, only a lower-bound comparator.

All training intervention settings are uniform in [-1.2,+1.2]. Evaluation target settings are +/-1.5, i.e. held out from the training intervention **support** (bounded extrapolation), not just the training sample. Test mean targets use a separate exact analytic SCM oracle for do(X), do(M), do(X,M). Planner chooses one of four do(X=+/-1.5) or do(M=+/-1.5) interventions maximizing estimated mean Y. Regret is true optimal reward minus reward of selected action. Counterfactual delta metric is the *average* same-exogenous-noise do(X=+1.5) minus do(X=-1.5) contrast, not personalized unobserved counterfactual inference.

Rewiring changes only graph orientation, leaving numerical coefficients constant. Static models are not retrained; adapted models consume an **additional** 120 same-type oracle rows from the changed world. The `observational_shift_adapt` baseline is again given postshift true orientation. Data leakage is prevented within each fit because evaluation truth is computed in the independent scoring path, but the **researcher** designed all environments and can inspect all data.

## Results (80 worlds / cohort, lower is better)

| Cohort | Causal MSE | Observational (oracle direction) MSE | Causal direction accuracy | Causal planning regret | Observational planning regret |
|---|---:|---:|---:|---:|---:|
| Nonlinear, confounded | **1.527752** | 3.580280 | 0.9375 | **0.354013** | 0.703704 |
| Nonlinear, no confounder | **0.075894** | 0.140154 | 0.9875 | 0.019362 | **0.004307** |
| Cubic (out-of-grammar) | **1.638252** | 3.880730 | 0.8875 | 0.353052 | 0.636325 |

World-paired 1,600-sample percentile bootstrap for causal-minus-oracle-observational MSE:

- Confounded: -2.052528; exploratory 95% interval [-2.606100, -1.535691].
- Unconfounded: -0.064260; interval [-0.112975, -0.009966].
- Cubic: -2.242478; interval [-2.763000, -1.755652].

Counterexamples and important negative results:

1. **Better prediction is NOT sufficient for better decisions.** In the unconfounded cohort the causal arm has worse regret, +0.015056 relative to the oracle-direction observational arm, bootstrap interval [+0.000820,+0.032976]. Any acceptance metric reporting only MSE would miss this failure.
2. In the cubic cohort, regret improvement -0.283273 has a bootstrap interval [-0.684133,+0.042191] crossing zero: no clear planner superiority on this cohort.
3. **Graph rewiring without adaptation fails:** confounded causal MSE 1.527752 → 2.684914 and its direction accuracy 0.9375 → 0.0625; cubic 1.638252 → 4.145758. Postshift re-learning with an extra 120 rows restores mean MSE to 1.412142 and 2.114385 respectively; not zero-cost resilience.
4. In unconfounded rewired settings, causal shift+adapt MSE 0.216341 is WORSE than the oracle-direction observational 0.148988, and its planning regret 0.030140 vs observational 0.004976.
5. Causal outcome pooling helps substantially in confounded worlds, MSE 1.527752 vs `causal_joint_only` 3.194216, **despite identical acquisition cost**. This is a within-design ablation, not a general proof; wrong orientation can make pooling unsafe.
6. Direction errors persist (6.25% confounded, 11.25% cubic). This benchmark only has two predeclared candidate directions and relatively strong edges; its high accuracy is not evidence of unknown-DAG reconstruction.
7. The held-out cubic is *out of the fitted grammar*, but **not genuinely blind** to the experiment designer. The observed MSE advantage does not establish novel primitives or broad causal generalization.

## Caveats / scientific gates

No nonlinear general graph discovery, latent structure learning, unknown intervention targets, edge-null worlds, genuine external holdout, distributional selection bias, cycles, noncompliance, costly-action optimization, individually identified counterfactuals, or true open-ended learning. The model knows the 3-variable node set and polynomial outcome form. Scores are development-only, all worlds are public, bootstraps describe this synthetic distribution and do not independently validate the hypothesis.

Next falsification: add near-zero effects, randomized noncompliance, changed hidden-confounder strength, and a *precommitted* family-disjoint third-party evaluator. Reject any general causal intelligence / OAIE claim until these and independent exact-head tests pass.
