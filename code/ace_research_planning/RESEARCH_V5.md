# R6 v5 — Online metareasoning: paid probing, action feedback, and planner switching

**Disposition: HOLD / PUBLIC synthetic development only.** No independently blinded holdout, autonomous algorithm invention, generally transferable reasoning gain, OAIE or deployment approval. This branch modifies only `code/ace_research_planning/`; ACE main and frozen E1.4 remain untouched. All historical R6 v1–v4 output is preserved.

## Falsifiable hypothesis

A finite policy selected with separate training and validation evidence might improve the **net utility of online decisions** over strong fixed planners and a predefined online-switch controller on new mechanism families, under **shared metered work limits**. The policy is allowed to probe one physical edge at a cost, act without probing and risk failure, or change its search algorithm *after actual evidence*. The policy is **not** allowed to see latent `World.shock`, future outcomes, post-shock oracle scores, or transfer labels.

**Scope of claim:** This is selection among **18 human-authored policies**, not invention of a new planner. Evidence of active sensing would require selecting a nontrivial probe rule with positive matched net utility after all sensing charges. Evidence of learned online adaptation over a strong comparator would require beating the **same predefined online-switch policy**, not just a worse static planner.

## Exact protocol

Files: `online_v5.py` (new controller), `study_v5.py` (frozen policy selection, deterministic benchmark and matched bootstrap), `test_study_v5.py` (16 new tests). Python standard library only. Existing planner and historical benchmark code is not modified.

- **Policy space:** 6 sensing rules (`never`, `always`, `heavy edge`, `nonlocal portal`, `low-degree fragile`, `first 6 successful actions`) × 3 planner rules (`hierarchy`, `Dijkstra`, `hierarchy then Dijkstra upon observed closure`) = **18 candidates**.
- **Information boundary:** The online controller constructs `replace(world, shock=None)` before planning or deciding whether to inspect an edge. `World.shock` is only read by the simulated environment when a probe or action is executed. Once a closure is discovered, that edge is removed from further planning; one closure per world is an explicit simulation assumption.
- **Costs:** Existing `Meter` charges expansion/heuristic events. A probe costs **2 additional instrumented work units**, and each actual failed action incurs an explicit **6-point utility penalty**, not travel cost. Probing itself also costs **0.5 reward points**. Utility for success is `1000 − 120 × (travel_cost / postshock_reference − 1) − 0.04 × work_units − 6 × failed_actions − 0.5 × probes`; failures receive `−200` instead of the 1000/route-quality term and the same resource penalties. This is a chosen synthetic objective, **not** calibrated real-world task value. All methods are subject to the same **300 / 900 work-unit** hard cap plus 1,800 search expansions.
- **Data:** Train seeds 32100–32111 (12), validation 33100–33111 (12), transfer 34100–34117 (18). Three families per split, three conditions per family: `static`, `neutral_closure`, `reference_targeted`. Train/validation families: ordered gated grid, free-order grid, terminal shortcuts. Transfer: interior shortcuts, gated bypass, changed edge-weight mechanism. All mechanisms are public and researcher-defined, and prior R6 versions already studied similar families: **NOT independent OOD blind testing**.
- **Condition caveat:** `reference_targeted` tries a solvability-preserving blocked edge on the initial **fixed hierarchical reference** route, a deliberately biased stress test. If no such edge can be blocked legally without destroying the task, it uses an unfiltered neutral closure. In transfer, **36/54** targeted cases actually close a reference-route edge, and **18/54** use neutral fallback. We report every case, never exclude difficult seeds.
- **Selection:** Rank all 18 using training utility, validate only the top 8, select deterministically, freeze an in-process SHA256 receipt **before** running transfer simulations. This is an ordering audit, **not durable independently escrowed holdout**. The same researcher knows the test generator. No policy receives condition labels. Comparison controls are the best of fixed hierarchy/Dijkstra each with never/always probing as selected on validation, plus the independently predeclared `never-probe then Dijkstra after failure` online control. Paired comparisons use **18 seed clusters**, each with correlated families and conditions.
- **Volume:** `42 seeds × 3 families × 3 conditions × 18 policies × 2 budgets = 13,608 planner rollouts`; **5,832** are transfer rollouts. Hindsight Dijkstra computes a lower bound from the origin after shock; this is not deployable to an online agent.

## Actual local results and failure cases

