# Round-2 gate design — the lifted mechanism behind a replication guard

Date: 2026-11-13. Status: **DESIGN + INSTRUMENT**.
Branch `research/ace-omega-round2-gate-design-20261113`.
This is not a preregistration and measures no gate:
the gate's run needs its own preregistration, after
this design is ratified. G3, G4, G5 remain
NOT_ASSESSED and this work does not bear on them.

## 1. Why this gate exists (measured, not conjectured)

The G3 application returned SPECIALIZATION: the
frozen mechanism transfers inside its home family
(grid +75pp) and adds nothing on pricing — once
because the catalog stratum was saturated, once
because the statement_order class lives outside
its schema space. The preregistered boundary
prediction for that stratum is confirmed, and its
named falsification consequence was schema-space
round 2 with statement-level operators. Round 2
has since been built and preregistered-confirmed
in the sandbox (discovery-round2-01:
ROUND2_CONFIRMED — H1 13/13 discriminating,
H2 capture 1.0, H3 no regression; design
`ACE_DISCOVERY_VNEXT_DESIGN_20261113.md`,
preregistration
`ACE_DISCOVERY_ROUND2_PREREGISTRATION_20261113.md`).
This gate asks the next question: does the
round-2 mechanism, lifted into the core, hold
its effect on a FRESH order-sensitive universe
— or was the sandbox confirmation a property
of one band?

## 2. The candidate: a core lift, not a new mechanism

The candidate is the frozen discovery mechanism
(artifact manifest digest `e2a59960…`, the G3
application's candidate) **plus** the round-2
motion family, lifted into `operator_discovery.py`
as a schema-space extension. The lift is a build
stage that follows this design; it is not part
of it. The lift's contract, fixed here:

- The motion schema is the prototype's (§2.1 of
  the v-next design): fingerprint-addressed
  motion keys, constants excluded, def/use
  legality filter, top-level Assign/AugAssign
  only, never after Return. If-block motion
  stays design-not-prototype.
- The lifted core keeps the frozen admission
  rule (≥2 pool fixes) and the frozen solver
  shape (greedy, 6 rounds, frontier ≤ 4).
- The lifted core's identity is a manifest
  digest over, in order: the lifted
  `operator_discovery.py` bytes, the frozen
  `grid_adapter.py` bytes, the frozen
  `pricing_adapter.py` bytes, ASCII
  `min_pool_fixes=2,max_rounds=6,frontier=4`,
  ASCII substrate freeze digest — the G3
  manifest construction, extended by the lift.

## 3. The replication guard (the gate's load-bearing part)

Before any new measurement counts, the lifted
core must reproduce the frozen mechanism's
measured behavior on its home ground:

1. **Grid replication:** the v4 protocol re-run
   through the lifted solver reproduces
   `operator_discovery_v4.json` on every count
   AND every admitted key set (the PR #151
   replication gate, exact match).
2. **Pricing probe:** the frozen substrate probe
   re-run on band 20000–20999 reproduces 1.000
   (the B-3 frozen-configuration bar).
3. **Sandbox replication:** the round-2
   confirmatory run re-executed through the
   lifted core reproduces discovery-round2-01
   on every count and the admitted key set.

If any guard fails, the run **abstains** — the
lift is not the mechanism it claims to be, and
no transfer number is reported. The guard is
run as separate processes and its evidence is
part of the dossier.

## 4. The application (what the gate measures)

- **Target family:** statement_order tasks on a
  FRESH band, **seeds 72000–72099** (pool first
  10 built, evaluation next 30), built by the
  prototype's task construction against the
  frozen generator. The band is disjoint from
  the sandbox band (70000–70099), the
  calibration band (40000–40023), every G3
  application band, and the B-3 probe bands.
- **Stability family:** grid tasks from the
  v4 protocol's evaluation set — the lifted
  core must not degrade the frozen mechanism's
  grid effect. This family is a stability
  check, not a transfer target: its numbers
  are reported, and a regression there fails
  the gate outright (§6).
- **Control:** ordinary lab pricing singles
  (levels 1–3, the sandbox control bands) —
  the lifted core must not reduce the frozen
  substrate's solved count where the substrate
  is below ceiling; ceiling sets are one-sided
  by construction and reported as such.
- **Arms:** A = frozen mechanism (substrate
  via the frozen adapter); B = lifted
  mechanism (substrate + motion keys discovered
  on the pool, admitted under §2). Same tasks,
  same solver shape, same budgets; the only
  difference is the lifted schema space.
