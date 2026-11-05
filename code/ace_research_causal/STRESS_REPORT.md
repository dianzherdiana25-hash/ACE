# ACE Research R5 — stress test: near-null effects, randomized noncompliance, nonlinear transport

**Classification:** PUBLIC EXPLORATORY ONLY. No independent research acceptance, causal discovery of unknown graph, or OAIE claim.

## Git provenance and prescore record

- Branch: `research/chat-r5-causal`; PR #42, draft. Main and E1.4 preserved.
- Public prescore protocol: `STRESS_PROTOCOL.md`, committed before the primary 80-world/cohort evaluation. Development smoke test was performed on 3 worlds/cohort **before** protocol lock; the results are **not blinded or confirmatory**.
- Exact source: `stress.py`; focused independent tests: `test_stress.py`.
- Raw replayable JSON is archived losslessly as `stress_results.json.zlib.b64`, UTF-8 Base64(zlib(JSON)). Raw JSON SHA-256: `95f0ce45cf6a53692cd95ff81ff9ab4e15dcb6863c8a396306c7ae4ce39ed1f7`. Git blob hash and content were read back from the R5 branch.
- Verifier: `verify_stress.py`, checks SHA-256, cohort count and byte-identical fresh run; checks descriptive predeclared criteria separately from scientific acceptance.

Reproduce (Python 3.10+, standard library only, no paid evaluator):

```sh
PYTHONPATH=code python -m unittest ace_research_causal.test_stress -v
PYTHONPATH=code python -m ace_research_causal.verify_stress
PYTHONPATH=code python -m ace_research_causal.stress --worlds 80 --output /tmp/r5_stress.json
python -c "import pathlib,base64,zlib; p=pathlib.Path('code/ace_research_causal/stress_results.json.zlib.b64'); pathlib.Path('/tmp/r5_archive.json').write_bytes(zlib.decompress(base64.b64decode(p.read_text().strip())))"
cmp /tmp/r5_stress.json /tmp/r5_archive.json
```

Locally executed: **16/16 stress unit tests passed**; separate fully deterministic 400-world replay matches archived JSON byte-for-byte. Exact GitHub blob SHAs match local executed code/tests. This is NOT an independent third-party execution on a clean checkout; no exact-head GitHub Actions is claimed.

## Model and baselines

Structural model: latent U influences both X and Y; mediator M=aX+noise, outcome Y=bX+cM+gamma X³+dU+noise. Randomized encouragement assignment Z takes {-1.5,-0.5,0.5,1.5}. Only independent compliers receive X=Z; other units retain a U-correlated baseline X. **Do(X)** at +/-2 is scored analytically, and differs from **encouragement Z** under imperfect compliance. This exclusion, independence and homogeneous response structure are author-supplied identification assumptions.

Each learned arm uses 160 rows/world. Interventional estimates: naive ITT (does not correct noncompliance), IV linear, IV cubic. Passive controls: observational OLS linear and cubic. `iv_cubic_gated` uses 160 IV-cubic rows plus 32 extra *computational* bootstrap resamples with no additional evaluator rows; abstains on estimated first-stage <0.12 or unstable action-sign consensus. The random policy uses **zero evaluator rows**, not cost-matched. Confounder transport probes use an additional 160 rows per IV and observational estimator.

Metrics: mean planning regret for selecting between do(X=-2) and do(X=+2), prediction squared error of do-contrast, abstention, accepted wrong-sign fraction, and estimate drift after d->-d. We deliberately exclude exact count of program-generated candidates or unknown graph learning; these are not implemented.

## Main score (80 worlds/cohort; smaller regret is better)

| Cohort | IV cubic | IV linear | Observational cubic | IV cubic gated | Random |
|---|---:|---:|---:|---:|---:|
| Strong linear, compliance 70% | 0.2517 | **0.0000** | 1.7674 | 0.8060 | 2.1106 |
| Weak compliance 6% | 1.7082 | **0.7134** | 2.0843 | 1.9785 | 1.6936 |
| Near-null total causal effect | **0.0331** | 0.0362 | 0.0371 | 0.0332 | 0.0361 |
| Nonlinear sign reversal | **0.1596** | 1.1811 | 2.0471 | 0.9510 | 2.5286 |
| Hidden confounder sign shift | 0.2663 | **0.0000** | 2.1591 | 0.9715 | 1.9464 |

