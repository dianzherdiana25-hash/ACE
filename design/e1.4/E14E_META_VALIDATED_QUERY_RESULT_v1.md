# ACE E1.4e — source training + separate meta validation: public development

**Decision: HOLD_META_VALIDATED_QUERY_TRANSFER.** This is a scientific result, not a request for user approval. Design and exact SHA-256 hashes were registered before scoring at [pre-score commit 73a428e](https://github.com/dianzherdiana25-hash/ACE/commit/73a428eda97740922a655a8b263e9343bb1750fd). The initial 8/8 prescore test run passed. Frozen code archive is stored below in the same branch and its Git blob SHA matched the local file byte-for-byte. Full source/protocol SHA manifest: [E14E_PRELOCK_MANIFEST](E14E_META_VALIDATED_QUERY_PRELOCK_MANIFEST_v1.md). No postscore changes to the source archive or decision gate.

## Exact experiment and result

- Synthetic fixed **five-event** S and G grammars; 12 source train, 6 held-out meta-validation, 12 target episodes. Rules disjoint from E1.4d five-event words. 30 eight-question pools were preallocated prior to word-conditioned examples. Each task contained 2 demos, 8 query candidates and 8 held-out probes (4 natural and 4 constructed diagnostic). The structural bank digest (SHA-256) was **2019d5ac169871b82295ac994160c033a4b6fe690dab0e5e2c91f483214417d0**. Prescore uniqueness suite confirmed **540/540 fresh, distinct input examples** against previously reserved public banks. Not a natural prevalence sample.
- Source-only training selected **G/low_ambiguity = first_disagreement**, but the disjoint meta-validation had two G/low_ambiguity episodes and **zero net predictive gain** for that policy. It was rejected by the frozen positive-improvement rule. S/high_ambiguity was ABSTAIN at training already. **All 12 targets therefore used ABSTAIN**, with 0 deployed extra target query labels; no evidence of contextual querying.

| Family / regime | Inherited | Task local | Minimax | No label | Exact random one-label expectation | Eight-label reference |
|---|---:|---:|---:|---:|---:|---:|
| S related | 19/24 | 19/24 | 19/24 | 19/24 | 19/24 | 19/24 |
| S unrelated | 21/24 | 21/24 | 21/24 | 21/24 | 20.875/24 | 20/24 |
| G related | 20/24 | 20/24 | 20/24 | 20/24 | 20.125/24 | 22/24 |
| G unrelated | 21/24 | 20/24 | 20/24 | 21/24 | 20.875/24 | 21/24 |
| **Pooled** | **81/96** | **80/96** | **80/96** | **81/96** | **80.875/96** | **82/96** |

The inherited policy did NOT strictly beat all controls in any required four-stratum pattern. Overall pooled difference does not override the prespecified gate, nor establish transferable query-policy competence. The eight-target-label reference can score worse than one-label arm due to finite-grammar tie breaking; it is not a theoretical upper bound.

## Verification, cost and failures

- Frozen source code (four Python files and prescoring tests): [binary tar.gz](../../code/e14/e14e_frozen_source_2026-11-04.tar.gz), Git blob SHA-1 **db452543d6bdeef6b4092881f467ab6345cd7cdf**, local archive SHA-256 **142e755566b6a0a7acde2a80d16844f03cc3e1c59707c69539d749d713882ba0**. The larger local pre-score archive including the complete protocol was SHA-256 **0890c747d92d0b99fb47496c3fd437ee53b37c19362fc1e23970b55c945f19c6**; only its hash/manifest, not its exact archive bytes, are registered remotely.
- [Frozen raw result JSON gzip](../../evidence/e14/e14e_public_development_v1.json.gz), Git blob SHA-1 **c9a7505542082a2822ed6853660273eb0200bd6d**. Decompress then SHA-256 of original JSON must be **a841018356a069f5a7f269791e9fecd69e4c5107a17347f6389ddabb6f7846c8**. The uncompressed JSON contains all 12 training, 6 meta and 12 target records.
- Deterministic frozen replay exit 0, exact JSON equality. **8/8 prescore structural tests passed; 12/12 independent saved-JSON corruption/consistency tests passed**. Arithmetic auditor recomputed source models, meta-validation acceptance, four strata, selected one-label arms and scientific decision. This validates internal report consistency, not oracle semantic custody or external generalization.
- Cost: **324 distinct source/meta training label events**, 216 distinct target-side experimental label events, **540 unique designed label inputs**. Instrumented evaluator found **636 actual oracle calls** within E1.4e, including **96 repeated calls** from the separate all-eight-target-label fit; historical inventory construction is excluded from those 636. Source/meta acquisition overhead = 27 labels per target at the 12-target horizon; end-to-end cost parity versus a target-local policy is NOT established. CPU parity unmeasured.
- A broad E1.4 unittest-discovery attempt was **interrupted**, after its partial dot log included an `E`; no complete traceback or terminal suite summary exists. It is explicitly **NOT a regression pass**. The focused E1.4e and independent auditor suites and replay did finish and pass.
- Candidate selector and evaluator reside in the same Python process; official Bubblewrap executable in this host does not support required isolation flags, so actual independent custody remains UNVERIFIED. No sealed E1.3 data opened; no external cost; no Tod or main change.

## Scientific next action

**Do not keep selecting smaller penalties or seeds to force query usage.** Across E1.4c, E1.4d and E1.4e, repeated abstention and ties suggest that these synthetic tasks may often lack a learnable positive value of one label under the fixed candidate grammar. Before another policy-transfer pilot, run an E1.4f **value-of-information identifiability audit**: on fresh families/inputs, measure what fraction of tasks have any strictly beneficial question compared with abstention, whether a valid unlabeled selector can distinguish those tasks, how much improvement is theoretically available at equal label cost, and whether representation insufficiency makes both models wrong. If opportunity is too rare, HOLD the benchmark and broaden the task design rather than endlessly tuning policies. Require official isolated evaluator and full-cost comparison before confirmation.

Research vision remains architecture-agnostic Open-Ended Autonomous Intelligence Evolution. E1.4e is a bounded negative development result, not AGI/ASI evidence.
