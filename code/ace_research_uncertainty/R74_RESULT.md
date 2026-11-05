# ACE R7.4 — precommitted e-process certification: public negative utility result

**Scientific decision: HOLD.** R7.4 improves selective correctness on the author-built shifted worlds but **fails the precommitted multi-objective gate on OOD utility**. Never promote its policy to ACE core from this experiment.

## Provenance and procedure

- [Locked protocol](R74_PROTOCOL.md) committed as `e39c0548bc6d0260af746366fb3646362722d833` before R7.4 code or final test sampling.
- Evaluator process: existing R7 public synthetic local `Evaluator`, source-training prior only fitted on `train:stable:r74:*`; task world/seed namespace `r74-new-world`, seed 20261108.
- Train 30 worlds (2160 **offline** train labels), validation 12. Final test 20 stable worlds; shifted OOD-A/B/C/D each 20 worlds. Six group decisions/world, 64 scorer-only probes/group. Each online method has a per-world **cap** in {0,6,12,24}; all observed purchase counts charged.
- Code `r74_riskgate.py` Git blob SHA `73f9a17271b9c1248891448c83a80cbb78054983`, test blob SHA `dbb1f469143305c3e8810927fec6a1b16e5646db`, both read back from GitHub and compared against `git hash-object` of locally tested bytes **before final scoring**.
- Local `PYTHONPATH=code python -m unittest ace_research_uncertainty.test_experiment ace_research_uncertainty.test_r72_certification ace_research_uncertainty.test_r73_shift ace_research_uncertainty.test_r74_riskgate -q`: **51/51 PASS** (36 earlier + 15 new), Python **3.13.5**.
- Validation-only: e-test accepted **5 correct/0 wrong** with 263 online purchases on 12 worlds vs R7.3 **18 correct/0 wrong** with 100 purchases; fixed protocol retained.
- New final bank scored **once**, command `PYTHONPATH=code python -m ace_research_uncertainty.r74_riskgate --phase final > ACE_R74_locked_final_results.json`. Full pretty-printed JSON **79,597 bytes**, SHA256 `0f7e01fade89eab217e717ca44a89dd807972cfabbdbd3e115c99bfa059918ef` (download attachment in conversation; regenerate locally to compare).
- Additional offline **JSON-only** audit read the saved result (not rerunning scoring): **120 arms (5 splits × 4 caps × 6 methods)**, 1,197 invariant checks, **0 fails**; arithmetic, hard budgets, oracle ceiling, decision conservation, paired acquisition, false-acceptance denominator and locked gate recomputation.
- Exact-head GitHub Actions **not run** (existing CI workflow only filters E1.5 core). No independent sealed scorer or real ACE semantic operator evaluation.

## Final outcomes (24 purchased labels maximum per world)

Each split has 20 worlds, i.e. **120 stratum decisions**. Columns use *accepted correctly / accepted incorrectly*; an unaccepted stratum is an abstention.

| Split | Oracle good strata | R7.3 shift-aware correct / wrong | R7.4 e-test correct / wrong | R7.4 bought labels | R7.3 bought labels | R7.4 utility | R7.3 utility |
|---|---:|---:|---:|---:|---:|---:|---:|
| Stable test | 45 | 32 / 0 | **14 / 0** | 410 | 145 | **−342** | 319 |
| OOD-A | 20 | 3 / 5 | **3 / 0** | 465 | 319 | **−639** | −783 |
| OOD-B | 32 | 7 / 1 | **2 / 0** | 470 | 480 | **−666** | −624 |
| OOD-C | 36 | 12 / 1 | **3 / 0** | 465 | 445 | **−639** | −479 |
| OOD-D | 40 | 19 / 0 | **0 / 0** | 480 | 462 | **−720** | −284 |

**Other matched evidence at 24-label cap:**
- R7.2 certificate: stable 29/0, OOD-A 0/7, B 0/0, C 0/0, D 0/0; online labels 122,79,44,54,49 respectively.
- Random+LCB: stable 24/0, OOD-A 0/5, B 0/0, C 0/0, D 0/0; online labels 480 per split.
- **Paired-LCB** on *the same selected groups and purchased labels as R7.4*: stable 16/0, OOD-A 5/0, B 5/0, C 6/0, D 0/0; identical purchases to the e-test, but fewer safety assurances because the Bayesian bound reuses diagnostic labels.
- E-test ECE/Brier: stable **0.080471 / 0.188925**; OOD-A **0.082531 / 0.220842**; OOD-B **0.040812 / 0.195745**; OOD-C **0.052353 / 0.207351**; OOD-D **0.129664 / 0.207962**.
- Always-abstain diagnostic control purchases exactly six labels/task (120 labels per split), certifies nothing, and illustrates why **zero wrong accepts alone** is not a valid success metric.
- The e-test first selects *one* group from groups 0,4,5 with two diagnostics each, then uses **fresh and separate certification labels** for a likelihood-ratio test at E≥10. Under an independent stationary Bernoulli null p≤0.8, conditional false acceptance probability of this **one selected candidate** is ≤0.10 by the nonnegative-supermartingale/Ville argument. This is a per-world nominal error control, **not** 0% false-acceptance risk and not a global guarantee across ACE task families.

## Falsifiable locked gate

| Criterion | Verdict |
|---|---|
| Stable accepts ≥25% of R7.3 with no extra false acceptance | **PASS** |
| OOD false accepts no worse than R7.3 on each family | **PASS** |
| At least one OOD with strictly fewer false accepts | **PASS** |
| Nonzero correct acceptance in ≥2 shifted families | **PASS** |
| Total OOD utility ≥ R7.3 | **FAIL** |
| Hard per-task label caps and cost conservation | **PASS** |

Total OOD utility under exact predeclared measure `20 correct−60 wrong−2 abstentions−purchased`: R7.3 **−2,170**, R7.4 **−2,664**. The difference **−494** fails the success contract. Single-seed exploratory results cannot promote a risky policy even if all gates passed.

## Failure mechanisms and constraints

1. **Narrow candidate coverage:** OOD-D hides good capabilities in groups 2 and 3, but diagnostics inspect only 0,4,5. R7.4 picks unproductive groups and returns **0/40** truly acceptable strata. This is a structural search problem, not a calibration-only issue.
2. **High evidence cost:** at most one candidate/world, typically 18 certification labels after six diagnostics. In stable test, R7.4 consumed 410 labels vs 145 for R7.3, greatly reducing utility and correct accept coverage.
3. **Observation-only improvement but no independent risk proof for ACE:** exact e-process bound requires independent identical Bernoulli draws under an unchanging task; correlated or adaptive real evaluations, per-task shifts or evaluator leakage invalidate the bound.
4. **Multiple tasks:** nominal 0.10 error control applies separately to each selected null candidate, not to the probability that *any* false acceptance occurs over 100 worlds. The empirical 0 wrong observed on finite worlds is not an estimate of a zero risk.
5. Test and all four OOD results are now **visible/public development**. Any modifications motivated by R7.4 outcomes require NEW precommitted worlds and separate custody; none of these worlds can be reused as fresh confirmatory evidence.

**Decision: HOLD / retain negative evidence / no main changes / no merge PR #43.**

Next falsification: mathematically controlled *candidate coverage vs certification costs*, selecting one of all six groups using diagnostic observations that do not enter the e-process, and testing under correlated/nonstationary labels with appropriately weakened or no guarantees. Perform independent-seed multi-replication and report confidence intervals before external acceptance.
