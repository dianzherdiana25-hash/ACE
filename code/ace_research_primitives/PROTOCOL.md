# R1 protocol v0.1 — observation-induced computational state abstractions

Status: **PUBLIC DEVELOPMENT / preregistered protocol**, authored before scoring. No OAIE claim.

## Boundary relative to S2
S2 (#28, #36) searches expression syntax with supplied arithmetic operators. R1 does **not** search arithmetic programs, add AST operators, or edit source. It constructs automaton states and transitions by **merging data-induced prefix states** using positive/negative examples; final transition graph is not listed as a candidate in advance. This is classical RPNI-style grammar inference, not a novel learning algorithm or unrestricted invention. Existing E1.4u researcher-authored graph primitive is also separate.

## Hypothesis
H1: Within a strict budget of 63 binary-string labels per task, evidence-driven deterministic state merging forms reusable loop/state abstractions that generalize to unobserved string lengths (8–13), outperforming the best of a fixed hand-authored unary predicate library and an exact-prefix memorizer by **at least +0.05 mean holdout accuracy** across 9 preselected regular tasks; at least **6/9** regular tasks must achieve >=0.90 accuracy on 256 holdout strings each.

H0: one or both numerical conditions fail. A perfect training fit alone is not evidence of induction.

## Splits and public bank (no tuning after scores)
Alphabet: a,b. Training: all words length 0..5 (63 examples per task); validation: all words lengths 6..7 (192 per task), **diagnostic only**, not used for model selection; terminal holdout: 256 deterministically sampled words length 8..13 (seed=20261105 + task index), disjoint from train/validation. Generation code was first locally run after this protocol commit and before code upload; exact-head verification remains required.

9 regular families: parity count(a); count(a) mod 3 = 0; contains ab; no bb; ends ba; odd total length; no aba; count(a) mod 4 = 0; nonempty first symbol equals last.

Two separate *out-of-class stressors*: equal counts a and b; balanced-parentheses Dyck-1 language (a=open, b=close). Holdout negatives and positives deliberately balanced by generator (128 each), with lengths 10, 12, 14. These are not included in the primary aggregate; finite DFA cannot recognize them for all lengths.

## Controls and limits
1. Exact prefix-trie memorizer (unseen inputs -> reject).
2. Majority label by word suffix of length <=3.
3. Best finite *single* predicate from frozen library: constants, starts/ends with 1-3 character pattern, contains/avoids length-2 or length-3 substring, count(a/b) mod 2/3 residues and total-length parity (optionally negated). Choose by training error only, tie by deterministic library order. Shared 63 labels for all methods.
4. RPNI-style prefix-state merging. No target-function identity enters learner. Strict training-consistency required; bounded <=63 created states and <=10,000 proposed merges/task; no arbitrary eval/exec.

Scoring: exact classification accuracy and reachable state count. Report errors and counterexamples for each task, plus full budgets and source SHA. Negative-controls outcome is diagnostic, not a primary pass criterion.\n\n## Transparently disclosed post-exploratory amendment\nThe first protocol commit listed `a^n b^n` as the second stressor. With the declared short holdout lengths this has too few distinct positives to supply 128 balanced positive examples. Before uploading source/evidence, that stressor was replaced by Dyck-1. **This adjustment occurred after the first local exploratory execution and is NOT pre-registered evidence.** Primary H1 task list, seed, label budget, thresholds, fixed controls and aggregation were unchanged; do not interpret either stressor as independent confirmatory science.

## Integrity and limits
Use fixed seed and programmatically disjoint words. Before claiming empirical pass: actually execute code and unittest, retain raw JSON output, and read back GitHub exact branch HEAD. Local execution is not independent science; source/bank/algorithm family are author-designed; terminal data are synthetic, not real-world. No write outside code/ace_research_primitives/ on the R1 branch. No merge or promotion.
