# ACE E1.4w — large exploratory result and falsification record

**Status: PUBLIC DEVELOPMENT / SCIENTIFIC NOT_ASSESSED.** The tested grammar is enumerated from supplied primitives; it does not invent its own operators.

## Main: 192 worlds × 6 strategies (1,152 arms)

| Strategy | Exact accepted | Wrong accepted | Abstain | Target labels | Accepted-probe errors |
| --- | ---: | ---: | ---: | ---: | ---: |
| Size-5 symbolic + 3-label check | **120** | **0** | 72 | 430 | 0 |
| Size-5 symbolic + early acceptance | 120 | **30** | 42 | 180 | 151 |
| Size-5 random question + check | 120 | 0 | 72 | 431 | 0 |
| Small size-3 grammar + check | 20 | 0 | 172 | 250 | 0 |
| True motif pair provided (upper bound) | 144 | 0 | 48 | 516 | 0 |
| Wrong inherited motif pair (sham) | 0 | 0 | 192 | 192 | 0 |

The MAX-rule predecessor learned 10/12 supplied motif pairs from **34 purchased source labels**. The difference 120 vs 144 exact acceptances is entirely attributable to those two unresolved pairs, not to success at inventing the operator formula. **1,999 purchased target labels**, independently reconstructed receipt-by-receipt; 6,912 logical probe evaluations were checked using a separate route walker and iterative program evaluator.

## Outside the grammar: adversarial falsification

Eight extra outside-family programs in **96 worlds / 576 arms**: safe checked policy falsely accepted **10** cases (28 probe errors); eager falsely accepted **30** (134 errors); random checked falsely accepted **12** (33 errors). All ten safe false accepts arose from the `gap-parity` operator: the purchased cost examples happened to share even differences, making the unseen rule indistinguishable from `lo+hi` at those points. This is a concrete counterexample to treating uniqueness in the finite candidate library as truth.

A distance-maximizing fourth-label check failed to reject these ten on the same postscore worlds (10 wrong accepted), while a neighboring-cost fourth-label check rejected them (0 wrong accepted). Each spent **690** target labels over 288 arms, versus the original checked policy's **560** on the same 288 worlds. Thus even the apparently successful near-neighbor guard costs more and was designed after seeing the failure.

A further author-designed eight-operator set then produced **96 worlds / 288 arms**: ordinary safe checked **20 wrong**, distant check **10 wrong**, near-neighbor check **20 wrong**. Error-bearing unseen semantics included `clamped-product` and `piecewise-product`, and neighboring input perturbation no longer protected the policy. None of the three canaries guarantees open-world soundness.

## Source-query design negative result

Across all 28 predecessor pair tasks, using **420** query offers did **not** improve a greedy query policy over the original **70** offers: the original solved **19/28** and the expanded solved **18/28**, both buying **91** labels. The larger pool changes tie-breaking and query paths; more offers are not equivalent to more usable information under a four-label cap.

## Worker boundary, debugging and reproducibility

The E1.4w stdlib-only worker was run in 12 disjoint namespace/chroot batches. **768/768 arms** matched six deterministic reference fields, using **1,931 separate worker processes**, **1,291 purchased target labels** and **34 source-label purchases**. All **eight namespace canaries** passed in each batch (target/evaluator files absent, no home or host system files, network denied, immutable system mount, small PID, private environment). An integration failure revealed a 32-bit random-seed truncation; preserving the full deterministic seed repaired the real random-policy discrepancy. Native Bubblewrap was unavailable and is **not** being claimed to pass.

Five development suites contain 2,592 execution arms; 56 source-only arms and 768 isolated replays raise the total to **3,416 arm records**. Across those different executions, **6,050 target-label purchases** and **386 source-label purchases** are recorded. These totals include repeated trials on the same synthetic worlds; additional audit oracle replays and probe calls are accounted separately. The canonical per-batch records and separate audit files preserve the exact counts and SHA-256 digests.

**215/215 locally available unit tests PASS in eight bounded groups**: prior E1.4t/u/v tests and audit tests, plus **33 new E1.4w synthesis/integrity tests and 13 isolated-worker tests**. This is a **partial local checkout**, not the entire original repository suite. Historical full clean-checkout regression, native Bubblewrap attestation, independent evaluator custody and prescore-blinded qualification are OPEN.

## Research decision

**Scientific NOT_ASSESSED; do not merge or promote to GO.** Continue research on out-of-grammar detection, operator form construction beyond the fixed DSL, evidence-based source acquisition and new non-posthoc benchmarks. Prefer honest abstention and negative findings to silent incorrect acceptance. Keep Tod and ACE main unchanged.
