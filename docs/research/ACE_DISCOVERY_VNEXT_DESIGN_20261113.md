# Discovery v-next — schema-space round 2: statement-level operators

Date: 2026-11-13. Status: **DESIGN + SANDBOX PROTOTYPE**.
Branch `research/ace-omega-discovery-vnext-design-20261113`.
This is not a preregistration and measures no gate:
G3's application of the *frozen* mechanism proceeds
independently, and nothing here touches its artifact,
its pools, or its seed bands (absolute fence, §6).
The prototype lives in
`code/ace_operational/statement_ops_prototype.py`.

## 1. Why round 2 exists (measured, not conjectured)

The frozen mechanism's schema space enumerates
expression-level edits — a schema bound to an AST path
plus a relative transformation (`enumerate_variants` in
`operator_discovery.py`). The statement_order
calibration (Addendum 49) measured what that space
cannot say: the class's repair is *moving* a statement,
and on a sealed calibration set the frozen mechanism's
discovery effect was Δ = 0 (pool 8 / evaluation 16,
11 operators admitted, none transferring), against a
substrate baseline of 20.8% and a token-search
comparator at 0/24. Addendum 49 §3 names the
falsification consequence explicitly: schema-space
round 2 with statement-level operators — this design —
to be built *after* the frozen mechanism's application
is measured, never instead of it. The sandbox work
here is that design and a prototype of its central
schema family; any gate use still requires its own
preregistration, after G3's run has reported.

Composition discovery v2 (Addendum 37) supplies the
second input: chains with per-step re-enumeration
solved 3/6 chain-pool tasks where pair discovery
scored 0/6, and the remaining 3 stall on a
non-improving step or the depth-3 bound. Round 2
generalises both lessons.

## 2. The round-2 schema space

### 2.1 Statement motion (new schema family)

A **motion** relocates one top-level statement of the
entry function to another top-level position. The
operator key is

```
("move_stmt", moved_fingerprint, anchor_fingerprint)
```

