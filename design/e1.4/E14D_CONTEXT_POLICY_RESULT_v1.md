# ACE E1.4d — context-conditioned question policy: public development result

**Scientific decision: `HOLD_CONTEXT_TRANSFER`.** This is a result, **not** an approval request. Prescoring frozen at [53b2f0a](https://github.com/dianzherdiana25-hash/ACE/commit/53b2f0a1f60bf06b69c7fda0bd49acb793af74a1), with a formatting-only (JSON bytes-to-text) correction **before scoring** at [32f73d7](https://github.com/dianzherdiana25-hash/ACE/commit/32f73d7dff66ab9ee586f48783f894fed6cd86d7). No outcome tuning.

## Design
12 source and 12 disjoint target episodes: families S symbolic and G graph-chain, three related and three unrelated pairs per family. Human-defined five-event hypothesis grammar. 24 source/target query pools of eight unlabeled questions preallocated using a rule-independent PRNG, before rule-conditioned demos/probes. Two demos and eight probes per episode, four natural/random and four engineered diagnostic. Bank SHA-256 `c6d728ecc7a69f6f7002b1068a800241c041a3a16a75e0e8200ab5847bbd94da`. Split audit reports 432 new distinct inputs, no old public overlap.

## Accuracy (correct out of 24 per stratum)

| Group | Inherited | Task-local max-partition | Grammar-informed minimax (1 label) | Sham | No label | Uniform 1-label expectation | 8-label fit |
|---|---:|---:|---:|---:|---:|---:|---:|
| S related | 20 | 20 | 20 | 20 | 20 | 20.5 | 22 |
| S unrelated | 22 | 22 | 22 | 22 | 22 | 22 | 22 |
| G related | 18 | 18 | 18 | 18 | 18 | 18.25 | 19 |
| G unrelated | 17 | 19 | 19 | 17 | 17 | 17.5 | 24 |
| **All (96 probes)** | **77** | **79** | **79** | **77** | **77** | **78.25** | **87** |

The learned source policy chose **ABSTAIN on all 12 targets** (0 additional deployed target query labels). Thus, the model has **not** demonstrated context-sensitive querying. On G unrelated it trails strong one-label baselines by 2/24. The locked strict four-stratum predictive GO gate failed.

## Information-cost accounting correction
The frozen JSON's `source_training_labels=96` counts only **8 source query-intervention labels × 12 sources**. Full source acquisition used **24 initial source-demo labels + 96 source query labels + 96 labeled source-probe outcomes used to select a meta-policy = 216 source label events**. An instrumented run counted **432 oracle label events** total (source 216; target 24 demo + 96 counterfactual query + 96 scoring probes = 216). Source overhead at 12 targets is 18 source label events per target, before target initial data. The frozen JSON's `inherited_total_acquisition_labels=96` is a *narrow intervention-only subtotal*; it is **not an end-to-end equal-cost result**. The 8-label target fit is a separately more expensive comparator. CPU parity is unproven.

## Reproduction and integrity
- Frozen JSON SHA-256: `eebd467968c8df351b53221d19a004a6c20bff6df31392c3e5d30270f1b91864` (29,383 bytes). Lossless [gzip binary](../../evidence/e14/e14d_public_development_v1.json.gz) stored as a Git blob; decode with `gzip -dc evidence/e14/e14d_public_development_v1.json.gz > evidence/e14/e14d_public_development_v1.json` then compare SHA-256.
- Exact deterministic `--verify` replay passed from frozen source. Local E1.4 regression log **46/46 tests passed**; saved report auditor **10/10 passed**; prescoring structural checks **7/7 passed**. The separate arithmetic audit, split audit, and oracle-call reconciliation were run locally. Their verbatim auxiliary logs are not all embedded in this Git commit; preserve them in the handoff archive.
- All work is public *development*: candidate/evaluator are in the same Python process, official Bubblewrap isolation and independent external sign-off were **not** established. Small synthetic human-engineered dataset; no causal generalization/AGI claim.
- No use of E1.3 sealed confirmation, no change to Tod or `main`, no paid services.

## Decision
**HOLD**, preserve this scored version and earlier E1.4c v1/v2 negative evidence. Next investigate **E1.4e**: whether abstention wins trivially because source utility is dominated by probe construction and label penalty; design separate source training/meta-validation and fully accounted target-cost baselines. Use fresh independent tasks, predeclare costs/gates, freeze before target scoring, and treat security isolation as a separate acceptance gate.

Source: `code/e14/e14d_run.py`, `code/e14/e14d_policy.py`, `code/e14/e14d_bank.py`; original prescoring protocol: `design/e1.4/E14D_CONTEXT_POLICY_PRELOCK_v1.md`.
