# ACE E1.4y — cross-task AST-form transfer, prescore public development results

**5 November 2026 | PUBLIC_DEVELOPMENT_NOT_SCIENCE | scientific NOT_ASSESSED**

## Scope and prescore custody

The seven source/protocol/bank/test files and lock were **committed before scoring** at GitHub checkpoint `51156d8b408f0f5e2555481cc289ba9172032221` on branch `research/e14y-cross-task-operator-transfer`. Original canonical bank SHA256: `c7dfa7c4758d5e43c649ea7679e0ad979da54e994245e888879dce20c47fe976`. Postscore check confirmed **6/6 frozen input files unchanged** bytewise; the lock's own SHA256 is `e7294d30e27d7caaf4795d6067bf895ffe0f55ae1d3ebcb9e384d0ed59285f5f`.

Design: 40 author-chosen operators (20 periodic residuals, 14 threshold residuals, 6 truly unrepresented) × 2 unseen motif-pair target tasks × 5 strategies = **400 arm executions**. Three predecessor tasks per operator, each with its own four-label cap; each target arm has a separate SQLite four-label cap. Target intervention cost tuples are **66** legal `[4..18]` pairs with high toll ≤14; six target probes use disjoint **54** legal cost tuples with high toll ≥15. Probes alternate disjoint and shared-prefix DAG topologies. The grammar has **175 unique semantic AST signatures** on the bounded grid. Templates/primitives, source/target motif IDs and operator generators are researcher-authored; this is NOT open-ended primitive invention.

### Results, per strategy across the 80 target worlds

| Strategy | Correct accepted | Wrong accepted | Abstain | Purchased target labels | Accepted probes / errors |
| --- | ---: | ---: | ---: | ---: | ---: |
| Transfer-direct | 68 | 4 | 8 | 0 | 432 / 15 |
| Transfer-verify2 | **68** | **2** | 10 | **144** | 420 / 10 |
| Cold new AST grammar | 12 | 2 | 66 | 298 | 84 / 7 |
| Old five-node DSL | 0 | 36 | 44 | 204 | 216 / 60 |
| Sham inherited grammar | 0 | 15 | 65 | 144 | 90 / 46 |

**Source acquisition:** **258 purchased source labels** over 40 operator tasks, across 120 source task slots, at most four per task, reused across both target pairs and all five strategy arms. All source labels were independently replayed in execution. Total target label purchases across all 400 arms: **790**; across the five mutually exclusive strategy comparisons these labels are NOT a per-strategy free common budget. All 790 receipts were independently replayed with historical E1.4p DFS graph semantics. For the verified transfer, source + target cost is **258 + 144 = 402 labels** across 80 target worlds, average 5.025 per target; cold-new bought 298, average 3.725. Thus target-stage transfer effectiveness improved, but **no matched-total-resource superiority has been established**. Do not treat source labels as free.

**Within the supplied grammar** (34 forms, 68 target tasks), transfer-verify2 recovered **68/68** exactly and made no wrong acceptance. On **six out-of-grammar forms** (12 target tasks), transfer-verify2 **wrongly accepted 2**, abstained 10; transfer-direct wrongly accepted 4, abstained 8. Cold-new wrongly accepted 2 outside grammar despite requiring ≥3 target labels. Two checks therefore do not certify open-world operator adequacy. Historic natural transfer and open-world robustness remain HOLD/NOT_ASSESSED.

### Independent reproducibility and audit

- Four sealed-source development score batches (10 operator tasks / 100 arms each) and **four fresh-ledger replay batches** agreed **400/400 complete raw arm records** including target purchased graph journals, receipt digests, returned labels, cost totals, scores, and summary hashes.
- Original score four canonical SHA256 digests:
  - operators 00–09: `02cfaf2319f8ddcd68c272ee0f00114936041854c64adffd8f1eb2177f8651c5`
  - operators 10–19: `1b9f6bcb98b9e7bf3f3f82ee90793f96df5caa2588361d2e24b51a07be5d7cc6`
  - operators 20–29: `ff201dcbe0be72b3a52384b6607e63be4a3de1f406db3bb2fa1e4f2cae68e79f`
  - operators 30–39: `750a91efe1b73c6a20aff2e969ffd1a3a974002e79e5e5596b0afaa88690d639`.
- Separate postscore auditor recomputed source acquisition, 790 target oracle receipts using historical independent DFS graph implementation, reconstructed exact accepted programs and 1,242 accepted held-out predictions. Auditor canonical report SHA256: `34ac7d4dcb28b11be1a028c2511240d935398e2448973c3b28d933705358662a`.
- **59/59** wrongly accepted arm programs have explicit postscore distinguishing witness graph and independent oracle answer. **57/59** witnesses lie in an unused but legal target-intervention cost pair; two require a cost pair outside the 66-point target query region. Counterfactuals are **59 extra auditor oracle calls, zero additional frozen purchased target labels**. Witness canonical report SHA256: `f3ec69c626fb3d38cd9df7d54ac7b219a7feab1971c58879007896af2168cf1f`.
- Full partial-compatible local regression E1.4t–E1.4y: **273/273 unit tests PASS across 12 bounded, hash-logged groups**. Includes 37 new E1.4y tests (21 preregistration, 11 adversarial audit, 5 witness). The initial monolithic attempt did NOT finish; the actual separately run complete 12-group result is the only asserted pass. Full clean exact-head repository regression and native Bubblewrap worker security attestations are NOT COMPLETE.

### Methodological omissions and negative evidence

1. Source oracle observations are supplied to the scored learner only as typed cost tuples. Their **raw source SQLite receipts were not included in original score artifacts**. The postscore auditor independently reruns source learning and checks label totals, source-task totals and uniqueness; this is reproducibility but is not bit-identity proof of archived source receipt journals. Future experiments should persist source journals before scoring.
2. Same-author bank, candidate grammar, query policy and scores; not independently assessed, not blinded, not population representative. Source tasks deliberately share the exact same operator but have different motif-pair inputs; do not claim independent natural-world predecessor transfer.
3. Strong controls have unequal cumulative label costs. The sham control is intentionally wrong but checked; it does not establish cost-equal superiority of transferred representation.
4. Out-of-grammar false acceptances persist, including ones whose six fixed probes show errors. After-the-fact distinguishing witnesses must not be used to modify original score, bank, or prescore acceptance claims.
5. Operator names for source truth and OOD stress were authored by the experimenter; the system induced **which bounded AST composition fits**, not a novel primitive unconstrained by supplied grammar.
6. The shared-cost grid is synthetic, no natural science data, native sandbox unverified, and no proven OAIE/general self-evolution.

**Next scientific hypothesis:** learn grammar expansions from repeated cross-task residuals without being supplied the target predicate templates; preserve separate source evidence and budget. Use an independently frozen new bank with truly unseen operator families, matched **total** resource cost, and a falsifiable open-world abstention gate. Do not revise E1.4y after its prescore lock; keep historical E1.4t HOLD and NATURAL_HOLD.
