# ACE Coordinator — R1/R8 Cross-Lane Science Intake v1 (PRE-SCORE)

Status: **PUBLIC SYNTHETIC / CONFIRMATORY WITHIN THIS PUBLIC DESIGN ONLY / SCIENTIFIC NOT_ASSESSED**. This document is locked as a Git commit **before** running this coordinator's new random-DFA evaluation or writing its runner. It is not a blind evaluator, publication preregistration, or authorization to merge/promote.

## Frozen pinned sources
- ACE `main` at intake start: `5b0059b85055404a46adcdef305de81f5257486c`.
- R1 primitive discovery PR #38, exact source HEAD `cf8948144919d41a70d1da6f3fb289d1dc818e36`. Only import its `ace_research_primitives.primitive_discovery` module, use `infer(examples)`, `fixed_predicates()`, `suffix_majority` and `training_words()` as written. Do not change R1 or copy its implementation.
- R8 measurement PR #40 exact HEAD `9fa4cb8ec3896ea157ad135d75d241da3a4cb6c1`. Run its existing public null simulation independently in a separate exact-HEAD checkout; require byte-for-byte equality with its committed JSON and check counts 42/512 naive versus 9/512 guarded false positives. This does not certify R8 as a calibration method.
- New coordinator source/tests/workflow only in `tools/ace_research_intake_*.py`, `.github/workflows/ace-research-science-intake.yml` and `docs/ACE_RESEARCH_INTAKE_*.md`. Other lanes, Tod, frozen E1.4, and `main` remain untouched.

## Scientific question (R1 outside authored bank)
Can the unchanged, standard RPNI-style R1 learner still generalize on **24 new** random deterministic finite automata with nominal source state counts 6, 8, 10, 12, under identical 63-label train budgets, noisy-label perturbation, and long-string OOD? This tests domain-limited transfer, **not creation of new algorithm classes, OAIE or generalization beyond finite state**.

Coordinator uses its own independent target generator; do **not** call R1's `new_tasks()` or its H1–H5 holdout generator. Binary alphabet `a,b`. Train words are lexicographically ordered exhaustive lengths 0..5, 63 labels/task (R1 input API constraint). For each nominal state count `n in [6,8,10,12]`, take first 6 targets accepted by:
- For attempts `j=0..49999`, seed `random.Random(76543000 + n*50000 + j)`.
- Draw exactly n pairs of random destinations in [0,n) for (a,b), then n independent Bernoulli accepting-state bits. Discard targets without all n source states graph-reachable from state zero; discard targets whose fraction of positive labels on the 63 fixed training words is outside [0.2,0.8]; discard training signatures already accepted anywhere across this bank. **No validation or holdout score is used for target selection**. If six cannot be collected in any group, mark experiment HALT rather than relaxing selection.
- For target index `i=0..23`, sample 256 unique binary strings by `random.Random(987654321+i)`, repeatedly choose length uniform on [12,20], then choose symbols uniform; refuse duplicates, cap 200000 attempts. No overlap with train by length; holdout strings and truth are never passed to `infer` or any training-based selector.

## Methods / budgets
Evaluate on exact same 24 targets, 63 train labels, 256 terminal labels, and holdout strings.
- Proposed unchanged R1 `infer`, `max_merges=10000`, not to be adjusted after seeing outcomes.
- Three source-provided controls fitted using *training labels only*: all-false default prefix memorizer, last-3-symbol majority with global fallback, and best single fixed predicate chosen by minimal train error (ties resolved by source order). Log each control's final score.
- Conservative *hindsight upper bound* per task = best of these three controls **on final holdout**. Never use this retrospective comparator for model selection; it makes the pass threshold tougher but is not a realistic selectable baseline.
- Clean regime trains on genuine labels. Noisy regime flips **one** train label at zero-based index `(i*17+7)%63`, then fits all methods from the same corrupted training data and evaluates against unchanged clean holdout truth. Reuse target and final sample exactly, so pairs are matched. Count all learner merge attempts and compare final scores separately.
- Semantic drift negative control: same clean training data as clean regime, but long-string *target truth is inverted* after unseen length 11. A forced-predict API cannot distinguish the stable/drift targets from observed training labels; count unsupported predictions and report a concrete witness. Do not claim an OOD detector unless the learner exposes a genuine abstention outcome (currently none).
- Budget: 24 targets x (63 training + 256 final) = 7,656 distinct clean-world label judgments; noisy uses the same original truth except one intentionally flipped label; drift uses a counterfactual judge on the same 256 strings. If counting replay visits across arms, report separately and never equate with distinct labels. Evaluator's computational cost includes at least merge attempts and elapsed/CPU time (diagnostic; hardware not controlled). Test-generation retries must be logged.

## Predeclared acceptance/falsification
R1 transfer candidate considered useful for **further independent research**, not production, only if ALL:
1. Clean R1 mean holdout accuracy exceeds the per-task hindsight best control by **>= +0.05 absolute**, AND >= 18/24 tasks achieve >= 0.90 accuracy.
2. Noise arm R1 mean holdout decrease versus clean <= 0.05 absolute, AND >= 16/24 tasks >= 0.90 accuracy, AND noisy R1 mean beats noisy per-task hindsight control by >= +0.02 absolute.
3. Irrespective of 1/2, if stable and inverted-drift worlds are indistinguishable from training, **automatic semantic transfer remains HALT** unless an independently validated abstention mechanism exists. Current R1 API produces forced binary outputs, so this is expected to disallow unconditional promotion.
4. R8 null canary must match its pinned committed public report; disagreement or missing exact-HEAD checkout HALTs intake even if R1 score is positive. Matching does not imply false-positive rate is controlled under real adaptive selection.

Report separate H1–H5 earlier R1 statuses exactly as their sources: H2 positive on author-generated 2–5-state public tasks; H3, H5 have falsifiers and scientific NOT_ASSESSED. R8 nominal 9/512 public null false positives are **nonzero**, so never say zero false acceptance. Distinguish reference/source tests from coordinator independent target study; return a SHA256 reproducible JSON receipt. Changes to this protocol after observing results require a new version and cannot erase a failed gate. No use of paid models or hidden holdout. **Draft PR; DO NOT MERGE.**
