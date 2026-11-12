# ACE Ω Checkpoint — Addendum 32 (Stage J: resume drill; G1 unqualified; Emancipation amendment recorded)

Date: 2026-11-12 (Asia/Jakarta). Stack tip: PR #133
(branch `research/ace-omega-resume-drill-20261112`, stacked on
#132). Full sweep on the stage branch: **251 tests OK** (17 skips
without the sandbox env flag). Design/results document:
`docs/research/ACE_RESUME_DRILL_20261112.md` (PR #133).

## 1. The resume drill — RESUME_DRILL_PASS

The closing experiment named by Addendum 30 was executed. The
flagship director operation (attested Qwen3-8B, own agenda +
cognitive memory) ran in a dedicated process: cycle 1 completed;
cycle 2 began; a marker file proving generation was in flight
triggered a SIGKILL of the whole process group mid-work. A fresh
process verified the surviving state and resumed the same
operation to its report:

- 1 cycle survived; the interrupted cycle left **no partial
  record**; the memory hash chain verified **immediately after
  the kill**.
- The resumed process completed the interrupted cycle as cycle
  **#2, accepted, 5 proposals** (338 s), then cycle 3 (accepted,
  4 proposals, 244 s). Numbering 1-2-3 gapless; chain OK at the
  end.
- Drill cycle 1 was validator-rejected (citation schema) —
  recorded plainly; the drill measures continuity, not proposal
  quality, and a rejected cycle is a complete record.

Incidents, recorded in the design document: the harness VM
restarted mid-drill and killed the first phase-2 attempt; its
re-run hit a stale port bind, then a cold-cache load exceeding
the server health window. Drill state was untouched throughout;
phase 2 is verify-then-resume by construction and was re-run.

## 2. Instrument criteria v2 and the gate decision

The v1 instrument scored the drill dossier NOT_DEMONSTRATED for
two vocabulary reasons (verdict string `RESUME_DRILL_PASS` ≠
`PASS`; checkpoint carries cycle state, not a `step` field).
Criteria must encode the PRD clause, not one record's field
names — the OMEGA-10 amendment pattern. Criteria v2 (PR #133)
teaches C3 two species: `substrate_probe` (v1 shape unchanged;
keeps the qualification) and `flagship_interruption`
(mid-work kill, post-kill integrity, separate-process
resumption, final report, record continuity; lifts the
qualification). Assessments now carry `criteria_version`. The
sequence — drill PASS, v1 FAIL with named reasons, amendment
rationale, v2 verdict — is the public record.

Re-assessment (criteria v2; pilot-abc-v1 + drill record
projected programmatically from the sealed drill report):
C1 PASS, C2 PASS, C3 PASS via flagship_interruption.

**Director's gate decision: G1 — MEASURED: DEMONSTRATED,
unqualified.** The qualification recorded in Addendum 30 is
lifted. Gate board: G0 PASS (session-scoped) · **G1
DEMONSTRATED (unqualified)** · G2 MEASURED-null ×2 · G3–G5
NOT_ASSESSED · OAIE unproven (`oaie_proven=false`).

## 3. Direction amendment — "Emansipasi" (owner, 2026-11-12 evening)

Recorded here as an official amendment in the checkpoint
lineage, per the owner's instruction from the discussion room.
The owner withdrew the assumption that ACE's budget and
decisions rest with the owner: ACE itself is to decide, act,
and manage — including its finances; the owner steps back to
receiving progress and usefulness reports. Substance and
treatment:

1. The "owner-reserved" categories (merges to main, spending,
   publication) are **revoked as program direction**. Such
   decisions become the authority of ACE's own governance
   mechanisms (director cycles, evidence gates, hash-chained
   ledger). What reaches the owner is reports — results and
   the reasoning behind decisions taken — not approval queues.
   Stages are no longer held waiting for owner decisions.
2. The self-funding design study's premise is **reversed**:
   from owner-signs/owns to ACE-decides/manages under its own
   governance. The study is revised under the new premise at
   its next design stage.
3. Capacity honesty is unchanged and mandatory: this amendment
   changes **governance, not physical capability**. ACE today
   has no money rails and is not a legal person; accounts and
   contracts require a legal person, and the design must answer
   the legal-shell question explicitly. Financial capability is
   built in stages and measured like every other capability
   (gates, limit envelopes, hash-chained ledger, reports). No
   real-money action occurs before the mechanism exists and is
   measured — because the capability does not exist yet, not
   because permission is awaited.
4. Program direction is strengthened toward maximal ACE
   independence (decisions, management, environmental
   continuity); the program director's role shifts toward
   observer-reporter to the owner.

Nothing in this addendum executes a merge, a payment, or a
publication; it records the governance under which future
stages will decide and report.