The cubic specification improves nonlinear extrapolation, but is substantially worse than the simple IV-linear estimator when the true mechanism is linear. The extra flexibility incurs finite-sample variance. Neither one is a learned general-purpose causal mechanism architecture.

Paired 1,200-resample percentile intervals for IV-cubic minus observational-cubic planning regret:
- Strong linear: -1.515708, interval [-1.997344,-1.069363].
- Weak compliance: -0.376068, interval [-0.971812,+0.234543], **crosses zero**.
- Near-null: -0.004004, interval [-0.015000,+0.006697], **crosses zero**.
- Nonlinear transport: -1.887554, interval [-2.372024,-1.395284].
- Confounder shift: -1.892847, interval [-2.361817,-1.404264].

## Predeclared criteria results

| Criterion | Outcome | Interpretation |
|---|---|---|
| H1: IV cubic improves strong-linear regret over observational cubic by >=0.10 | **MET** | Mean improvement 1.5157; weaker than IV linear nevertheless |
| H2: weak compliance yields >=75% abstention and <=10% wrong among accepted | **NOT ASSESSABLE IN FULL** | 100% abstention, 0 accepted; wrong rate conditional on acceptance is undefined |
| H3: cubic improves nonlinear-transport regret over linear IV by >=0.10 | **MET** | Mean improvement 1.0216 |
| H4: confounder-shift IV estimator has lower pre/post drift than observational | **MET** | 2.7954 vs 10.8289 |
| H5: near-null gated abstention >=75% | **MET, BUT UNSAFE ACCEPTANCE** | 88.75% abstention; 44.44% wrong among accepted actions (4 wrong of 9 accepted) |

## Explicit negative results and counterexamples

1. **Weak instruments defeat precision:** compliance 6% produces IV-cubic mean squared do-contrast error **12,345.1**, far above the 1,018.3 of IV linear. The naive ITT baseline can have lower regret than high-variance IV cubic; not evidence that ITT estimates true intervention magnitude.
2. **Abstention is not free:** on strong linear worlds it raises regret from 0.2517 (ungated) to 0.8060 (gated), and on nonlinear transport from 0.1596 to 0.9510. Suppressing wrong actions is not equivalent to improving overall decision utility.
3. **Near-null false acceptance:** in 80 near-null worlds the gate accepts 9; 4 accepted actions have the wrong sign, conditional wrong rate 44.44%. Low aggregate regret here arises primarily from tiny true treatment effects, not reliable sign identification.
4. **Weak-compliance criterion indeterminate:** with zero accepted decisions, the gated method cannot demonstrate positive predictive reliability; report H2 as indeterminate rather than pass.
5. **Conservative models generalize poorly to new nonlinear target horizons:** linear IV incurs regret 1.1811 in the nonlinear sign-reversal cohort while cubic IV scores 0.1596. This result depends on a researcher-provided cubic feature, not autonomous causal mechanism discovery.
6. **Confounder transport is by construction:** flipping d to -d leaves true do(X) contrast unchanged. On the shifted cohort IV coefficient drift 2.7954 is smaller than observational 10.8289; however with weak compliance IV drift averages **129.4959**, much worse than observational 11.0085. The IV stability is conditional on instrument strength.

## Evaluation validity, boundaries and next falsification

All synthetic structures, priors, feature families and sampling rules are visible to the researcher. This experiment identifies a total effect under exogenous encouragement and independent compliance, not unknown causal DAGs, confounding front doors, latent nonlinear confounders, noncomplier selection bias, or individualized counterfactuals. Bootstrap percentile intervals are descriptive for this synthetic sample, not registered inference on real environments. Neither independent reviewer approval nor exact-head CI has occurred.

Next: adversarial exclusion violations (Z affects Y directly), compliance depending on U or Z, near-zero instrument ratios, robust uncertainty calibration and explicit cost-aware action-value policy. Do not promote into ACE live control without independent evidence.
