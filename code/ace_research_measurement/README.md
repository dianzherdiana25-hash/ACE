# ACE R8 — Intelligence Measurement & Capability Growth

Status: PUBLIC SYNTHETIC METHOD DEVELOPMENT ONLY. This package measures whether reported gains survive family-balanced evaluation, transfer and contamination checks; it does NOT evaluate the intelligence of a real ACE agent. Ownership: code/ace_research_measurement/ on research/chat-r8-measurement, forked from research/e15-source-evolution SHA 965640786cbf2f8adcd89eb1d980945f78c2da77.

## Falsifiable hypotheses

H1 (transfer): an exact-development-instance memorizer should not score a positive improvement on semantically disjoint evaluation instances, particularly unseen task families. An explicitly hand-coded expanded solver is the positive *measurement* control, not self-learning.

H2 (Goodhart): overweighting easy routine tasks can increase micro-average success while reducing equally weighted per-family performance. The evaluator must show both and flag sign inversions rather than conclude growth.

H3 (contamination): copying the same semantic instance under a new display ID must invalidate the dataset; marking an already-seen structure or family as novel must be rejected.

## Reproduction

Python standard library, no paid services. From repository root:

    PYTHONPATH=code python -m unittest ace_research_measurement.test_measurement -v
    PYTHONPATH=code python -m ace_research_measurement.experiment --output /tmp/ace-r8-public-results.json

Eight arithmetic mechanism families (add, multiply, affine, square, nested, parity, mod, negshift) are used. Four are present in development; the other four are unseen by development family, but all code and task-generation rules are **public**. The evaluation split is a public simulated separation, NOT a private holdout. All observations are synthetic and researcher-generated.

Each record includes trusted semantic-instance SHA256 fingerprint, family/structural key, novelty/composition flags, paired correctness, pre/post adaptation correctness, operation counts and label-query counts. The evaluator checks duplicate instances (even under renamed case IDs), invalid costs, invalid booleans and invalid novelty tagging. In actual ACE integration, evaluator custody must supply genuine task semantics and correctness; self-reported candidate records are untrusted. Normalization by input JSON only catches exact semantic duplicates, not arbitrary paraphrases or equivalent programs.

Metrics: micro change; mean of family-specific paired changes (macro); separate novelty and composition deltas; adaptation pre/post; operations and labels separately; exploratory clustered bootstrap by family. A 2x-operation warning is illustrative, not an independently validated resource equivalence. The claim gate always reports NOT_CONFIRMED. Without independent confirmatory evaluation, neither statistical superiority nor intelligence growth follows.

## Local measured results

| Constructed control | Evaluation n | Micro delta | Family-macro delta | Novel-family delta | Compositional delta | Ops (baseline -> candidate) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Expanded hand-coded positive measurement control | 64 | +0.7500 | +0.7500 | +1.0000 | +1.0000 | 640 -> 768 |
| Exact-instance memorizer negative control | 64 | +0.0000 | +0.0000 | +0.0000 | +0.0000 | 640 -> 640 |
| Goodhart easy-family overweight control | 144 | +0.3333 | **-0.7143** | -1.0000 | -1.0000 | 1440 -> 1440 |

The Goodhart control is a deliberately generated counterexample; its frequency in real ACE environments is unknown. There are 13/13 passing local unit tests for determinism, controls, cross-split/within-split semantic duplicates, fake novelty, invalid costs and stable ordering. The full JSON report can be regenerated from source. Development report SHA256 is 012b8744793776d2a83aa62cc2a7ef038cb7f5e4c26247dc3b661814f58456e1 (exact local JSON output, Python 3; not an independently deposited sealed evaluator artifact).

## Next gates — OPEN

1. Freeze trusted evaluator-owned record semantics, analysis plan and lineage/exposure receipts before private evaluation. Validate semantic equivalence beyond exact fingerprints.
2. Evaluate actual ACE revisions on unseen *mechanisms* created by a distinct evaluator, with matched resource budgets and paired family clusters; retain negative transfer and cost regressions.
3. Pre-register effect sizes, multiplicity correction, repeated adaptive benchmark selection and compositional family coverage. Keep private confirmatory bank inaccessible to candidates and researchers adjusting metrics.
4. Test time-separated retention, transfer to distinct generators, adaptation sample-efficiency, crash recovery and performance per measured wall/CPU/memory/label costs; prevent confusing more search with more intelligence.
5. Require blind independent replication before any scientific claim. E1.4 frozen artifacts, main, security red team and S5 open-ended exploration are out of scope.

Decision: METHOD_DEVELOPMENT_PROBE_PASS, SCIENTIFIC_ACE_CAPABILITY_GROWTH=NOT_ASSESSED, OAIE=NOT_ESTABLISHED.


## R8 follow-up: E1.5 aggregate-readback adapter and adaptation audit

The archive `evidence/e15/E15_DEVELOPMENT_SUMMARY_v0.json` (Git blob SHA `2561d8ee47f84a85388cbd4c7de7737f1266342b` at `research/e15-source-evolution` SHA `965640786cbf2f8adcd89eb1d980945f78c2da77`) contains real **public-development** outcomes from the ACE E1.5 loop. R8 now provides a standalone, **read-only** audit of that source. It checks byte identity before parsing, rejects duplicate JSON keys, recalculates E1.5 utility from the actual acceptance/abstention/label-cost scoring rule, checks paired aggregate denominators, cross-checks archived delta and verifies non-promotion/reversion decisions. It does not modify the source.

From an exact ACE checkout containing historical `evidence/`:

```sh
PYTHONPATH=code python -m ace_research_measurement.e15_audit --output /tmp/ace-r8-e15-audit.json
PYTHONPATH=code python -m unittest ace_research_measurement.test_measurement ace_research_measurement.test_e15_audit -v
```

The **in_family** archived validation increase is +42 utility units (−36 to +6). On holdout the chosen policy has one more correct acceptance (0→1), spends +35 labels (18→53), and has **−13** utility units relative to baseline (−54→−67). The **mixed_grammar** track has zero utility delta. These totals support a cost-sensitive validation→holdout reversal, **not** a measurement of cross-family intelligence growth. The archive exposes aggregate outcomes but no evaluator-custodied per-case structure labels; R8 explicitly refuses to invent compositional, OOD, novelty or family-cluster scores from aggregates.

In local R8-only staging, the source archive is absent: the exact-byte archive test is **skipped**, while synthetic audit invariants run; the historical values were separately read from GitHub, but **the pin-verified CLI still needs an actual full checkout**. Thus `PINNED_ARCHIVE_EXECUTION=NOT_RUN_LOCAL` and `HISTORICAL_RECORDS_AUDITED_AGGREGATE_ONLY` (not independent semantic confirmation). The command above will fail closed if the source is absent/tampered. Do not report this as an independent sealed holdout replication.

### Method correction

The earlier generic pre/post metric could be misread as "adaptation speed" even where the generator records no actual label acquisition. R8 now uses the key `pre_post_difference_descriptive_only` and emits `ADAPTATION_PROTOCOL_NOT_ESTABLISHED` when such a difference occurs. It flags **any** unmatched operation/label budget (in addition to the >2× warning), rather than treating modest extra compute as free. A causal adaptation claim requires documented intervention, pre/post timing, controlled exposure, correct task identity and matched compute. Claim gate remains `NOT_CONFIRMED`.
