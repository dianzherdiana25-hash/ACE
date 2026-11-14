# ANTIGRAVITY TASK 12b — VERIFICATION CHECKLIST: G5 INSTRUMENT BUILD

For the two independent checkers of the build specified in
`ANTIGRAVITY_TASK_12_G5_BUILD_BRIEF.md` — operations post
(first checker), Antigravity bench (second checker), the
adopted pattern. Every item is checked against the build on
disk and the checker's own runs, never the builder's report
alone. Record per item: PASS / FAIL / NOT VERIFIED, with
evidence.

---

## Section 0 — Tree, branch, baseline

- [ ] 0.1 Worktree, branch, HEAD recorded from disk; base
      tree contains the current `g3_instrument.py` (and
      `g4_instrument.py` if landed).
- [ ] 0.2 Builder's recorded pre-build sweep baseline present
      in the PR body and plausible (right-tree caution: a
      sweep far below the program baseline = wrong tree;
      stop and report).
- [ ] 0.3 Builder's brain-of-origin recorded in the PR body.

## Section A — Scope of the diff

- [ ] A.1 Diff vs base = exactly two files:
      `code/ace_operational/g5_instrument.py` and
      `code/ace_operational/test_g5_instrument.py`.
- [ ] A.2 No other file changed (including evidence, harvest
      data, checkpoint files).
- [ ] A.3 No live harvest performed or scored; test fixtures
      contain **no real chat content** (invented summaries and
      invented owner messages only — inspect the fixtures);
      the PR states G5 remains NOT_ASSESSED.

## Section B — Interface and pattern conformance

- [ ] B.1 `assess_g5(*, dossier=...)`; pure: reads JSON under
      the dossier dir only; no writes, no network, no clock.
      Critically: nothing in the module reads live chats,
      message stores, or any path outside the dossier.
- [ ] B.2 Returned dict carries `gate`, `criteria_version`,
      `overall`, `clauses`, `integrity_failures` on every
      path.
- [ ] B.3 Single construction point traced across all return
      paths, including error paths.
- [ ] B.4 Vocabulary exactly `ACCESS_DEMONSTRATED` /
      `DELIVERY_ONLY` / `NOT_DEMONSTRATED`; clause verdicts
      exactly PASS/FAIL; failures named, warnings separate.
- [ ] B.5 No output field characterises the owner (the A6
      distinction): grep the scorer's strings — a C3 failure
      is phrased as use-not-evidenced, never as an owner
      property.

## Section C — Clause semantics (trace each in the code)

- [ ] C.1 C1: completeness = 4/4 fields; fraction computed
      over the full unit list (the denominator is the file's
      list, not a filtered subset — trace the count).
- [ ] C.2 C1 HASIL floor traced separately from the fraction:
      any unit with `hasil` false/missing fails C1 regardless
      of the fraction (probe E2 is the decisive test).
- [ ] C.3 C2: both `delivered_in_channel` and
      `self_contained` required per unit; fraction vs the
      read threshold.
- [ ] C.4 C3 qualification = all three tests (sequence by
      timestamp comparison; reference to an existing unit id;
      action_type in the four action-bearing values). The
      three non-qualifying action types are excluded in code,
      not by fixture convention.
- [ ] C.5 C3 bars traced: count, distinct domains, and the
      correction requirement honoured only when
      `c3_requires_correction` is true in the report (a false
      value must genuinely relax it — probe with a variant
      dossier).

## Section D — Fences and thresholds

- [ ] D.1 Digest fence traced: file/record digests recomputed
      and compared to `sealed_digests`; any mismatch lands in
      `integrity_failures` and forces `NOT_DEMONSTRATED` —
      including when all clauses would otherwise pass.
- [ ] D.2 Two-hats fence traced: `harvester_id` ∈
      `summary_author_ids` → named failure, overall
      `NOT_DEMONSTRATED`.
- [ ] D.3 Period fence traced: out-of-period units/events
      excluded from every count and surfaced as warnings.
- [ ] D.4 Thresholds read from `harvest_report.json`; grep
      the scorer: no 0.90 / 3 / 2 literals (or arithmetic
      equivalents) in clause logic; missing threshold →
      named clause failure, never a default.
- [ ] D.5 Lesson 1: each record's digest verified at one
      code site; an integrity failure named exactly once
      across the assessment (probe E5).
- [ ] D.6 Lesson 2: invalid extras degrade to warnings and
      flip a clause only when its requirement is unmet by
      valid records (probe E6).

## Section E — Verifier probes (checker-built dossiers, actual outputs recorded)

- [ ] E.1 Happy path: complete synthetic dossier → expect
      `ACCESS_DEMONSTRATED`, all clauses PASS.
- [ ] E.2 HASIL floor: 20 units, 19 complete, 1 missing only
      `hasil` (fraction 0.95 ≥ 0.90) → expect C1 FAIL,
      `NOT_DEMONSTRATED`. **This probe is decisive for the
      build.**
- [ ] E.3 Correction missing: C3 otherwise satisfied, zero
      corrections, requirement on → expect C3 FAIL,
      `DELIVERY_ONLY`.
- [ ] E.4 Acknowledgement trap: dossier padded with
      acknowledgement / bare-approval / owner-initiative
      candidates → none qualify; C3 outcome unchanged.
- [ ] E.5 Tamper: alter one unit record post-sealing →
      integrity failure named exactly once, overall
      `NOT_DEMONSTRATED`.
- [ ] E.6 Warnings semantics: an extra invalid candidate
      beside qualifying events → C3 still PASS, candidate
      listed as warning with its failing test.
- [ ] E.7 Harvester-is-author dossier → named
      `NOT_DEMONSTRATED`.
- [ ] E.8 `dossier=None`; malformed JSON; a unit timestamped
      outside the period → fail-closed / warning behaviour as
      specified, no exceptions.

## Section F — Test suite and regression

- [ ] F.1 All ~20 brief-required tests (§8) present, each
      asserting outcome **and** named failure/warning, not
      outcome alone.
- [ ] F.2 Checker runs `test_g5_instrument.py` directly: all
      OK.
- [ ] F.3 Checker runs `test_g1_instrument.py`,
      `test_g3_instrument.py` (and `test_g4_instrument.py` if
      present): still OK.
- [ ] F.4 Full discover sweep: after = baseline + new tests;
      skip profile matches baseline; runtime recorded.

## Section G — Verdict (each checker files independently)

```
Build under check: <branch> @ <head>
Checker: <operations post | antigravity bench> (independent)
Overall: TAHAN / GAGAL / BELUM TERVERIFIKASI
Findings: <numbered; each with section ref + evidence>
Counts re-measured: baseline <n> → after <n>; g5 tests <n> OK
```

TAHAN requires Sections 0–F to pass and probes E1–E8 to
behave as specified. Violations of the HASIL floor, the
threshold-reading rule, the digest fence, or fixture purity
(real chat content) are automatically GAGAL, not minor.

— End of checklist.
