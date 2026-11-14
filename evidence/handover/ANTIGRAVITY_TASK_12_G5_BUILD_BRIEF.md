# ANTIGRAVITY TASK 12a — BUILD BRIEF: G5 INSTRUMENT (g5_instrument.py)

Status: **RATIFIED-DESIGN BUILD BRIEF** — the pair to Task 10
(G4), ready to execute by whoever the director assigns.
Author: Antigravity bench room, 2026-11-13. Design sources:
PR #136 Part II and the ratified G5 application dossier
design (`ANTIGRAVITY_TASK_09_G5_APPLICATION_DOSSIER_DRAFT.md`,
decisions D-G5-1..5 ratified 2026-11-13, harvest axiom
locked).

**Scope fence (absolute):** synthetic dossiers only. No live
harvest, no real chat records scored, no G5 verdict, no
push/merge beyond a draft PR. G5 remains **NOT_ASSESSED**.
The instrument scores a *sealed harvest dossier*; it never
contacts the owner, never reads live chats, and manufactures
no evidence — the dossier design's harvest axiom binds the
instrument's shape as much as the harvest itself.

---

## 1. Deliverables — exactly two files

In `code/ace_operational/` of the build worktree (§2):

1. `g5_instrument.py` — the pure scorer.
2. `test_g5_instrument.py` — its synthetic test suite.

Nothing else. Open schema questions resolve toward the
G3/G4 instruments' precedent (`assess_g3`, `assess_g4`):
shape, naming, fail-closed discipline, single construction
point, `CRITERIA_VERSION` on every path.

## 2. Tree and baseline discipline

As Task 10 §2: build on the tree containing the current
`g3_instrument.py` (and `g4_instrument.py` if it has landed);
record base commit + pre-build discover-sweep baseline in
the PR body before writing code; a sweep far below the
program baseline means the wrong tree — stop and report.
Invocation: `PYTHONPATH=code python3
code/ace_operational/test_g5_instrument.py`.

## 3. Interface

```python
CRITERIA_VERSION = 1
def assess_g5(*, dossier: str | Path | None) -> dict: ...
```

Pure function over a dossier directory; JSON only; no
network, clock, or writes. Returns on **every** path, via a
single construction point:

- `gate`: `"G5"` · `criteria_version`
- `overall`: `ACCESS_DEMONSTRATED` / `DELIVERY_ONLY` /
  `NOT_DEMONSTRATED`
- `clauses`: `{"C1": {...}, "C2": {...}, "C3": {...}}`, each
  `{"verdict": "PASS"|"FAIL", "missing": [...],
  "warnings": [...]}`
- `integrity_failures`: list (see §6)
- Never raises on bad input: missing/malformed/non-numeric
  content is a named FAIL, overall `NOT_DEMONSTRATED`.

## 4. Dossier schema (what the scorer reads)

`dossier/` holds `dossier.json` referencing three files:

```json
{
  "harvest": "harvest_report.json",
  "units": "units.json",
  "use_events": "use_events.json"
}
```

**harvest_report.json** — the ratified bars live here and
are **read by the scorer, never hard-coded** (§6):
```json
{
  "period_start": "2026-11-12T19:00:00+07:00",
  "period_end": "2026-…",
  "c1_threshold": 0.90,
  "c2_threshold": 0.90,
  "c3_min_events": 3,
  "c3_min_domains": 2,
  "c3_requires_correction": true,
  "harvester_id": "ops-post",
  "summary_author_ids": ["ila-main", "ila-bench", "…"],
  "sealed_digests": {"units": "<sha256>", "use_events": "<sha256>"}
}
```

**units.json** — one record per assessed unit (the
denominator is this list, complete by the dossier design's
enumeration rule):
```json
{"units": [{
  "unit_id": "u-001", "message_ref": "…", "timestamp": "…",
  "author_id": "ila-main",
  "content_digest": "<sha256 of the summary text as harvested>",
  "fields": {"dicoba": true, "hasil": true,
             "keyakinan": true, "batas": false},
  "delivered_in_channel": true, "self_contained": true
}]}
```

