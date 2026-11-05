# ACE Issue #13 — one shared label budget engineering contract (v1)

**Status:** IMPLEMENTED_AND_UNIT_TESTED **only for the reusable evaluator-side journal**; integrated branching-graph experiment is **not implemented, frozen, scored or accepted** by this change. This is a new engineering interface, not an amendment to any historical E1.4 freeze.

## Evidence and motivation

- In [E1.4o](../design/e1.4/E14O_RESULT_v1.md), the graph-chain active loop fully recovered just **1/9** reachable graph worlds under a shared four-label cap; symbolic recovered 8/9. This is a scientific HOLD for the combined loop, not an infrastructure defect.
- In [E1.4q](../design/e1.4/E14Q_RESULT_v1.md), packed branching-graph queries improved diagnosis in controlled shared-prefix cells, but cost more nodes/edges than chains.
- In [E1.4s](../design/e1.4/E14S_RESULT_v1.md), bounded qualification with up to three labels rejected all wrong motif pairs in its known grammar, but generalization to novel semantics is not supported (**NATURAL_HOLD**).
- [Issue #13](https://github.com/dianzherdiana25-hash/ACE/issues/13) needs a fresh graph bank to test detection → repair → qualified reuse with **one total four-label budget**, rather than treating three individually successful components as one scientifically validated system.

## Implemented code — reusable budget journal

- [`code/e14/e14_shared_budget.py`](../code/e14/e14_shared_budget.py) provides `SharedLabelBudget(cap=4)` and `BudgetContractError`.
- [`code/e14/test_e14_shared_budget.py`](../code/e14/test_e14_shared_budget.py) contains **12 unit tests**, run with Python **3.13.5** in a separate local harness; **12/12 PASS**. Two code blobs were verified byte-for-byte against their locally tested Git blob hashes before attachment.
- Tested: shared cap over diagnosis/repair/qualification/inheritance; cross-stage label reuse without new charge; persistent charged reservations after interruption; pending-reservation reconciliation; duplicate query refusal; `None` as a legitimate negative response; canonical JSON and SHA-256 checks; journal recovery; resource totals; invalid labels/cost/stage/cap and tampering failures.
- Run from complete ACE checkout: `PYTHONPATH=code python3 -m unittest e14.test_e14_shared_budget -v`.
- The **full 114-test ACE suite is not rerun in this chat host**. This module does not call the target oracle, the Bubblewrap worker or any scored bank and **does not establish end-to-end correctness**.

## Integration invariants — mandatory for Codex and the independent auditor

1. The trusted evaluator creates exactly **one ledger per world × strategy**, initialized with cap 4. **No stage may create a separate budget.** The worker sees remaining budget and only the labels actually purchased for that arm.
2. Before each real target-oracle request, validate query legality, validate per-query graph limits, call `reserve(stage, query, cost={nodes, edges, events})`, and **durably checkpoint the pending reservation** before invoking the oracle. Then call oracle once, `settle(receipt_id, answer)`, and durably checkpoint the settlement. On interruption, do not silently refund a pending reservation or blindly retry it; reconcile from trusted durable evaluator state. The current journal is **in-memory**; durable SQLite integration remains necessary.
3. A diagnosis label can be fed into repair/qualification/inheritance by `reuse(receipt_id, stage)`; this must not count as a second oracle label. The receipt's `reused_in` audit field records stages. Duplicate canonical query purchases fail rather than bypassing the budget.
4. No worker may choose or view a held-out probe label, source oracle implementation, sealed bank, or external secret. All labels are purchased by the trusted isolated evaluator, and resource accounting must be computed independently of the worker.
5. A `None` oracle output is a **purchased** negative label, not a free abstention. A worker decision to abstain without a query costs zero target label but must decrease accepted coverage in the report.
6. The journal's `nodes/edges/events` are **caller-supplied declared costs**, not verified against query topology by the journal. The scorer and *independent auditor* must derive the actual counts from validated typed graph input and reject discrepancies; semantic graph duplicates may require stronger canonicalization than the journal's JSON digest.
7. Distinguish **target intervention labels** (cap 4 per arm) from initial demonstrations, hidden probes, exhaustive auditor counterfactual calls, replays, training and warm-up. Record every category in the raw report; do not present cap 4 as total physical oracle invocations.
8. Compare strategy arms under matched total target label caps and document graph nodes/edges, worker calls, candidate fits, CPU, memory and wall time. Outcome metrics: detection, repair success, qualification correctness, use/abstain, total held-out probe coverage, wrong accepted predictions, false expansion and rare/novel failures. Do not score abstentions as correct predictions.
9. Independently replay each output from a fresh ledger and verify snapshot digests, four-label cap, purchased queries, responses, and all stage transitions against the oracle. Include interruption/crash/resume and deliberately corrupted evidence tests.
10. Before scoring a **new** integrated benchmark, prespecify novel bank, seeds, full scoring gates, source-code/bank SHA, four strata (natural, reachable, rare, out-of-grammar), strong equal-budget baselines, and a strict GO/HOLD rule. Do not adjust those after viewing target outcomes.

## Next bounded Codex implementation sprint

1. Start from refreshed GitHub HEAD and read Issue #13, this document, E1.4o/E1.4q/E1.4s results and `NEXT_ACTION.md`. Do not retest or change frozen E1.4o/E1.4s banks.
2. In an isolated `codex/13-integrated-graph-loop` branch, **integrate the shared journal into a new evaluator-side orchestration** for the branching graph. The implementation should produce one independently auditable `steps` trace and one journal snapshot **per strategy**. Keep all candidate search work inside an isolated worker. Ensure resource-cost verification is independent, not a trust in worker counters.
3. Add integration tests for complete four-label use, a diagnosis receipt reused during repair, unresolvable ambiguity, out-of-grammar abstention, a misleading short motif, a timeout after reserve, runner resume without free extra query, and label-equivalent arm comparisons.
4. Implement a **new** untouched public bank + freeze manifest and full protocol. Audit bank freshness/novelty, oracle nonexposure, hidden probes, cost accounting, negative cases and strict thresholds before any scoring.
5. After frozen readback and suite success, run score / independent replay / oracle audit with bounded logs, raw gzipped evidence and per-stratum decisions. If scientifically HOLD, preserve the negative conclusion and hand off a *new* testable hypothesis; do not rescue the scored bank.
6. Open a PR against `research/e1.3-design`, not `main`. Include exact commands, logs, test counts, resource budgets, raw results, limitations, and proposed next action. Do not claim engineering acceptance from this standalone journal alone.

**Owner constraints:** no additional spend, no Tod edits, no `main` merge, no opening sealed E1.3 confirmatory material, no unvalidated sandbox substitution. Claude involvement is paused; Codex and this ChatGPT thread are the active workflow. GitHub coordination does not autonomously launch Codex.
