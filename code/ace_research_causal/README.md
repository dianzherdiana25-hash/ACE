# ACE R5 — Causal Intelligence: public synthetic experiment

Status: EXPLORATORY / not independently accepted / NOT evidence of OAIE.
Ownership: code/ace_research_causal/ only. Independent of frozen E1.4 and Scheduled S3. No live ACE policy integration, no edits to main or other research lanes.

## Reproduce (Python 3.10+, stdlib only)

    PYTHONPATH=code python -m unittest ace_research_causal.test_study -v
    PYTHONPATH=code python -m ace_research_causal.study --worlds 100 --output /tmp/causal_results.json

Executed locally with Python 3.13.5: 11/11 unit tests PASS, deterministic repeat on the checked seeds, full JSON summary archived in results.json. Source and test Git blob SHA were matched to the tested local bytes; this is NOT a full clean GitHub checkout, exact-head CI run, or third-party audit.

## Structural causal model and identification limit

A hidden Gaussian U influences X and Y:

    U ~ N(0,1)
    X = U + eps_x              unless do(X)
    M = a X + eps_m            unless do(M)
    Y = b X + c M + d U + eps_y

Noise standard deviations: X .25, M .25, Y .3; independent. Candidate edges a,b,c may be zero (probability .28) or signed nonzero (magnitude .8-1.6). Confounded worlds have d magnitude 1.3-2.0; unconfounded negative-control worlds have d=0. Every do intervention replaces a structural assignment. Fitters see only (X,M,Y), never U or structural coefficients; oracle evaluator privately uses the ground truth.

The model ordering and linear additive family are researcher supplied; this is restricted sparse edge/parameter identification, NOT general unknown-DAG causal discovery.

Arms: observational least squares on 80 observational rows; causal least squares on 40 do(X) rows (to estimate a) and 40 independent do(X,M) rows (to estimate b,c); random coefficients with zero row queries. Learning arms have exactly equal 80 training row-query budgets; random is a cheaper no-learning baseline, not compute matched.

Test requests: 8 queries for do(X), do(M), do(X,M) at values +/-1.25. The causal learner never sees do(M) in training. Metrics: intervention target-mean MSE; do(M) subset MSE; discrete do(X=+1) vs do(X=-1) action regret; additive same-unit counterfactual delta for changing X by +2; thresholded sparse edge F1 (threshold .45).

Mechanism shift changes exactly one of a/b/c (flip sign, or add previously zero edge). Static arms remain unchanged. Adapted arms refit on 32 NEW-regime training rows, 16 do(X) +16 do(X,M) for causal or 32 observational rows. No evaluation query or target is used for fitting.

Two disjoint public development cohorts: 100 confounded worlds (seeds 50000-50099), 100 unconfounded worlds (seeds 90000-90099). Each arm uses separate sampling RNG. The researcher chose design and thresholds; no prescore sealed bank or preregistered confirmatory hypothesis.

## Main results (100 confounded worlds)

| Method | Stationary intervention MSE | Stationary plan regret | Edge F1 | Shift-static MSE | Shift-adapt MSE |
| --- | ---: | ---: | ---: | ---: | ---: |
| Observational | 3.078365 | 0.477008 | 0.851667 | 8.910370 | 3.263981 |
| Causal | 0.281533 | 0.014764 | 0.976667 | 5.125858 | 0.938797 |
| Random | 5.062599 | 1.136539 | 0.637667 | 5.379247 | N/A |

Paired 2,000-resample bootstrap for causal minus observational:
- Stationary intervention MSE: -2.796831; 95% interval [-3.000097, -2.610758].
- Stationary plan regret: -0.462244; interval [-0.637672, -0.284106].
- Adapted shift intervention MSE: -2.325183; interval [-2.644568, -2.006121].

These are exploratory world-level simulation intervals, NOT independent confirmation.

## Failures, negative cases, alternative mechanisms

1. On specifically unseen do(M), the observational model WINS: stationary MSE 0.078706 vs causal 0.194598; under shift+adapt 0.264937 vs causal 0.601766. Causal outcome estimation uses only 40 joint training samples and still has latent U noise.
2. Without confounding, stationary MSE remains 0.040546 observational vs 0.010139 causal; the causal advantage may partly reflect observed predictor collinearity, not only backdoor-confounding correction. This is a negative-control cohort, NOT an observed negative performance result.
3. With mechanism shift and NO adaptation, causal MSE rises from 0.281533 to 5.125858, near the random shift MSE 5.379247. Current causal fit does not remain robust to structural changes automatically.
4. Nonidentifiability: SCM A X=U,Y=X and SCM B X=U,Y=U give exactly the same observational pairs for every U. Under do(X=1), their expected Y values are 1 and 0 respectively. No observational-only algorithm can distinguish those two worlds without further assumptions or interventions.

## Boundaries and next falsifiers

No general graph discovery, nonlinear SCMs, changing latent confounding, feedback cycles, selection bias, unknown intervention targets, unequal intervention cost modeling, real-world data, or genuinely unobserved model families. Counterfactual evaluation is exact only for additive same-noise interventions. No causal transfer across families is learned. No independent reviewer or full historical regression/Actions CI. This does NOT satisfy scientific evidence for OAIE. Keep as draft research-only branch pending independent validation.
