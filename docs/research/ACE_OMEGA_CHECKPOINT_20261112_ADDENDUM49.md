# ACE Ω Checkpoint — Addendum 49 (statement_order class: construction + calibration)

Date: 2026-11-13. This addendum records the
dossier-construction defect class created under the
coordinator's lever decision on the P4 data (Addendum
48), its construction, and its three-arm calibration.
The lab generator and the B-3 freeze are untouched by
this class. **G3 remains NOT_ASSESSED**; nothing here
is a preregistration.

## 1. The class

`statement_order` (dossier construction, not a lab
class): from a pricing reference program of the frozen
generator, the tax statement — structurally, the final
top-level `AugAssign` with op `Add` — is moved to
directly after the opening assignment, before both
discount statements. The repair requires moving a
statement; no substrate operator reorders statements,
and token substitution cannot either. Construction is
by AST transform with a validity gate: a task counts
only if the variant actually fails at least one case
of the reference's grid (40 of 40 sampled seeds built
valid tasks).

## 2. Calibration (sealed set, never evaluation)

Fresh band seeds 40000–40023, 24 single-defect tasks
of the new class; judged on holdout throughout.
Evidence: `evidence/statement_order_calibration.json`.

- **Baseline arm** (frozen substrate v1 via the
  pricing adapter, the dossier's own arm): **5/24
  (20.8%)**. The class is therefore ~79%
  substrate-blind, not 100% — on some parameter
  combinations the substrate's edits compensate on the
  full case grid. The preregistration will use
  measured baselines, never assumed zeros. Crucially,
  20.8% sits inside the 10–90% headroom band: an
  evaluation set of this class does not trip the P4
  saturation gate.
- **Generic comparator** (token search, budget 400):
  **0/24** — as constructed, token substitution cannot
  reorder statements.
- **Discovery** (pool 8 / evaluation 16, pricing
  adapter, mechanism exactly as frozen, digest
  `48f2d95d…b2f`): 11 operators admitted from the pool;
  evaluation baseline 4/16, extended **4/16 — Δ = 0**.
  The mechanism's schema space enumerates
  expression-level edits; it contains no statement
  motion, and the operators it admits on this class's
  pool do not transfer to held-out tasks of the class.

## 3. What this means for the preregistration

The lever achieved its purpose — pricing headroom
exists (baseline ~21–25%, comparator 0%) — and the
calibration simultaneously gives the preregistration
its honest expectation: with the mechanism **as
frozen**, the pricing effect on this class is likely
~0 for a named, measured reason (no statement-level
edits in the schema space), not by saturation. The
execution room's recommendation: lock the
preregistration with the class included in the pricing
evaluation composition and measure the frozen
mechanism as it is; the falsification consequence —
schema-space round 2 with statement-level operators —
is already a named program item (discovery v-next),
and it must come AFTER the application that measures
the current mechanism, not before it. Changing the
mechanism now would change the artifact the
application exists to measure.
