# A/B/C v3 — preregistration DRAFT

Experiment: `abc-v3-01`. Status: **DRAFT** — this text
fixes the decision rule, the gate denominator, and
the run bands before any run; it submits nothing to
any kernel and locks nothing until ratified. Design
source: PR #147 (`ACE_ABC_V3_DESIGN_20261113.md`).

Build state at drafting: budgeted `solve_task`
shipped (PR #151, v4-replication gate EXACT);
census band 1 done; calibration band 2 done.
Remaining build before submission (named as
TBD-GATE fields below): the DI scorer module
(following the g3_instrument pattern) and the
run driver `abc_v3_run.py`.

Build state after midday track (a), 2026-11-13:
the DI scorer module (`abc_v3_scorer.py`, criteria
v1, 17 tests) and the run driver (`abc_v3_run.py`,
harness, 12 unit tests, never run on the run bands)
are built; the v3-solver lineage is carried
byte-identically into this branch and the `solve_task`
trace hook is added; the §6 digests below are filled
from this branch's files. The v4-replication gate
re-run from this branch is the remaining proof
before submission (see §6).

## §1 Claim

Strategy differentiation is real, not a universe
artefact: on held-out grid tasks, the arms
differentiate by strategy over one substrate and
one score-call budget — A catalog-only, B +
admitted discovered singles, C + admitted chains
with per-step re-enumeration. The decision rule
is ONE composite metric, DI (§4); per-arm and
per-stratum figures are telemetry.

## §2 Universe and bands

- Family: grid only. Universe per band from
  `grid_generalization.build_universe(seed=...)`
  with the census split (pool = first 3 singles
  per class; evaluation = the rest of new_only;
  control = catalog_control).
- Run bands (three disjoint seed bands, the
  repetition structure): **20261501, 20261502,
  20261503**. Disjoint from every prior use
  (census 20261201, calibration 20261301, G4's
  grid universe 20261401/20261402, G3 bands,
  B-3 probe bands).
- Score-call budget: **4000 per task per arm**,
  identical across arms (a chain step costs the
  same budget as a single step). Per-task wall:
  60 s; exceeding it counts the task unsolved
  for that arm and is listed, never a silent
  abstain.
- Discovery runs ONCE per band over the same
  training pool, before evaluation; the admitted
  catalog + chains are frozen and digested.
  Arm A receives no discovery artifact.

## §3 Calibration gate (denominator fixed here)

The design's anti-saturation gate reads on the
**POOLED** denominator (evaluation + control
tasks together), arm A strictly between 10% and
90%. Justification, measured on two bands:
arm A solves 0% of capability tasks on both
bands (it is by construction blind to new
classes) and ~100% of control tasks — an
evaluation-only reading can therefore never
pass and would make the gate a guaranteed
INCONCLUSIVE rather than a check. Measured:
band 20261201 pooled 32/63 ≈ 50.8% (PASS);
band 20261301 pooled 34/64 = 53.12% (PASS).
The calibration sets are those two disjoint
bands; the run bands in §2 are separate
evaluation universes. If the gate fails on a
run band's own calibration re-check, the
outcome is SATURATED_BY_DESIGN, never a
false null.

## §4 Decision rule (ONE composite metric)

```
DI = min( (C - A) - 15pp , (B - A) - 5pp , control_margin )
control_margin = min over arms of (S3 solve rate of the arm
                 - S3 solve rate of arm A), in pp
                 (0 if no arm regresses below A; negative if any)
DI >= 0  ->  DIFFERENTIATION_DEMONSTRATED
DI <  0  ->  NOT_DEMONSTRATED
```

Amendment to the design's control term, stated
with its measured reason: the design wrote the
control term as the lowest S3 rate minus 100%.
Band 1 measured arm A itself at 32/33 control
(the failing task is **catalog_control-032**,
identified by re-running arm A over the band-1
control set at the operative cap; band 2 is
34/34, so the failure is band-specific, not
systematic). Under the absolute-100% reading,
any band where A misses one control task would
force DI < 0 by construction. The regression-
relative reading above preserves the design's
intent (any regression on already-solvable
catalog tasks voids the improvement narrative)
while measuring what the arms do relative to
the baseline arm actually achieves.

Per-arm solve rates are computed per band and
pooled across the three bands; DI is computed
on the pooled rates (per-band DI reported as
telemetry).

## §5 Strata (S2 redefined, with its measured reason)

- **S1** discovery-solvable (B solves, A does
  not): census band 1 measured 30 — floor met.
- **S2** composition-requiring (C solves, B
  does not): census band 1 measured **0** — the
  floor is WITHDRAWN as a run condition. Cause,
  mechanism-level: discovered singles chain at
  solve time through the greedy solver, so no
  task needs a catalog chain to be solved.
  S2 is kept as a reported **usage stratum**:
  tasks whose B-solve applies ≥ 2 distinct
  admitted keys in sequence (trace
  instrumentation is a run-driver requirement);
  the run reports the C−A vs B−A decomposition
  on usage-stratified tasks as telemetry, not
  as a gate. If C == B everywhere, DI is
  decided by the (B−A) − 5pp term — an honest,
  publishable outcome.
- **S3** control: census 33 (band 1), 34
  (band 2); floor ≥ 15 met on both bands.

## §6 Kernel mechanics (TBD-GATE at submission)

- Candidate: the v3 solver artifact
  (`operator_discovery.py` + `grid_adapter.py` as
  carried byte-identically from the v3-solver branch
  tip c5e62a8 into this design branch, plus the trace
  hook of midday track (a) — an optional `trace`
  keyword on `solve_task`, behaviour-identical when
  `trace=None`; the v4-replication gate re-run from
  this branch shows EXACT MATCH on all counts and
  admitted sets (wall 1429.9 s, excluded from the
  comparison) — evidence
  `evidence/v3_solver_replication_run_abcv3.json`,
  independently re-verified deep-equal to
  `evidence/operator_discovery_v4.json` except
  `elapsed_seconds`)
  — digest
  `4232868d7545391e92f74007990e6c5fc6607a29adaa5e9d45b8a9ae4dc813fc`
  (SHA-256 over `operator_discovery.py` bytes then
  `grid_adapter.py` bytes, in that order, no
  separators; components:
  `operator_discovery.py` c64a1cdc… (with the trace
  hook), `grid_adapter.py` d7803d0c…).
- Evaluator: the DI scorer module
  (`abc_v3_scorer.py`, criteria version 1, following
  the g3_instrument pattern) — digest
  `c6ca3421eca3ff4f086b324820ad5168a57cea645ff83bfa922f95b47fd3b6c1`.
- Kernel root: `~/workspace/ace-omega/abc-v3-kernel/`
  (created at submission — not yet created).
- Pass rule: single-metric dict
  `{"metric": "differentiation_index_pp", "gte": 0}`.
- Custodies, audit CLEAN before any score is
  read, and the negative-control discipline
  follow the G3 application pattern.

## §7 Pre-written consequences

- DI ≥ 0 with audit CLEAN: the first measured
  evidence of strategy differentiation; feeds
  the G2 assessment.
- DI < 0: the THIRD measured null; the
  consequence is a new agenda item about why
  strategy does not transfer — never "try again".
- SATURATED_BY_DESIGN / INCONCLUSIVE: reported
  as their own outcomes with the numbers shown.

Brain of origin: Muse (Ian).
