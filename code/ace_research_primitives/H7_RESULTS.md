# R1 H7 postscore findings — counterexample-induced residual substring readouts

**Status: PUBLIC SYNTHETIC DEVELOPMENT / SCIENTIFIC NOT_ASSESSED.** Prescore protocol GitHub commit `9e7e810952a39a1003e28fb0005037ffe62db0fd`, authored before H7 implementation and scoring. All code/evidence live under R1 ownership only. No merge or OAIE claim.

## Research question and scope

Given a **privileged and correct short-input base predictor**, can R1 construct a new residual-readout *instance* from disagreements with an observed synthetic oracle? The learner discovers positive residual strings, extracts the contiguous substrings **present in those observations** (bounded lengths 2–5), retains only strict-fit train candidates, validates exact fit on separate query words, and predicts via base XOR discovered feature. No target literal is passed into `discover`.

This is meaningful evidence-conditioned **feature construction within a hand-authored class**, **not** unrestricted primitive-type invention. It neither chooses between prewritten target-literal entries nor invents a fundamentally new representation grammar.

## Scoring and locked gates

64 tasks = 4 supplied base predicates × all 16 length-four target substring values, all distinct targets. Each task uses 128 unique query labels, 128 separate validation labels, 256 separate holdout labels, plus the 63 short-input base observations. Query/validation length 6–10; terminal length 11–13. All selection frozen prior to scoring terminal. No adaptive purchased-query selection.

Strong fixed control: optimistic hindsight-best terminal accuracy among base-only and five immutable H6 five-character triggers; **the selected control is chosen using holdout and is thus advantaged as a comparator**. A fixed-trigger candidate selected using training+validation is also recorded but is not used to boost the proposed method.

| Preregistered gate | Observed | Verdict |
|---|---:|---|
| New representation instances accepted | 64/64 (requires >=56/64) | PASS |
| Held-out accuracy, learned feature or conservative base fallback | 16,384/16,384 = 100% (requires >=95%) | PASS |
| Hindsight-best fixed control | 10,998/16,384 = 67.126953% | Comparator |
| Gain over optimistic hindsight control | +5,386/16,384 = **+32.873047 pp** (requires >=10pp) | PASS |
| Negative-control abstentions from new feature creation | 8/8 (requires >=7/8) | PASS |
| Overall preregistered H7 gates | H7a=true, H7b=true | **PASS, SYNTHETIC ONLY** |

72 worlds total, **18,432** synthetic query/validation oracle labels (72×256); 18,432 terminal holdout predictions in the replayer, plus 72×63 initial baseline observations. Per world, candidate count 0–60, 51–60 on 64 primary worlds. No arbitrary source execution or external oracle expense.

## Negative results retained rather than disguised

**The eight negative abstentions mean only “no new residual substring feature accepted.” They DO NOT mean reliable semantic correctness, drift detection or epistemic safety.** In these controls, the base fallback made only **912/2,048 correct terminal predictions (44.53%)**. Four late-drift targets changed at length >=14 and four out-of-class parity residuals defeated the substrate grammar. Observed results:
- late-drift (equal_counts, a_mod3, contains_ab, dyck): **90/256, 111/256, 117/256, 94/256** correct;
- parity/out-of-class in same base order: **123/256, 123/256, 123/256, 131/256** correct.
- Witness: late-drift equal_counts on `aaaabbbabbababba` truth=0, base-fallback predicted=1; no accepted new feature.

**Post-exploratory engineering corrections:** A resource-cap adversarial unit test first exposed that `discover` did not reject oversized lists explicitly; it was tightened to fail closed for >128 observations in either query or validation. The original 72-world bank uses exactly 128 each, so results/evidence remained byte-identical. A test-import correction enabled both named-module and directory-discovery `unittest` modes. These fixes were not a change to prescore acceptance thresholds.

## Reproduction and source-integrity checks

From the project root:

```sh
cd code
PYTHONPATH=. python -m unittest ace_research_primitives.test_h6_distinguish ace_research_primitives.test_h7_residual_memory -v
PYTHONPATH=. python -m unittest discover -s ace_research_primitives -p 'test_*.py' -v
PYTHONPATH=. python -m ace_research_primitives.h7_residual_memory --output /tmp/r1-h7.json
PYTHONPATH=. python -m ace_research_primitives.audit_h7 /tmp/r1-h7.json
sha256sum /tmp/r1-h7.json
```

**Actually executed**: on a local working copy containing byte-identical H6 GitHub source, **22/22 H6+H7 tests PASS** both named-module and discovery modes. Full historical R1 H1–H7 suite has NOT been run on the exact PR HEAD; GitHub CI exact-head also OPEN. Standalone H7: 10/10 tests PASS. Unit checks include sample disjointness, no residual abstention, >128 query budget rejection, late drift, non-substring out-of-class, and detection of forged feature, score, aggregate.

Independent within-team `audit_h7.py` does not import the H7 learner/runner; it independently reconstructs all 72 target truths, samples, candidate extraction/selection, fixed controls, decisions and 18,432 terminal predictions. **Exact JSON hash reproducibility** (84,162 bytes): SHA256 `57db292e75f46fc333191b33281da1720fed9d78848314bb0b00399efe740e6f`.

Source Git blob SHAs, equal to the locally tested Python files:
- `h7_residual_memory.py`: `673aa2dcc8afe062da3e08b35c9761b135aeb380`
- `audit_h7.py`: `121dcd3934eced215dcb9a155847b2e05d32d9c2`
- `test_h7_residual_memory.py`: `d3d3561250c977d7b4c4b257a62a9df79b3976a9`

## Scientific assessment

A positive H7 indicates that a familiar residual-gram class can be populated from data and generalize to longer strings **within the same researcher-chosen substring family**. The bank is deliberately aligned with the method; the correct base predicate is supplied, and all true target features belong to an intentionally small known class. Holdout data are deterministic public synthetic rather than independent sealed evaluations. The fixed-list baseline is relatively weak for unseen four-grams despite its hindsight advantage. It does not distinguish this induction procedure from stronger modern grammar-learning algorithms or prove new primitive-type invention.

Next falsifiers: third-party unseen feature families (length-varying delimiters, counting with ordering, nested dependences), noisy/missing labels, budget-matched structural learners, and unknown-world abstention calibrated to **prediction correctness** rather than feature acceptance. Cross-family independent review and exact GitHub CI are mandatory before any broader capability claim. **DO NOT MERGE. Scientific NOT_ASSESSED.**


## Coordinator-owned independent transfer falsification (not an H7 rerun)

Coordinator [PR #50](https://github.com/dianzherdiana25-hash/ACE/pull/50) pinned **the older R1 source** at `cf8948144919d41a70d1da6f3fb289d1dc818e36` (prior to H7) and obtained exact-head GitHub Actions success for its public independent R1 DFA transfer bank. It found only **5/24** clean and **3/24** noisy tasks above 90% accuracy, plus **24/24** unprotected indistinguishable semantic drifts; all coordinator predeclared gates failed. This is strong **negative cross-bank evidence for earlier R1 finite-state behavior**, and argues against treating H7's 64/64 author-designed substring results as general primitive discovery. It **does not test H7 code** and does not replace an independent H7 transfer audit. Source: coordinator PR #50, exact-head CI documented there.
