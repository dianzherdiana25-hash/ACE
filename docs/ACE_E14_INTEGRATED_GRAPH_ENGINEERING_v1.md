# ACE Issue #13 — integrated graph engineering checkpoint (2026-11-05)

**Status: ENGINEERING_PARTIAL / SCIENTIFIC_OPEN.** This is a new working-branch checkpoint, **not** a scientific GO, not a new E1.4 freeze, and not evidence of OAIE. The historic E1.4o graph-chain HOLD, E1.4s bounded-qualification GO, robust-inheritance HOLD and NATURAL_HOLD remain intact.

## Concrete implementation

- `code/e14/e14_integrated_graph.py`: evaluator-side graph validator and exact-cost public oracle, strict limits of 16 nodes, 16 typed edges, 16 completed paths and 256 enumerated path events. Graph resource cost is computed from typed topology, not trusted from the worker. Canonical edge ordering prevents reordered duplicate-query purchases.
- The same module adds `DurableGraphBudget`, backed by an SQLite journal scoped to **one world × one strategy**, with a shared four-label cap inherited from `SharedLabelBudget`. `reserve` commits a pending receipt **before** oracle invocation. `settle` and `reuse` commit their transitions. Pending reservations remain charged after interruption; attempts to buy another query fail closed until trusted reconciliation.
- `audit_journal` revalidates stored digest/receipt structure, query topology, resource costs, and optionally recomputes each settled oracle label. Auditor calls are counted separately from the purchased four target labels.
- `execute_protocol` provides an action-limited engineering driver for query → receipt reuse → accept/abstain. It **does not** isolate the policy from its Python closure or guarantee private target nonexposure.
- `code/e14/e14_integrated_policy.py`: a **mapped-only engineering control** that composes existing E1.4r mapped-interpretation queries and E1.4s shorter-motif qualification; reuses the diagnosis receipt in the repair and inheritance stages. Here “repair” means **interpreting an existing mapped hypothesis**, not inventing a new graph representation or grammar.

## Verified local results

Environment: Python 3.13.5, locally constructed test checkout containing byte-verified **new** GitHub source blobs and locally reconstructed compatible historical E1.4 dependencies. This is **not** a regression run on a complete live GitHub checkout.

Command from repository root:

```bash
PYTHONPATH=code:. python3 -W error::ResourceWarning -m unittest \
  e14.test_e14_integrated_graph \
  e14.test_e14_integrated_policy \
  e14.test_e14_issue13_smoke -v
PYTHONPATH=code:. python3 tools/ace_issue13_smoke.py --output WORK/issue13-smoke.json
```

**33/33 local engineering unit tests PASS, exit 0.** Tests cover graph cost derivation and resource mismatch, strict typed edges and path caps, semantic duplicate purchases, four-label shared cap, `None` as paid negative evidence, crash during oracle purchase, reopening the SQLite journal, concurrent reservations, a corrupted checksum, a mismatched oracle replay, receipt reuse, deterministic policy execution and a deliberately wrong-accept control. The repository-wide 114-test historical suite **has not** been rerun against this branch.

The **hand-chosen public engineering smoke** contains 6 example truths × 3 existing-component controls = **18 arms**. It is not a newly frozen or blinded benchmark.

| Control | Correct accepted | Wrong accepted | Abstain | Target labels bought | Auditor oracle calls |
| --- | ---: | ---: | ---: | ---: | ---: |
| Active mapped + guard | 3 | 0 | 3 | 14 | 14 |
| Fixed mapped + guard | 3 | 0 | 3 | 14 | 14 |
| One positive receipt only | 3 | 2 | 1 | 6 | 6 |

Deterministic smoke report SHA-256 (canonical report, excluding the hash field):
`dfca7b9d32358566719bca84f44e8ac3f43f7518ae51e5a1d80181ffdae7e318`.
The smoke includes no statistical inference and cannot support an independent claim of transfer or new capability discovery. Equal budget **caps** do not imply equal labels **spent**.

## Critical limitations / hold points

1. **Independent isolation NOT verified.** The engineering driver executes policy and trusted oracle in one Python process. It cannot be used on sealed scientific tasks. A real isolated worker stage and tests of evaluator, file, secret and network nonexposure must precede scoring.
2. **Representation repair not implemented end-to-end.** The mapped control can distinguish a supplied closed set and reject known shorter aliases; it does not autonomously synthesize an out-of-grammar replacement. The integrated four-label scientific problem remains OPEN.
3. **Pending-oracle ambiguity remains a real boundary.** The journal preserves reservation and prevents a blind retry, but operator-side `settle` does not itself verify an external oracle-response record. The scorer must durably bind oracle invocation/result to the receipt and reconcile UNKNOWN before resuming.
4. **SQLite digest is not an adversarial signature.** It detects accidental corruption; an attacker able to rewrite payload and checksum together is outside this module's threat model. Sealed scoring needs trusted storage and an independent audit.
5. **Query cost and resource counters are only partial.** Event cost sums positions across bounded completed graph routes. Full future experiment also requires worker CPU/wall/RSS, fit counts, graph generation attempts, demonstrations, source-acquisition labels, and all auditor/probe oracle calls.
6. **No fresh prescored bank, B*, replayed isolated scientific score, or confirmatory evidence** was produced. Existing historical frozen banks and E1.3 sealed confirmation data were not touched.

## Next implementation gates for this Issue

1. Integrate the new journal with the existing official Bubblewrap worker staging and exact-head evaluator; test the actual worker can see only its own observations and offers. No substitute for validating the full boundary.
2. Add a genuinely representation-expanding graph-repair candidate and a distinct guarded inheritance decision, both consuming the same four-label journal. Compare against fixed, exhaustive, no-inheritance and sham controls under matching resource caps.
3. Build a **fresh evaluator-owned** graph bank for natural, reachable, rare, and out-of-grammar strata. Define novelty audit, fixed seeds, eligibility, controls and GO/HOLD thresholds; freeze code and bank before any target scoring.
4. Run the complete 114-test regression **plus new tests** from a clean checkout, then bounded score, fresh-ledger replay, oracle audit and interruption/recovery. Record terminal states and exact commit SHA. Preserve negative outcomes.
5. Submit for review via a draft PR targeting `research/e1.3-design`. Do **not** merge `main`, edit Tod, run paid infrastructure or reinterpret historical GO/HOLD decisions.

**Issue:** https://github.com/dianzherdiana25-hash/ACE/issues/13
