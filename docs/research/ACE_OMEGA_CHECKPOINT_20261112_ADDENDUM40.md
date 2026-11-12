# ACE Ω Checkpoint — Addendum 40 (G3 instrument built by Ian)

Date: 2026-11-13 (Asia/Jakarta). Written directly on `main`.

## 1. The build (draft PR #143, stacked on PR #135's design branch)

`ace_operational/g3_instrument.py` + its tests, built by
Ian (Claude-class) under the Addendum 38 §3 reassignment
(the Antigravity bench stopped clean on its Gemini quota
before writing any file; commit messages record the brain
of origin accordingly). Build lineage: branch
`research/ace-omega-g3-instrument-20261113` from aa36a02
(the design tip), HEAD c839bba; the diff against aa36a02
is exactly the two files. The remote branch was created
by the snapshot push mechanism over current main, so
GitHub's web diff looks larger than the build; the two
files are sha256-identical to the verified local build,
and verification runs against the local lineage per the
bench's Task 03 checklist.

`assess_g3` is a pure scorer over a dossier of sealed
report files (schema in the module docstring), following
the G1 instrument's pattern: fail-closed loading, per-
clause verdicts with named missing items, and
`criteria_version` on every outcome (single construction
point). Clauses implement the PR #135 design: C1
identified improvement (name + digest) with an audited,
preregistered, positive source effect; C2 the same
artifact evaluated held-out in ≥2 distinct families
(pricing / shipping / grid); C3 per-family effects
counted against the margin read from each family's own
preregistered report — never hardcoded in the scorer.
The identity fence is hard: any name/digest mismatch in
any report forces NOT_DEMONSTRATED with the mismatch
named. Outcome vocabulary is exactly the design's three
strings.

Design interpretations, stated openly for the verifiers
(not silently resolved): (a) C1's "positive effect" reads
as improvement score strictly above baseline; the margin
rule belongs to C3, where the design places it. (b) The
source report doubles as a family evaluation — if held
out and margined, the source family can be one of the
two families C3 counts. (c) The family set is the
design's current three; an unknown family name is a
named C2 failure.

Tests: 17 synthetic tests OK, including the name-trap
test (artifact name matches across families, digest
differs → NOT_DEMONSTRATED) and the checklist's probe
shapes E1–E4 in test form. Sweep on this lineage: 268
tests OK (17 skipped) = the 251 baseline + 17; the G1
neighbour's 8 tests still pass. Verification of this
build runs next under the Task 03 checklist — operations
post first, bench room second (Section G form). **No G3
verdict is asserted; G3 remains NOT_ASSESSED.**

## 2. Toward the first G3 application (no run authorized)

The bench's Task 02 dossier draft was ratified by the
coordinator as DESIGN decisions D1–D6 (2026-11-13 ~00:55
WIB; ratification is not a preregistration). Its
preconditions stand: P1 decouple `run_discovery` from the
grid family (a design note exists as the bench's Task 04;
no code changed), P2 a pricing adapter, P3 schema match
against §1's instrument (now satisfiable — the schema
exists), P4 pricing anti-saturation calibration. The
preregistration text is drafted only after P1's refactor
shape is settled. None of this is in the current queue
slot; it follows the KBM pilot design package.

## 3. Gate board (unchanged)

G0 session-scoped PASS. G1 MEASURED — DEMONSTRATED.
G2 MEASURED — null ×2. G3, G4, G5 NOT_ASSESSED (G3 now has
a built instrument; an instrument is not an assessment).
OAIE unproven (`oaie_proven=false`).

## 4. Queue after this addendum

KBM pilot design package (separate work, privacy rule
applied) → services demand test → A/B/C v3 design
(strategy arms) → G3 application preconditions (P1
refactor first) and preregistration drafting → G4/G5
instrument implementations. Facebook mission verification
remains blocked on the owner showing the mission panel.
The 14B partial download still awaits a resume/delete
decision; no action taken.
