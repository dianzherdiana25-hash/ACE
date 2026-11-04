# ACE E1.4c — cross-episode query-policy transfer (first public development pilot)

**Scientific gate: `HOLD_CROSS_EPISODE_TRANSFER_HYPOTHESIS`.** The source-trained policy did NOT consistently beat a task-local class-aware selector, randomized one-label expectation, sham inheritance, and no-label in all four prespecified S/G x related/unrelated strata. This is a negative/heterogeneous *development* finding, **not** a confirmatory rejection of general transfer.

## Provenance / frozen design

- Prescoring design + scorer committed as [`3025d7f`](https://github.com/dianzherdiana25-hash/ACE/commit/3025d7ffcb1362104c8ffd39530e07208aafeaf8); its five source/protocol Git blobs matched the experiment-local files before scoring.
- `bank_seed=141701`, `pilot_seed=141702`, bank SHA-256 `e145c2fe95bd6fc59923973c1c35133b198cb53512f08c701e8ac5e1eee4b529`.
- 12 source and 12 target tasks, 6 paired tasks per family, 3 per family/regime. All rule words were 4-event words disjoint from the previous E1.4 public pilot/replication word identifiers. Input-overlap audit: **432/432 normalized case inputs fresh and unique across E1.4c and the earlier public inventories**.
- Per target, two weak negative demonstrations, eight unlabeled candidate queries and eight held-out probes; the probes were engineered to contain four positives and four negatives. Learning involves a *fixed human-defined 4-event grammar inventory*, not novel grammar discovery or general intelligence.
- Sources: each of the 12 source tasks evaluated eight one-label interventions, 96 source labels in total, and trained one heuristic per family. Learned S policy `last_disagreement`, G policy `short_disagreement`; sham policies S `short_disagreement`, G `long_disagreement`. Source selection **preceded** target scoring.
- Targets: one oracle label per applied policy; 96 separate target-side oracle calls were used to enumerate all eight branches, so the actual evaluation incurs more label calls than a deployed one-label policy. The inherited strategy's source-training overhead is **not included** in the one-target-label comparison.

## Prespecified primary outcome, correct / 24 independent held-out probes per stratum

| Family / relatedness | Inherited | Task-local max-partition | Sham inheritance | Exact random one-label expectation | No extra label | Hindsight best one-label ceiling |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| S / related | **16** | 12 | **20** | 14 | 12 | 20 |
| S / unrelated | **12** | 12 | 12 | 12.5 | 12 | 16 |
| G / related | **11** | **16** | 15 | 14 | **16** | 16 |
| G / unrelated | **10** | 8 | 8 | 8.875 | 9 | 10 |

- Overall inherited 49/96; task-local 48/96; sham 55/96; exact random expected 49.375/96; without label 49/96. Local seeded-disagreement 54/96. Aggregate means **do not** override the four-stratum preregistered rule.
- No resource caps were reported by the finite enumerator; external wall timeout was 90s and process finished in ~3.3s. This is not a separate-worker sandbox proof.
- The G/related stratum exhibits material negative transfer: inheritance 11/24 vs task-local 16/24 and sham 15/24. Several strata tie, and S/related sham wins. These results fail the stricter GO gate.

## Reproduction and audits

- Initial run terminal `OK`, exit code 0. Score artifact SHA-256: `e60f72bfbeefc36c28f9de3fc2193b0ee79d3d09101b64228cbd16228457b7d6`.
- **Actual replay defect found:** frozen `--verify` compared native Python tuples in memory against JSON arrays loaded as lists. It failed even though a normalized canonical JSON comparison returned true. The initial failure traceback is preserved in `evidence/e14/e14c_initial_replay_failure_v1.log`.
- After a **verification-only** one-line fix (`canonical_json(saved) != canonical_json(result)`) and a regression test, replay `OK`; the experiment logic, bank and original evidence remain unchanged. Run result compared byte-equivalent after canonical JSON serialization. This bug fix was made **after** prescoring freeze and is disclosed explicitly.
- New E1.4c prescore/replay tests 6/6 PASS. Independent report-only corruption/consistency tests 7/7 PASS; E1.4 regression discovery 24/24 PASS. The first regression invocation was incorrectly scoped and failed to import relative-package tests; the corrected invocation used `unittest discover -s code/e14 -t code` and passed. Preserve these failures rather than erase them.
- `evidence/e14/e14c_arithmetic_audit_v1.json` independently recalculates source-policy utilities, selected family policy IDs, all one-label choices, per-stratum totals and decision from the saved report. This verifies **report arithmetic only**.

## Methodological weakness identified AFTER the v1 scoring

The v1 `_task()` uses the same PRNG stream to reject target-word-containing demonstration traces **before** generating the supposedly target-unconditioned pool. Rejection consumes a target-word-dependent number of random draws. Thus, even though the pool constructor does not directly call an oracle or read hidden labels, its PRNG state can be correlated with the hidden rule. Prior `test_question_selection_does_not_call_oracle` does **not** detect this indirect dependence. **The v1 claim of an unconditioned question pool is therefore not fully established.** This is a test-design limitation and precludes interpreting the HOLD as a causal generalization result.

## Decision and next study

1. Preserve all v1 evidence unchanged and label it **HOLD with pool-independence flaw**. Do not modify the prescoring `3025d7f` commit or re-label the score as a confirmatory result.
2. Create E1.4c-v2 protocol and **preallocate all unlabeled pools before any word-conditioned examples are drawn**, using separated deterministic RNG streams. Test pool invariance under altered hidden words. Freeze v2 before scoring; perform a fresh development run. This v2 is a corrective follow-up motivated by the **posthoc audit**, not an independent prespecified replication.
3. If transfer still fails or is unstable, move to representation-level invariance, source acquisition cost amortization, and separately isolated worker benchmarking. Include additional strong informed reference and effective compute budgets.
4. Preserve the architecture-agnostic long-term **Open-Ended Autonomous Intelligence Evolution** charter. No E1.3 sealed confirmation, no changes to Tod or `main`, no external costs.
