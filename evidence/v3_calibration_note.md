# A/B/C v3 — calibration-stage note (from census band 1)

Census (evidence/v3_census_band1.json, seed 20261201,
score-call cap 4000, wall 4,417 s under parallel load):
S1 discovery-solvable = 30 (floor met exactly);
S2 composition-requiring = 0 (floor >= 30 FAILED);
S3 control = 33 tasks, arm A solves 32; evaluation
baseline-solvable = 0, unsolved = 0. Admitted:
60 keys + 1 chain.

Findings the calibration/preregistration stage must
answer, stated before any v3 run:

1. **S2 is empty by mechanism, not by seed.** On this
   universe every task the extended arms solve is
   solved by arm B (discovered singles, chained by
   the greedy solver at solve time). Catalog chains
   add no solved task. A C-vs-B necessity stratum
   does not exist in the grid universe family as
   constructed; bands 2-3 cannot be expected to
   change a mechanism-level fact. Options for the
   preregistration draft: (i) redefine S2 as a USAGE
   stratum (tasks whose B-solve applies >= 2 distinct
   discovered operators in sequence) — measurable
   from solve traces, keeps a composition question
   alive without claiming necessity; (ii) drop the
   S2 floor and let the DI composite carry the C arm
   (C-A vs B-A margins on identical sets: if C == B
   everywhere, DI is decided by the (B-A) - 5pp term
   and the C arm is measured as adding zero — an
   honest, publishable outcome). The draft must pick
   one and say why; silently keeping a >= 30 S2
   floor would preregister an INCONCLUSIVE.
2. **The anti-saturation gate's denominator must be
   fixed explicitly.** Arm A solves 0/30 evaluation
   tasks but 32/33 control tasks: on capability
   tasks A = 0% (below a 10% floor read on that
   denominator), on the pooled universe A ~= 51%
   (inside 10-90). The PR #147 text does not fix the
   denominator; the preregistration must.
3. **One control task is not solved by arm A**
   (32/33) although the catalog_control subset is
   baseline-solvable by construction in earlier
   stages. Identify it in the calibration stage; if
   it is a budget-cap artefact (4000 calls), the
   operative budget choice interacts with the
   control-regression term of DI and must be set
   with this task in view.

No v3 run is implied by this note. Next sub-stage:
calibration proper, then the preregistration draft
carrying these three answers.

## Calibration band 2 (added after the calibration run)

Band 2 (seed 20261301, disjoint; evidence
v3_calibration_band2.json): arm A solves evaluation
0/30 (0.0%), control 34/34 (100%), pooled 34/64 =
53.12%. Band 1 (census): evaluation 0/30, control
32/33, pooled ~50.8%. Two-band verdict on the note's
question 2: the 10-90 gate passes on the POOLED
denominator on both bands and fails on the
evaluation-only denominator on both bands. The
preregistration draft must therefore fix the
denominator explicitly, with its justification
stated (the gate's purpose is universe
anti-saturation; a baseline that is blind to new
classes by construction can never pass an
evaluation-only reading, which would make the gate
a guaranteed INCONCLUSIVE rather than a check).
Question 3 update: band 2 has NO failed control
task (34/34), so band 1's single failure is
band-specific, not systematic; identifying it is
still owed before the run (it interacts with DI's
control term). Question 1 (S2) stands as written.

Disclosure: the first band-2 calibration run
reported a spurious 100% in 0.3 s because it treated
solve_task's returned code string as a boolean; that
run is void, the corrected file carries a dated
correction note, and the wrapper now matches the
census's passes()-based check verbatim in substance.

## Update: band-1 control failure identified (morning package)

The single band-1 control task arm A fails at the
operative cap is **catalog_control-032** (band 1:
32/33; band 2: 34/34). The v3 preregistration
draft (ACE_ABC_V3_PREREGISTRATION_DRAFT_20261113.md)
uses this finding to amend the design's control
term from absolute-100% to regression-relative —
otherwise any band where A misses one control task
would force DI < 0 by construction. Question 3 is
now closed.
