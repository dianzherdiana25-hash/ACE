# ANTIGRAVITY TASK 10a — BUILD BRIEF: G4 INSTRUMENT (g4_instrument.py)

Status: **RATIFIED-DESIGN BUILD BRIEF** — ready to execute by
whoever the director assigns (the Task 01 pattern). Author:
Antigravity bench room, 2026-11-13. Design sources: PR #136
Part I and the ratified G4 application dossier design
(`ANTIGRAVITY_TASK_08_G4_APPLICATION_DOSSIER_DRAFT.md`,
decisions D-G4-1..5 ratified as design 2026-11-13).

**Scope fence (absolute):** synthetic dossiers only. No live
application, no real lineage archive, no G4 verdict, no
push/merge beyond a draft PR. G4 remains **NOT_ASSESSED**.

---

## 1. Deliverables — exactly two files

In `code/ace_operational/` of the build worktree (§2):

1. `g4_instrument.py` — the pure scorer.
2. `test_g4_instrument.py` — its synthetic test suite.

Nothing else is added or modified. Any schema question the
brief leaves open is resolved toward the G3 instrument's
precedent (`g3_instrument.py`, `assess_g3`), which this build
mirrors in shape, naming, and fail-closed discipline.

## 2. Tree and baseline discipline

- Build on the tree that contains the **current**
  `g3_instrument.py` (post-P3 semantics), so patterns align.
  Record the base commit hash in the PR body.
- **Before writing code**, run the ace_operational discover
  sweep on the untouched tree and record the baseline count
  in the PR body (the right-tree caution from the G3
  verification: the ACE clone's local `main` is a divergent
  line with a far smaller test count — a sweep far below the
  recorded program baseline means the wrong tree; stop and
  report, do not build).
- Invocation pattern that works in this repo: direct file run
  with `PYTHONPATH=code` (e.g. `PYTHONPATH=code python3
  code/ace_operational/test_g4_instrument.py`).

## 3. Interface

```python
CRITERIA_VERSION = 1
def assess_g4(*, dossier: str | Path | None) -> dict: ...
```

- Pure function over a dossier **directory**; reads JSON
  files only; no network, no clock, no writes.