**use_events.json** — ALL harvested candidates, qualifying
or not (the dossier design's enumerate-then-score rule):
```json
{"events": [{
  "event_id": "e-001", "message_ref": "…", "timestamp": "…",
  "content_digest": "<sha256>",
  "references_unit": "u-001",
  "action_type": "correction",
  "domain": "operations"
}]}
```
`action_type` vocabulary: `decision` / `direction` /
`correction` / `resource_commitment` (action-bearing) and
`acknowledgement` / `owner_initiative` / `bare_approval`
(non-qualifying by construction, per the ratified
exclusions).

## 5. Clause semantics

- **C1 — FR-09 completeness.** A unit is complete iff all
  four fields are true. PASS iff: (fraction of complete
  units ≥ `c1_threshold`) **AND every unit has
  `hasil == true`** — the HASIL floor is absolute and is not
  a threshold: a single result-less unit fails C1 whatever
  the fraction (ratified: a summary without HASIL is not a
  report). Per-unit missing fields are named in the clause's
  `missing` (aggregated by unit id + field).
- **C2 — delivery without a technical detour.** A unit
  passes iff `delivered_in_channel` **and** `self_contained`
  are both true. PASS iff the passing fraction ≥
  `c2_threshold`. Failing units named.
- **C3 — recorded owner use.** A candidate **qualifies** iff
  all three ratified tests hold: (i) *sequence* — its
  timestamp is after the referenced unit's timestamp;
  (ii) *reference* — `references_unit` names an existing
  unit in this dossier; (iii) *action* — `action_type` is
  one of the four action-bearing values. PASS iff:
  qualifying count ≥ `c3_min_events` **and** distinct
  `domain` values among qualifying events ≥ `c3_min_domains`
  **and** (if `c3_requires_correction`) ≥1 qualifying event
  has `action_type == "correction"`. Each unmet component
  is named separately. Non-qualifying candidates are listed
  as warnings with their failing test — visible, never
  silently dropped (the denominator stays auditable).

## 6. Integrity fence + thresholds + the two lessons

- **Digest fence (this gate's form of the hard fence).**
  The scorer recomputes the SHA-256 of each file's canonical
  content and of each record's `content_digest` basis as
  specified by the harvest format, and compares against
  `sealed_digests` in the harvest report. Any mismatch is an
  **integrity failure**: recorded in `integrity_failures`,
  and the overall is forced to `NOT_DEMONSTRATED` with the
  mismatch named — a tampered or re-edited harvest is not
  evidence, whatever its contents claim. (G3/G4 bind an
  artifact's digest; G5 binds the *record's* digest — the
  harvest is this gate's artifact.)
- **Two-hats fence, mechanical:** if `harvester_id` appears
  in `summary_author_ids`, the dossier is invalid by
  construction (ratified D-G5-5: the harvester is never a
  summary author): overall `NOT_DEMONSTRATED`, named
  `harvest.harvester_is_author`. The instrument enforces
  what the protocol promises.
- **Period fence:** units or events timestamped outside
  [`period_start`, `period_end`] do not count toward any
  clause and are named as warnings (out-of-period material
  smuggled into a dossier must not inflate it).
- **Thresholds are read, never owned:** every bar in §5
  comes from `harvest_report.json`. A missing threshold
  field is a named failure of the affected clause — never
  defaulted, never hard-coded (the Task 10 grep rule
  applies verbatim: no 0.90 / 3 / 2 literals in clause
  logic).
- **Lesson 1 (check once):** each record's digest is
  verified at one code site; C1–C3 consume the result; an
  integrity failure is named exactly once.
- **Lesson 2 (verdict = requirement met by valid evidence):**
  invalid extra records degrade to named warnings; they
  flip a clause only when the requirement is unmet by the
  valid records.

## 7. Outcome mapping

| C1 | C2 | C3 | Overall |
|---|---|---|---|
| PASS | PASS | PASS | `ACCESS_DEMONSTRATED` |
| PASS | PASS | FAIL | `DELIVERY_ONLY` |
| FAIL | any | any | `NOT_DEMONSTRATED`, items named |
| any | FAIL | any | `NOT_DEMONSTRATED`, units named |
| any integrity failure / harvester-is-author | | | `NOT_DEMONSTRATED`, named |

The instrument's output language must preserve the dossier
design's A6 distinction mechanically: a C3 failure is
recorded as use *not evidenced* (a property of the reporting
system's record), and no field of the output characterises
the owner.

## 8. Required synthetic tests (all in test_g5_instrument.py)

1. Complete dossier → `ACCESS_DEMONSTRATED`, all PASS,
   `criteria_version` present.
2. C1 fraction below threshold → C1 FAIL, `NOT_DEMONSTRATED`.
3. **HASIL floor:** 19/20 units complete but one unit lacks
   `hasil` → C1 FAIL by name (fraction 0.95 must NOT save it).
4. Units missing `keyakinan` beyond threshold → named per unit.
5. C2 fraction below threshold (units deferring substance)
   → `NOT_DEMONSTRATED`.
6. Only 2 qualifying events → C3 FAIL → `DELIVERY_ONLY`.
7. 3+ events, 1 domain only → C3 FAIL (domains named) →
   `DELIVERY_ONLY`.
8. 3+ events, 2+ domains, no correction (with
   `c3_requires_correction` true) → C3 FAIL → `DELIVERY_ONLY`.
9. Acknowledgement-only candidates never qualify.
10. Owner-initiative candidates (`references_unit` null)
    never qualify.
11. Event timestamped *before* its referenced unit never
    qualifies (sequence test).
12. Bare-approval candidates never qualify.
13. **Tamper probe:** one unit's content altered after
    sealing (digest mismatch) → integrity failure,
    `NOT_DEMONSTRATED`, named exactly once.
14. **Harvester-is-author** → `NOT_DEMONSTRATED` by name.
15. Out-of-period unit/event → warnings, not counted.
16. Missing threshold field (e.g. no `c3_min_events`) →
    affected clause FAIL by name; nothing defaulted.
17. Missing dossier / `dossier=None` → fail-closed.
18. Malformed JSON → named FAIL, no exception.
19. Non-boolean field values / non-numeric thresholds →
    named FAIL, no exception.
20. Extra invalid candidate alongside qualifying ones →
    warning; C3 stands on the valid evidence (Lesson 2).

Target ~20 tests, deterministic, seconds of runtime. All
fixtures are invented summaries and invented owner messages
— synthetic people saying synthetic things; no real chat
content in fixtures, even anonymised.

## 9. Completion evidence (what the builder reports)

- Branch, base commit, worktree; diff = exactly the 2 files.
- Direct-run output of `test_g5_instrument.py` (all OK) and
  the discover sweep: baseline (before) → after counts,
  skips explained.
- Brain-of-origin recorded in the PR body.
- Statement that no live harvest was performed or scored,
  no real records were read by the instrument, and G5
  remains NOT_ASSESSED.

— End of brief. Verification follows
ANTIGRAVITY_TASK_12_G5_BUILD_CHECKLIST.md.
