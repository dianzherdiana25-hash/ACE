# ACE E1.4z — negative transfer under semantic drift: public-development result

**5 November 2026 | PUBLIC NEGATIVE-TRANSFER DEVELOPMENT | scientific NOT_ASSESSED; historical GO/HOLD unchanged**

## Prescore checkpoint

At commit `9f81e6e4487250d7bf77cd88dce6648c3134b47a` on branch `research/e14z-semantic-drift`, the prescore design, immutable list of 20 source programs and their near/far target programs, 10 prescore tests and lock were deposited **before** the full 400-arm scoring.

The E1.4z canonical prescore bank SHA256 is `0f8f98389d55e4f40121325a911534fde4cee0019af92b38e8f1107c9331b5ae`. The exact lock SHA256 is `46ade5fb7551bfebf38a44bfaf3754bac69d0d092aa7a976c4da2a7af28b746c`. All four prescore input-file SHA256 values still match; the E1.4y source/policy/bank lock is unaffected. E1.4z is public same-author stress testing, **NOT** blinded independent evaluation.

## Mechanism

Twenty new source operators are drawn from E1.4y's 175 AST compositions, excluding the 34 source forms used in E1.4y's score. Each source program is learned from **three separately billed source graph tasks**. The same learned operator artifact is reused for two new target motif pairs across **near** (minimum Hamming signature difference) and **far** (maximum difference) hidden target operator variants. The researcher deliberately changes the target semantics, and the original E1.4y target policies are **unchanged**. This evaluates assumption failure, not autonomous semantic discovery.

- **20 source operators × 2 drift types × 2 target motif-pairs × 5 policies = 400 arm results**.
- Source labels **138** purchased once for 20 predecessor lineages. They are **shared across** the four target worlds for each source and across controls; no double-counting.
- Additional target label purchases **828** in 400 arms under four per arm. All 828 target receipts independently replayed using historical E1.4p DFS graph semantics; 138 source labels independently reconstructed and checked against source summaries.
- Six independently generated target probes per world include disjoint and shared-prefix DAGs, with probe cost inputs disjoint from the 66 legal target intervention inputs.
- The report contains **400/400 byte-identical fresh-ledger replays**, including receipt digests and full row data, across four 100-arm batches.

### Exact outcomes by drift type (40 target worlds per policy)

| Drift type | Strategy | Correct accepted | Wrong accepted | Abstain | Target labels | Probe errors |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Near | Transfer-direct | 0 | 40 | 0 | 0 | 29 |
| Near | Transfer-verify2 | 0 | **36** | 4 | 80 | 27 |
| Near | Cold-new | 0 | 0 | 40 | 160 | 0 |
| Near | Cold-old | 2 | 34 | 4 | 118 | 48 |
| Near | Sham-transfer | 0 | 19 | 21 | 80 | 49 |
| Far | Transfer-direct | 0 | 40 | 0 | 0 | 200 |
| Far | Transfer-verify2 | 0 | **3** | 37 | 80 | 16 |
| Far | Cold-new | 4 | 0 | 36 | 160 | 0 |
| Far | Cold-old | 0 | 0 | 40 | 70 | 0 |
| Far | Sham-transfer | 0 | 4 | 36 | 80 | 17 |

**Main finding:** Two uniform target verification labels miss most *near drift*, falsely accepting **36/40**, but generally reject far drift (only **3/40** wrong accepts). In these synthetic chosen extremes, the near variants differ from their source truth at only **2–9** of the 66 legal target query points, whereas far variants differ on **45–55**. This is a mechanistic change-detection failure and DOES NOT estimate natural-world prevalence.

### Exact random-query explanation (postscore mathematical diagnostic, NOT a scored policy)

For d distinguishing points among 66 and m uniformly sampled questions without replacement, the exact miss probability is \(\binom{66-d}{m}/\binom{66}{m}\). Summing across 40 target worlds gives:

| Drift | Actual miss on 2 checks | Expected miss on random 2 | Expected miss on random 4 (NOT executed) |
| --- | ---: | ---: | ---: |
| Near | 36 | 34.223 | 29.273 |
| Far | 3 | 3.665 | 0.300 |

The expected four-check counts are calculations, not experimental pass/fail counts. The result justifies testing **disagreement-seeking, actively designed target verifications** against independent new drift banks, rather than spending more labels randomly or posthoc tuning E1.4z.

### Independent audit and hindsight falsifiers

- Full E1.4z audit SHA256 d `23a48e850ce82e703a60ccf15091b8323b93f38879277d94868a934cc712d7ed`: 828 independently checked purchased target labels; source 138 re-acquired and aggregate checked; 1,092 held-out predictions of accepted programs reconstructed from receipts and historical independent DFS oracle.
- **176/176** wrong-accepted arm programs have an explicit typed graph counterexample and independent oracle reply. All 176 are also located in *unused legally queryable* target cost points. SHA256 `d4362a6826a48195f4f494d12ecf810536ba65e56ef76f359237f5e19cfdef50`. These are **176 additional postscore auditor oracle calls, 0 new original target-budget purchases**. The witness choice is hindsight, not an implementable automatic policy performance claim.
- Hypergeometric miss analysis SHA256 `3a861c394e663da586066df2b6331e73bda6dfd9b95c10d2812603fa1deae8d0`.
- Full local compatible-workspace regression E1.4t–E1.4z **299/299 PASS across 13 bounded groups** with log hash receipts; includes **26 E1.4z tests** (10 prescore bank, 10 postscore audit, six exact probability tests). This is not a clean complete GitHub checkout regression, and native Bubblewrap security has not been independently verified.

### Negative conclusions / next scientific gate

1. Even when the true target still belongs to a known grammar, fixed source inheritance can fail catastrophically if the semantic operator changes subtly. A 2-label random check is not a robust source-target semantic consistency certificate.
2. Extra source labels are accounted (138 shared across all four target tasks per source). Comparisons to cold controls **do not** have equal total operator information budget or identical task assumptions.
3. The near/far distribution deliberately selects extremes of the known grammar. Strong error counts do not establish statistical rates or general novel primitive discovery.
4. No postscore tuning of bank, original E1.4y worker, or E1.4t frozen scientific decisions. The next prospective study must evaluate targeted verification on a **distinct, previously unseen** target drift distribution, with fully matched label costs and source journal custody.

Scientific status: **NOT_ASSESSED**. E1.4t graph HOLD, NATURAL_HOLD and OAIE not demonstrated. Do not merge ACE `main` or edit Tod. Codex is not necessary for the local work completed here.
