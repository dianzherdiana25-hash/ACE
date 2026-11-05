# ACE R6 v3 — metric-shift falsification, admissible graph heuristics and a proof-guard fix

Status: **PUBLIC AUTHOR-DESIGNED / exploratory mechanism-shift stress / HOLD**. This is **not a blind holdout**, not a learned planner, not a general-reasoning claim, and not OAIE. Owns only `code/ace_research_planning/`; does not alter frozen E1.4, any other research lane or `main`.

## Question and falsifiable hypotheses

H1 (admissibility under mechanism shift): Manhattan-distance MST A* is optimal when each physical edge weight is no less than Manhattan displacement, but can return a suboptimal *successful* route after cheap nonlocal edges break that assumption. H2: a graph-metric MST lower bound that uses observable shortest paths in the relaxed physical graph can recover optimal static planning on such tasks. H3 (falsification): even if graph-metric A* expands fewer search states, its graph-distance preprocessing could make it slower overall. H4: a sufficiency certificate for forced key order must reject nonlocal transitions that bypass intermediate gate checks.

The code implements a **hand-authored, rule-based** `robust` selector: use the v2 structural planner only when each physical edge respects the Manhattan edge lower bound; otherwise use `astar_metric`. This is **not** policy learning or autonomously invented reasoning. In the nonlocal family this selector is behaviorally identical to `astar_metric` and cannot be counted as independent corroboration. In the paired control family, v2's structural fallback is selected under tight node budgets.

## Reproduction and fixed public study

Python 3.10+ stdlib only, from project root:

```sh
PYTHONPATH=code python -m unittest ace_research_planning.test_planning ace_research_planning.test_study_v2 ace_research_planning.test_study_v3 -v
PYTHONPATH=code python -m ace_research_planning.study_v3 --output /tmp/ace_r6_v3.json --n 24
PYTHONPATH=code python -m ace_research_planning.profile_v3 --n 24 --repeats 5
```

Public seeds `12100..12123`, distinct from previous v1/v2 sets; paired families: unchanged weighted grid graph with free key ordering (`paired_control`), and that same graph with up to two cheap nonlocal shortcut edges connecting predeclared task terminals (`nonlocal_portals`). This is a **deliberately adversarial** changed-distance mechanism, not an impartial sample of environments. Conditions: static, and seeded route-independent (but solvability-preserving) surprise edge removal (`neutral_closure`). Algorithms: greedy best-first, hierarchical replanning, v2 structural, Manhattan-MST A*, Dijkstra, graph-metric-MST A*, and a rule-based `robust` selector. Budgets: 60, 180 and 1800 total expanded states including repeated plans. `2 families × 24 seeds × 2 conditions × 3 budgets × 7 arms = 2,016 simulations`.

The per-run `results_v3.json` is regenerated locally; GitHub retains `results_v3_summary.json` with the deterministic full-run canonical SHA256 hash. Pairing ensures the same base graph and key layout per seed; independently coded Dijkstra checks action costs and gate semantics. In dynamic trials, the post-surprise reference is only a **hindsight lower bound**, not a feasible online optimal policy. Neutral closures frequently are not attempted; report encounters separately.

## Methods and proof preconditions

The old `heuristic` uses grid Manhattan distance to build a nearest-terminal + MST lower bound. It is admissible only when every physical edge has `cost >= Manhattan(endpoint_a, endpoint_b)`. Cheap portal edges can make this condition false and create misleading A* ordering.

New `metric_heuristic` uses Dijkstra distances in the *observable* undirected weighted physical graph while relaxing all locks and ignoring surprise closure. The weighted graph metric cannot overestimate any physical route. The MST over outstanding targets and the minimum current-position-to-target distance lower-bound the cost of a walk visiting all targets; lock restrictions and actual closures only raise or preserve cost. A* can reopen cheaper states. Caching Dijkstra computations within a single rollout avoids duplicate graph-source calculations. Metric precomputation charges `metric_edge_scans`, `metric_heap_pops`, and `metric_sources`, reported separately from `expanded` and `heuristics`. These counters are proxies, not a common FLOP unit; comparing only expansion budgets remains **not compute matched**.

