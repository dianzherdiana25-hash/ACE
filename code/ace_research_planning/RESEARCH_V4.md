# ACE R6 v4 — bounded planner-selection learning under mechanism shift

**Disposition: HOLD / public synthetic research only.** Not a blind holdout, independently reviewed study, discovered reasoning primitive, open-ended planning system, or OAIE. Scoped exclusively to `code/ace_research_planning/`; original E1.4 data and ACE `main` are unchanged. v1–v3 reported receipts remain intact.

## Falsifiable question

Can an inexpensive, *trained* strategy selector outperform the strongest fixed planner selected on disjoint validation data when transferred to different task-generating mechanisms, under an explicit combined operation budget? A positive result requires a paired transfer improvement **over the validation-chosen fixed planner**, not merely a victory over a weak baseline or a greater number of search expansions.

## Protocol

The v4 selector is a finite, researcher-specified decision stump, **not an invented or continuously learned planning algorithm**. Five candidate planners: hierarchical replanning, Manhattan A*, graph-metric A*, Dijkstra, and v3 robust. Five observable Boolean features: forced-key-order certificate, geometric certificate, >=4 keys, graph size >=42, and a graph-density predicate. Every candidate is either a fixed planner (5 choices) or a Boolean partition with two distinct planner leaves (5 features × 5 × 4 = 100 choices): **105 total**. Training ranks all 105; validation selects among the top 12. Candidate search and tie-breaking are deterministic. The selector is frozen and hashed **in-process before the transfer rollouts are computed**; this is not a separately trusted, time-stamped or independently escrowed holdout lock.

Seed ranges: train `22100–22123`, validation `23100–23123`, transfer `24100–24123`. Each seed produces 3 mechanism families × static/neutral closure; closure is chosen by solvability-preserving random edge selection **without consulting the planner's selected path**. Development families: ordered gated grid, free-order grid, and cheap portals connecting terminals. Transfer families: cheap non-terminal portal shortcuts, gated portal bypasses, and a shifted edge-cost regime. Both splits share a researcher-written finite interpreter and graph family, so the transfer is only mechanism stress, not truly unanticipated generalization. The first eight transfer seeds were observed in a smoke test during development; do not treat even the remaining seeds as independently blinded.

Every split has `24 × 3 × 2 = 144` world/condition cases; each case uses 5 planners and 2 aggregate work limits (`250`, `2200`) and also an expansion limit `1800`, for **4,320 total planner rollouts**, of which 1,440 are transfer executions. The offline independent Dijkstra oracle supplies a static optimum or a post-shock *hindsight lower bound* (not an online optimal policy). Reward is a researcher-defined trade-off: solve bonus + route quality − measured work. Failing attempts are recorded; recovery is counted **only when a blocked action was actually attempted**.

### Work metering, validity and limitations

`Meter.work_limit` hard-stops search as soon as another charged event would exceed the cap. One unit is charged per expanded node, heuristic call, graph-distance Dijkstra heap pop, or physical edge scan. The total covers replanning and heuristic precomputation. This is more informative than using equal node expansions alone; it **is not FLOPs, CPU time, byte cost, or equal implementation-level work** (e.g. World.cost scans the weight table and heuristic MST has nonconstant cost). Old runs omit `work_limit` and preserve their original behavior and hash receipts. Both methods are charged by the same *declared* event instrumentation; feature calculation and selector-training compute are not included in per-rollout budgets.

## Actual local execution

```
PYTHONPATH=code python -m unittest ace_research_planning.test_planning ace_research_planning.test_study_v2 ace_research_planning.test_study_v3 ace_research_planning.test_study_v4 -v
PYTHONPATH=code python -m ace_research_planning.study_v4 --n 24 --output /tmp/ace_r6_v4.json
```

