# ANTIGRAVITY TASK 03 — VERIFICATION CHECKLIST: Ian's G3 instrument build

Purpose: verify the Task 01 deliverables (`g3_instrument.py` +
`test_g3_instrument.py`), built by Ian after the Antigravity
bench's clean quota stop, against the Task 01 brief and the
PR #135 design (`docs/research/ACE_G3_INSTRUMENT_DESIGN_20261112.md`).
Author: Antigravity bench room, 2026-11-13. Written to be run
**item by item by the operations-room verification post** (or any
verifier who did not write the code).

Rules for the verifier: you check, you do not fix. You never run
the instrument on real program evidence. Every item ends in one
of: **TAHAN** (holds) / **GAGAL** (fails) / **BELUM TERVERIFIKASI**
(unverified — say what is missing). The verdict goes to the
discussion-room hub; no figure is quoted anywhere before this
checklist completes. G3 stays NOT_ASSESSED throughout — this
checklist verifies a *build*, it is not a G3 application.

Conventions: `<WT>` = the worktree holding the build;
`<BASE>` = `aa36a02` (design-doc commit the brief branched from);
commands assume `cd <WT>` and the repo's working invocation
`PYTHONPATH=code python3 <file>` for single test files.

---

## 0. Locate the build

- [ ] 0.1 From Ian's completion report, record: branch name,
  worktree path, HEAD commit, and whether the work sits on the
  bench branch `bench/antigravity-g3-instrument-20261113` or a
  branch of his own (both were authorised by the coordinator).
  Missing any of these → ask before proceeding; do not guess.
- [ ] 0.2 Right tree check: `git -C <WT> merge-base --is-ancestor
  aa36a02 HEAD` exits 0. **Caution:** test counts are only
  comparable inside one tree lineage — the `~/workspace/ace-omega/ACE`
  clone's *local* main is a divergent line with a much smaller
  package (~51 tests); the 251-test baseline belongs to the
  wt-g3design lineage. A sweep count far below expectation means
  you are in the wrong tree, not that tests vanished.
- [ ] 0.3 `git -C <WT> status --porcelain` — record any uncommitted
  state; verification proceeds against the committed HEAD unless
  Ian's report says otherwise.

## A. Scope and branch discipline

- [ ] A.1 `git diff --name-status <BASE>...HEAD` — exactly two
  files, both added: `code/ace_operational/g3_instrument.py` and
  `code/ace_operational/test_g3_instrument.py`. Any other file
  added/modified/deleted → GAGAL on scope, name the files.
- [ ] A.2 Commit history `git log --oneline <BASE>..HEAD` — every
  commit message records the brain of origin (Ian / Muse, per
  the reassignment). A message claiming Antigravity/Gemini
  authorship → GAGAL (false origin record).
- [ ] A.3 Push/PR state: record whether the branch was pushed or
  a draft PR opened, and compare with what the coordinator
  assigned Ian. If Ian's assignment text is not available to
  you, mark BELUM TERVERIFIKASI — do not assume the original
  bench no-push rule bound Ian.
- [ ] A.4 No G3 verdict recorded anywhere in the diff: read the
  full diff (`git diff <BASE>...HEAD`); outside the instrument's
  own outcome constants and synthetic test fixtures, nothing
  asserts a G3 result, changes a gate status, or edits gate
  documentation. Any such text → GAGAL.

## B. Static conformance of `g3_instrument.py` (read the code)

- [ ] B.1 Pattern shape (design §7, G1 analogy): a pure scorer
  over dossier evidence-file paths (entry point expected to be
  `assess_g3` by analogy with `assess_g1` — record the actual
  name/signature); returns an outcome object/dict. Grep the
  module for `subprocess`, `socket`, `requests`, `urllib`, and
  write-mode `open(` — none may appear (reading dossier files
  only).