The v2 `forced_key_order_certificate` was too weak for arbitrary topology: a nonlocal edge from column 0 to 2 could bypass boundary 1 because edge transitions check only the smaller endpoint column. v3 now rejects the forced-order proof whenever any physical edge is nonlocal (`Manhattan != 1`), even if that portal has high cost. A focused regression test constructs this bypass while preserving the geometric metric certificate.

## Actual deterministic results

Full-run canonical receipt: `2a3525324db46ff974dc57d953459a120c2706b794c5b3a8930fc41f33845303`. Nonlocal static, cap 1800, n=24:

| Method | Success | Static optimal | Mean expansions | Mean metric edge scans | Mean successful cost/optimal |
|---|---:|---:|---:|---:|---:|
| Greedy | 24/24 | 5/24 | 19.38 | 0 | 1.6061 |
| Hierarchical replan | 24/24 | 8/24 | 43.54 | 0 | 1.3888 |
| Manhattan-MST A* | 24/24 | 20/24 | 127.96 | 0 | 1.0299 |
| Dijkstra | 24/24 | 24/24 | 193.88 | 0 | 1.0000 |
| Graph-metric A* | 24/24 | 24/24 | 29.67 | 2431 | 1.0000 |
| Robust selector | 24/24 | 24/24 | 29.67 | 2431 | 1.0000 |

Concrete nonoptimal Manhattan A* static counterexamples (`seed: A* / independent optimum`): `12108: 44/43`, `12114: 34/26`, `12116: 30/25`, `12118: 19/16`. The four failures are successful **but suboptimal**, demonstrating why success alone cannot validate planning correctness.

Nonlocal neutral-closure, cap 1800, n=24: A*, Dijkstra and graph-metric A* each 24/24 success; route-blockage encounters only **5/24** per method. Mean success cost/offline hindsight lower bound: A* **1.0460**, Dijkstra **1.0161**, graph-metric A* **1.0161**. This is not a demonstration of 24 independent recoveries; only the five encountered changes trigger repair.

Nonlocal static, cap 60, n=24: graph-metric A* 22/24 successes versus Manhattan A* 7/24 and Dijkstra 5/24, **under equal expanded-state caps**, not equal total compute. On paired control static, cap 60: graph-metric A* 23/24 and robust selector 17/24 because the latter uses a cheap hierarchical fallback. **Robust is not universally more successful.**

Local CPU timing diagnostic, Python 3.13, 24 portal worlds × two conditions × five repeated measurements, pre-run warmup, per-world medians then median across worlds: hierarchical replan **0.2371ms**; Manhattan A* **1.1648ms**; Dijkstra **0.9261ms**; graph-metric A* **2.7356ms**; robust **2.64ms**. These values vary by machine, scheduler and runtime; the timing experiment is optional and not deterministically replayable. It *undercuts* claims of superior compute efficiency, despite the favorable graph-metric expansion count. Precompute and interpreter overhead dominate here.

## Adversarial checks and limitations

31/31 local stdlib unit tests pass across v1–v3. v3 tests verify paired topology controls, portal metric violation, original A* suboptimal witness, graph-metric A* exact matching against an independently implemented Dijkstra reference under known closures, admissible lower bound at sampled subgoal states, hidden-shock nonleakage, cumulative cap conservation, stable replay, malformed parameters and the strengthened gate-order proof. This is **local testing**, not GitHub CI, third-party independence, or formal proof of every implementation path.

Negative evidence remains: the new selector is manually engineered, `robust` duplicates metric A* on shifted worlds, advanced heuristic is slower on measured local workloads, neutral closures are rarely encountered, and total-compute-matched or independent blinded evaluation has **not** been done. Even the metric itself is computed from fixed graph knowledge: no online acquisition of unknown transition rules. No claims of autonomous capability growth, independently verified transfer, or scientific GO are warranted.

**Disposition:** HOLD. Keep PR as draft; request exact-head test run and independent methodological review before integrating. Preserve v1/v2 public results and negative controls unchanged.
