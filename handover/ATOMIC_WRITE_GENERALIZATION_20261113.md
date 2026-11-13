# CRASH-SAFE ATOMIC WRITING — GENERALIZATION (2026-11-13)

Built on hub feeding (2026-11-13 ~22:39 WIB) as the
generalization of the PR #181 hardening. One draft
PR; the pattern is identical everywhere: write a
temp file in the SAME directory, fsync, then
os.replace — a host death mid-write leaves the old
file or the new one, never a torn one. This VM
rebooted five times on 2026-11-13; the tear risk is
measured, not theoretical (Bake-off 02's aborted
launch #1 died in exactly this class of window).

## Audit (run-state / checkpoint / evidence writers)

ALREADY SAFE (named, not touched):
- abc_v3_run.py checkpoints + heartbeat — hardened
  in PR #181 (its final evidence write was still
  direct; converted in this package, see below).
- preaudit_validator v1/v2 — the lane's read-only
  design writes reports to a separate out-dir
  (PR #179/#185; different risk class, not a
  resumable-state writer).

CONVERTED in this package (15 files, 28 call sites;
helper `_atomic_write` inserted per file, every
`.write_text` state/evidence write replaced):
round2_gate_run.py (central save() + 6 evidence/
dossier writes), bakeoff02_a.py, bakeoff02_b.py,
bakeoff02_c.py, bakeoff02_finalize.py (rejection
ledger + result), bakeoff_a.py, bakeoff_b.py,
bakeoff_c.py (bake-off 01 harness), abc_v3_run.py
(final evidence write), dashboard_state_build.py
(the dashboard state producer the sandbox guard
uploads), regression_anchor.py (run artifacts),
inoculation_demo.py, ctrlreg_stage0_replay.py,
ctrlreg_stage1_counterfactual.py,
ctrlreg_stage2_dose.py.

NOT SWEPT (scope honesty): the many historical
one-shot probe scripts in the workspace root
(g1_*, omega*, b3_probe*, ...) — single-run probes
whose outputs are already sealed records; they hold
no resumable state and are not writers of any
living line. If one is ever revived as a driver, it
inherits this pattern first.

## Sealed-instrument care

No locked instrument's logic, parameters, or
already-written records were touched — only the
write LAYER of its harness. Bake-off 02's recorded
A result stands exactly as written by the pre-patch
code; B/C harnesses now write atomically when the
owner reopens them.

## Verification (evidence/atomic_write_generalization_verification.json)

Per writer (15/15 PASS): the extracted helper
round-trips a payload exactly; a planted torn temp
file leaves the real file intact; output bytes are
identical to the old write_text bytes for the same
payload. In situ: dashboard_state_build.py ran
end-to-end post-patch (6,082 bytes written).
Existing artifacts (round-2, both bake-offs, v3,
dashboard state) all still load — readers untouched,
old checkpoints load exactly.

— Ian, 2026-11-13.
