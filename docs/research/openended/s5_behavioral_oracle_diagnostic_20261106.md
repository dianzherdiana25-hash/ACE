# S5: behavioral-equivalence oracle diagnostic (2026-11-06)

Scientific status: **REJECT** the zero-output proxy as a stand-alone measure of behavioral task solving. PUBLIC SYNTHETIC DEVELOPMENT, not OAIE, not confirmatory.

## Predeclared hypothesis and decision
The zero-output witness proxy represents a behaviorally correct solution in >=95% of its positive events. Reject if >5% of proxy hits disagree with an exhaustive 256-probe response-function oracle. This rule was written into the local script before the local execution; it was not independently timestamp-locked in GitHub before running, so this is an exploratory rather than independently preregistered experiment.

## Experiment
Five methods (QD archive, greedy, random drift, no-archive QD, fixed curriculum), four predefined families (xor, rotate, parity, threshold), 48 evaluation seeds (100..147), 64 candidate proposals per arm. 960 arms, 61,440 synthetic selection labels/proposals, 14,739 proxy-hit candidate checks, 3,773,184 independent diagnostic probe comparisons. The exhaustive behavioral oracle evaluates the response function defined by each proposed parameter at all 256 inputs and compares it to the target response function, thereby allowing behaviorally equivalent but parameter-distinct candidates.

## Actual local result
Proxy hits: **14,739**. Behaviorally correct hits: **6,194**. False proxy hits: **8,545 (57.9754%)**. Decision **REJECT** (greater than 5%). Local process CPU: **0.441862 s** (machine-specific). This is a diagnostic of proxy validity, not an independent ranking of the search algorithms. No external oracle or paid label was used.

## Limitations
The four families and seeds are public and author-designed; this is not disjoint-family generalization. Exhaustive 256-probe oracle was used for evaluation only, not selection. Random and QD-no-archive have identical sampling rules in this diagnostic, so the no-archive comparison does not isolate archive effects. Candidate success is a response-function property, not parameter identity; the earlier parameter-identity proxy diagnostic cannot be read as a behavioral failure rate. Code was run locally before commit; exact GitHub-head replay and independent CI are not claimed. Local script SHA256 before cleanup: `3604f8a7a6fbd07ac737cb008bad7c7f8f9662c02abac65f7813df69cbdc5cf0`. Committed code omits an unused import, so source bytes differ and the committed SHA requires separate replay. Frozen E1.4/E1.4aa evidence and HOLD/NOT_ASSESSED are untouched.

## Next falsifiable experiment
Evaluate learned behavioral descriptors from training-only generator families on independently generated family-disjoint evaluation tasks, with fixed candidate/label budgets and independent response-function oracle; require >=10 percentage-point improvement over greedy and random, compare to random-descriptor, operator-matched no-archive and fixed-curriculum controls, and reject on task-ID-only novelty or failure under semantic remapping.
