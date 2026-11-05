# R7.2 — Precommitted certificate-seeking acquisition, actual result

**Decision: HOLD / distribution-shift failure. No merge, no capability promotion.**

## Provenance, scope, replay
- R7.1 pilot is *development*, not independent confirmation. R7.2 protocol was committed first as `R72_PROTOCOL.md` at `22ad8e21db6bcd8e770593e92718f03bd9b8271c`.
- Frozen R7.2 **code and prescore test** HEAD: `a4f1cd200dd395e85bed46fcc89b1398c176e250` (before first final test/OOD scoring).
- Source blob `r72_certification.py`: `8b96117e1834074a0cbed2d0038ae66c295906f8`. Prescore test blob: `b36febbfedd990740fc725c23e4a2155a9da3e4e`. Both verified by GitHub readback.
- Local Python **3.13.5**, unit command: `PYTHONPATH=code python -m unittest ace_research_uncertainty.test_experiment ace_research_uncertainty.test_r72_certification -q` => **23/23 PASS**. A separate aggregate audit verified conservation and budgets across 32 method/split/budget combinations.
- Actual full-result command (after freeze): `PYTHONPATH=code python -m ace_research_uncertainty.r72_certification --phase final > ACE_R72_locked_final_results.json`. Output **14,081 bytes**, SHA256 `77221baa6be986f09e5e4b75437630460abe5e9dfe6cd48aa04ba4028716c7a9`.
- No exact-head GitHub Actions for this directory has been observed; no independent evaluator or secure external holdout. This is local public synthetic development.

## Setup and cost
- Six observable groups per world; accept iff latent Bernoulli reliability ≥0.80; LCB rule uses **min 3 target labels**, Beta strength 12 and normal-based z=1.0, frozen before final.
- 30 independent source tasks (**2,160 offline source-training labels**), 12 validation tasks, **24 stable test tasks** and **24 shifted OOD tasks** with non-overlapping R7.2 task IDs and world perturbation seed 20261106.
- The R7.2 world perturbations use seed 20261106 but inherited R7.1 deterministic evaluator `query` and scoring-probe streams use seed 20261105 plus unique R7.2 task IDs. This is separate deterministic identity, **not** a cryptographically sealed evaluation.
- Four max online purchase budgets: 0/6/12/24 **per task**. Fixed, random and random+LCB purchase their full budgets; certificate-seeking can stop early. Report realized purchases explicitly; a smaller spend is not a matched-cost comparison by itself.
- Privileged oracle ceiling is evaluation-only: 59 truly good test strata and 25 OOD strata; never used as a query policy.

## Initial validation, never used as confirmatory evidence
At cap 24 across 12 validation worlds: certificate **17 true / 0 false / 55 abstain, 68 purchases**. Matched random+LCB **10 true / 0 false / 62 abstain, 288 purchases**. Original random **13 true / 5 false** and fixed **16 true / 6 false** with 288 purchases.

## Final after precommit: cap 24, 144 stratum decisions per split

| Split | Method | True accepts | False accepts | Abstain | Purchases | ECE | Brier | Utility |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| stable test | fixed | 46 | 16 | 82 | 576 | .043186 | .170259 | -780 |
| stable test | random | 35 | 10 | 99 | 576 | .052524 | .177725 | -674 |
| stable test | random+LCB | 24 | 0 | 120 | 576 | .035690 | .150515 | -336 |
| stable test | **certificate** | **41** | **0** | **103** | **159** | .054924 | .150294 | **455** |
| shifted OOD | fixed | 18 | 13 | 113 | 576 | .056496 | .215145 | -1222 |
| shifted OOD | random | 11 | 6 | 127 | 576 | .043417 | .216510 | -970 |
| shifted OOD | random+LCB | 0 | 4 | 140 | 576 | .196627 | .289327 | -1096 |
| shifted OOD | **certificate** | **0** | **8** | **136** | **96** | **.334062** | **.334228** | -848 |

Utility is **20×true - 60×false - 2×abstain - 1×online purchases**, identical method comparison. Offline training labels and public validation tuning cost are not included in that target-task utility and must be accounted separately.

At cap **6**: stable certificate 23 true / 0 wrong / 78 purchases (budget max 144); OOD certificate 0 true / **8 wrong** / 72 purchases.
At cap **12**: stable certificate 41 true / 0 wrong / 159 purchases (budget max 288); OOD certificate 0 true / **8 wrong** / 96 purchases.
At cap 24 certificate stops once positive acquisition value vanishes: 159 test purchases, 96 OOD purchases. This is not a guarantee of sound early stopping.

## Locked gate: FAILED
- **Stable:** true coverage 41 ≥ 24, wrong accepts 0 ≤ 0, at least one strict improvement and nonzero coverage. Stable gate **PASS (on one synthetic seed only)**.
- **OOD:** true coverage 0 ≥ 0, but **8 false accepts > 4** and **zero true coverage**. OOD gate **FAIL**.
- Overall precommitted conjunctive success **FALSE**. Do not claim a safe new ACE capability.

## Negative evidence and counterexample
The initial stable source reliability for groups 4 and 5 is around 0.91/0.97; shifted OOD changes those groups to around 0.33/0.72 while making another group genuinely safe (~0.91). The certificate policy optimizes near-certification under a confident *source* prior, so it concentrates purchases on groups whose inherited confidence is wrong. On shifted OOD all **8 of 8 accepted capabilities were false**, and it missed all 25 truly acceptable strata. Its false-acceptance rate among accepted predictions was **100%** on this split. Stable test had 0/41 false, but this does not prove an upper bound on future false acceptance risk.

ECD and Brier deterioration on shifted OOD are substantial; an efficient acquisition rule is not a substitute for mechanism-shift detection and credible interval coverage. This is a useful adversarial falsifier.

## Limitations and next precommitted study
One seed, 24 worlds per final family, author-visible synthetic source, Gaussian confidence heuristic, no independent escrow, no full exact-head Actions, and in-process evaluator boundaries. Test/OOD were viewed once, so their future use is **diagnostic only**, never fresh confirmatory evidence. New strategies must be prototyped with *separately generated train/validation families*, then frozen and independently tested on fresh disjoint test/OOD seeds. The next falsifiable question is whether explicit shift detection and conservative prior discounting can prevent negative transfer at comparable purchases **without** collapsing to universal abstention.

Scientific decision remains **HOLD**; all R7.1 and R7.2 negative evidence retained.
