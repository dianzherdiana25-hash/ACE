# ACE E1.4f — one-label opportunity and benchmark identifiability (public development)

**Preregistered result: `BENCHMARK_HOLD_REDESIGN`.** E1.4f explicitly asks whether the benchmark offers enough attainable one-label improvement to evaluate an active query learner, not whether autonomous intelligence has evolved.

## Provenance and design

- Prescore [freeze commit 5d44ed7](https://github.com/dianzherdiana25-hash/ACE/commit/5d44ed79f9e7a3cac1f0940748d3f375ecdf4385) registered SHA-256 for each source/protocol, complete archive, all seeds, and fresh bank hash **`d79acfec7a9778bae4f2e6599a00cdbe5b3e22b4a13d269fa74bf7d54bdfbf2b`**. Local 8/8 prescore structural tests passed. The full frozen source code archive Git blob SHA expected **`d9c867040a76e8903b534dd0f0e06bd6f608e731`**; its local SHA-256 **`2f5f365c7d7940b39cdce361c31bdb28bf448a45a8ecc2e0c1503c3257be9865`**. The exact frozen source archive is now preserved in [GitHub's research branch](../../code/e14/e14f_frozen_source_2026-11-04.tar.xz) as Git blob **`d9c867040a76e8903b534dd0f0e06bd6f608e731`**, matching the SHA-256/expected Git hash registered **before scoring** at commit `5d44ed7`. The prescore manifest itself remains unchanged.
- 24 fresh tasks (S/G × fixed-inventory five-event vs out-of-inventory six-event hidden rule × 6) with 2 demos each. All 24 task IDs distinct and all 1,776 generated raw input examples unique and disjoint from older public banks. Fresh random and curated query pools per task: natural **8 random**, curated **8 chosen without oracle from a separate preallocated 48-candidate reservoir**, based on fitted hypotheses. Probe sets: 8 natural-heavy (6 natural, 1 true-positive, 1 true-negative), and 8 diagnostic-heavy (2 natural, 4 true-positive, 2 true-negative). Curator uses more unlabeled predictions than random; CPU equalization not established.
- Fixed grammar5 candidate inventors (S 243, G 48), not autonomous method invention. Six-event hidden rules are adversarial out-of-basis controls, not expected to be exactly representable.
- Retrospective **hindsight best of eight** uses probe outcomes and is **not deployable**. The feasible max-Gini and minimax selectors use only demo-fitted hypotheses and unlabeled question pools. All methods share the same probes within each episode/treatment.

## Primary locked comparison: represented rules + diagnostic-heavy probes + curated query pool

| Family | Hindsight opportunities (tasks with gain >0) | Max-Gini opportunities (tasks with gain >0) | Total paired Max-Gini gain | No-label correct / 48 | Max-Gini correct / 48 | No-disagreement tasks |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| S symbolic | **2/6** | **1/6** | **+4** | 36 | 40 | 3/6 |
| G graph | **2/6** | **1/6** | **+2** | 31 | 33 | 1/6 |

The frozen feasibility rule required in **each** family: hindsight positive ≥3/6, deployable Max-Gini positive ≥2/6, and positive aggregate Max-Gini gain. **Both fail the first two requirements.** No posthoc pooling or alternate seed permitted to relabel HOLD.

## Additional findings

- In represented symbolic tasks, random 8-query pools have **0/6** hindsight-positive episodes; curated pools have 2/6, under diagnostic-heavy prevalence. Graph represented tasks show 2/6 hindsight-positive with either query pool, though the random-pool Max-Gini gains occur on 0/6.
- In out-of-basis tasks, curated hindsight opportunity appears in **1/6 symbolic and 1/6 graph** under diagnostic-heavy probes. Their true six-event rules are outside the candidate's five-event inventory by design. A positive score on individual probes is not a proof of recovered representation.
- Natural-heavy versus diagnostic-heavy outcomes and all **16** family × basis × prevalence × pool strata are preserved in [full raw evidence](../../evidence/e14/e14f_public_development_v1.json.gz). Sample sizes (6 tasks/group) are not sufficient for confirmatory inference or real-world generalization. Hindsight and feasible selections must never be conflated.

## Reproduction, integrity and costs

- Frozen scoring ran once with exit 0 from exact SHA-registered source. Raw JSON SHA-256 **`ede97348d64aa879a7072bffde02a62cef661bebf4ff91166e7a92fc6acd11c5`**, 64,075 bytes. [Losslessly compressed raw JSON](../../evidence/e14/e14f_public_development_v1.json.gz) Git blob SHA-1 **`c3a69c31b60fc128439c99b8f953f94a1f9e0012`**, gzip SHA-256 **`b9b49baddb5e4e6ca5041bb1b379e4db548c899dcfea5df407991b38843dbdf8`**. Decompress and verify the original raw JSON SHA-256.
- **Replay deterministically reproduced byte-for-byte the 64,075-byte result**, exit 0. Independent saved-JSON arithmetic audit PASS; **10/10 corruption-detection tests** passed. Source/protocol pre-score checksum **6/6 matched** after scoring.
- **Full E1.4 regression 84/84 PASS in 71.577 seconds** after restoring two missing historical fixture JSON files in the local checkout. Earlier broad regression's error was primarily missing fixture files (`e14c_public_development_v1.json`, `e14d_public_development_v1.json`) and heavy tests; restored historical files' SHA-256 match prior published hashes. No old code/scorer or evidence changed. [Local log summary checksum] `8c50944e47dfbc8baa7aefbd1c3b17306fd8094917cb7cf2e34916aad3b3ac01`.
- Per new task: 2 demo labels + 16 counterfactual query labels + 16 scoring-probe labels = **34** uniquely labeled public examples, or **816 newly measured oracle labels** for 24 tasks, excluding fixture construction. One deployed selector requests one label; the 16 per-task query labels are for exhaustive retrospective evaluation. Curated pool has **higher unlabeled computation cost** and is not compute-parity matched.
- The trusted candidate/evaluator share one Python process. No official Bubblewrap independently isolated worker, no independent semantic signoff, no sealed E1.3 confirmation, no claimed open-ended autonomous intelligence or AGI.

## Decision and next research

**`BENCHMARK_HOLD_REDESIGN`:** Even with a preallocated candidate-aware curated query pool and manufactured diagnostic positives, legal single-query opportunities remain scarce and unevenly accessible. Do not continue source→target meta-policy searches on this bank. Next **E1.4g benchmark-design decision** should establish an experimentally useful **opportunity-positive task distribution**, with a separate untouched natural distribution and adversarial representation-out-of-basis controls, then require controlled label/CPU fairness and genuinely isolated evaluator before capability claims. Register new protocols *before* any scores; never tune E1.4f outcomes to produce an artificial GO.

Vision remains **Open-Ended Autonomous Intelligence Evolution**. Science HOLD is not an owner-approval gate. No costs, no Tod edits, no `main` merge.
