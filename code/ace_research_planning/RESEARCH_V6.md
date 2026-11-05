# ACE R6 v6 — empirical-Bayes online value-of-information (public synthetic study)

**Scientific verdict: HOLD / NEGATIVE RESULT.** Local implementation and replay work; neither independent hidden evaluation nor useful autonomous reasoning capability growth has been shown. No OAIE, no scientific GO, no deployment or merge authorized.

## Motivation and falsifiable hypothesis

R6 v5 found that active probing never beat the strong no-probe comparator after accounting for sensor cost, and the selected online switch was identical to a predefined control. R6 v6 therefore asks a narrower question: **Can a risk estimator learned from labelled training worlds make better online probe decisions than the validation-selected fixed rule under the same paid search/probe resource budget?** Our default null hypothesis is no paired positive utility gain, even if the risk probabilities are more calibrated.

Conceptual background: Russell & Wefald, *Principles of Metareasoning* (Artificial Intelligence 49, 1991, DOI `10.1016/0004-3702(91)90015-C`). Decision-theoretic reasoning treats information/computation as instrumental only insofar as it improves downstream external action. This study is not an implementation or validation of their full theory.

## Ownership and baseline

- Branch: `research/chat-r6-planning`; draft PR #41. Modified files exclusively under `code/ace_research_planning/`. Frozen E1.4, ACE `main`, Codex, other research and Red Team files untouched.
- Existing `online_v5.rollout` now accepts an **optional** decision callback while preserving its byte-level *default return shape and algorithm behavior*. It gets only `visible_world`, current attempted edge, number of completed steps, observed opens/closures, and whether a closure was discovered. Callback return: `(should_probe: bool, extra_work_units: nonnegative integer)`.
- Each callback pays one work unit; a probe pays two more. Learned/top-ranked salient controllers pay `ceil(E/4)` metered feature-setup units. Posterior updates add `floor(open_edges/4)` work units. These are **instrumented proxy costs, not FLOPs or latency**; all six v6 policies use the same planning backend and work cap.
- Source is not executed as arbitrary generated Python; no external actions, network, paid or hidden evaluator.

## Data-generation protocol (deliberately disclosed)

- Five disjoint seed ranges: training 52100+, validation 53100+, matched IID transfer 54100+, mechanism-shift transfer 55100+, negative no-shock transfer 56100+.
- Main run uses **12 seeds × 3 families = 36 training worlds**, **8 × 3 = 24 validation worlds**, and **12 × 3 = 36 worlds** per transfer regime. Training and IID transfer share family types (`ordered_grid`, `free_grid`, `terminal_portal`) but have disjoint seeds. Mechanism-shift and no-shock worlds use `interior_portals`, `gated_bypass`, and `weight_shift`, which were already author-visible in earlier R6 studies: do **not** call this independently blinded OOD generalization.
- The generator selects a single hidden blocked edge with probability 0.85, otherwise leaves the world static. It considers solvability-preserving edges only, determined by an evaluator-owned Dijkstra oracle **before** a planner is run. A high-risk set of three edges is determined from *visible* cost/degree/portal features **without reference to any contestant's path**. Under aligned risk, 90% of sampled closures are drawn from this set when eligible; shift reverses preference to other edges. This generative construction is intentionally human-designed and easy to overfit. The no-shock transfer has no closure. Worlds without eligible closure remain in the dataset as static, never discarded based on policy success.
- Every policy sees the same worlds and actual shocks. The online agent does not see which regime it is in, the selected hidden edge, oracle route costs, or future labels.
- Prediction model: train-only Beta-smoothed per-edge two-class frequencies (`salient` vs `ordinary`), plus the fitted probability of *any* closure. Normalize per-edge prior mass to the fitted shock frequency; after observing edges open, update with `p(edge | observations)=p(edge)/(1 - Σ p(known_open))` under the stipulated one-shock assumption. The decisions use a fixed one-step approximation: probe when `p(blocked) × 6 > 0.5 + 2 × 0.04`. This is **not** an estimated full replanning or physical world model.
- Baselines: `never`, `always`, `salient` (same public high-risk class, predefined), `anti_salient`, and `global_voi` (uninformative prior). Baseline selected once using validation **before creating transfer worlds**. Learned VOI policy not retuned on transfer. All modes use fixed hierarchical replanning to isolate sensing policy, not compare search paradigms again.
- Work ceilings 300 and 900 units; search expansions limited to 1800. Same v5 main synthetic utility: success `1000 − 120 × (travel_cost/reference −1) − 0.04 × work_units − 6 × failed_actions − 0.5 × probes`; failure `−200` minus the resource/failure/probe penalties. Hindsight Dijkstra reference is evaluator-only and is a lower bound, not information the online planner has.

## Actual local evidence

Reproduce (Python 3.10+, stdlib only):