`PYTHONPATH=code python -m unittest ace_research_planning.test_planning ace_research_planning.test_study_v2 ace_research_planning.test_study_v3 ace_research_planning.test_study_v4 ace_research_planning.test_study_v5 -v`

**56/56 PASS** on Python 3.13 (16 v5 tests + 40 historical). v5 full report was run twice with identical canonical digest **`891bb2d7a29c763929143909b0a62978aeb29645936060d396c26599e8199da0`**. Historical v2/v3/v4 reruns retain respective digests `6ae6b52754bd844a4e01295ca3fa02ff008e3edd196f11867535b874ec750873`, `2a3525324db46ff974dc57d953459a120c2706b794c5b3a8930fc41f33845303`, `5ba666eea5ae256b5a8699566e76335b8d43d40a1aa686e641ccee9c24e4de44`.

| Transfer metric (162 correlated tasks per budget) | Selected at cap 300 | Fixed validation baseline at 300 | Selected at cap 900 | Fixed validation baseline at 900 |
|---|---:|---:|---:|---:|
| Strategy | never+hier | never+hier | never+hier→Dijkstra on discovery | never+hier |
| Solved | 161/162 | 161/162 | 162/162 | 162/162 |
| Mean utility | 974.754507 | 974.754507 | 982.458204 | 982.104781 |
| Mean work units | 126.870 | 126.870 | 158.136 | 126.957 |
| Mean successful route/reference | 1.09305 | 1.09305 | 1.07958 | 1.09292 |
| Observed closure events / successful recovery | 45 / 44 | 45 / 44 | 45 / 45 | 45 / 45 |
| Probe calls | 0 | 0 | 0 | 0 |

- At cap 300 the selected policy equals the fixed hierarchy baseline; matched utility improvement **0**. The predefined post-closure switch only solves 148/162 under this cap, versus 161/162 for hierarchy: switching can consume too much compute.
- At cap 900 the learned selector yields **+0.353423** average utility versus validation-selected fixed hierarchy, with descriptive **seed-cluster bootstrap** interval **[−0.564420, +1.489353]**. This is small, does not exclude zero, and is contingent on the chosen reward weights.
- **Critical comparator:** at cap 900 the learned policy is **exactly identical to the researcher-written predefined post-closure switch** on *every* transfer case. Thus its delta against that strong predeclared online control is **0**. No autonomous improvement in switching logic is demonstrated.
- `always` sensing with hierarchy prevents 45 failed physical actions on cap 900 but makes ~9.5 probes per task and decreases utility relative to never-probe: 978.261448 vs 982.104781. The selected policy probes zero times. **No positive evidence of beneficial active information acquisition** under this scoring rule.
- Under cap 300 the only learned-policy failure is seed **34100**, transfer `interior_portals/reference_targeted`, terminated by `work_budget`. Do not drop this case.
- **Sensitivity (no refitting):** cap 900 learned-minus-fixed utility changes sign under alternate *post hoc diagnostic* weights. With route-quality penalty 60 and work penalty 0.04 it is **−0.4469**; with 120 and 0.04 it is **+0.3534**; with 120 and 0.10 it is **−1.5173**. The small win is not reward-robust. The primary result uses only the prespecified 120/0.04 weights. Never use transfer sensitivity to retune the selector.

## Reproduce

```bash
PYTHONPATH=code python -m unittest ace_research_planning.test_planning ace_research_planning.test_study_v2 ace_research_planning.test_study_v3 ace_research_planning.test_study_v4 ace_research_planning.test_study_v5 -v
PYTHONPATH=code python -m ace_research_planning.study_v5 --n-train 12 --n-validation 12 --n-transfer 18 --output /tmp/r6_v5_full.json
```

`results_v5_summary.json` keeps receipts, aggregate metrics and a compact audit. The full per-run 4+ MB result is intentionally **not checked into GitHub**; it is exactly regenerated by the CLI and available in the local downloadable research package. The canonical digest hashes the uncompressed full report excluding the digest field itself using sorted compact JSON encoding.

## Disposition and next gate

**HOLD.** The online controller is executable and correctly reacts to newly acquired evidence, but finite selector learning **did not improve on a predeclared strong online-switch rule**, and paid sensing did not improve net utility. A scientific next gate requires a truly separately held environment/evaluator, independently enforced policy freeze, and realistic compute/latency/observation costs. No CI result is implied by local tests, and no merge is authorized.
