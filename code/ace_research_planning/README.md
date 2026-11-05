# ACE R6 — compositional planning, bounded search, and recovery

**Status:** author-designed PUBLIC synthetic prototype; not independent blinded validation, not an OAIE claim. Isolated ownership `code/ace_research_planning/`, no ACE core, frozen E1.4 or main changes.

## Reproduce (Python 3.10+, stdlib only)

```sh
PYTHONPATH=code python -m unittest ace_research_planning.test_planning -v
PYTHONPATH=code python -m ace_research_planning.benchmark --output /tmp/r6.json --limit 1800 --n 18
```

11 focused tests: deterministic generators and runs; split-disjointness; admissible A* result vs Dijkstra for 16 generated worlds; fixed-plan failure and adaptive recovery after a newly blocked edge; strict total expansion cap across replans; invalid inputs; unreachable task; greedy ordering counterexample; and no shock information visible to the search planner.

### Fixed protocol

* Two **disjoint** seed sets: dev 1000–1017 and OOD 9000–9017; each evaluated in static and surprise blocked-edge conditions, 72 worlds in all.
* Dev: 4–5 × 4 grid, two ordered collectible keys with locked passage boundaries, 10% missing edges. OOD: 7–8 × 5–6, three to four keys, 19% missing edges; alternating tasks use no gate locks and key locations anywhere, requiring free ordering rather than fixed lock order.
* An agent's initial known graph omits the surprise closure. Surprise closure is selected from the **fixed hierarchical planner's first intended route** and is guaranteed to preserve solvability. All methods encounter the same closed edge but not all methods attempt it. Failed attempt reveals this single edge. No other concealed changes.
* Six planners: BFS (step-optimal search), greedy best-first, full-state A* (admissible Manhattan MST lower bound), fixed hierarchical subgoal decomposition (cannot recover from blocked action), hierarchical replan, and adaptive hierarchy-to-A* switch after failed action.
* All planners receive the **same total expanded-state cap** per rollout including replans. Heuristic calls, search calls, peak frontier, action cost, failed actions, success, and recovery are recorded separately. Expansions are not CPU time; A* heuristic is more expensive per expansion. This is not a precisely compute-matched experiment.
* All keys must be collected before arriving at the terminal goal; crossing gate boundary *j* requires key *j*. Actions have positive integer edge weights 1–5. Independent Dijkstra reference evaluates each world. Post-surprise offline optimal route cost is a **lower bound only**, not an attainable dynamic-policy oracle. No planner sees oracle score or a held-out label.
* The initial code is not trained; OOD is a manually distinct family, not an independently blinded holdout. We explicitly do not tune based on OOD outcomes.

### Main findings at 1,800 expansions

| Family/condition | BFS | Greedy | A* | Fixed hierarchy | Replanning hierarchy | Adaptive hierarchy→A* |
|---|---:|---:|---:|---:|---:|---:|
| dev/static success | 18 | 18 | 18 | 18 | 18 | 18 |
| dev/shock success | 18 | 18 | 18 | 0 | 18 | 18 |
| OOD/static success | 18 | 18 | 18 | 18 | 18 | 18 |
| OOD/shock success | 18 | 18 | 18 | 0 | 18 | 18 |
| OOD/shock mean expanded nodes | 393.83 | 41.89 | 351.11 | 16.89 | **71.78** | 189.56 |
| OOD/shock mean successful cost / post-shock lower bound | 1.151 | 1.194 | 1.026 | n/a | 1.047 | 1.026 |

**Negative findings and falsifiers:** Switching from hierarchy to A* after surprise did **not** decrease search cost relative to simply replanning hierarchy; mean OOD/shock expansions increase 71.78 → 189.56. Under 60 expansion cap, only 2/18 adaptive OOD/shock tasks succeed versus 6/18 hierarchical replans; under 120, 9/18 versus 17/18. Four of eighteen OOD/static hierarchical outcomes are suboptimal (seeds 9004, 9006, 9008, 9014). Greedy spends fewer expansions but yields worse paths (OOD/shock ratio 1.194). Recovery success among agents that encounter the blocked edge is the relevant conditional metric. Fixed hierarchy is purposely a brittle no-replan control; its failure does **not** demonstrate sophisticated general intelligence.

**Design limitations:** Researcher-designed graph generator, heuristics and surprise selection; no learned skill induction or natural-language compositional reasoning; no stochastic action model; OOD family chosen in advance but openly inspectable; shock selection favors the fixed hierarchical trajectory; per-state expansions not equal FLOPs; optimistic replanning under hidden closure can incur wasted moves; no fully independent reviewer or CI verification. Some designs guarantee solvability and impose artificial key ordering; these are not evidence of open-ended adaptation.

