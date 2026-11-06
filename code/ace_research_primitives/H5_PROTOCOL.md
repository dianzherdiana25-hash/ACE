# ACE R1 H5 PRE-SCORE — task-blind representation selection and indistinguishable drift

Status: PUBLIC SYNTHETIC DEVELOPMENT / SCIENTIFIC NOT_ASSESSED. This document is committed **before** H5 implementation and scoring. Research ownership is strictly `code/ace_research_primitives/` on `research/chat-r1-primitives`; never merge, never mutate E1.4/main/other lanes.

## Research question / boundary
Given training traces but **no task-family name or source-model internals**, can a controller select between a data-induced finite automaton (H1 RPNI) and a data-induced signed counter (H4) by paying for **separate diagnostic validation labels**, and then generalize beyond both observed length ranges? This tests evidence-guided selection between researcher-provided representation classes, **not primitive-class invention**. Unlike S2 arithmetic AST synthesis, this is sequence-state representation selection. Any success is bounded: the class inventory and selector rule are authored by the researcher.

## Locked experiment bank
Alphabet a/b. All tasks share 63 labeled binary words of lengths 0..5 for fitting. All receive the same 192 *additional paid validation labels* on words of lengths 6..7, which are permitted for **class selection only**, NEVER to retrain either model. All final holdouts have length >=8 and are not used for selection.

24 tasks in fixed order:
- 12 novel seeded random DFA targets (three each with nominal source states 2,3,4,5). For each size N generate candidate at attempt j with `random.Random(20261105 + 24000 + 1000*N + j)`, draw N (a,b) destinations then N acceptance bits. Accept only when all N source states are reachable and 63 train labels have positive proportion in [0.2,0.8] and train signatures are unique. Select first three accepted each N, max 50000 attempts/size. No validation/holdout filtering. Final holdout is 256 uniformly sampled **without replacement** binary strings from lengths 12..18, RNG `Random(20261105 + 25000 + task_index)`; draw length uniformly then independent symbols; cap 100000 attempts. Exact duplicates rejected, disjoint lengths.
- 8 counter families from prior H4: equality counts, a=2b, b=2a, a=3b, Dyck-1, reverse Dyck-1, a^n b^n, b^n a^n. Their generators were researcher-known at H4 and therefore **not independent new task families**. For the six non-block tasks, call H4's fixed balanced holdout generator with `index=3000+task_index`, yielding 24 positives and 24 matched negatives at lengths 8..20. For the two block families construct 24 positives a^n b^n (or reverse) with n=28..51, plus 24 unique negatives by shuffling each positive's symbols (same counts), using `random.Random(20261105 + 26000 + task_index)`, reject positives/duplicates, cap 250000 per negative. These blocks are length 56..102 and out of prior bank.
- 4 **indistinguishable drift controls**, based in fixed order on equal-count, a=2b, Dyck-1, a^n b^n: target labels are IDENTICAL to the base source on training and validation lengths <=7, but **inverted for length >=8**. Holdout uses the corresponding base task's 48 balanced examples and flips target labels. Since training AND validation are semantically identical, no model-selection rule observing only those splits can identify the drift. These do not count in the H5a aggregate; negative control on false confidence.

## Candidate representations and selection
RPNI `primitive_discovery.infer` on the 63 training labels (cap 10000 merge attempts), and H4 `h4_counter_induction.infer_counter` on the same 63 labels (cap 1000 register proposals and 1000 guards). If H4 abstains, the counter option is the RPNI baseline, with documented reason. No target name passed to either learner. All candidate fits are frozen **before** validation scoring.

Select the candidate with the smaller number of mistakes on all 192 validation examples. Tie -> RPNI (conservative). This step consumes 192 additional evaluator labels per task; both candidates see exactly the same validation labels. No automatic modification/selection based on holdout.
Baselines: always RPNI; always H4 counter-or-RPNI fallback; best original fixed single predicate fitted on train; 3-symbol suffix majority; prefix memorizer. Show hindsight oracle max(RPNI,counter) on holdout for context only; it is not a selectable model. Report correctness, selected type, validation margin, register parameters, abstention, state count, merge/proposal attempts, counterexamples.

## Falsifiable gates (defined before scoring)
H5a on 20 *non-drift* tasks passes only if ALL:
1. Task-macro mean terminal holdout accuracy of validation-selected model exceeds max(task-macro mean always-RPNI, task-macro mean always-counter) by >= **0.05** absolute; and
2. >= **16/20** non-drift tasks have at least 0.90 holdout accuracy; and
3. selected model never performs worse than both original candidates on any non-drift holdout task (trivially true with just those two choices; recorded as integrity check, not evidence of discovery).
H5b drift false-confidence gate passes only if the controller explicitly **abstains from semantic generalization on at least 3/4 drift controls**. The current selector has no OOD detector or abstention signal; this gate is deliberately designed as a strong falsifier. Outputting a prediction for any holdout is **not** abstention. Overall H5 GO requires both H5a and H5b, so a misleading positive H5a cannot hide drift failure.

## Budget and validity
Train labels=24*63=1512; validation labels=24*192=4608; final holdouts: 12*256+12*48=3648. Total true synthetic oracle evaluations=9768; no validation/holdout re-purchases. No code execution of generated candidate, network, paid labels, or branch promotion. This is not a compute-matched comparison with external DFA learners; H4/RPNI implementers and bank designer overlap. Noise and alphabet shifts not tested in H5.

## Evidence and strict reporting
Commit code and tests only after this protocol. Execute local full regression (H1–H5), serialize all models, train/validation/holdout scores and counterexamples; independently reconstruct at least holdout truths and verify selection from validation-only scores. Record failed cases, confidence failure and exact hashes. If unexpected bank-generation limitations occur, disclose them as post-protocol amendments and mark affected data exploratory rather than altering silent conditions.