- **Shown-identifiability:** the evaluation
  set is reported in both conventions —
  overall (n = 30) and shown-discriminating
  (the subset any shown-driven solver can move
  on). The pass rule (§6) reads the
  discriminating subset as the effective n;
  the overall figure is reported alongside
  and never substituted for it.

## 5. The instrument

`round2_instrument.py` (this branch) scores a
sealed dossier in the G3 instrument's shape
(criteria version 1, single construction point,
fail-closed, pure function over a dossier
directory). Dossier schema: `dossier.json`
referencing `source` (the target-family report)
and `evaluations` (target + stability family
reports); each family report carries
protocol_hash, audit_status, improvement name
and digest, held_out, baseline and improvement
scores (percent scale), margin_pp. Clauses:

- **C1** — identified improvement, measured
  source effect: the improvement digest matches
  the lift manifest; the source report is
  preregistered and its kernel audit is CLEAN;
  the source effect is positive by the §6 rule.
- **C2** — two distinct families evaluated:
  target + stability, each preregistered,
  CLEAN, held-out, identity-matching.
- **C3** — positive lift effect: the target
  family's effect meets the §6 composite, and
  the stability family shows no regression.
  Margin encoding: the target family's report
  carries margin_pp = 80 − baseline_score, so
  the instrument's check (improvement −
  baseline ≥ margin) reads exactly the H1 bar
  (arm B ≥ 80% of shown-discriminating tasks);
  the stability family's report carries
  margin_pp = 0 (no regression).

Outcome vocabulary:
`LIFT_DEMONSTRATED` (C1–C3 all pass),
`LIFT_WITH_REGRESSION` (target effect met
but the stability family regressed — a named
failure, never a partial pass),
`NOT_DEMONSTRATED` (anything else, items
named). The digest fence is hard: an identity
mismatch is recorded once, in
`identity_mismatches`, and forces
NOT_DEMONSTRATED.

## 6. Decision rule (fixed here, before any run)

One composite metric, computed by the run
driver and scored by the instrument:

```
round2_index = min( B_disc - 80 , (capture - 0.6) * 100 ,
                    control_margin_pp )
B_disc       = arm B's solved share (%) of the shown-
               discriminating evaluation tasks
capture      = (C - A) / (B - A) in solved counts on the
               full evaluation set (C = B here: the lifted
               arm IS the admitted-keys arm; see note)
control_margin_pp = min over control sets of
               (B_solved - A_solved) in tasks, x100/n
               (0 if no regression; negative if any)
round2_index >= 0  ->  LIFT_DEMONSTRATED (if C1-C3 pass)
round2_index <  0  ->  NOT_DEMONSTRATED
```

Note on C: unlike the v3 design, this gate has
two arms, not three — the lifted mechanism is
built by discovery on the pool and applied as
one arm. "Capture" here is measured against a
direct-enumeration reference arm run by the
driver (all legal motions, no admission): the
capture ratio is (lifted − A) / (direct − A).
If direct − A = 0 the ratio is undefined and
the outcome is INCONCLUSIVE (no gain exists
to capture). The stability family's regression
is a separate, absolute failure: any drop in
the stability family's solved count forces
LIFT_WITH_REGRESSION regardless of the index.

Pre-written consequences: LIFT_DEMONSTRATED →
the lifted core becomes the mechanism's next
version candidate (a new freeze cycle, with
its own probe and freeze record); the G3
SPECIALIZATION reading is revisited with the
lifted mechanism as the candidate in a
follow-on application. NOT_DEMONSTRATED →
the lift direction is recorded as falsified
at this scale on this class; the sandbox
confirmation stands as a band-scale result.
LIFT_WITH_REGRESSION → the lift is unsafe
as a core change whatever its target effect;
the regression is the finding.

## 7. Prerequisites before preregistration

- The lift build (operator_discovery.py +
  motion schema, behind the replication guard
  of §3) with its own replication-gate evidence.
- The round-2 instrument's synthetic test
  suite green (this branch).
- The run driver (separate processes per arm;
  the no-discovery attestation pattern from
  the G4 successor runner where the lifted
  core's discovery phase is the pool phase).
- A fresh-band universe validation (Stage F
  validity gates on paper) for 72000–72099.

## 8. Limits, stated

- The gate measures ONE class (statement_order)
  on ONE fresh band at sandbox scale (n = 30
  evaluation). A pass is a band-scale result,
  not a general transfer claim.
- The shown-identifiability bound stands: if
  the fresh band yields few discriminating
  tasks, the effective n is small and the
  verdict is reported with it, not inflated
  by the overall n.
- The fingerprint collision-stability limit
  (per-program occurrence suffixes) is
  inherited from the design and is not
  repaired in this gate; a mis-located key is
  a named failure mode, not a silent one.