Exact deterministic main-run report digest (canonical JSON with the `sha256` key omitted before digest): `d13e42e05f2385075218d9dab9f659c3425898381fd61cb93bd1143f96cc909f`.

## Exploratory v2 follow-on (2026-11-05)

`RESEARCH_V2.md` documents the unchanged v1 receipt alongside a structural-key-order certificate, new `structural` policy, separately chosen neutral edge closures, a separately implemented finite-state Dijkstra reference, 3,024 synthetic runs at multiple budgets, 8 new independent focused tests, and negative low-budget outcomes. Run `PYTHONPATH=code python -m ace_research_planning.study_v2 --output /tmp/r6_v2.json --n 24`. No independent blinded validation, no autonomous learning, and no scientific GO.


## R6-v3 public mechanism-shift falsification (exploratory / HOLD)

`study_v3.py` compares the previous grid-only methods against cheap nonlocal
shortcuts that invalidate the Manhattan admissibility assumption. It adds
`astar_metric` (graph-metric MST heuristic with separately accounted physical
edge scans and heap pops), a manually specified geometry-certified `robust`
selector, and a corrected forced-key-order certificate which rejects bypass
portals. **R6 v3 is not learned reasoning or OAIE.** Original v1/v2 results and
programs remain reproducible. New v3 canonical digest and negative timing
evidence are in `RESEARCH_V3.md` and `results_v3_summary.json`.

```sh
PYTHONPATH=code python -m unittest ace_research_planning.test_planning ace_research_planning.test_study_v2 ace_research_planning.test_study_v3 -v
PYTHONPATH=code python -m ace_research_planning.study_v3 --output /tmp/ace_r6_v3.json --n 24
PYTHONPATH=code python -m ace_research_planning.profile_v3 --n 24 --repeats 5
```


## v4 (public strategy learning and event-budget falsification)

New `study_v4.py` learns a **bounded decision-stump selector** from train/validation outcomes before examining mechanism-shift transfer data. `Meter.work_limit` enforces a cumulative mixed-event proxy (expanded nodes, heuristic calls, relaxed-graph scans, heap pops); this is not FLOP/CPU equivalence. The default unlimited-work behavior of v1–v3 is unchanged. **Local v4 finding is negative:** under work cap 250, selector defaults to hierarchy on all transfer tasks, exactly matching fixed hierarchy (141/144 success). Under 2200 it collapses to fixed Dijkstra (144/144). Paired transfer utility delta versus the best validation-selected fixed planner is zero at both caps. No learned planning primitive, OAIE or independent blind claim.

```sh
PYTHONPATH=code python -m unittest ace_research_planning.test_planning ace_research_planning.test_study_v2 ace_research_planning.test_study_v3 ace_research_planning.test_study_v4 -v
PYTHONPATH=code python -m ace_research_planning.study_v4 --output /tmp/r6_v4.json --n 24
```

See `RESEARCH_V4.md` for pre-declared environment splits, case-level accounting, policy freeze digests, caveats, negative controls, and exact reproduction.


## v5 — online probe/act/replan research (PUBLIC, HOLD)

New `online_v5.py`, `study_v5.py`, `test_study_v5.py`, `RESEARCH_V5.md`,
`results_v5_summary.json`. Offline, explicit observation boundary: the planner
never sees the hidden closure before an action/probe reveals it. Eighteen
human-authored online policies; shared 300/900 instrumented-work-unit budgets,
separate training/validation/transfer seeds. In 13,608 simulated rollouts, the
selected learned policy is identical to fixed hierarchical search at cap 300
and to a predeclared hierarchy→Dijkstra-after-discovery policy at cap 900.
Paid probes are not selected; no demonstrated autonomous reasoning gain.
**56/56 local unit tests PASS.** Read `RESEARCH_V5.md` for the negative result,
conditional recovery, seed counts, exact hash, fallbacks, and limitations.

Reproduce from repository root:

```sh
PYTHONPATH=code python -m unittest ace_research_planning.test_planning ace_research_planning.test_study_v2 ace_research_planning.test_study_v3 ace_research_planning.test_study_v4 ace_research_planning.test_study_v5 -v
PYTHONPATH=code python -m ace_research_planning.study_v5 --output /tmp/ace_r6_v5.json
```
