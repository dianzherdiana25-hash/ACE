# R1 H3 PRE-SCORE Protocol — complexity scaling and single-label noise

Mode: **public synthetic development / NOT_ASSESSED**.
This protocol is committed **before implementing/scoring H3** and is additive to H1/H2. No historical bank, main, or another team path may change.

## Falsifiable question

Are H1/H2 improvements robust when the **target DFA state count exceeds the maximum reliably identifiable from 63 short positive/negative traces**? Does single-label corruption expose overfitting? This is falsification of a bounded fixed-state abstraction inference method, **not** claim of general new primitive discovery.

### Source worlds — 48 new task instances

- Alphabet remains (`a`,`b`), all 63 train words lengths 0..5, 192 validation words lengths 6..7.
- Source automaton sizes `N=(6,8,10,12)`, 12 accepted tasks for each N. Each attempt uses an independent instance `random.Random(20261105 + 4000 + N*10000 + attempt)`, attempt indices starting 0.
- Draw each of N states' destination for `a` then `b` uniformly from range(N); then acceptance bits uniformly. Initial state 0. Accept only if every *source graph* state is reachable from start and training positives fall within [0.2,0.8]. Exclude exact duplicate 63-bit training-label signatures among accepted worlds. **No validation or holdout filtering.** Maximum 50,000 draw attempts per N; fail loudly if short.
- Holdout: 256 independently sampled **unique** random binary strings per world with lengths uniformly drawn from 14..20 inclusive, using `random.Random(20261105+6000+world_index)`; each character drawn via `randrange(2)`. Rejection-sample duplicates only, cap 10000 attempts/world. These are disjoint in length from train/validation; no holdout labels used by training or model selection.
- Fixed original 63 train observations (no active sampling); 192 diagnostic validation; 256 terminal holdout. All baselines use identical training labels.
- Learners: original unmodified `infer` and original three control families from R1 H1/H2. An additional deterministic 1-nearest-neighbor count-vector baseline (`len`, `count(a)`, `count(b)`, first/last symbol) is permitted if implemented **before scoring**; no tuning on holdout. Core comparisons primarily use the same 3 original control classes to retain comparability.
- Noise arm: flip **exactly one label of the 63 training examples** at index `random.Random(20261105+8000+world_index).randrange(63)`. Run all methods on noisy labels; compare against unchanged true holdout labels. This synthetic corruption consumes no additional oracle labels.
- Budget: maximum 10,000 merge attempts per world per arm, fail closed; at most 63 prefix nodes; 48*63=3024 true training labels + 48*192=9216 diagnostic labels + 48*256=12288 holdout labels, **24,528 distinct oracle-label evaluations** (reused in noisy arm). Not compute-matched against all model selection routines; log merge attempts and runtimes.

## Numeric predeclared gates
H3a clean scaling passes ONLY if:
1. mean holdout accuracy of induced DFA beats per-task **oracle-selected best of original 3 controls** by >=0.05 absolute; AND
2. at least 36/48 tasks achieve >=90% clean holdout accuracy.

H3b single-label noise robustness passes ONLY if:
1. mean noisy-arm induced holdout accuracy falls by <=0.05 absolute compared with clean induced mean; AND
2. at least 36/48 noisy-arm tasks achieve >=90% holdout accuracy.

There is **no aggregate H3 GO unless BOTH H3a and H3b pass**. Invalid bank generation, method exceptions, budget breach, or evaluation-integrity failures also invalidate GO.

## Reports and falsifiers
Record per-world source state count, accepted draw index, 63-bit train signature, true/false holdout scores, inferred reachable states, merge attempts, corruption index, first failed holdout witness, sample SHA256, aggregate by source state count, and code/protocol hashes. Independent replay on actual Git branch still needed. Any failure or null-model result is reported. Blind evaluation means learner receives observations, never source DFA transitions or holdout labels. Fixed finite-state representation class is *researcher-chosen*, hence even positive results do not establish open-ended primitive invention or OAIE.
