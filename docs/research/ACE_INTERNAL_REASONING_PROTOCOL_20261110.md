# ACE internal reasoning integration — protocol v1

Registered before implementation/scoring on 2026-11-10. Base: PR #94 head
`52394dcf6f203197ffa66b2dc7f802c475690a63`. Ownership: new
`code/ace_cognition/reasoning*.py`, `tools/ace_reasoning*.py`, this protocol,
new audit/reasoning evidence and a dedicated CI workflow. No daemon/main,
frozen source, historical evidence, evaluator or other branch is changed.

## Hypotheses and limits

H1 (engineering): a data-only integration of the existing ComponentSynthesizer
can synthesize internally, validate, persist and recall closed arithmetic/Boolean
programs with zero external AI calls. At least 7/8 nominal families must attain
>=95% terminal correctness on every one of three public seeds. Failures stay
in the report. This is supplied-grammar reasoning, not new primitive discovery.

H2 (engineering): malicious/out-of-schema advice is rejected before execution;
wrong well-typed advice with a development counterexample is rejected. Missing
solutions and exhausted budgets abstain. Predictions require exact train and
validation correctness. Restarted memory is revalidated, never trusted by name.

H3 (narrow retention): a second process reuses each successfully synthesized
program on new development inputs of the SAME rule with zero new synthesis
candidates and unchanged program digest. This is executable retention and
within-rule reuse, not cross-family transfer or a learned learning algorithm.

H4 (negative control): indistinguishable hidden terminal semantic shifts are
expected to defeat empirical admission. Report false admissions and terminal
errors; do not turn this into an unsupported OOD detection claim.

## Tasks, baselines and separation

Eight nominal rules: x+y, x-y, x*y, 2*(x+y), x*x+y, x==y, x<y,
x+y==2. Internal allowed operators are the EXISTING component-library
add/sub/mul/eq/lt; no newly written task-specific solver. Maximum search depth
2, 5,000 nominal search candidates (upstream checks are soft), 300,000 actual
primitive operations and 5 seconds per solve. Integer inputs bounded to 64;
program depth <=4, nodes <=31 and intermediate magnitude <=1,000,000.

Public seeds: 20261110, 20261111, 20261112. Per rule/seed: 12 training inputs
from [-3,3]^2, 12 disjoint validation inputs from [-6,6]^2 outside training,
24 disjoint terminal inputs from [-12,12]^2 outside both. Shuffle once by seed.
Selection sees train and validation only. Terminal is scored AFTER selection and
cannot be passed to the reasoning interface. No terminal tuning or replacement
of failed task families. Record labels, work counters, wall/CPU, peak memory and
source hashes. These are public generated splits, NOT an independent sealed bank.

A: internal reasoning, external models disabled. Strong baseline F: the SAME
fresh ComponentSynthesizer, same operators, examples and limits; no expected
novel solver advantage. Compare exact terminal predictions and measured work.
Weak fixed comparator: supplied x+y predictor, explicitly secondary.

B-fixture: synthetic advisor JSON containing wrong and valid candidate trees;
test rejection/acceptance and costs using the same development labels. This is
an injection test, NOT a real model consultation. Real B and C (AI as primary
controller) are NOT_RUN / NOT_ASSESSED unless an authorized available provider
can be called with logged identity, token usage, cost and identical information
budgets. Never rename fixtures into real external-AI experiments.

Controls: inconsistent training labels, validation disagreement, unsupported
advice including a source-execution payload, hard operation exhaustion,
corrupted stored tree and a hidden terminal sign/Boolean inversion. Stop on
unexpected source execution or historical/frozen-file changes. No deployment,
no paid resources and no promotion. Scientific status remains NOT_ASSESSED.

## Reproduction and decision

Commit this protocol before creating the integration. Store raw machine-readable
results, measured resource data, tests and replay hashes. Canonical deterministic
scientific cells are separate from volatile profiling. Run exact-head GitHub CI
and create a draft stacked PR to the audited fix branch. A successful narrow
slice supports further independent evaluation, never OAIE or scientific GO.
