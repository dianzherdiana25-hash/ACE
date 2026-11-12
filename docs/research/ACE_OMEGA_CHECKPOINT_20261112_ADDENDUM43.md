# ACE Ω Checkpoint — Addendum 43 (G3 instrument: two convergent verifications, the C2 ruling, corrections applied)

Date: 2026-11-13 (Asia/Jakarta). Written directly on `main`.
Addendum 42 §2 pre-recorded the findings as accepted
correction work; this addendum closes them.

## 1. Two independent verifications, convergent

The G3 instrument build (PR #143, HEAD c839bba as
verified) was checked item-by-item under the bench's
Task 03 checklist by two independent posts:

- **Operations post (first checker): TAHAN**, with two
  findings — found independently, from its own E5 probe.
- **Bench room (second checker): TAHAN**, with the same
  two findings (its probes E1b and E5).

The findings, identical from both posts: (1) a
source-report identity mismatch was recorded twice in
`identity_mismatches` (the source report was checked in
both the C1 block and the family loop); (2) with two
valid positive families plus one extra invalid evaluation
entry, C2 printed FAIL while the overall was
TRANSFER_DEMONSTRATED — entry-level problems conflated
with requirement failure in the clause verdict. Outcomes
never exceeded valid evidence in any probe; both findings
were bookkeeping/semantics, not scoring errors.
Execution reruns at both posts matched exactly (g3 17 OK,
g1 8 OK, sweep 268 = 251 + 17 at verification time).

## 2. The coordinator's C2 semantics ruling (2026-11-13)

A clause verdict reflects whether the clause's
requirement is met by VALID evidence. When ≥2 valid
distinct family evaluations exist, C2 = PASS and extra
invalid entries are recorded as named WARNINGS, not a
clause FAIL; below 2, C2 = FAIL as before. Rationale
(coordinator's): a FAIL on a demonstrably satisfied
clause damages the instrument's readability — clauses
report satisfaction plus named missing items, and a
surplus invalid entry is not a missing item; the reverse
danger is already fenced, since effects count only from
valid families. The overall outcome must never exceed
valid evidence — that fence is unchanged.

## 3. Corrections applied (same branch, PR #143)

Two commits by Ian (Muse) on
`research/ace-omega-g3-instrument-20261113`, new HEAD
dde75ef:

1. The source report is now checked **once**; both the
   C1 block and the family loop reference that single
   check (the coordinator's ruled mechanism). A source
   mismatch is recorded exactly once.
2. Clause bookkeeping follows the ruling: entry-level
   problems are recorded under `warnings` on C2 and C3;
   `missing` holds only requirement-level failures, so
   verdict ⟺ missing-empty holds on every clause. The
   same split was applied to C3, which had the identical
   shape.

Regression tests added for both probes (E1b: mismatch
recorded once; E5: two valid positive families + one
invalid entry → C2 PASS, TRANSFER_DEMONSTRATED, entry
named as a warning). No outcome changes in any case:
19 g3 tests OK; lineage sweep 270 OK (17 skipped) =
251 + 19. Remote files sha256-verified against the local
build. The operations post re-verifies with the same
E1b/E5/E5b probes against the new HEAD. **G3 remains
NOT_ASSESSED** — an instrument, verified and corrected,
is still not an assessment.

## 4. Gate board (unchanged)

G0 session-scoped PASS. G1 MEASURED — DEMONSTRATED.
G2 MEASURED — null ×2. G3, G4, G5 NOT_ASSESSED.
OAIE unproven (`oaie_proven=false`).

## 5. Queue after this addendum

Local brain succession stage (bake-off preregistered,
protocol hash 7db0976460f85dd3…; download + verification
gate → runs → registry swap + 8B museum-izing only on a
pass) → A/B/C v3 design (strategy arms) → G3 application
preconditions (P1 refactor first; the pricing census from
the bench's Task 07 is on file for its preregistration)
→ G4/G5 instrument implementations. Facebook mission
verification remains owner-panel-blocked. The 14B partial
download still awaits a resume/delete decision.
