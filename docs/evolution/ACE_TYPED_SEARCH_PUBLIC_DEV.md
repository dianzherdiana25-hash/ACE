# ACE bounded observational typed search — development only

## Scope
New isolated module `code/ace_evolution/typed_search.py`; no modification to ACE research-loop, E1.4 frozen evidence, or historical scorers. Bottom-up integer expression synthesis with +, -, *, constants and variables; no eval or execution of generated source. Candidate deduplication uses **observational equivalence on train + validation rows**, not semantic equivalence on unseen inputs. Depth <= 5, operators <= 6, candidates <= 100000 are hard ceilings; ordinary experiment uses depth 3, ops 3, 3000 candidates.

## Public synthetic development example (author-designed, NOT confirmatory)
Target is `3*x-2*y`, deliberately absent from the five manually enumerated proposals in the E1.5 source-evolution example. Train rows: (-3,2,-13),(-2,-1,-4),(0,1,-2),(2,0,6). Validation: (-5,3,-21),(4,-2,16),(1,5,-7). No holdout passed to search.

Measured local Python run (7/7 focused unittest cases PASS):
| Candidate cap | Status | Evaluated | Validation absolute error | Truncated |
|---|---|---:|---:|---|
| 20 | NO_TRAIN_FIT | 20 | n/a | yes |
| 100 | NO_TRAIN_FIT | 100 | n/a | yes |
| 300 | NO_TRAIN_FIT | 300 | n/a | yes |
| 1000 | FOUND | 1000 | 0 | yes |
| 3000 | FOUND | 2283 | 0 | no |

Selected expression at cap 3000: `((-2*y)+(3*x))`, train and validation absolute error zero. The same-author five-proposal fixed baseline yields train/validation errors: x+y 20/46; 2*x+y 15/38; 3*x+y 12/30; 3*x+2*y 16/40; 2*x+2*y 19/48. This comparison does NOT equalize search compute: fixed baseline uses five proposals; synthesis uses 2283 candidates. It shows grammar reach, not compute efficiency.

## Negative and adverse evidence
At candidate caps 20/100/300, search fails to find a training fit. Inconsistent identical-input labels (0,0,100) and (0,0,-100) yield NO_TRAIN_FIT. A cap of 1000 returns a valid fit but truncates; thus it cannot claim exhaustive search. Tests reject invalid integer data and hard-budget violations, check deterministic replay and reject a holdout argument. A zero validation error on a tiny public author-designed split does not establish out-of-distribution generalization.

## Reproduce
`cd code/ace_evolution && python -m unittest -v test_typed_search.py`

## Limitations / next steps
Observational dedup can discard expressions that differ outside observed rows, and grammar/constant/operator choices are human-specified. Input splits are public, not blinded. Add a predeclared disjoint hidden bank and independently evaluate, and compare strong grammar-matched enumerators under equal compute budgets before claiming improved research capability. This is not open-ended architecture discovery, OAIE, scientific GO, or proof of safe autonomous source mutation.
