# R3-v2 — neutral-step architecture search, exploratory negative evidence

2026-11-05. **Research-only**. This note supplements the existing JS v1 pilot. The Python v2 implementation, tests and full 180-case record are available in the conversation artifact `ACE_R3_v2_experiment.zip`. The Python code has **not** been committed to this PR; these figures are local-run evidence only, **not exact-PR-head CI**.

## Question and method
Do depth-stratified neutral stepping stones and depth-aware validation coverage improve typed Boolean dataflow topology search, compared with simple greedy topology evolution, random graph search and a cheaper fixed-wiring operation-configuration baseline?

All arms use 5 binary inputs, at most 5 AND/OR/XOR gates, 18 train / 7 validation / 7 final test examples, up to 240 scored candidates and 750 proposal attempts per case. The search arms share a cap of 9,000 evaluated gate operations per case, with actual expenditures reported separately. All candidate graphs are interpreted as closed typed data; no candidate Python code is executed. There is no external assessor or OS sandbox. Six development functions plus six *additional public author-visible* task functions, seeds 0, 1, 2; results are exploratory, not blinded confirmation.

## Development (18 task-seed cases/arm)

| Arm | Accuracy | Exact | Gate evaluations |
|---|---:|---:|---:|
| Fixed-wiring configurations | **78.57%** | 6/18 | 31,158 |
| Random topology | 46.03% | 0/18 | 156,502 |
| Greedy evolution | 72.22% | 5/18 | 146,079 |
| Neutral stepping stones | 53.97% | 0/18 | 156,670 |
| Neutral + coverage selection | 53.97% | 1/18 | 157,475 |

## Additional public tasks (18 task-seed cases/arm)

| Arm | Accuracy | Exact | Gate evaluations |
|---|---:|---:|---:|
| Fixed-wiring configurations | 50.79% | 1/18 | 31,158 |
| Random topology | 57.94% | 3/18 | 156,803 |
| Greedy evolution | 62.70% | **4/18** | 151,022 |
| Neutral stepping stones | 53.97% | 1/18 | 156,397 |
| Neutral + coverage selection | **63.49%** | 3/18 | 157,587 |

## Engineering checks
21/21 **local** Python unit tests passed (14 inherited v1 tests + 7 new v2 tests). The new tests cover deterministic repetition, invalid arms and edge validation, finite budgets, actual topology mutations, and a holdout-label inversion that changes test scoring without changing architecture selection. All 180 record rows were generated with the same source and declared budget, using separate runs per bank to avoid long in-process execution. Full independent exact-source replays of the combined v2 archive remain unverified.

## Interpretation
Neutral stepping stones alone lose to greedy in *both* banks. Neutral + validation coverage is worse than greedy by 18.25 percentage points in development, but ahead by only 0.79 points on the additional public bank, with greater measured gate-work and a lower number of perfect solutions. Neither positive nor negative split warrants population-level extrapolation. This does **not** meet the gate for scientific superiority, autonomous runtime self-modification or OAIE. The author-visible additional bank is not an independent holdout. A common per-case ceiling is not equal actual cost.

## Constraints
Do not merge, promote or integrate R3 based on this result. Do not change `main`, frozen E1.4, S4 or other agent directories. V2 code and evidence require separate exact-head commit + CI/replay verification if this research is advanced. The existing JS pilot in this PR remains the only runnable committed implementation at this point.
