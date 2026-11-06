# R5 stress study — prescore protocol lock (PUBLIC; non-blind)

Written before scoring the 80-world/cohort primary run. The author already ran a three-world-per-cohort smoke test and unit tests on developer-known worlds; it is **not** independent confirmatory or blind evidence.

Objective: stress causal-effect estimation and action selection under near-null total effects, incomplete randomized treatment compliance (weak instruments), nonlinear extrapolation, and a confounder-strength sign flip.

Source implementation: `code/ace_research_causal/stress.py`. Planned analysis run:
```sh
PYTHONPATH=code python -m unittest ace_research_causal.test_stress -v
PYTHONPATH=code python -m ace_research_causal.stress --worlds 80 --output code/ace_research_causal/stress_results.json
```

Worlds: 5 disjoint seed intervals, 80 each: strong_linear 410000–410079; weak_compliance 420000–420079 (p=.06); near_null_effect 430000–430079 (absolute total effect <=.035, a magnitude <=.04); nonlinear_transport 440000–440079 (cubic response and sign reversal between local linear effect and long-horizon contrast); confounder_shift 450000–450079 (same do-contrast, sign-inverted hidden confounder at reevaluation). All are researcher-authored public simulation fixtures, not blind held-out real-world tasks.

SCM: exogenous U influences treatment X and outcome Y; mediator M=aX+noise; Y=bX+cM+gamma*X^3+dU+noise. Random assignment Z in {-1.5,-.5,+.5,+1.5}. Compliance is independently drawn Bernoulli(p). Compliers get X=Z; noncompliers retain U-correlated baseline X. Estimator observes Z, X, Y and M but never U. Counterfactual oracle evaluates full `do(X=+2)` vs `do(X=-2)`, NOT partial-compliance encouragement.

Matched learner training budget 160 rows per world (randomized IV/ITT vs passive observational). A separate no-learning random policy uses zero rows; not cost matched. Interventional estimators: IV-linear (Wald ratio on linear reduced form), IV-cubic (separate Z/Z^3 reduced form, same first-stage X~Z), ITT (incorrectly treats encouragement as full compliance), IV-cubic gated (same data, plus 32 zero-cost-for-label bootstrap replicates). Passive baselines: OLS-linear and OLS-cubic on 160 observational rows. Gated IV abstains if estimated compliance <.12 or resampled action sign consensus <.94. Equal oracle-row budget, unequal internal compute (bootstrap overhead reported). `iv_cubic` is *researcher-specified* cubic family, not discovered by ACE.

Metrics: world-level mean absolute true do-contrast, squared contrast error, planning regret relative to best +/-2 action, accepted action correctness, abstention, incorrect-accepted; paired bootstrap differences and empirical 95% world-resampling intervals (1200 draws). Separate sign-flip confounder probe uses 160 new rows per observational and IV arm and computes estimate drift (at equal additional evaluator cost). No test target/label fed to learners.

Precommitted falsifiers (exploratory criteria, not scientific significance):
H1: under strong_linear, IV-cubic mean regret at least 0.10 lower than passive cubic.
H2: under weak_compliance, gated IV abstention >=0.75 and accepted wrong-direction proportion <=0.10 **conditional on any acceptance**. If no acceptance, accuracy conditional on acceptance is undefined and not counted as proof of reliable selection.
H3: under nonlinear_transport, IV-cubic mean regret at least 0.10 lower than IV-linear; if no improvement, cubic structural features did not solve extrapolation.
H4: under confounder_shift, average absolute pre/post sign-flip coefficient drift for IV-cubic less than observational cubic.
H5: near_null_effect false-decision risk: gated abstention >=0.75 (regret must also be reported; trivial low regret alone is not progress).

All results, counterexamples, uncertainty, failed gates and caveats must be archived. Do not merge, change main, touch frozen E1.4, or claim OAIE/general causal intelligence. Separate scientific review, full exact-head CI and unknown-SCM family tests remain required.
