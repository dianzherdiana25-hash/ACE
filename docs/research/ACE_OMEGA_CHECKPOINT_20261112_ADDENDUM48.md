# ACE Ω Checkpoint — Addendum 48 (P4 calibration: gate fired on pricing; CAP caps re-derived)

Date: 2026-11-13. This addendum records precondition
P4 of the G3 application dossier (bench Task 02 §4):
the pricing anti-saturation calibration, run exactly
as prescribed, and the re-derivation of the CAP-1/2/3
allocation caps against the frozen B-3 census, per the
coordinator's instruction not to inherit them silently.
**G3 remains NOT_ASSESSED.** No preregistration is
locked by this addendum.

## 1. Calibration, as run

Baseline arm = the dossier's own arm: the discovery
core's greedy solve loop (6 rounds, frontier ≤ 4, safe
scoring) with the variant source restricted to the
frozen pricing substrate v1 via the pricing adapter —
`solve_with(task, ∅)`, no discovered keys. Calibration
set: fresh seed band 30000–30999 (disjoint from the
probe and census bands), levels 1–3, deduplicated by
program; stratified 24 single-defect tasks (8 per
class) + 12 pair tasks (4 per pair class) = 36 tasks,
none of them evaluation tasks. Solved = all holdout
cases passed.

**Result: baseline solves 36/36 = 1.000. The ≥90%
gate fires.** Evidence:
`evidence/p4_calibration_pricing.json`.

## 2. The prescribed regeneration is exhausted

Task 02's regeneration recipe — 2-defect compositions,
threshold_boundary weighted — is already inside this
calibration set: the 12 pair tasks are 2-defect
compositions, and the baseline solves all of them.
The pricing family has no composition beyond pairs
(level 4 dresses pairs with specification poison; the
programs are identical). Within the current defect
catalog there is therefore **no harder pricing
universe to regenerate**: headroom cannot be created
by allocation, weighting, or case selection. This is
the same measured state the B-3 probe reported for
the generic comparator (1.000 on 1,768 programs); the
calibration now confirms it for the dossier's own
baseline arm.

Consequence, stated plainly: a pricing evaluation
locked today would measure an effect of ~0 by
construction, whatever the discovery mechanism does —
the v1/v2 saturation failure in dossier form. The
preregistration therefore does **not** lock for
pricing until the coordinator decides the one lever
that can create headroom: a defect-class decision.
The execution room's recommendation, with its cost
named: add ONE new defect class at the *dossier*
construction level (applied by the dossier harness to
reference programs, preregistered as such — the lab
generator, and with it the B-3 freeze, stay untouched),
a class whose repair is neither a substrate edit nor
a single-token swap — the candidate shape is a
statement-order defect (tax accumulated before the
discounts), whose repair requires moving a statement,
not editing one. The alternative paths are equally
recorded: substitute the shipping family as the second
evaluation family (no authored substrate exists there;
an adapter build is its own stage), or lock the
dossier as-is and let a measured ~0 pricing effect
stand as the result.

## 3. CAP re-derivation against the frozen census

The CAP-1/2/3 caps were scarcity instruments computed
against the old 108-single universe. Against the
frozen census (2,857 programs: 1,439 singles, 1,418
pairs), the Task 02 allocation consumes, worst case:
pool 12 singles + evaluation 45 singles/18 pairs +
control 30 + calibration 24 singles/12 pairs = 111 of
1,439 singles (7.7%) and 30 of 1,418 pairs. No segment
binds. **CAP-1/2/3 are therefore retired as
non-binding under the frozen census**; the Task 02
allocation table stands as written, and this
re-derivation — not the old caps — is what the future
preregistration cites.

## 4. Grid side and next step

The grid family's headroom is not in question (Stage
F: baseline 0/47 on capability tasks against a 34/34
control), so no calibration gate stands on the source
family. Next step on decision: draft the application
preregistration (Task 02 D1–D6, instrument PR #143,
mechanism digest `48f2d95d…b2f`, substrate v1 digest
`658b9022…d21`, this addendum as the P4 record).
