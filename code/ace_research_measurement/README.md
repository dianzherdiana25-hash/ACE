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

## R8 follow-up: winner's-curse / adaptive benchmark selection falsifier

`selection_bias.py` simulates a **known-null** research selection problem: 48 independent Bernoulli(0.5) candidate policies, 24 validation and 24 separate evaluation cases, 512 seeded repetitions (`seed=14005`). In every repetition, all 48 candidates are compared on validation, the candidate index is frozen with deterministic tie-break, and only selected and fixed-baseline arms receive post-freeze evaluation scores (same receipt reused if they are the same arm). This is a **simulation** of separate evaluation, not a sealed third-party scorer.

Execute:

```sh
PYTHONPATH=code python -m unittest ace_research_measurement.test_measurement ace_research_measurement.test_e15_audit ace_research_measurement.test_selection_bias -v
PYTHONPATH=code python -m ace_research_measurement.selection_bias --output /tmp/r8_selection_bias.json
```

Actual local run: **34 tests / 33 PASS / 1 SKIP** (pinned E1.5 archive still absent from R8-only local staging). The selected arm's average validation score **0.725749** falls to **0.509766** on new evaluation; the fixed baseline's evaluation score is **0.510661**. Selection optimism = **+0.215983**. A naive +0.10 relative-to-baseline validation rule would accept **452/512** null experiments; **257/512** of all experiments meet that validation rule and show **no holdout gain**. A +0.10 single evaluation threshold still fires in **118/512** trials under this null, so merely observing a threshold excess is **not** a calibrated independent statistical significance test.

No actual ACE policy was run, no new intelligence demonstrated, and the public simulated evaluation is not sealed. The negative result motivates prespecified effect sizes, post-selection correction, evaluator-only fresh banks, exposure logs, confirmatory clustered intervals and disclosure of all tested candidate arms. See `results_selection_bias.json`. This study is independent of the S5 open-ended exploration mechanism.

## R8 follow-up: lineage provenance and pseudo-replication checks

`lineage.py` provides separate fail-closed evaluator-record **structural** checks across development, validation and evaluation. It uses canonical evaluator-owned digest fields: semantic instance, generating program, claimed mechanism and origin world, plus a per-instance exposure flag. In `generator_disjoint` mode it rejects reused generator, source-world ancestry, evaluation exposure, and multiple evaluation cases from the **same source world** counted as independent. In `mechanism_disjoint` it also rejects reused mechanism identity; `public_diagnostic` reports signals without falsely calling exposed public tasks independent. It warns when fewer than four distinct evaluation mechanisms are represented.

Negative controls include renamed generator reuse, same mechanism under new generator, cross-split derivation, within-evaluation pseudo-replication, exposed evaluation, duplicated semantic instance, malformed digest, and invalid exposure flag. **Important limit:** different SHA-256 labels do not prove different semantics, and the package cannot independently authenticate evaluator custody. A candidate can forge claimed lineages; this audit must be coupled to independently held evaluator receipts before science acceptance.

Reproduction: `PYTHONPATH=code python -m unittest ace_research_measurement.test_measurement ace_research_measurement.test_e15_audit ace_research_measurement.test_selection_bias ace_research_measurement.test_lineage -v`.

Actual R8-only local staging after this change: **45 tests, 44 PASS, 1 SKIP** (pinned full E1.5 archive unavailable). The published selection simulation JSON is independently replay-checked by a unit test. The archive readback was verified through the GitHub connector, but the pinned on-disk archive test remains open, and no full-checkout exact-head CI run is claimed.


## R8 checkpoint 4 — family-cluster growth screen and pinned E1.5 audit

The previously skipped E1.5 pin-verification test **now passes locally**. The exact source `evidence/e15/E15_DEVELOPMENT_SUMMARY_v0.json` was obtained through the authenticated GitHub connector from fixed commit `965640786cbf2f8adcd89eb1d980945f78c2da77`, reconstructed byte-identically, and reverified as Git blob SHA-1 `2561d8ee47f84a85388cbd4c7de7737f1266342b` before executing `e15_audit.py`. Result in `results_e15_verified.json`. This is **public development archive** evidence, not a sealed holdout or fresh ACE agent run.

`growth_gate.py` adds a fail-closed *diagnostic* screen requiring a sufficient number of task families, distinct evaluator-claimed mechanisms, disjoint lineage, paired baseline/candidate outcomes, sufficient novel and compositional families, explicit costs, no extra candidate operations/labels per case, and no material family regression. An exact one-sided family sign-flip nominal p-value is calculated (up to 16 families). This assumes independent, symmetric family effects; the hashes do not establish this. The public plan is not preregistered or sealed. Even a positive outcome remains `PASS_PUBLIC_SCREEN_ONLY` with `scientific_claim=NOT_CONFIRMED`.

Under the **known-zero-effect** synthetic falsifier (`growth_falsifiers.py`), 512 seeded trials with 8 families and 12 cases per family yielded 42/512 (8.20%) naive +10 percentage-point micro-score passes versus 9/512 (1.76%) stricter family-screen passes. The stricter screen reduces, but does **not eliminate**, false positives under *this particular null*. These are *observed simulation frequencies*, not independently calibrated Type-I error across adaptive trials or distribution shift. Retain negative result; see `results_growth_null.json`.