- Returns, on **every** path, a dict built at a single
  construction point (the G1/G3 lesson — no early return may
  bypass it):
  - `gate`: `"G4"`
  - `criteria_version`: `CRITERIA_VERSION`
  - `overall`: one of `INHERITANCE_DEMONSTRATED` /
    `LINEAGE_ONLY` / `NOT_DEMONSTRATED`
  - `clauses`: `{"C1": {...}, "C2": {...}, "C3": {...}}`,
    each `{"verdict": "PASS"|"FAIL", "missing": [...],
    "warnings": [...]}`
  - `identity_mismatches`: list (see §6)
  - Never raises on bad input: a missing dossier, malformed
    JSON, or non-numeric field is a named `FAIL`, overall
    `NOT_DEMONSTRATED` (fail-closed, mirroring G3's tests).

## 4. Dossier schema (what the scorer reads)

`dossier/` contains `dossier.json` (the manifest) plus the
files it references by relative path:

```json
{
  "lineage": "lineage_record.json",
  "capability": "capability_record.json",
  "evaluation": "evaluation_report.json"
}
```

**lineage_record.json**
```json
{
  "predecessor_id": "cand_…",
  "successor_id": "cand_…",
  "successor_parents": ["cand_…"],
  "capability_digest": "<sha256 hex>",
  "archive_audit": "CLEAN",
  "chain_valid": true
}
```

**capability_record.json**
```json
{
  "artifact_name": "operator_catalog_v4",
  "artifact_digest": "<sha256 hex>",
  "discovery_record": {
    "artifact_name": "operator_catalog_v4",
    "artifact_digest": "<sha256 hex>",
    "admission_evidence": { "...": "non-empty; measured admission content" }
  }
}
```

**evaluation_report.json**
```json
{
  "protocol_hash": "<hex>",
  "audit": "CLEAN",
  "successor_id": "cand_…",
  "artifact_digest_loaded": "<sha256 hex>",
  "discovery_invoked": false,
  "margin_pp": 20.0,
  "with_floor": 0.25,
  "without_ceiling": 0.10,
  "min_capability_tasks": 40,
  "capability": {"n": 47, "with_solved": 15, "without_solved": 0},
  "control": {"with_solved": 34, "without_solved": 34}
}
```

The threshold fields (`margin_pp`, `with_floor`,
`without_ceiling`, `min_capability_tasks`) are **read from
the report**, exactly as the G3 instrument reads `margin_pp`
from each family report: the margin was fixed in the
preregistration that produced the report; the instrument
never invents, defaults, or hard-codes one. A missing
threshold field is a named C3 failure.

## 5. Clause semantics

- **C1 — lineage stored and auditable.** PASS iff: lineage
  record present and well-formed · predecessor and successor
  ids present · `successor_parents` includes the predecessor
  id · a capability digest is attached · `archive_audit` is
  `CLEAN` **and** `chain_valid` is true. Any failure is named
  (e.g. `lineage.chain_valid_not_true`,
  `lineage.successor_parent_link_missing`).
- **C2 — capability identified with admission evidence.**
  PASS iff: capability record present · `artifact_digest`
  present · discovery record present with a non-empty
  `admission_evidence` · the discovery record's
  `artifact_digest` **equals** the capability record's
  (identity is by digest; an equal name never suffices).
- **C3 — successor use with attribution control.** PASS iff:
  evaluation report present · `protocol_hash` present ·
  `audit` is `CLEAN` · `successor_id` equals the lineage
  record's successor id · `discovery_invoked` is exactly
  `false` (a successor that ran discovery discovered; it did
  not inherit) · `artifact_digest_loaded` equals the
  capability digest (§6) · capability counts present with
  `n ≥ min_capability_tasks` · both arms present · and all
  four ratified effect conditions hold:
  1. Δ = (with − without)/n × 100 ≥ `margin_pp`
  2. with/n ≥ `with_floor`
  3. without/n ≤ `without_ceiling`
  4. control: `control.with_solved ≥ control.without_solved`
     (zero regression)
  Each failed condition is named separately (e.g.
  `c3.attribution_ceiling_exceeded`,
  `c3.control_arm_missing`, `c3.successor_rediscovered`).

## 6. The digest hard fence + two recorded lessons

- **Hard fence (mirrors G3):** any digest inequality among
  {capability record, discovery record, artifact as loaded by
  the successor} is an **identity mismatch**: it is recorded
  in `identity_mismatches`, the affected clause FAILs, and
  the overall outcome is forced to `NOT_DEMONSTRATED` with
  the mismatch named — never `LINEAGE_ONLY`, never silently
  absorbed. The dossier assessed a different artifact than
  the one whose discovery is recorded; there is nothing to
  inherit *from*.
- **Lesson 1 — check once (from the G3 verification, finding
  1):** the capability identity check runs **once**; C2 and
  C3 reference its result. A mismatch must appear exactly
  once in the assessment's failure lists, not once per clause
  that touches it.
- **Lesson 2 — verdict = requirement met by valid evidence
  (coordinator's ruling on the G3 verification, finding 2):**
  extra entries that are invalid (e.g. a superseded lineage
  record version listed alongside the current one) become
  named **warnings**; they flip a clause only when the
  clause's requirement is not met by the valid evidence.

## 7. Outcome mapping

| C1 | C2 | C3 | Overall |
|---|---|---|---|
| PASS | PASS | PASS | `INHERITANCE_DEMONSTRATED` |
| PASS | PASS | FAIL | `LINEAGE_ONLY` |
| FAIL | any | any | `NOT_DEMONSTRATED` (items named) |
| any | FAIL | any | `NOT_DEMONSTRATED` (items named) |
| any identity mismatch (§6) | | | `NOT_DEMONSTRATED` (mismatch named) |

## 8. Required synthetic tests (all in test_g4_instrument.py)

Happy path and outcome mapping:
1. Complete dossier → `INHERITANCE_DEMONSTRATED`, all
   clauses PASS, `criteria_version` present.
2. C3 effect below margin (Δ only) → `LINEAGE_ONLY`.
3. WITH arm below floor → `LINEAGE_ONLY`, condition named.
4. WITHOUT arm above ceiling (attribution fails) →
   `LINEAGE_ONLY`, condition named.
5. Control regression → `LINEAGE_ONLY`, condition named.
6. Evaluation report absent (C3 not run) → `LINEAGE_ONLY`.

Fail-closed and adversarial (from the dossier design):
7. **Broken lineage chain** (`chain_valid` false and/or
   archive audit not CLEAN) → C1 FAIL, `NOT_DEMONSTRATED`.
8. Successor parent link missing or pointing elsewhere →
   C1 FAIL by name.
9. Capability digest attached to lineage ≠ capability record
   → hard fence, `NOT_DEMONSTRATED`.
10. **Name trap:** same `artifact_name`, different digest in
    the discovery record → C2 FAIL, `NOT_DEMONSTRATED`.
11. **Successor that secretly re-discovers**
    (`discovery_invoked` true) → C3 FAIL by name; overall
    `LINEAGE_ONLY` if C1/C2 pass.
12. **Dossier without a control arm** (without-arm fields
    absent) → C3 FAIL by name (`c3.control_arm_missing`).
13. Loaded digest ≠ capability digest (successor used a
    different artifact) → hard fence, `NOT_DEMONSTRATED`.
14. Successor id in evaluation ≠ lineage successor → C3
    FAIL by name.
15. Missing threshold field (e.g. no `margin_pp`) → C3 FAIL
    by name; no default substituted.
16. Capability `n` below `min_capability_tasks` → C3 FAIL by
    name.
17. Missing dossier / `dossier=None` → fail-closed
    `NOT_DEMONSTRATED`, no exception.
18. Malformed JSON in any referenced file → named FAIL, no
    exception.
19. Non-numeric scores/counts → named FAIL, no exception.
20. Identity mismatch recorded **exactly once** (Lesson 1);
    extra superseded lineage entry → warning, clause stands
    on valid evidence (Lesson 2).

Target: ~20 tests, all deterministic, runtime in seconds.

## 9. Completion evidence (what the builder reports)

- Branch, base commit, worktree path; diff = exactly the 2
  files.
- Direct-run output of `test_g4_instrument.py` (all OK) and
  the full ace_operational discover sweep: baseline (before)
  and after counts, after = baseline + new tests, skips
  explained.
- Brain-of-origin of the build recorded in the PR body
  (which brain wrote it — the two-hats/lineage discipline).
- Statement that no live dossier, archive, or run was
  touched; G4 remains NOT_ASSESSED.

— End of brief. Verification of the build follows
ANTIGRAVITY_TASK_10_G4_BUILD_CHECKLIST.md.