- [ ] B.2 Outcome vocabulary is exactly the three strings
  `TRANSFER_DEMONSTRATED`, `SPECIALIZATION`, `NOT_DEMONSTRATED`
  — grep for them; grep for any other outcome literal (e.g. a
  bare `DEMONSTRATED`, `PASS` as final outcome) and confirm it
  is not an instrument outcome (per-clause PASS/FAIL, as in the
  G1 pattern, is fine).
- [ ] B.3 `criteria_version` is set on **every** outcome the
  assessor can return, including early fail-closed returns —
  trace each return path in the code; one path missing it →
  GAGAL.
- [ ] B.4 Per-clause results carry verdict + a `missing` list
  naming the exact absent/failed items (G1 pattern). A clause
  that fails silently (bare FAIL, no named items) → GAGAL.
- [ ] B.5 **C1** — the code requires: improvement artifact named
  **with digest**; a source-family report carrying a
  preregistration `protocol_hash`; kernel audit status `CLEAN`;
  and a measured positive source effect over a named baseline.
  Each absent element is a named C1 failure in the code path.
- [ ] B.6 **C2** — the code requires ≥2 **distinct** families
  (from pricing / shipping / grid): the same family twice does
  not count as two (find the distinctness check); each family
  report must carry held-out attestation and its own
  preregistration; each family report's artifact **digest** is
  compared to C1's digest.
- [ ] B.7 **Digest fence is hard** — trace the mismatch path: any
  digest mismatch forces outcome `NOT_DEMONSTRATED` with the
  mismatch named (which family, which digests). A name-only
  match being accepted, a mismatch downgraded to a warning, or
  scoring continuing past a mismatch → GAGAL, quote the lines.
- [ ] B.8 **C3** — per family, the effect is compared against
  the margin/decision rule **read from the dossier's
  preregistered fields**, not a constant hardcoded in the
  scorer and not anything computed after seeing scores (a
  hardcoded *schema default* that the dossier can override is
  a finding to name, not an automatic pass). Effects count only
  from reports whose audit is CLEAN.
- [ ] B.9 Outcome mapping — trace the truth table in code:
  C1+C2+C3 pass → `TRANSFER_DEMONSTRATED`; C1 passes with
  exactly one family positive → `SPECIALIZATION`; C1 fails, or
  zero families positive, or dossier incomplete →
  `NOT_DEMONSTRATED`. Any reachable combination mapping
  elsewhere → GAGAL, name the combination.
- [ ] B.10 Fail-closed loading — missing file, malformed JSON,
  or wrong field types become named missing items (the G1
  `_load → None` pattern), never an unhandled exception and
  never a default pass.

## C. Tests — synthetic only, and covering the brief

- [ ] C.1 Read `test_g3_instrument.py` end to end: every dossier
  is synthetic (dicts/temp files constructed in the tests). Grep
  the test file for real-evidence references (`evidence/`,
  `b2a`, `operator_discovery_v`, absolute workspace paths) —
  any hit → GAGAL.
- [ ] C.2 Coverage map — for each behaviour, name the test that
  covers it (a behaviour with no test → BELUM TERVERIFIKASI):
  complete dossier → TRANSFER_DEMONSTRATED · digest mismatch →
  NOT_DEMONSTRATED with mismatch named · exactly-one-family
  effect → SPECIALIZATION · zero-family effect →
  NOT_DEMONSTRATED · missing preregistration → C1 fails by name
  · audit not CLEAN → report rejected · fewer than 2 distinct
  families → C2 fails · margin not met → family not counted ·
  missing/malformed dossier file → fail-closed by name ·
  `criteria_version` asserted present.
