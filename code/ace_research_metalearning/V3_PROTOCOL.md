# R4 v3 — task-conditioned adaptation: prescore protocol (public development)

Project: dianzherdiana25-hash/ACE. Isolated path: `code/ace_research_metalearning/`, branch `research/chat-r4-metalearning`. Parent study: R4 v1/v2 draft PR #39. No modification to E1.4, ACE main, other agent directories or frozen historical evidence.

## Motivation and new hypothesis

R4 v1's global evidence-kernel weights and v2's global first-order Reptile initialization failed cross-family OOD thresholds. V3 tests a genuine task-conditional *prediction adaptation* rule. A six-feature logistic gate is trained to vary the mixture of two fixed model families (local distance kernel and target-updated logistic SGD) as the purchased target examples change. This is **learned mixture weighting over researcher-designed representations**, not autonomous algorithm or primitive invention.

**H3, frozen before v3 OOD score:** across four new seeds `[503,607,701,809]`, a training-learned conditional mixture must exceed the strongest of scratch logistic SGD, local kernel, 1-nearest neighbor, validation-tuned fixed mixture, heuristic gate and an independently fitted Reptile model by **>= 0.05 absolute full-domain balanced accuracy** at exactly four target observations. Otherwise reject H3. Use the same target purchase positions for every arm, and no family name or hidden family tag in the learner's inputs. Separate source, validation, and OOD by disjoint generative family; disallow repeated 32-bit truth masks across all three splits per seed.

## Families and evaluation

- **Meta-train** (66 tasks per seed): monotone threshold 18; one interval 24; alternating blocks 24.
- **Validation only** (32): inverted threshold 10; outside interval 10; block-XOR rule 12.
- **OOD test only** (48): XOR of two modular predicates 12; three disjoint-or-overlapping bands 12; bitwise parity 12; quadratic modular predicate 12. Four seeds give 192 OOD tasks (48 per seed), with 32 binary points per task. All tasks constrained to between 5 and 27 positives to defeat trivial majoritarian success. The OOD generators are public to the author; tests are *not* independently sealed.
- Fixed query order per task and seed, without response-dependent acquisition. Curves at k = 0,1,2,4,8. Each arm receives the same labels in the same order. Full-domain balanced accuracy credits purchased labels as observed and keeps a fixed denominator; secondary unqueried accuracy/Brier evaluates only unseen points; right-censored adaptation speed at balanced accuracy >= 0.75 uses 9 for no hit through k8.

## Models, selection and compute cost

The six learned-gate inputs are intercept, support size, support label imbalance, support label transition rate, nearest support distance, and disagreement magnitude between kernel and SGD probabilities. Gate weights (six real values) update via bounded batch gradient descent on source-task outcomes using support prefixes k1/2/4/8 and all unqueried source labels (source supervision is *not free*). Candidate sweep uses 3 SGD rates `[0.08,0.25,0.6]` x 2 kernel lengthscales `[2.5,5]` x 2 gate learning rates `[0.03,0.15]`; ten epochs. Candidate selection is by validation k4 balanced accuracy, then unqueried Brier, then deterministic ties. Baseline SGD, kernel, fixed mixture and Reptile hyperparameters are selected independently using validation only. Reptile is trained on the v3 source bank with the existing deterministic v2 method, 3 rates x 2 outer rates; it is not a comparison to the v2 numeric result on a different test bank. Fixed mixtures `[0.25,0.5,0.75]` select their best validation combination. Report source meta-label exposures, source-gradient work, target purchases, feature multiplications, kernel pairs and gate computations; do not claim equal total compute with these candidate sweeps.

## Prescore freeze and rejection rules

Before *any* OOD scoring, commit `V3_PROTOCOL.md`, `v3_study.mjs`, `v3_test.mjs` and `v3_prescore.json` together on R4 branch. Frozen JSON records trained parameters, every selected hyperparameter, validation results and SHA256 digests of all three split banks per seed. The GitHub pre-score commit SHA is recorded in `V3_RESULTS.md`, and scoring is strictly later. `scoreFrozen` deterministically refits and validates every freeze value to prevent modified weights, sources or task banks from silently changing. Do not use v3 OOD results to tune v3; any follow-on is a new explicit version with separate scoring. Negative/heterogeneous outcomes are retained. No merge, promotion, or OAIE claim.

## Reproduce

```sh
node --test code/ace_research_metalearning/v3_test.mjs
node code/ace_research_metalearning/v3_study.mjs test
node code/ace_research_metalearning/v3_study.mjs freeze /tmp/v3_prescore.json
# The prescore freeze must be committed and its commit SHA recorded before these:
node code/ace_research_metalearning/v3_study.mjs score /tmp/v3_prescore.json /tmp/v3_score.json
node code/ace_research_metalearning/v3_study.mjs verify /tmp/v3_prescore.json /tmp/v3_score.json
```

## Known limits

The feature map, kernel/SGD experts, conditional gate features, candidate search and synthetic task generators were human-designed. Cross-family OOD is a finite simulation, not a concealed external evaluator or scientific confirmation. Holding query positions fixed isolates learner updates but does not test active acquisition. CPU and memory overhead are not fully represented by logical operation counters. A SHA256 digest checks deterministic content integrity only; it is not a cryptographic commitment to an independent sealed holdout.