```bash
PYTHONPATH=code python -m unittest ace_research_planning.test_planning ace_research_planning.test_study_v2 ace_research_planning.test_study_v3 ace_research_planning.test_study_v4 ace_research_planning.test_study_v5 ace_research_planning.test_study_v6 -v
PYTHONPATH=code python -m ace_research_planning.study_v6 --n-train 12 --n-validation 8 --n-transfer 12 --output /tmp/ace-r6-v6.json
```

- **72/72 tests PASS** (56 historical, 16 new). Determinism confirmed by two complete runs with byte-identical JSON files (file SHA256 `894e2f4b4254d6cbdcc7c4c66915d494191f3186f33be3f1e7d45f6c34c4a156`). Canonical report digest excluding its own digest field: `17201ce57393c15d59601e9b291b5b7130fad45f74457de25b7db2b86c1fc7a8`.
- **168 worlds × 6 policies × 2 budgets = 2,016 rollouts**; 108 worlds and 1,296 rollouts are transfer. Model trained on 36 worlds (30 latent edge closures), with estimated salient-edge raw risk 0.21875, ordinary raw risk 0.00201005 and overall shock frequency 0.81579; per-world priors are normalized to that frequency.
- **Validation-selected fixed comparator = `never` for both 300 and 900 units**; selected controls are recorded and serialized into the SHA256 pretransfer model/selection receipt. This receipt is an in-process ordering audit, not immutable external escrow.

### Transfer scores (36 paired worlds per regime per budget)

| Condition | Budget | Learned success | Fixed-never success | Learned − fixed mean utility | Descriptive 95% seed-cluster bootstrap |
|---|---:|---:|---:|---:|---:|
| Aligned IID | 300 | 36/36 | 36/36 | **−0.956111** | [−1.557222, −0.282222] |
| Aligned IID | 900 | 36/36 | 36/36 | **−0.956111** | [−1.557222, −0.282222] |
| Shifted risk + mechanism | 300 | 32/36 | 36/36 | **−133.890667** | [−233.795710, −34.623376] |
| Shifted risk + mechanism | 900 | 36/36 | 36/36 | **−1.558333** | [−1.898889, −1.193889] |
| No shock + new mechanism | 300 | 36/36 | 36/36 | **−1.560000** | [−1.738889, −1.373889] |
| No shock + new mechanism | 900 | 36/36 | 36/36 | **−1.560000** | [−1.738889, −1.373889] |

Cluster bootstrap is deterministic, descriptive, 1,999 resamples over **12 seed clusters** (three correlated family tasks each). Not an independently designed statistical significance test or proof of population generalization.

### Prediction calibration versus decision utility

| Transfer | Fitted Brier (all edges) | Uniform risk Brier | Learned probe count | True positives |
|---|---:|---:|---:|---:|
| Aligned IID | **0.01057039** | 0.01368174 | 25 | 4 |
| Shifted risk (cap900) | 0.01663475 | **0.01444839** | 31 | 1 |
| No shock | 0.00284099 | **0.00020511** | 26 | 0 |

A calibrated risk estimate can become *operationally inferior* if sensing decisions are too expensive or priors shift. The learned model and **researcher-defined salient probe rule** produce exactly the same successful action/probe outcomes on all 36 IID cases at both budgets, and all 36 shifted cases at 900. Learned VOI has lower utility than this strong manual control because its posterior maintenance costs extra work; no original sensing policy emerged.

### Counterexamples, no result filtering

- Shifted / budget300: failed cases: `(55100, weight_shift)`, `(55101, gated_bypass)`, `(55102, interior_portals)`, `(55110, weight_shift)`. All four complete under fixed never-probe baseline. Notably, **55100 fails even with zero probes**, from model/decision overhead alone. 55101 also fails despite zero probes. 55110 fails after one *true-positive* probe: correctly identifying a hazard did not rescue the budget.
- Risk-class model is intentionally miscalibrated after the shift. Aligned transfer has 28/108 salient edges actually blocked and 2/2054 ordinary; shifted transfer has 3/108 salient and 29/2074 ordinary. Uniform risk beats the fitted model on shifted and null-hazard samples. This is a deliberate adversarial falsifier, not a newly discovered broad failure distribution.
- The training model uses complete simulator labels, not independently purchased real-world information; 36-world fitting sample is small. The no-shock arm is an extreme shift, not an IID test. Stronger baselines could be devised. Work-unit proxy charges count events, not wall time, FLOPs, feature sort complexity, or the **offline generator/oracle**; route-quality reference is not achievable by an agent without knowledge of the shock.

## Negative result and acceptance gate

**Hypothesis rejected on this public benchmark:** better probability estimates in the aligned setting **do not** result in better paid online information acquisition. Learned VOI is dominated by the validation-selected fixed no-probe baseline across all three tested transfer regimes and both budgets, and matches the human-written salient rule's actual decisions on most cases.

Next experiment, not performed here: independent evaluator-owned, truly unfamiliar task families with richer observation actions, unknown/learnable hazard changes, strong Bayesian/partially observable planning controls, calibrated computation/latency metering, and durable pre-registered model freezes. Test risk-adaptive stopping and *value of computation* only after isolating the impact of model overhead. **Do not merge or claim OAIE.**