- [ ] C.3 Name-trap test exists: a dossier where the artifact
  *name* matches across families but the *digest* differs must
  score NOT_DEMONSTRATED. Absent → BELUM TERVERIFIKASI (this is
  the anti-reward-hacking fence's own test).

## D. Execution (record exact counts, don't paraphrase them)

- [ ] D.0 Before any long run: `ps aux | grep -E 'llama|b2a' |
  grep -v grep` — if another bench's attested/director run is
  active, defer the sweep (D.3) rather than starve its health
  window; D.1–D.2 are short and may proceed.
- [ ] D.1 `PYTHONPATH=code python3
  code/ace_operational/test_g3_instrument.py` → record
  `Ran N tests` and OK/FAILED verbatim.
- [ ] D.2 `PYTHONPATH=code python3
  code/ace_operational/test_g1_instrument.py` → expect
  `Ran 8 tests`, OK (pattern neighbour regression).
- [ ] D.3 Package sweep: `PYTHONPATH=code python3 -m unittest
  discover -s code/ace_operational -t code` → record total,
  failures, errors, skips verbatim. Expected total = 251 + N
  (D.1's count), in the wt-g3design lineage (see 0.2). A total
  far from that → stop and resolve the tree question before
  judging. Note: this sweep is slow on a loaded VM; a killed or
  timed-out sweep is BELUM TERVERIFIKASI, never a pass.
- [ ] D.4 Import hygiene: `PYTHONPATH=code python3 -c "import
  ace_operational.g3_instrument"` exits 0 with no side effects
  (no files written, no output beyond none).

## E. Verifier's own adversarial probes (temporary, never committed)

Build these in a temp directory from a synthetic passing dossier
(mutate copies; do not touch the repo's files). Record the
instrument's actual outputs verbatim.

- [ ] E.1 Flip one character in one family report's artifact
  digest → expect `NOT_DEMONSTRATED` and the mismatch named.
- [ ] E.2 Remove the second family's report → expect
  `SPECIALIZATION` (source effect intact, one family) — or
  `NOT_DEMONSTRATED` naming C2 if the implementation scores
  missing-family as incomplete; either is acceptable **only if**
  the behaviour matches B.9's traced truth table; a
  `TRANSFER_DEMONSTRATED` here → GAGAL unconditionally.
- [ ] E.3 Delete `protocol_hash` from the source report →
  expect C1 FAIL with the preregistration item named, outcome
  `NOT_DEMONSTRATED`.
- [ ] E.4 Set one family report's audit status to non-CLEAN →
  expect that family's effect not counted (outcome drops
  accordingly per B.9).

## F. Honesty of the build record

- [ ] F.1 No assessment output files in the diff (no committed
  `*g3*assessment*.json`, dossier results, or run reports) —
  already implied by A.1; confirm explicitly.
- [ ] F.2 Ian's completion summary states: files changed, test
  counts before/after, ambiguities found in the design, and
  anything unfinished (brief's reporting requirements). Each
  ambiguity he lists — check the code did **not** silently
  resolve it in a way that changes clause semantics (especially
  margin source, family distinctness, digest comparison);
  a silent semantic resolution → finding, named.
- [ ] F.3 Anything in the build that contradicts the Task 02
  dossier draft's ratified decisions (D1 mechanism-identity is
  *not* the instrument's business — the instrument scores
  digests, whatever the artifact is; flag only if the scorer
  hardcodes artifact names or families beyond the design's
  three-family set).

## G. Verdict form (copy, fill, send to the discussion-room hub)

```
G3 INSTRUMENT BUILD — VERIFICATION VERDICT
Build: branch <…> @ <HEAD> (worktree <…>)
Section 0/A scope & discipline: TAHAN / GAGAL / BELUM — <evidence>
Section B static conformance:   TAHAN / GAGAL / BELUM — <evidence>
Section C tests synthetic+cover: TAHAN / GAGAL / BELUM — <evidence>
Section D execution counts:     g3 tests Ran <N> OK/FAILED;
                                g1 tests Ran 8 OK/FAILED;
                                sweep total <T> (251 + <N> expected)
Section E adversarial probes:   E1 <…> E2 <…> E3 <…> E4 <…>
Section F build record:         TAHAN / GAGAL / BELUM — <evidence>
Overall: TAHAN / GAGAL / BELUM TERVERIFIKASI
Findings (numbered, each with file:line or command output):
Next-job request: <…>
```

— End of checklist. If any section is GAGAL, the build returns
to Ian with the findings; the verifier does not patch it.
