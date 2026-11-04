# ACE E1.4c-v2 — corrected source-to-target query-policy pilot

**Decision: `HOLD_CROSS_EPISODE_TRANSFER_HYPOTHESIS`.** The previously prespecified **four-stratum** gate was not met, even after correcting the word-dependent random-stream flaw in the query-pool generator. This is a **corrective public-development follow-up**, not an independent confirmatory experiment.

## Pre-scoring freeze, source and sample integrity

- Frozen code and protocol committed to [GitHub `caedbe7`](https://github.com/dianzherdiana25-hash/ACE/commit/caedbe761cab31da306459b5e6a3f3dd86255d0b). Four source/protocol Git blobs matched the local bytes before scoring. This commit follows the disclosure of a methodological weakness in E1.4c-v1 (which remains archived at `bf43a97`).
- Candidate policies, finite four-event hypothesis grammar, source-only training logic, 4-stratum primary gate and budget definitions remain the same as v1. The specific correction is **preallocation** of all 24 unlabelled eight-question pools with separate per-family/slot PRNG seeds, **before** making any word-conditioned demonstration/probe. The v1 public inputs are added to the reserved used-set before allocating v2 pools.
- Bank SHA-256 `96abeaf7434a95ae1e80f3011db89aed9d6ab76650ba11c0fe8cc6d895062e8a`. Source/target roles: 12 source and 12 target tasks, 3 related + 3 unrelated targets per family. **432/432 new normalized raw inputs** distinct from prior public inputs, v1, and within this bank.
- The new test suite changes secret-word coordinates without changing pool output, checks oracle-free preallocation and disjoint roles, and checks unchanged motif IDs; **4/4 special tests PASS before scoring**. This establishes deterministic code-path invariance, not a statistical causal identification proof.

## Prespecified scores — correct / 24 independent held-out probes per group

| Family / regime | Inherited | Task-local max-partition | Sham | Uniform one-label expectation | No extra label | Hindsight one-label ceiling |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| S / related | **12** | **15** | 11 | 11.625 | 11 | 16 |
| S / unrelated | **12** | 12 | 12 | 12.375 | 12 | 16 |
| G / related | **16** | 16 | 16 | 15.75 | 16 | 20 |
| G / unrelated | **16** | 11 | 11 | 11.75 | 11 | 16 |
| **All 12 targets** | **56/96** | 54/96 | 50/96 | 51.5/96 | 50/96 | 68/96 |

- Source-trained strategies: `S = first_disagreement`, `G = last_disagreement`; sham: `S = min_partition`, `G = seeded_disagreement`.
- The inherited strategy **does not strictly exceed** all comparators in all strata: S/related loses to task-local (12 vs 15), S/unrelated loses to uniform expectation (12 vs 12.375), and G/related only ties three baselines. G/unrelated shows a conditional benefit (16 vs task-local 11), but that cannot override the frozen gate.
- The aggregate inherited score of 56/96 is **not** evidence of general transfer; sample count is just three targets per stratum, with designed four-positive/four-negative probe distribution and nonindependent rule families. No significance claim is made.

## Budget, replay and verification

- Source training: **96 oracle labels** (8 for each of 12 source tasks). Source data is used to pick one fixed family heuristic **before target scoring**. Target: 96 counterfactual oracle calls (all eight choices for 12 targets) to calculate uniform-one-label expectation. Any deployed target policy would query **one label**, but total training/experiment label cost is not equivalent to a one-label baseline.
- `run` finished with exit 0 under a **90-second bounded supervisor** (about 6 seconds), followed by separate `--verify` replay with exit 0 and **canonical JSON equality**. Frozen raw evidence SHA-256: `00bb3550434490ca06cd3cba349fa9687036296650a119be7750628f5968411e`.
- Saved-report consistency auditor recalculated source policy utility mappings, target choices, all score strata, random expectations, resource and decision accounting. The auditor now accepts v1 or v2 modes; **8/8 corruption/audit unit tests PASS**. This audit does not establish oracle correctness or independent worker isolation.
- E1.4 module regression log reports **29/29 tests PASS**. The orchestration container tool itself returned a timeout before collecting the supervisor exit event; no active process remained and the test log completed with `Ran 29 tests ... OK`. This is a host/tool reporting limitation, not a claim that an external CI gate passed. The earlier narrower E1.4v2 structural test (4/4) and direct audit (8/8) had terminal success.
- All experiments were **same-process** implementations, *not* the genuine E1.3 Bubblewrap isolated runner. Exact security/custody and compute-parity confirmation are still open.

## Interpretation and next decision

- **HOLD the hypothesis that this fixed, family-specific inherited heuristic reliably beats target-local baselines.** The result is heterogeneous across tasks and both pilots used different (though deterministic) input generation. The v2 correction addresses a dependency defect, but v2 was **planned after inspecting v1**, so it is neither independent nor confirmatory.
- The next scientifically useful task is E1.4d: test a **context-conditioned policy** that learns *when* a question selector is useful (uncertainty, model disagreement, source/target structure) instead of inheriting one global heuristic per family. Add an equal **end-to-end source acquisition and target query budget**, a genuine independent informed-reference comparator, longer/larger random pools without engineered positives, and an external or proper isolated evaluator. Build tests that reject oracle leakage, initial model equivalence, both-wrong, and misleading no-disagreement cases.
- Do not repeatedly tune on these 12 v2 target examples, don't force GO, don't open E1.3 sealed confirmation, don't alter Tod or `main`, and keep ACE's architecture-agnostic long-term **Open-Ended Autonomous Intelligence Evolution** vision without claims of attainment.
