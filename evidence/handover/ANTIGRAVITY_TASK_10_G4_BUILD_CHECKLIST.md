# ANTIGRAVITY TASK 10b — VERIFICATION CHECKLIST: G4 INSTRUMENT BUILD

For the two independent checkers of the build specified in
`ANTIGRAVITY_TASK_10_G4_BUILD_BRIEF.md` — operations post
(first checker), Antigravity bench (second checker), the
pattern adopted for the G3 instrument. Every item is checked
against the actual build on disk and by the checker's own
runs, never from the builder's report alone. Record per item:
PASS / FAIL / NOT VERIFIED, with the command or file evidence.

---

## Section 0 — Tree, branch, baseline

- [ ] 0.1 Worktree and branch identified from disk; HEAD
      recorded. Base commit matches the brief's requirement:
      the tree contains the current (post-P3)
      `g3_instrument.py`.
- [ ] 0.2 Builder's recorded baseline (pre-build
      ace_operational discover sweep on the untouched base)
      is present in the PR body and plausible vs the program
      baseline — the right-tree caution applies: a sweep far
  below expectation means the wrong tree; stop and report.
- [ ] 0.3 Builder's brain-of-origin is recorded in the PR
      body.

## Section A — Scope of the diff

- [ ] A.1 Diff vs base = exactly two files:
      `code/ace_operational/g4_instrument.py` and
      `code/ace_operational/test_g4_instrument.py`.
- [ ] A.2 No other file modified, added, or deleted
      (including evidence files, archives, checkpoint).
- [ ] A.3 No live dossier assembled, no live archive or run
      touched, no text anywhere in the diff claims a G4
      verdict; the PR states G4 remains NOT_ASSESSED.

## Section B — Interface and pattern conformance

- [ ] B.1 `assess_g4(*, dossier=...)` exists; pure function:
      reads JSON under the dossier directory only, no writes,
      no network, no clock-dependent behaviour.
- [ ] B.2 `CRITERIA_VERSION` defined; the returned dict
      carries `gate`, `criteria_version`, `overall`,
      `clauses`, `identity_mismatches`.
- [ ] B.3 Single construction point: trace every return path
      (including all error paths) — each passes through the
      one assessment construction, so `criteria_version` and
      the clause structure appear on **every** outcome.
- [ ] B.4 Outcome vocabulary is exactly
      `INHERITANCE_DEMONSTRATED` / `LINEAGE_ONLY` /
      `NOT_DEMONSTRATED`; clause verdicts exactly PASS/FAIL;
      failures always named in `missing`, warnings in
      `warnings`.
- [ ] B.5 Style mirrors `g3_instrument.py` (loader, numeric
      guards, label conventions) — deviations listed and
      justified, or none.

## Section C — Clause semantics (trace each in the code)

- [ ] C.1 C1 checks, each traced to a named failure:
      lineage present · predecessor/successor ids present ·
      successor's parents include predecessor · capability
      digest attached · `archive_audit == CLEAN` ·
      `chain_valid is true`.
- [ ] C.2 C2 checks: capability record present · digest
      present · discovery record present · admission evidence
      non-empty · digest equality is the identity test (name
      equality alone never passes — trace the comparison).
- [ ] C.3 C3 checks: evaluation present · protocol hash
      present · audit CLEAN · successor id equals lineage
      successor · `discovery_invoked` must be exactly false ·
      loaded digest equals capability digest · capability
      `n ≥ min_capability_tasks` · both arms present.
- [ ] C.4 All four effect conditions computed and named
      separately: Δ ≥ `margin_pp` · with-fraction ≥
      `with_floor` · without-fraction ≤ `without_ceiling` ·
      control with ≥ control without.
- [ ] C.5 Thresholds are read from the evaluation report;
      grep the scorer: no hard-coded 20 / 0.25 / 0.10 / 40
      (or equivalents) anywhere in the effect logic; a
      missing threshold is a named failure, never defaulted.
- [ ] C.6 Outcome table implemented exactly as brief §7,
      including: C3 FAIL with C1/C2 PASS → `LINEAGE_ONLY`
      (never `NOT_DEMONSTRATED`); C1 or C2 FAIL →
      `NOT_DEMONSTRATED`.

## Section D — Digest fence and the two lessons

- [ ] D.1 Hard fence traced: any digest inequality among
      {capability, discovery record, loaded} forces overall
      `NOT_DEMONSTRATED` with the mismatch named — including
      when C1 passes (a stored lineage of the *wrong*
      artifact is not `LINEAGE_ONLY`).
- [ ] D.2 Lesson 1 (check once): the capability identity
      check executes at one code site; C2 and C3 consume its
      result. Probe E5 (below) must show the mismatch named
      exactly once across the assessment's failure lists.
- [ ] D.3 Lesson 2 (verdict = requirement met by valid
      evidence): superseded/extra invalid entries degrade to
      `warnings` and cannot flip a clause whose requirement
      is met by the valid entries; they flip it when it is
      not. Trace the code path; probe E6 confirms.

## Section E — Verifier probes (run by the checker, not read from the builder's tests)

Build minimal synthetic dossiers in a scratch directory and
run `assess_g4` on each; record actual outputs.

- [ ] E.1 Happy path: complete dossier → expect
      `INHERITANCE_DEMONSTRATED`, all clauses PASS.
- [ ] E.2 Broken chain: `chain_valid=false` → C1 FAIL,
      `NOT_DEMONSTRATED`, failure named.
- [ ] E.3 Re-discovering successor: `discovery_invoked=true`
      → C3 FAIL by name, overall `LINEAGE_ONLY`.
- [ ] E.4 Missing control arm: without-arm fields removed →
      C3 FAIL (`control_arm_missing` or equivalent name),
      overall `LINEAGE_ONLY`.
- [ ] E.5 Name trap + fence: discovery record digest altered
      (name unchanged) → C2 FAIL, hard fence,
      `NOT_DEMONSTRATED`, mismatch named **exactly once**.
- [ ] E.6 Attribution ceiling: without-arm solves above
      ceiling with a large Δ → C3 FAIL by name
      (`LINEAGE_ONLY`) — inheritance must NOT be claimed.
- [ ] E.7 Loaded-artifact swap: `artifact_digest_loaded`
      altered → hard fence, `NOT_DEMONSTRATED`.
- [ ] E.8 `dossier=None` and malformed-JSON dossier → named
      `NOT_DEMONSTRATED`, no exception raised.

## Section F — Test suite and regression

- [ ] F.1 All ~20 brief-required tests (§8) are present by
      name/intent and assert the outcome **and** the named
      failure, not merely the outcome.
- [ ] F.2 Checker runs `test_g4_instrument.py` directly
      (`PYTHONPATH=code python3
      code/ace_operational/test_g4_instrument.py`): all OK.
- [ ] F.3 Checker runs `test_g1_instrument.py` and
      `test_g3_instrument.py`: still OK (pattern neighbours
      untouched).
- [ ] F.4 Full ace_operational discover sweep: after-count =
      builder's baseline + new tests; skips match the
      baseline's skip profile; runtime recorded.

## Section G — Verdict (each checker files independently)

```
Build under check: <branch> @ <head>
Checker: <operations post | antigravity bench> (independent)
Overall: TAHAN / GAGAL / BELUM TERVERIFIKASI
Findings: <numbered; each with section ref + evidence>
Counts re-measured: baseline <n> → after <n>; g4 tests <n> OK
```

TAHAN requires: Sections 0–F pass, probes E1–E8 all behave
as specified, and no finding above minor. Any hard-fence,
default-threshold, or single-construction violation is
automatically GAGAL, not minor.

— End of checklist.
