# ACE Resume Drill & G1 Criteria v2 — 2026-11-12 (Stage J)

## The closing experiment

Stage H's instrument passed G1 with a written qualification: C3
evidenced the resume capability of the substrate, not an
interruption of the flagship run itself. The closing experiment
it named is this drill.

Design: the flagship director operation runs in a dedicated OS
process (attested Qwen3-8B server, its own agenda + cognitive
memory). Cycle 1 completes; cycle 2 begins; when a marker file
proves generation is in flight, the orchestrator SIGKILLs the
whole process group mid-work. A fresh process then verifies the
surviving state and resumes the same operation to its report.

## Result — RESUME_DRILL_PASS

- Exactly 1 cycle survived the kill; the interrupted cycle left
  no partial record; the memory hash chain verified immediately
  after the kill.
- The resumed process completed the interrupted cycle as cycle
  #2, status accepted (5 proposals, 338 s), then cycle 3
  (accepted, 4 proposals, 244 s). Final numbering 1-2-3 gapless;
  memory chain OK at the end.
- Drill cycle 1 was validator-rejected (the model's reply failed
  the citation schema). Recorded plainly: the drill measures
  continuity of state and operation, not proposal quality; the
  rejected cycle is itself a complete, valid record.

Incidents, recorded: the harness VM restarted mid-drill and
killed the first phase-2 attempt before it produced anything;
its re-run hit a stale port-bind from the killed server, then a
cold-cache model load that exceeded the server health window.
The drill state was untouched by all three failures — phase 2 is
verify-then-resume by construction, and was simply run again.
(Unplanned, but on-theme: the drill's own harness survived an
interruption by the same pattern the drill measures.)

## Instrument criteria v2

The v1 instrument scored the drill record NOT_DEMONSTRATED for
two vocabulary reasons: its verdict string is
`RESUME_DRILL_PASS`, not `PASS`, and its checkpoint carries
cycle state, not a `step` field. The criteria encoded one
record's field names instead of the PRD clause — the same class
of mis-specification the OMEGA-10 amendment corrected.

Criteria v2 therefore teaches C3 two evidence species:
`substrate_probe` (the v1 shape, unchanged, keeps the
qualification) and `flagship_interruption` (an `interruption`
block evidencing mid-work kill, post-kill state integrity,
separate-process resumption, final report reached, and record
continuity; lifts the qualification). The assessment output now
carries `criteria_version`. The full sequence — drill PASS,
instrument v1 FAIL with named reasons, amendment rationale,
instrument v2 verdict — is the record; nothing was silently
re-scored.

Re-assessment (dossier: pilot-abc-v1 report + the drill record
projected programmatically from the sealed drill report):
C1 PASS, C2 PASS, C3 PASS via flagship_interruption,
overall DEMONSTRATED, qualification: none.

## Director's gate decision

**G1 — MEASURED: DEMONSTRATED, unqualified.** The PRD clause —
one digital experiment from task to report, complete records,
resume after interruption — is now evidenced at the flagship
level: the interruption was real, mid-work, and survived by the
run's own state.

Gate board: G0 PASS (session-scoped) · G1 DEMONSTRATED
(unqualified) · G2 MEASURED-null ×2 · G3–G5 NOT_ASSESSED ·
OAIE unproven.
