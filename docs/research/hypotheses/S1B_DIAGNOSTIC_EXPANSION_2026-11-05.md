# S1-B — Diagnostic expansion after version-space contradiction (public synthetic)

2026-11-05. **Exploratory development only; scientific gate NOT_ASSESSED.** This follows the negative S1-A result in draft PR #34, not a repeat of that experiment.

## Hypothesis, criterion, and protocol

Hypothesis considered before the local run: when a bounded hypothesis grammar is misspecified, expanding it **only after all current hypotheses contradict observed labels** will improve disjoint-test accuracy on four-bit parity by >=0.10 absolute over the fixed-grammar adaptive baseline at the same six training-label budget, without increasing expansion triggers in in-grammar and one-flipped-label negative controls above 5% of runs. This is an author-selected development hypothesis, **not independently timestamped preregistration**.

Use 16 Boolean inputs. Baseline grammar is all 28 affine parity functions with 1–3 active variables and a bias. Expansion adds exactly two 4-variable parity functions (30 total). The candidate grammar extension is **predefined by the researcher**, not autonomously invented. Policies: random, static-order, adaptive maximum version-space split, and adaptive with contradiction-triggered expansion. For each of three strata, run 100 paired seeded train/test partitions (12 eligible train points, four disjoint test points), six queried labels per arm. Strata: missing four-variable parity, in-grammar function, and one label flipped in an in-grammar truth table. Same world and split seed per policy. The four test labels are only scored at the end, never used for selection. CPU is process_time, not isolated per-arm CPU.

## Measured local run

Run command: `python code/ace_research_hypotheses/s1b_diagnostic_expansion.py`. A local source prototype ran before commit; output was transcribed into `evidence/research/hypotheses/S1B_LOCAL_RUN_2026-11-05.json`. Source prototype SHA256 `ab816d6eea246b348f4775ccf0d52d6460a76d3a0a5946086a606488040cad80`; local JSON SHA256 `94c67a19cbaaa5531e3f7c99381cd9f180499152459f22eef614db3cbef57e05`. GitHub-committed source has not been exact-HEAD rerun or independently reviewed; SHA equality with prototype is **not established**.

| Stratum | Random | Static | Adaptive fixed | Adaptive repair |
| --- | ---: | ---: | ---: | ---: |
| Four-variable parity | .0150 | .0125 | .2775 | **.5575** |
| In-grammar | .9500 | .9850 | 1.0000 | 1.0000 |
| One-flip noisy | .7200 | .7450 | .7500 | .7500 |

All methods spent 600 training labels per stratum, totaling **7,200 training labels** across 1,200 arms, with 4,800 additional disjoint test-label lookups for scoring only. CPU process time 0.085134 seconds (local). Repair triggered in 28/100 parity runs and **0/100** in either negative-control stratum. In parity, fixed adaptive had empty posterior 28/100 times and repair had 0 empty posteriors. The repair-versus-adaptive accuracy difference is +0.2800, or +0.0004667 mean test-accuracy units per aggregate training label, descriptive only, not information-theoretic mutual information. No external evaluator or paid oracle.

## Interpretation and adversarial limitations

The development acceptance criterion is met **within this small, intentionally chosen synthetic bank**, not as a general scientific claim. Counterexample: repair does not trigger on 72/100 parity splits and therefore cannot diagnose a missing representation there; average parity accuracy remains only .5575. One-flip noise did not trigger in this seed set, but does **not** establish robust noise safety. The base grammar is deliberately missing only two known functions, so the experiment tests a narrow hand-authored extension, not novel hypothesis creation. All 100 parity trials reuse the same truth function with different partitions; they are not 100 independent worlds. Fixed six-label budget, single seed family, no confidence intervals, no blinded bank or heldout custody. The zero-posterior score rule assigns zero accuracy to all such arms; alternative abstention/coverage metrics could change the comparison.

**Decision: EXPLORATORY SUPPORT for a narrow contradiction-triggered expansion mechanism; NOT_ASSESSED for autonomous hypothesis discovery or ACE scientific promotion.** Preserve the prior S1-A REJECT result unchanged. No E1.4/E1.4aa scientific status changed.

Next falsifiable test: across unseen composed Boolean families with multiple missing primitives, noisy labels and cost-weighted queries, a learned grammar-repair proposer (not a supplied parity extension) must improve test accuracy by >=0.10 over fixed and oracle-supplied grammar controls at matched labels **and** achieve <=5% false expansion triggers on noisy in-grammar worlds. Precommit a new bank and confidence method before scoring.
