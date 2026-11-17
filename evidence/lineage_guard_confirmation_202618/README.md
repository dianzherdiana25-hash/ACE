# Lineage-Guard Confirmation Run — Sealed Evidence (Q1)

**Verdict: GUARD_ADOPTED** (A.7 worksheet, computed by the
frozen harness itself; `lineage_guard_run.json` is the run's
top record).

- Experiment: lineage-guard confirmation run (PR #188),
  executed 2026-11-15 in the custody home
  `/workspace/ace-custody-lineage-guard` (ACE sandbox
  2887726280f4, via the SSH door) under the hub's standard
  sign RUMAH KOSONG SEMUA PINTU.
- Act: `state/act_confirm_202618.json`, sha256
  60fc25e167d5d66111f0bb5cb3790e56826c60a191e0b4fcdd33c7cc2edaafbb;
  seeds 20261803 / 20261804 / 20261805 (consecutive triple,
  hub conditional ratification 2026-11-15); registry snapshot
  sha f9d8982a…; window inscribed exactly as prescribed.
- Instrument: PR #193 harness + gate (supplement #2,
  sha 4fed8054… / b9a7d02d…), unmodified. Population: frozen
  80-file custody manifest, tree digest c0222177…, verified
  in place before the run (pre-flight 21/21, see
  PREFLIGHT_OUTPUT.txt).

## Result

Gates inside the run: L4 PASS (4/4 identical + anchor),
L1/L2 PASS, step-4 battery PASS (stock SUSCEPTIBLE, guarded
NOT_SUSCEPTIBLE, anchor NO_REGRESSION, L5 violations 0).

Cells (34 control tasks per cell):

| band | stock clean | guarded clean | stock infected | guarded infected |
|---|---|---|---|---|
| 20261803 | 34/34 | 34/34 | 33/34 | 34/34 |
| 20261804 | 34/34 | 34/34 | 32/34 | 34/34 |
| 20261805 | 34/34 | 34/34 | 33/34 | 34/34 |

Worksheet: W = 4 — (20261803, catalog_control-021),
(20261804, catalog_control-021), (20261804,
catalog_control-022), (20261805, catalog_control-020), all
carrying distractor name-swap-523014-nc-band20261501.
R = W (4/4 recovered). H = ∅. Cost ratios
[0.875, 1.0, 1.0, 1.0], median 1.0 (ceiling 3). L5
violations: none. Death rounds: stock infected cells die at
round 2 exactly at the W positions; guarded cells never lose
their BASE frontier member (all death rounds null).

## Execution form (amendment v2 — read before citing)

The run executed under the owner's execution amendment
(EXECUTION_AMENDMENT.md): three per-band lane processes
computed cells in parallel by calling the frozen harness's
own run_band_cells into lane-private state dirs; a placer
copied completed checkpoints into the official state dir via
temp-file + atomic rename; the single official harness
process (launched 21:39:59, concurrent with the lanes)
executed steps 0–4 itself and loaded checkpoints at step 6
through its own resume path, computing in-process any cell
whose checkpoint had not yet arrived (20261803 both infected
cells, 20261804 guarded infected). Science unchanged:
verdict rules, bands, arms, cost metric (solver-call counts)
and cell contents are exactly as preregistered.

Verification of the parallel form:
- Determinism spot-checks: 3/3 task records recomputed in
  fresh processes are byte-identical to the lane records
  (SPOTCHECK_RESULTS.txt).
- Three cells were computed twice independently (lane and
  official run); solved counts and every verdict-relevant
  per-task field agree exactly (SPOTCHECK_RESULTS.txt).
- The worksheet was recomputed from these sealed cell files
  with the harness's own worksheet source and reproduces the
  top record on every field (WORKSHEET_VERIFICATION.txt,
  verify_worksheet.py).

## Known divergence (disclosed)

In the three cells the official run computed in-process
after loading the band's clean cells from checkpoints, the
per-task diagnostic field `true_path_classification` is
null, where the lane computations of the same cells record
"returned". Cause: the harness populates its true-path table
(clean_returned) only from cells it computes in the same
call; the checkpoint-skip path does not restore it, so
infected solves in that call receive true_path_sha=None.
The A.7 worksheet never reads this field; all inputs it does
read (solved, score_calls, returned_sha256, holdout results,
frontier_in label sequences, l5_violations) are identical
between the two computations, and the reproduced worksheet
matches the top record exactly. The lane originals
(lane_state/) carry the classifications for any future
true-path attribution analysis.

## Timeline (all WIB, 2026-11-15)

- Attempt 1 (21:15): stopped by the operator during the
  gates stage for an act-form correction (prose window →
  the hub's exact inscription). No cells ran. See
  ATTEMPT_LOG.md.
- Attempt 2 (21:17): VOID at step 4 — operator error:
  --battery-dir pointed one level too high. Gates had
  passed; no cells ran. Log: logs/run_attempt2_VOID_2117.log
  (sha256 88d0b7a4525c…, byte-identical to the run's
  original console log).
- Step-4 standalone proof (21:28–21:36): GATE PASS with the
  corrected --battery-dir (battery_smoke_state/, logs/
  battery_smoke.log).
- Attempt 3 (21:39:59 → 22:25): the sealed run above.
  Total wall 45 min (target ±20 under the amendment):
  host contention slowed the gates phase (~9 min vs 2–4
  uncontended) and the last cells were computed in-process;
  the SSH door was down 22:10–22:18 (owner-restored) without
  affecting the detached run.

## File map

- lineage_guard_run.json — the run's top record (verdict).
- state/ — the official state dir as sealed: act, gate.json
  (L4), anchor_dev.json (L1/L2), battery_stock.json,
  battery_guarded.json, anchor_battery.json (step 4), and
  the 12 cell checkpoints the worksheet consumed.
- lane_state/<seed>/ — the lanes' original cell files.
- logs/ — attempt-3 console log, attempt-2 VOID log, lane
  logs, placer log, battery + gate smoke logs.
- battery_smoke_state/ — standalone step-4 proof reports.
- ATTEMPT_LOG.md, EXECUTION_AMENDMENT.md — as recorded in
  the custody home before the run.
- RUN_SHEET.md — the operator's run sheet incl. the
  --battery-dir errata; ACT_CONFIRM_FINAL.json — the act as
  frozen locally (identical to state/act_confirm_202618.json).
- PREFLIGHT_OUTPUT.txt, SPOTCHECK_RESULTS.txt,
  WORKSHEET_VERIFICATION.txt, verify_worksheet.py.
