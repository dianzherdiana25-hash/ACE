# ACE Ω Checkpoint — Addendum 47 (Stage B-3: pricing substrate built, levered, frozen)

Date: 2026-11-13. This addendum records the B-3 stage:
the authored pricing substrate (bench Task 06 design),
the case-grid lever taken before the freeze under the
coordinator's ratification, and the freeze itself.
Builders: Muse (Ian), ACE's registered development-
engine brain. Design: the Antigravity bench (Task 06).
Lever scope ratified by the coordinator (discussion
room). **G3 remains NOT_ASSESSED.**

## 1. What shipped (PR #150, stacked on #149)

- `pricing_substrate.py`: two structural operator
  generators in fixed order — `_variants_threshold`
  (a `>` bulk-threshold guard → `>=`) and
  `_variants_rebase_basis` (a discount/tax chain rooted
  at the raw parameter → rebased onto the accumulator;
  one generator serving tax_basis and member_basis, one
  variant per offending statement). The accumulator is
  identified structurally (the variable bound from the
  first parameter), never by the literal name `t`;
  operators are signature-based, never string-replace.
  `pricing_variants` and `solve_pricing` mirror the
  grid substrate's shapes.
- Tests (3, grid-pattern): variants change code and
  parse; the reference produces NO variants across
  seeds; the solver repairs single and pair defects.
- The P2 adapter is rebound in this stage:
  `baseline_variants` = the substrate's
  `pricing_variants`, `baseline_catalog_id` = the
  freeze digest (§4). The interim generic enumeration
  is retired as the dossier baseline.
- Freeze record: `docs/research/ACE_B3_FREEZE_20261113.md`.
- Lineage sweep: **262 OK (skipped=17)** — the 259 of
  P2 plus the 3 substrate tests (invocation: full
  package discovery from the lineage worktree's
  `code/`).

## 2. Probe discipline and the first probe

Per Task 06 §3 the probe set was fixed BEFORE any
operator was written: seeds 5000–5999, levels 1–3,
deduplicated by `normalized_form` — it saturated the
original universe (exactly 216 programs, 36 per single
class and per pair class; an independent reproduction
of the bench census ceiling). One-shot probe, holdout
judged by the lab verifier, both arms at evaluation
budget 400: **substrate 216/216** (bar ≥95% incl. all
singles met) — and the **generic token-search
comparator also 216/216**. Evidence:
`evidence/b3_probe_set.json`, `evidence/b3_probe_report.json`.

## 3. The lever (B3-R3), taken before the freeze

Freezing over a universe that even generic search
saturates would repeat the v1/v2 saturation with open
eyes. The stage reported the fork; the coordinator
ratified the case-grid lever ONLY, with a no-serial-
widening fence: `_pricing_family` ranges were widened
ONCE to their realistic commercial spans (thresholds
{50k, 100k, 150k, 200k, 250k, 300k, 400k, 500k, 750k,
1M}; bulk/member percentages {5, 10, 15, 20}; tax
{10, 11, 12} bracketing the 11% PPN rate) — 480
parameter combinations, no new defect classes, no
structural template change. Official census (B3-R5)
against the widened generator, seeds 20000–25999:
**2,857 unique programs** (of 2,880 theoretical;
singles 479–480/class, pairs 471–474/pair-class).

Re-probe of the frozen configuration on a fresh band
(20000–20999; 1,768 unique programs; the operators
were never iterated against any probe set): substrate
**1.000** overall — singles, pairs, and every pair
class — bar met. Comparator: **still 1.000**, reported
as measured: the expansion multiplies distinct
programs; per-program token reachability is unchanged.
Per the coordinator's fence this state returns to the
hub as the input for the next lever decision (defect
classes); it does not block the freeze, whose baseline
arm is the substrate and whose ceiling risk is P4's
checkpoint to measure before the preregistration
locks. The CAP-1/2/3 caps, computed against the old
216 universe, are to be re-derived against this
census at lock-in, not inherited (coordinator's
instruction; restated for the preregistration stage).

## 4. The freeze

**Pricing substrate v1**, digest
`658b9022681bcb9e658b7b3f1c85fd3bc8e106718dca8b5ff1fd6b8cffd6bd21`
— SHA-256 over the substrate module bytes
(`791fd77f…7292`) · the ordered operator names · the
solver parameters (max_rounds 6, frontier 4) · the
frozen-configuration probe report digest
(`2ce79d88…0a6`) · the generator digest
(`curriculum_lab.py` at freeze: `22304a45…75c`). Any
post-freeze change to an operator, a signature, or a
solver parameter is v2: fresh probe, new digest, new
freeze record. A dossier preregistration names this
version and digest; a discovery run against any other
digest is an integrity failure of that run.

## 5. Named next steps

Per the corrected sequence: **P4 calibration** (CAP
caps re-derived against the frozen census; Task 02's
anti-saturation gate) → **G3 application
preregistration** (Task 02 D1–D6, instrument PR #143,
mechanism digest `48f2d95d…b2f`, substrate v1 digest
above) → the application run. In parallel queue:
A/B/C v3 build (PR #147), G4/G5 instruments (PR #136;
bench dossier drafts Tasks 08/09 ratified as designs).