### Reproduce with Python standard library

```sh
PYTHONPATH=code python -m unittest ace_research_measurement.test_measurement ace_research_measurement.test_e15_audit ace_research_measurement.test_selection_bias ace_research_measurement.test_lineage ace_research_measurement.test_growth_gate ace_research_measurement.test_growth_falsifiers -v
PYTHONPATH=code python -m ace_research_measurement.e15_audit --output /tmp/ace-r8-e15-audit.json
PYTHONPATH=code python -m ace_research_measurement.growth_falsifiers --output /tmp/ace-r8-growth-null.json
```

Observed on local R8 staging with verified full E1.5 public aggregate archive: **62/62 PASS, 0 skip, 0 fail** (Python 3.13.5). Source and tests match GitHub Git blob IDs. The entire historical ACE regression and exact-head Actions CI have **not** been performed. No frozen E1.4, main, S5, or other agent's directories were modified.

Next required scientific gates: third-party evaluator-custodied per-case ACE outputs and exposure receipts, pre-registered sealed bank and multiplicity control, compute/evaluator-label matched baseline, and blind replication on truly disjoint mechanisms. `OAIE` and general intelligence growth remain **NOT_ESTABLISHED**.


## R8 checkpoint 5 — cross-PR task-level audit of actual ACE search results

This checkpoint audits **real recorded ACE development experiments**, not just new contrived R8 null simulations. The input is the Codex team's *public synthetic* candidate search summary from draft PR #36 (`codex/ace-candidate-search` at exact commit `08da5702828285e0bd4d0f4dd8876f331ac89fe2`), path `code/ace_candidate_search/results/summary.json`, Git blob SHA-1 `069b4ffdf2f0a5a363d81bcec6ddfc4f2a5e098a`. The original summary includes 64 runs (8 researcher-designed tasks × 2 budgets × 4 search modes). It contains per-task holdout aggregates (3 cases/task), **not evaluator-custodied individual-case predictions** or independent mechanism-lineage attestations.

The adapter `candidate_search_audit.py` evaluates a derived, compact 64-run snapshot with strict task/mode/budget completeness, numerical invariants, declared resource ceilings, input provenance and task-paired comparisons. It can additionally load the **original entire JSON** from a separate checkout, verify the exact pinned Git blob hash before parsing, regenerate the snapshot and refuse any discrepancy. Without `--full-source`, the output must be labeled `DERIVED_SNAPSHOT_ONLY`: the source identity recorded inside the snapshot is not by itself a cryptographic verification of the original bytes.

Reproduce from ACE full checkout **plus** a local fetched copy of the pinned Codex PR #36 summary:
```sh
PYTHONPATH=code python -m unittest ace_research_measurement.test_candidate_search_audit -v
PYTHONPATH=code python -m ace_research_measurement.candidate_search_audit --output /tmp/ace-r8-task-audit.json
PYTHONPATH=code python -m ace_research_measurement.candidate_search_audit \
  --full-source /path/to/pinned/codex/summary.json \
  --output /tmp/ace-r8-task-audit-verified.json
```


### Observed recorded task-level results

| Maximum budget | Fixed | Fixed-list | Enumerate | Beam |
|---|---:|---:|---:|---:|
| Standard, task solved (all 3 holdout) | 0/8 | 1/8 | 5/8 | 6/8 |
| Tight, task solved (all 3 holdout) | 0/8 | 1/8 | 0/8 | 0/8 |
| Standard actual logical work, all eight | 240 | 1,632 | 440,866 | 286,707 |
| Tight actual logical work, all eight | 240 | 1,632 | 304 | 304 |

Standard beam versus enumeration has **one discordant solved task** (1 win, 0 losses, 7 ties), giving exploratory one-sided task-paired sign **p=0.5**. A visual 6/8 vs 5/8 lead is not statistically established superiority. Beam's standard logical work is ~175.7× the fixed-list control, even though both share the same *maximum* work ceiling: shared ceilings do not mean cost-matched comparisons. Under the tight ceiling beam solves 0/8 versus fixed-list 1/8. Beam does not transfer across budgets as a reliably dominant choice in this public pilot.

`candidate_search_snapshot.json` is an extracted 64-cell diagnostic input, not raw journals. The separate PR #36 includes its own journal verification; **R8 has not independently reproduced all 64 journals**. The original underlying task-generators are human-designed and public; no sealed confirmatory bank is available. The new R8 task-level adapter **cannot** measure novel primitives, independent OOD families, true sample-efficient adaptation, or general intelligence. Treat all nominal p-values as exploratory, uncorrected for multiplicity, and questionable under nonindependence of tasks. No changes to Codex source, main, frozen E1.4, or S5.

### Test status

A separately assembled local R8 adapter prototype with the same paired-task validation logic completed **14/14 tests PASS**, including missing arms, invalid correctness, impossible zero error, over-cap work, false SHA labels and source-format normalization. The exact GitHub-committed adapter has **not yet run on a complete local checkout or exact-head CI**, and its full-blob mode is pending local access to original bytes; do not mislabel the prototype pass as exact-head verification.

Scientific status: `PUBLIC_TASK_ANALYSIS=DESCRIPTIVE`; `INDEPENDENT_VERIFICATION=OPEN`; `OAIE=NOT_ESTABLISHED`.
