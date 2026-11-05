# ACE E1.4x — Bounded-label semantic nonidentifiability

**5 November 2026 | Postscore public development | Scientific decision: NOT_ASSESSED**

## Constructive result

Among 192 previously evaluated E1.4w safe-policy worlds, 120 programs were originally accepted correctly. Every one of those 120 had three distinct paid target cost observations out of a 120-point legal integer domain. The other 117 cost pairs were unmeasured.

For each originally correct case, the new audit constructs a different operator by changing its value by +1 at a single valid unqueried cost pair. The altered operator is provably *not* represented in the original five-node expression grammar. It answers every purchased graph query identically to the original operator, but differs on an explicit legal witness graph. The archived certificates contain the exact graph, both computed costs, and full source record.

The unchanged deterministic learner was replayed with the altered operator and a fresh per-arm SQLite journal. In **120/120 cases**, the purchased graph digests, oracle labels, resource costs, stage/reuse records and accepted expression were identical to the original transcript. The same accepted program was now wrong for the countermodel; **zero replay failures**. This is a constructive worst-case impossibility bound under unrestricted semantic operators, not a measured natural-world error rate or new confirmatory score.

## Third-path evaluator checks

Three separate runs of the prior independent-DFS auditor covered all 12 main development batches. Recomputed counters: **12 predecessor tasks; 34 predecessor oracle receipts; 1,999 purchased target receipts; 6,912 logical held-out probe evaluations**. Oracle semantic, receipt, integrity and graph topology checks passed. Probe counts represent evaluations per arm, not unique physical oracle calls.

## Regression and reliable execution

After the 12 new E1.4x unit tests were included, **227/227 local tests PASS** in ten bounded execution groups, with SHA-256-hashed logs, explicit terminal receipts and a cross-checked aggregate. Long ablation was divided into two groups (4 tests each) to avoid ambiguous host-level timeouts. This is **not** a full historical GitHub checkout regression and does not certify native Bubblewrap isolation.

## Limits and next actions

All countermodels are intentionally constructed *after* observing the original results. The finding does not alter the original E1.4w within-grammar success, E1.4t HOLD, or the E1.4u/v scientific status. Its proof is conditional on deterministic observed transcripts and an unrestricted class of cost functions on the specified finite domain. A randomized policy requires treatment of the seed and adversary visibility.

Next scientific direction: attach precise assumption scopes to accepted claims; distinguish confidence *within an assumed grammar* from confidence over novel operators; test structured grammar-extension policies on a new precommitted independent bank and independently learned source tasks. No Tod, ACE main, sealed E1.3, or frozen E1.4t files changed. No Codex escalation required for this engineering sprint.

## Typed assumption-scope contract — postscore engineering extension

A separate follow-up implements the contract in `e14x_assumption_contract.py`. It verifies the receipt structure, canonical graph resource costs, canonical predecessor artifact shape, and exact uniqueness inside the five-node DSL. It reports **conditional acceptance** only when `bounded-dsl-assumed` is explicitly selected; for unrestricted operators it returns `abstain` with the reason `UNRESTRICTED_OPERATOR_NOT_IDENTIFIABLE`. Neither operation grants new target labels.

On the same 192 archived safe-policy worlds, the conditional branch accepts **120** and abstains on **72**; the unrestricted branch accepts **0** and abstains on **192**. This is a deliberately zero-coverage worst-case guarantee, not a useful general purpose detection rate. Nine new unit tests cover the claim behavior, typed inputs, journal tampering, lineage failure and zero-purchase scope switching. **Updated local test count: 236/236 PASS across 10 bounded groups**, instead of the earlier 227/227 checkpoint. This update retains all prior E1.4w and E1.4x evidence, including negative results.
