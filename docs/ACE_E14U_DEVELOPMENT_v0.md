# ACE E1.4u — graph-global two-route primitive: public DEVELOPMENT only

**Date:** 2026-11-05. **Status:** ENGINEERING DEVELOPMENT; SCIENTIFIC HOLD / NOT ASSESSED. This does not amend the frozen E1.4t bank, score, lock, oracle, or E1.4o/E1.4s decisions. All code is on a separate stacked branch rooted at the E1.4t PR #15 HEAD.

## New executable representation

Previous `single-path` programs return minimum path cost over any route containing one contiguous motif. The new typed `branch-pair` constructor requires **two distinct complete root-to-goal routes** matching two independently specified three-event motifs, and returns the minimum of the larger of their two route costs. An example must supply both routes to return a non-null label. A pair-positive graph plus two one-route negatives with matching individual routes excludes **every possible single-path contiguous motif** as an explanation: any motif matching either positive route must incorrectly match at least one corresponding negative. This is a finite constructive witness of increased *representational expressivity* over the single-path DSL, not autonomous synthesis of unknown primitives.

## Implementation

- `code/e14/e14u_primitive.py`: typed constructor, graph builder, candidate grammar, contradiction detector, exact version-space search, query pool and adaptive/fixed/random selector. Candidate limits are 56 single-path hypotheses, 28 distinct unordered two-path conjunctions and 70 graph offers.
- `code/e14/e14u_dev.py`: fresh per-arm SQLite four-label budget; charged diagnosis/qualification queries, receipt reuse, full structured output; **initial demos (three or four)** and probe calls accounted **outside** the four purchased target interventions.
- `code/e14/e14u_worker.py`: standalone stdlib-only candidate policy. Packet accepts `mode`, `seed`, `demos`, `purchased`, and **rejects target/oracle/probe fields**. It never imports evaluator or inherited source. Hard stop after four purchased queries. A missing/native denied sandbox must not silently fall back to in-process scoring.
- `code/e14/e14u_isolated.py`: integrates this worker with the existing E1.4t Linux user/mount/network/PID namespace + chroot runner, one fresh process per decision, strict evaluator-side graph/action validation, independent receipt audit and worker CPU/RSS/wall counters. **8/8 local namespace canaries passed**, but this is **not native Bubblewrap** nor an independently approved equivalent.
- `code/e14/e14u_audit.py`: separate route-enumeration path (`e14p_graph.paths`), checks all 168 receipt sets, actual oracle labels, purchase costs, trace stage/reuse, version spaces, predictions, exact target correctness, and summary arithmetic. Adversarial tests reject forged labels, graph costs, outcome scores, lost receipt reuse and duplicate arm coverage.
- `code/e14/e14u_robustness.py`: **post-development**, nonconfirmatory seed sensitivity on eight contexts of the SAME 28 target pairs. Do not describe this as an untouched held-out split.

## What was actually executed locally

A compatible **partial** ACE workspace in Python 3.13 executed the 80 historical E1.4t local tests plus 50 new E1.4u tests: **130/130 PASS**. This is **not** the historic 114-test full-repository regression.

**Development matrix:** 42 distinct synthetic worlds (28 two-route pair, 8 single-path, 6 out-of-grammar three-route) × 4 arms (`active`, `fixed`, `random`, `base-only`) = **168 arms**. The identical 168 arm matrix ran twice: (a) in-process engineering and (b) actual separated namespace worker with **404 worker process calls** and 8 namespace canaries. All **168/168 deterministic outcome/cost metrics matched** between modes. One unanticipated bug that allowed a fifth query proposal was fixed and covered by a new regression test. New runs all retained the four-target-label cap.

| World stratum | Active exact | Fixed exact | Random exact | Base-only exact |
| --- | ---: | ---: | ---: | ---: |
| Pair (28) | **28/28** | 21/28 | 26/28 | 0/28 |
| Single (8) | 8/8 | 8/8 | 8/8 | 8/8 |
| Triple / outside represented grammar (6) | 0/6; abstain | 0/6; abstain | 0/6; abstain | 0/6; abstain |

On pair worlds, active purchased 51 labels, fixed 73, random 68. Across all strata and all four strategies, **236 purchased target labels**, audited against trusted evaluator labels and their graph topology; **528 initial demonstration labels** and **1,008 held-out probe labels** are accounted separately. There were zero wrong accepted exact hypotheses and zero errors among covered probes in this **constructed synthetic development matrix**. The base-only arm abstained completely on pair worlds.

**Post-development eight-seed diagnostic:** active 28/28 for every seed; fixed 21–25/28, random 24–27/28. Seeds reuse the 28 predefined target pairs with varied context, so these are NOT independent generalization estimates.

### Known confounds / reasons to withhold GO

1. **Synthetic aligned demonstrations:** the evaluator deliberately supplies a graph showing both target motifs and contrasting one-path negatives. This creates an exceptionally informative starting point. Source acquisition was not learned and is not covered by the four intervention labels. The improvement does not establish unbiased scientific discovery.
2. **Author-defined grammar:** the new `branch-pair` constructor is preprogrammed by the researcher. The worker selects among 28 supplied candidates; it does not invent a new primitive or a successor architecture on its own.
3. **In-process oracle vs worker semantics:** physical namespace isolation shows worker protocol nonexposure on this host, but chroot/unshare canaries are not a complete threat-model evaluation, and different isolation from official Bubblewrap cannot be silently substituted in a final research gate.
4. **No prescore freeze or independent confirmation:** world constructors, source examples and policy were developed together. These are open development controls, and the repeated 8-seed run is **post-development analysis**. There is no untouched E1.4u confirmatory bank/threshold/independent reviewer and no GO claim.
5. **No full checkout regression:** only 130 tests using current partial E1.4u workspace ran; the 114 historical full-suite integration, simultaneous latest-head checkout, resource/power controls and E1.4u independent scientific score remain open.

## Exact reproduction on the compatible E1.4t PR checkout

```bash
export PYTHONPATH=code:.
python3 -W error::ResourceWarning -m unittest \
  e14.test_e14_integrated_graph e14.test_e14_integrated_policy \
  e14.test_e14_issue13_smoke e14.test_e14t e14.test_e14t_audit \
  tools.test_ace_e14t_semantic_audit e14.test_e14u_primitive \
  e14.test_e14u_audit_worker e14.test_e14u_robustness -q
python3 -m e14.e14u_dev --output WORK/e14u-dev-report.json
python3 -m e14.e14u_audit WORK/e14u-dev-report.json
python3 -m e14.e14u_isolated --output WORK/e14u-isolated-all.json
python3 -m e14.e14u_robustness --output WORK/e14u-seed-sensitivity.json
```

Expected standalone deterministic development report SHA-256 (canonical JSON, without SHA field): `0f2e91e697666fe2fbfad587d90b4bb03026e6336c9cd51d7c9066e491dd48d2`.

Expected isolated deterministic result SHA-256 (excluding timing/RSS): `8ce95957534f20e29204e71b6fbf93da13e5d600def58406bdaddfcfffb6b772`.

**Acceptance next step:** pre-register an independent bank with *unassisted* source evidence, unseen graph structure, rival two-route cost algebras, equal CPU/fit and label budgets, and predeclared semantic correctness. Resolve native sandbox custody before any scientific acceptance. Do not edit any frozen E1.4t artifact or call the 28/28 result OAIE.
