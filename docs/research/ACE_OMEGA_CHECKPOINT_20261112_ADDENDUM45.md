# ACE Ω Checkpoint — Addendum 45 (A/B/C v3 design shipped)

Date: 2026-11-13 (Asia/Jakarta). Written directly on `main`.
Design: PR #147,
`docs/research/ACE_ABC_V3_DESIGN_20261113.md`. Design
only — **G2 remains MEASURED — null ×2.**

## 1. What the design decides

Arms differentiated by **strategy** (the cycle-#4
ruling), over one substrate and one score-call budget:
**A** catalog-only; **B** + admitted discovered singles;
**C** + admitted chains with per-step re-enumeration
(the composition-v2 machinery). The universe is held out
by program digest in three strata chosen for measured
discriminating power — S1 discovery-solvable, S2
composition-requiring, S3 control — behind a
preregistered anti-saturation calibration gate (arm A
strictly between 10% and 90% on a disjoint calibration
set, or the universe regenerates; a saturated run
records INCONCLUSIVE, never a third false null).

The decision rule applies the bake-off 01 paperwork
lesson: the conjunction is encoded as **one composite
metric** the kernel can derive — DI = min((C−A) − 15pp,
(B−A) − 5pp, control margin) — with thresholds derived
from measured effect sizes (chains +50pp on S2-shaped
tasks; singles transfer +4 of 15 classes), stated openly
as contestable until they lock at preregistration.

Build order when the stage is taken: lift `solve_with`
into a budgeted per-arm solver behind a v4-replication
gate → grid universe census per stratum → calibration →
preregistration → run. Estimated < 1 h wall, Rp0, no LLM
inside the experiment.

## 2. Gate board (unchanged)

G0 session-scoped PASS. G1 MEASURED — DEMONSTRATED.
G2 MEASURED — null ×2. G3, G4, G5 NOT_ASSESSED.
OAIE unproven (`oaie_proven=false`).

## 3. Queue after this addendum

**G3 application preconditions** (next): P1 refactor
first — decouple `run_discovery` from the grid family
per the bench's Task 04 design (FamilyAdapter protocol,
six coupling points), guarded by exact v4 replication;
then P2 pricing adapter, P3 schema match (satisfiable),
P4 anti-saturation calibration with the ratified
CAP-1/2/3 caps from the Task 07 census → preregistration
drafting → the application run (Task 02's D1–D6 are the
ratified design decisions it executes). Then A/B/C v3
build per PR #147, and G4/G5 instrument implementations.
Facebook mission verification remains owner-panel-blocked.
The 14B partial download still awaits a resume/delete
decision.
