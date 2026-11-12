# ACE Ω Checkpoint — Addendum 46 (P1 done: discovery decoupled; mechanism digest frozen)

Date: 2026-11-13 (Asia/Jakarta). Written directly on `main`.
Build: PR #148 (stacked on PR #140), per the bench's
Task 04 decoupling design.

## 1. What changed

`operator_discovery` no longer imports any family module.
All six couplings (K1–K6) are gone, including the deferred
`grid_variants` import hidden inside the solver and the
`#` wall-character seed, which now arrives through the
adapter. The `FamilyAdapter` protocol carries
make_budget / passes / baseline_variants /
baseline_catalog_id / extra_string_candidates, plus the
written task contract; `grid_adapter.GridAdapter`
delegates byte-for-byte to the pre-refactor machinery.
Callers name the adapter explicitly; the `None` default
resolves to the grid adapter at one documented legacy
point (the deviation from Task 04 §2's no-default
preference, taken because §4 requires the existing suite
to pass unchanged; the audit property that matters —
preregistrations naming their adapter — is preserved).

## 2. Guards (all green, zero tolerance)

- `test_operator_discovery` passes **unchanged**: 9 OK.
- Lineage sweep: **255 OK (17 skipped)** — identical to
  the pre-refactor baseline.
- **Replication guard (Task 04 §4): EXACT MATCH.** The
  full v4 protocol re-run through the refactored core
  (1,369 s) reproduces `operator_discovery_v4.json` on
  every count (pool 12 / eval 29; per-class pool,
  candidates, eval, baseline→extended; pairs 0/6; chains
  3/6; mixed 0→18/18; control 34→34) **and** every
  admitted operator/chain key set. Evidence:
  `evidence/p1_replication_run.json`.

**Mechanism digest, frozen after the refactor** (Task 02
precondition P1's second half): sha256 over
`operator_discovery.py` ‖ `grid_adapter.py` =
`48f2d95d2d02d038a10241ff641b3327d9e0e871c17def183e6a1639c005db2f`.
Admission parameters stay protocol-level
(`min_pool_fixes=2`, recorded in preregistrations).

## 3. Canonical tree — R7 closed in writing

The mechanism's canonical home is the
**composition-discovery lineage** (PR #140's branch):
it carries the newest discovery mechanism (pairs +
chains, the v4 evidence producer). This refactor is
stacked on it. The older copy on the G3-design lineage
is superseded as a mechanism source (it remains the G3
instrument's design lineage).

## 4. The G3 application sequence, as corrected with the hub

P1 (this addendum) → **P2** pricing adapter → **B-3**
build + probe + **freeze** of the authored pricing
substrate (Task 06 design; the calibration lever 3–4
decision is taken BEFORE the freeze per B3-R3; the
official B3-R5 census runs against the frozen
generator) → **P4** calibration (CAP-1/2/3 against the
frozen census) → preregistration drafting (Task 02's
ratified D1–D6; margin +10pp Δ, ≥3-task floor, zero
control regression) → the application run. P3 (schema
match against the instrument, PR #143) is satisfiable
now. The services demand test file is closed by its
checkers (TAHAN; the two wording corrections are applied
and the Addendum 42 §1 band erratum stands on main at
117c580).

## 5. Gate board (unchanged)

G0 session-scoped PASS. G1 MEASURED — DEMONSTRATED.
G2 MEASURED — null ×2. G3, G4, G5 NOT_ASSESSED — P1 is a
precondition, not an assessment. OAIE unproven
(`oaie_proven=false`).

## 6. Queue after this addendum

P2 pricing adapter → B-3 substrate stage → P4 → G3
application preregistration + run → A/B/C v3 build
(PR #147) → G4/G5 instrument implementations. Facebook
mission verification remains owner-panel-blocked. The
14B partial download still awaits a resume/delete
decision.