**40/40 local tests PASS.** Full report was run twice with byte-identical JSON and digest `5ba666eea5ae256b5a8699566e76335b8d43d40a1aa686e641ccee9c24e4de44`. Previous v2 report digest `6ae6b52754bd844a4e01295ca3fa02ff008e3edd196f11867535b874ec750873`; previous v3 digest `2a3525324db46ff974dc57d953459a120c2706b794c5b3a8930fc41f33845303`: both re-executed exactly unchanged. Python 3.13 local standard-library environment; no GitHub Actions run or external reviewer claimed.

### Transfer results (144 trials per budget)

| Work cap | Planner | Success | Mean metered units | Mean successful route / hindsight optimal |
|---|---|---:|---:|---:|
| 250 | learned | 141/144 | 141.37 | 1.1143 |
| 250 | hierarchical replanning | 141/144 | 141.37 | 1.1143 |
| 250 | Dijkstra | 74/144 | 202.26 | 1.0021 |
| 250 | v3 robust | 0/144 | 250 | N/A |
| 2200 | learned | 144/144 | 284.97 | 1.0026 |
| 2200 | Dijkstra | 144/144 | 284.97 | 1.0026 |
| 2200 | hierarchical replanning | 144/144 | 142.36 | 1.1160 |
| 2200 | v3 robust | 54/144 | 1677.93 | 1.0010 |

At cap **250**, the trained selector is `if forced_order then Dijkstra else hierarchy`. This feature is true on 48/144 development and validation cases but **0/144 transfer cases**. Thus transfer *always runs hierarchy*; this is **no evidence of adapting successfully to novel structure**, even though success is 141/144. At cap **2200**, the selector collapses to **constant Dijkstra**, again with no learned conditional adaptation. The validation-selected best fixed planners are hierarchy for cap 250 and Dijkstra for cap 2200. The paired, seed-clustered transfer utility difference (`learned − best fixed`) is **0.0 for both caps**, with deterministic 999-draw bootstrap descriptive ranges `[0.0, 0.0]`. The zero range is due to identical method choices for every transfer case, **not statistical evidence of a generally precise null effect**. Cluster unit is the seed (24), not 144 independent cases.

Under cap 250 the learned method encounters 10 closures and recovers in 8; under cap 2200 Dijkstra encounters 10 closures and recovers in 10. Most simulated neutral closures are never attempted, so raw success rate cannot be construed as a 144-trial recovery rate. At cap 250 two of three failed trials occur in the same seed/condition family pairing.

### Important negative results and risks

1. **No observed superiority to a strong validation-selected fixed baseline.** The learned selector merely recovers one of two known planners on transfer.
2. Severe computational overhead of graph-metric preprocessing: 0/144 successes for robust under cap 250, and 54/144 under 2200. The zero successes refer to **this instrumented budget only**, not unrestricted performance.
3. Transfer uses entirely different feature support for the low-cap selector's true branch; the positive development gain cannot be interpreted as transferred conditional skill.
4. Work-budget event count is a narrow deterministic proxy. A future experiment needs calibrated wall time/FLOPs and common search implementation costs, which might alter the ordering.
5. Selection among 105 candidates risks overfitting 144 small, correlated validation observations; a separate *independent* study is needed. No policy innovation, oracle escrow, autonomous science, self-improvement, or real-world planning has been established.

## Evidence and re-verification

`results_v4_summary.json` contains the canonical digest, selector freeze hashes, validation ranking, family-level total results, paired descriptive intervals and support counts. Regenerate complete per-run `results_v4.json` from the CLI; the complete results are intentionally not included in Git history. Added tests cover exact work caps, no-impact default behavior, old regression suite, split separation, new portal construction, hidden-shock features, selection without transfer input, ordering of transfer evaluation after fitting, determinism and invalid input rejection.

**Conclusion: reject the v4 hypothesis of superior transferred learned selection under the tested event caps. KEEP PR DRAFT.** Next scientific gate: a separately held, authentically blind environment family evaluated by an independent runner after a durable, verifiable freeze; more representative resource accounting; decision policies that can update online after evidence and are compared to strong fixed baselines and fixed budgets.
