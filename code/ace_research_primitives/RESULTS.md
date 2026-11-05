# R1 v0.1 — empirical report: observation-induced finite-state primitives

Status: **PUBLIC SYNTHETIC DEVELOPMENT ONLY; scientific NOT_ASSESSED; no OAIE claim**. Owner: `research/chat-r1-primitives`, files restricted to `code/ace_research_primitives/`.

## Why this does not duplicate other research
- S2 Algorithm Discovery PR #36 and adjacent PR #28 synthesize typed **arithmetic expression trees**; R1 infers finite-state **transition graphs** from positive/negative sequential traces. Its generated automaton was *not* an explicitly prelisted program candidate.
- E1.4u (#16) introduced a researcher-written graph-global branch-pair primitive. R1 is instead about finding a compact data-induced state abstraction.
- RPNI/state merging is established prior art. This is **not discovery of a new fundamental computational operation** or a novel algorithm. Model induction is deliberately bounded to deterministic regular languages over a two-letter alphabet.

## Preregistered primary experiment
Protocol recorded at commit `7f4d2d8f0938a4fd1f1c44c45c584b9dd852e39e` before the first local scoring run. Nine known regular-language task generators and numerical success gate: mean holdout gain >=0.05 relative to strongest of three baseline classes, plus >=6/9 tasks at >=0.90 holdout accuracy. Each task has all 63 strings of length 0..5 for learning, 192 strings of length 6..7 for diagnostic validation, and 256 seeded disjoint strings of length 8..13 for holdout.

Controls shared the same training labels: exact prefix memorizer; suffix-3 majority; best-of-130 **single** frozen string predicates fitted on train. For conservative reference, the report also takes the best holdout *control per task*, which is oracle-favored post hoc; it never selects the induced model.

## Local execution
`cd code && PYTHONPATH=. python -m unittest ace_research_primitives.test_primitive_discovery -v`
=> **13/13 PASS**, Python standard-library only. The run was made on source Git blob hashes identical to live GitHub files:
- implementation `48904d7f344bd0bce6d5c392ccdc015309479fd5`;
- test file `44c794371b51777212d308e1d119ba8994020c2b`.

`cd code && PYTHONPATH=. python -m ace_research_primitives.primitive_discovery --output /tmp/r1-evidence.json` regenerates full traces, canonical automata, per-split metrics, sample SHA256, and up to three holdout counterexamples per method. The local raw evidence artifact SHA256 is `f56c6bf22f2f6ca3cc1e05bca889e6ac291f4e5c3388df04dba8fd7f5ed49415`. This report records the observed local result; GitHub CI / independent exact-head rerun **not completed**.

### Regular heldout tasks (256 examples per task)
| Target | Induced states | Induced correct | Strongest single fixed predicate correct |
|---|---:|---:|---:|
| count(a) even | 2 | 256 | 256 |
| count(a) mod 3 = 0 | 3 | 256 | 256 |
| contains `ab` | 3 | 256 | 256 |
| avoids `bb` | 3 | 256 | 256 |
| ends `ba` | 3 | 256 | 256 |
| odd length | 2 | 256 | 256 |
| avoids `aba` | 4 | 256 | 256 |
| count(a) mod 4 = 0 | 4 | 256 | 190 |
| first symbol equals last (nonempty) | 5 | 256 | 130 |

**Aggregate**: induced 2304/2304 = **100%**; oracle best of all control families per task = **91.9705%** mean; absolute gain **+8.0295 percentage points**, above +5pp preregistered threshold. 9/9 tasks >=90%. **H1 PASSED on this synthetic public development bank only**. All tasks combined had **170 merge attempts**, 63 learning labels each (693 total across 11 tasks), and 5621 synthetic labels including diagnostics/holdouts.

### Out-of-class / adversarial
Two separate *nonregular* languages, 128 positive + 128 negative holdout labels each:
- equal numbers of `a` and `b`: 181/256 = **70.7031%**; 6 induced states. One counterexample: `babbabbbbb`, true=0, prediction=1.
- balanced nesting with `a` opening, `b` closing (Dyck-1): 147/256 = **57.4219%**; 4 induced states. Counterexample: `aaaababbbb`, true=1, prediction=0.
- Noise counterexample: flipping the single training label on `aabba` in a count(a)-parity problem gives a 5-state automaton; heldout correct drops from 256/256 to **187/256** while training consistency remains perfect. This demonstrates sensitivity to corrupted evidence.

**Protocol disclosure:** original first protocol commit proposed `a^n b^n` for the second stressor; that language has too few distinct positives for balanced 128/128 holdout at the specified short lengths. It was replaced with Dyck-1 *after initial exploratory scoring*. This stressor is **not prescore-confirmatory**; amendment is explicitly recorded in a second protocol commit. Primary nine tasks and thresholds were unchanged.

### Exploratory training-label ablation, not prespecified acceptance
| Labels/task | Mean regular holdout accuracy |
|---:|---:|
| 7 | 66.15% |
| 15 | 85.94% |
| 31 | 96.48% |
| 63 | 100.00% |

## Interpretation / unsolved questions
**Demonstrated:** a fixed inference procedure can construct *task-specific data-induced reusable finite-state abstractions* rather than simply choose from a prewritten AST candidate list; short-trace positive/negative evidence can be enough for length generalization on small regular languages.

**Not demonstrated:** open-ended invention of a new operator class, representation outside finite automata, real-world transfer, performance under stochastic/noisy labels, objective algorithm self-improvement, generality across alphabets, search compute parity with all controls, statistical independence of synthetic examples, or any form of OAIE.

The fixed library already perfectly solves 7/9 regular targets. The overall gain is concentrated in two constructed targets and does not establish broad superiority. RPNI is researcher-authored; its state merging and its bias are predesigned. All oracles and data are synthetic and visible in source, though the model learner is passed only training observations. Validation and holdout are not used in state merge decisions. Exact-head CI and independent scientific sign-off remain OPEN. **Do not merge, promote, or cite as scientific GO.**

## Next falsifiers
Third-party independently generated (precommitted) regular languages, higher alphabet diversity, transition noise, hard-to-distinguish DFA pairs, sparse-label regimes, and compute-matched strong baselines (SAT DFA induction / modern red-blue EDSM). Audit the generated DFA against an independent evaluator and test longer extrapolation. Require preregistered gate before assessing any subsequent bank.