— insert the identified statement directly before the
anchor statement (or at the body's end slot). Three
design decisions, each forced by a measured property
of the frozen design:

- **Statements are addressed by structural
  fingerprint, not AST path.** The frozen keys locate
  expression sites by child-index path; a motion
  invalidates its siblings' indices (path rot), so a
  path-addressed operator cannot survive its own
  family. A fingerprint is (kind, binding target,
  operator, leftmost leaf name of value/test) with an
  occurrence suffix for in-body collisions.
- **Constants are not part of the fingerprint.** A
  key carrying the literal tax rate (12) could never
  transfer to a program whose rate is 11; the family's
  parameter variation would fragment every motion key
  into per-program singletons and admission (≥2 pool
  fixes) would be unreachable. Granularity is a
  trade — coarser fingerprints transfer, finer ones
  locate more precisely — and round 2 fixes this
  middle point deliberately.
- **A def/use legality filter bounds the space.**
  A motion is enumerated only if, in the resulting
  order, every name a statement uses is defined
  before that use (parameters defined at entry). This
  blocks use-before-def motions generically. It
  deliberately does *not* block reorderings among
  statements mutating the same accumulator: that
  reordering is the semantic content this family
  exists to express, and whether a given reordering
  is a repair is the score's business, not the
  filter's.

Prototype scope (stated as a limit, §5): movable
kinds are `Assign` and `AugAssign`; anchors may be
any top-level statement; motions never land after a
`Return`. Round 2's full design also admits whole
`If`-block motion (a conditional and its body move
as one statement — the fingerprint scheme already
covers it) and treats *swap-adjacent* as a derived
macro of two motions, not a primitive.

### 2.2 Composition depth > 3, with a beam

Chain discovery's bound rises from `max_depth=3` to
a parameterised depth (design point: 5), and the
single greedy path becomes a **beam over chain
steps** (design point: width 4, the solver frontier's
own width): at each step the beam keeps the best
few partial chains by current-program score, each
expanded by full re-enumeration. Addendum 37 names
the beam as the obvious next iteration for exactly
the observed stall mode; round 2 adopts it with a
hard fence — a per-task scored-variant budget for
chain discovery (design point: ≤ 2,000), abstaining
beyond it, because the depth-3 greedy chain run
already cost 1,337 s of wall on six tasks.

### 2.3 Re-enumeration, unified

The L2 diagnosis was that pair discovery composed
keys drawn from the *original* enumeration and never
re-enumerated on the intermediate program (0/6),
while solve-time greedy — which re-enumerates —
composed fine (18/18). V2 fixed this for chains.
Round 2 retires the asymmetry: **pair discovery is
deprecated into depth-2 chain discovery**, keeping
its crediting rule (a shown-perfect composition
credits both constituent keys toward admission).
Every composition path in round 2 — pairs, chains,
motion chains — re-enumerates after every step, and
every admitted operator, motion keys included, is
applied by re-location on the program the previous
step produced (fingerprint match for motions,
path + re-enumeration match for expression keys, as
`apply_chain` already does).

### 2.4 Admission, unchanged

An operator (expression key, chain, or motion key)
is admitted iff it fixes ≥ `min_pool_fixes` (= 2)
independent pool tasks, credited per defect class.
Round 2 changes the *space*, not the epistemics:
the admission rule, the pool/evaluation separation,
and the holdout judgement are the frozen protocol's.

## 3. Hypotheses (falsifiable) and measurement fences

- **H1 — reachability.** On a fresh statement_order
  evaluation set, the motion-augmented solver solves
  ≥ 80% of the *shown-discriminating* tasks (the
  subset any shown-driven solver can in principle
  move on), vs the frozen substrate's measured
  ~21–27% overall baseline on this class.
  Falsified below 50%.
- **H2 — transfer.** Motion keys discovered on a
  disjoint pool and admitted under §2.4 capture
  ≥ 60% of the direct-enumeration arm's gains on
  held-out tasks of the class. Falsified if the
  admitted arm's Δ over baseline is ≈ 0 — the frozen
  mechanism's calibration result, repeated.
- **H3 — no regression.** On the lab's own pricing
  classes, motion augmentation does not reduce the
  frozen substrate's solved count on any set where
  the substrate is below ceiling. (On ceiling sets
  the check is one-sided by construction and is
  reported as such.)

Fences for any future gate use: fresh seed bands
disjoint from the calibration band (40000–40023),
from every G3 application band, and from the B-3
probe bands; preregistration before any gate claim;
the class stays a dossier construction (the lab
generator and the B-3 freeze are not modified — the
round-2 mechanism changes, the frozen artifacts do
not).

## 4. Sandbox prototype and its measurement

`statement_ops_prototype.py` implements §2.1
(enumeration, fingerprints, legality filter,
`apply_motion`), a greedy solver loop mirroring
`run_discovery.solve_with` in shape (frontier ≤ 4,
≤ 6 rounds, timeout-guarded scoring) with the
variant provider injected — the frozen core's solver
cannot host motion arms without the core change
this document proposes, and a prototype does not
edit the frozen core — plus a discovery prototype
(§2.4 admission over motion keys) and the Addendum
49 task construction rebuilt against the carried
frozen generator.

**Carried files (provenance).** This branch is based
on `origin/main`, which does not contain the pricing
family. Three files are carried onto it
*byte-identical* to the B-3 freeze components, so the
baseline arm is the frozen substrate through the
frozen adapter against the frozen generator — not
main's narrower pre-lever generator:
`pricing_substrate.py` sha256 `791fd77f…7292`,
`pricing_adapter.py` sha256 `0f19ff1c…72b`,
`curriculum_lab.py` sha256 `22304a45…75c` (the
freeze record's component digests). No frozen file
is modified anywhere; the B-3 branch is untouched.

**Measurement** (sandbox band: statement_order tasks
from pricing seeds 70000–70099; pool = first 10
built, evaluation = next 30; evidence:
`evidence/discovery_vnext_sandbox_20261113.json` in
the harness tree). All 100 seeds built valid tasks.

| Arm | Evaluation (n=30) |
|---|---|
| A — frozen substrate via frozen adapter | 8/30 (26.7%) |
| B — A + every legal motion (reachability) | 13/30 (43.3%) |
| C — A + admitted motion keys only (transfer) | 13/30 (43.3%) |

Exactly one motion key was admitted from the pool —
`("move_stmt", ("augassign", "t", "Add", "t"),
("return",))`, the class's repair in general form —
and arm C captures **all** of arm B's gains: on this
set, discovered-and-admitted transfer is complete
(H2's direction, at sandbox scale).

The decomposition that makes the headline honest:
only **13 of the 30** evaluation tasks are
shown-discriminating — on the other 17 the buggy
program is already shown-perfect, because every
pricing operation is accumulator-multiplicative and
statement order shows only through floor-division
rounding; no shown-driven solver can move on them.
On the discriminating 13: **A = 8/13, B = 13/13** —
the motion family reaches 100% of its reachable
ceiling here (H1's direction). Arm A's 26.7% overall
also cross-checks the calibration's 20.8% on an
independent band (different band, same construction).

Regression control: ordinary lab pricing tasks,
seeds 71000–71029 at level 1 and seeds 71000–71014
at levels 2–3 — A and B both solve 30/30 + 30/30.
The substrate is at ceiling on its own classes, so
this is a one-sided check (B < A would have shown;
none did), reported as such per H3's fence.

Unit tests: `test_statement_ops_prototype.py`,
10 tests (repair motion enumerated and behaviourally
exact on the full grid; no no-ops; use-before-def
motions filtered; motions never land after Return;
key determinism; apply round-trip; augmented arm
solves a discriminating task the substrate arm
fails; frozen catalog identity) — all green.

## 5. Limits, stated

- The schema space remains human-designed (the
  stage-I honesty boundary): round 2 discovers
  *which* motion, at *which* fingerprint, admitted
  under measurement — it does not invent the notion
  of motion.
- The prototype's movable set is Assign/AugAssign
  at the top level only; nested statement motion
  (inside If bodies) and If-block motion are design
  (§2.1), not prototype.
- The def/use model is straight-line: no nested
  scopes, no attribute/subscript targets.
- Fingerprint occurrence suffixes are per-program;
  if two programs in a family disagree on collision
  order, a key can mis-locate. A production round 2
  needs a collision-stable fingerprint (e.g. a
  content hash of the statement's normalised form
  as the suffix) — named here, not built.
- Shown-identifiability bounds this class for ANY
  solver (§4): a future gate design for
  order-sensitive classes must reckon with shown
  sets chosen for order discrimination, or report
  the discriminating subset as the effective n.
- Sandbox scale: one class, one family, n = 30.
  Nothing here is a gate measurement; G3 remains
  NOT_ASSESSED and this work does not bear on it.

## 6. The fence this work was built under

Discovery v-next does not enter G3's pool, does not
touch the frozen artifact at 83041dc, the B-3
branch, or the G3 run's worktrees/kernels, and uses
none of the G3 application's seed bands (pricing
50000–59999, 60000–60099; grid 20261112–20261153)
nor the calibration band (40000–40023). Its sandbox
bands are 70000–70099 (class tasks + pool) and
71000–71029 (controls). When G3's application has
reported, this design is the named falsification
consequence's build order: lift §2 into the core as
schema-space round 2, behind a replication guard,
under its own preregistration.
