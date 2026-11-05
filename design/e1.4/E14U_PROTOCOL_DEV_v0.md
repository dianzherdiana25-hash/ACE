# E1.4u — two-route graph-global representation, DEVELOPMENT PROTOCOL v0

**NOT FROZEN. NOT CONFIRMATORY.** This file describes a completed exploratory engineering experiment and proposes a future preregistered scientific test; it is not a prescore lock. Original E1.4t scores, bank, and HOLD remain immutable.

## Scientific hypothesis

A hypothesis DSL restricted to `exists path with contiguous motif` cannot represent a predicate that requires *two different paths* satisfying two motifs. A new typed graph-global `branch-pair` constructor should be able to fit positive and route-specific negative observations and choose informative weighted DAG queries under a shared four-label intervention cap. This tests an **increased representational basis**, not self-invention of a previously unspecified basis.

## Current development setup

Worlds: 28 pair targets from all unordered distinct binary length-3 motif pairs, eight single motif controls, six three-route conjunction truths (outside the worker grammar). Each world provides an aligned positive graph and one-path negatives or pairwise negatives. Four arms (`active`, `fixed`, `random`, `base-only`) receive the identical initial demonstrations, but different intervention strategies. The evaluator draws up to four charged oracle labels per arm and always writes a pending SQLite receipt before invocation; receipt reuses cost no further target labels. Precomputed held-out probe labels and independent auditor labels are accounted outside the four-intervention cap.

The query pool has 70 four-branch DAGs with differentiated edge tolls, 16 edges maximum, four completed paths and 14 nodes. Active chooses a legal query by minimizing collisions among survivor labels, fixed chooses the first informative query, random chooses a seeded available query. Results are counted as **exact program recovery**, wrong exact acceptance, abstention, held-out probe coverage/error, per-arm label purchases and topology costs. Abstention is not scored as success.

## Important a posteriori limitation

The active method, candidate lengths, graph constructor and development worlds are not an independently randomized blind evaluation. Source demonstrations are generated from known target motifs. Eight additional seeds rerun those same truths after exploratory results were known. These are sensitivity checks and must not be used as new confirmatory evidence or to change any frozen scientific decision.

## Proposed next clean experiment (separate bank v1 required)

- Acquire the predecessor artifact through an actual learner and **charge its acquisition cost**; do not hand in target-aligned witness paths.
- Randomize graph geometry and path depth under the same typed graph limits, rather than always combining two disjoint chains with fixed route tolls.
- Add target representations of *branch conjunction*, branch disjunction, prefix-to-suffix shared-node relations and adversarial cost aliases; do not supply their constructor names to the worker in advance if the claim is primitive invention.
- Add equal-CPU and equal-fit baselines (`single`, `pair exhaustive`, `grammar search`, `sham source`, `no-inheritance`, and strong predeclared references) with identical four-label intervention cap.
- Predefine numerical GO/HOLD gates for exact semantic recovery, negative transfer, rare failure, false trigger, wrong acceptance and robust abstention **before opening a novel bank**.
- Validate official native Bubblewrap or an independently certified equivalent, then run exact-head full repository regression and isolated score/replay/audit; require source hashes and genuine fresh-ledger recovery.

Scientific status stays `HOLD / NOT ASSESSED` until those gates are met. Do not merge to `main` or alter Tod.
