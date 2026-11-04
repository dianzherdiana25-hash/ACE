# ACE E1.4c — Cross-Episode Query-Policy Transfer PRELOCK v1

**Registration status:** PRE-SCORING, public development only. Do not edit this study to rescue the result after any source or target scoring. Freeze a Git commit before evaluating the runner.

## Why this experiment

E1.4b showed a heterogeneous improvement for model-disagreement querying in two synthetic task families. It did **not** test whether an acquired *query-selection policy* transfers to a different hidden rule. E1.4c tests a narrower claim: selecting among pre-existing unlabeled query heuristics using labeled source interventions can improve target test accuracy relative to task-local querying, sham inheritance, and one-label random expectation.

## Frozen design

- Two families, `S` (symbolic adjacent-comparison event words) and `G` (single-chain graph label-event words). The candidate hypothesis inventory contains **only four-event words**; this is a finite model class chosen by human engineers, not automated grammar invention.
- `bank_seed=141701`, `pilot_seed=141702`; 12 disjoint source→target pairs, six per family, with **three one-edit related** and **three >=3-edit unrelated** motif pairs per family.
- All words in this bank must differ from the earlier E1.4 query pilot and E1.4b replication words, and all input-level source and target roles must be distinct from prior public fixtures. A normalized input overlap test must run before scoring.
- Each task has two labeled **word-avoiding** demonstrations, eight unlabeled pool questions drawn **without oracle/predictor consultation**, and eight independently labeled held-out probes (four word-positive and four negative). The bank explicitly makes model uncertainty likely; the heldout distribution is therefore *engineered*, not representative of real-world tasks.
- Candidate is a finite four-event exhaustive fit over demonstrations. Ties choose the lexically first hypothesis. Eight predefined heuristics: first, last, shortest, longest disagreement; maximum/minimum output-partition diversity; seeded disagreement; seeded uniform. Candidate query selection has **no access to the true target word**, pool labels, or held-out labels.
- First, each of the 12 source tasks evaluates eight one-label interventions. Source-only accuracies select **one fixed heuristic per family** (48 source labels per family). A sham heuristic applies a deterministic rotation of the source utility-to-policy association, destroying the intended mapping. Target interventions are **not scored before source policy selection**.
- Then, 12 unseen target tasks each score the same eight counterfactual one-label interventions exactly once. Primary endpoints on eight probes: inherited policy, sham, class-aware task-local `max_partition`, and exact expectation of uniform one-label random. Secondary: seeded local disagreement, no extra label, hindsight one-label oracle upper bound. One target label per *deployment policy*; exhaustive counterfactual evaluation incurs eight evaluator oracle calls and is **not** one physical label.
- Primary aggregation is separately reported for S/G x related/unrelated (4 strata, 3 targets each, 24 probes per stratum). A `GO_CROSS_EPISODE_TRANSFER_DEVELOPMENT_ONLY` requires inherited score to be **strictly greater** than sham, local max-partition, uniform expectation, and no-label *in every stratum*. Any failure: `HOLD_CROSS_EPISODE_TRANSFER_HYPOTHESIS`. Unresolved integrity or resource cap: `HOLD_RESOURCE_INTEGRITY`.
- No statistical significance claim is authorized on these 12 target tasks. The entire study is engineering **development**, not independent confirmation.

## Isolation, budget and negative results

- Candidate and evaluator are distinct Python modules but reside in the **same process**; this is not an isolated-worker E1.3/E1.4b trial. An external bounded process imposes a maximum runtime and captures an exit code and stdout/stderr SHA-256. A correct exit is NOT evidence of semantic non-leakage.
- All 8 source interventions per task are used for heuristic selection. Total 96 source labels; the target arms expend up to 96 additional oracle calls to compute exact uniform expectation, but each compared deployment arm uses one label. **Overall label-cost parity is not established**, because inherited policy carries training overhead.
- Test disjoint role and earlier bank inputs, identical per-target probes, exact arithmetic, policy selection before targets, deterministic replay and oracle/candidate semantics agreement. Keep leakage, both-wrong, no-disagreement, representation-capacity, negative-transfer and the no-inheritance baseline visible.
- Do not tune to the target results, open the E1.3 sealed bank, modify ACE's charter, change Tod, purchase services, or merge to `main`.

## Hypothesis scope

The long-term goal remains **Open-Ended Autonomous Intelligence Evolution**, including architecture-agnostic successor systems. This pilot only explores transferable choices among a fixed set of methods; it **cannot** establish autonomous research, self-invention, or open-ended general intelligence. A failed gate is a scientific HOLD, **not** a request for the user's permission.
