# G5 harvest — period preregistration LOCKED

Experiment: `g5-harvest-01`. Status: **LOCKED** —
this text fixes the period rule, the thresholds,
the roles, and the sealing before any harvest;
it submits the preregistration to the kernel
(§7) and locks the mechanics. It submits nothing
else and runs no harvest. **G5 remains
NOT_ASSESSED** — no verdict is recorded anywhere
by this lock; the verdict comes only from
`assess_g5` over a sealed dossier after the
checker returns TAHAN (§7).

Lock record: locked 2026-11-15 by Misi 8 (hub act
via ace-queue-watchdog, submission 38c40278…).
Base: origin/main `055dd64`. Draft pre-lock sha256
`d3f2bb2515e6b10b0fcc4da35c51b038959d65984db615fe83c5ca91b885e78b`
(PR #156 head `c8162bb`). Filename retained
(`..._DRAFT_20261113.md`) so existing pointers —
the readiness memo, the G5 evidence index — keep
resolving; the status inside this file is what
binds, not the filename.
Design sources: the G5 dossier design
(D-G5-1..5 RATIFIED, Task 09), the harvest
checklist (Task 15), the instrument
(`g5_instrument.py`, PR #156, criteria v1),
the instrument build brief (Task 12), and the
readiness memo
(`G5_HARVEST_READINESS_MEMO.md`).

## §1 The harvest axiom (restated, binding)

The evidence is harvested retrospectively from
records that already exist. Nothing is staged,
solicited, edited, or re-sent to the owner for
the sake of evidence. The period is fixed by a
milestone rule (§2), never by inspecting which
window would score well.

## §2 Period

- Start: **2026-11-12, evening** — the
  Emancipation amendment, the point at which
  reporting to the owner became the program's
  governance channel (D-G5-1).
- End (cutoff): **2026-11-30** (end of day,
  Asia/Jakarta) — SET by hub decision
  2026-11-13 under the owner's full delegation
  (harvest period: 12 Nov 2026 → 30 Nov 2026).
  The hub named the period by date rather than
  by the milestone rule this draft proposed;
  the value is recorded as decided.
- Records after the cutoff are out of period:
  the instrument reports them as warnings and
  never counts them.
- Machine values (locked; the instrument reads
  these from `harvest_report.json`, inclusive
  bounds): `period_start` =
  **2026-11-12T19:00:00+07:00**,
  `period_end` =
  **2026-11-30T23:59:59+07:00**. The start
  operationalizes "evening" as 19:00 WIB: that
  value is the one the Task 12 build brief (§4
  example) and the instrument's own test fixture
  (`PERIOD_START`) both carry, and no record
  gives a finer time. It is fixed here, not
  fitted to any window.

## §3 Unit rule (Task 09 §3)

One unit = one consolidated discussion-room
summary in the period that reports a stage
result, a measured finding, or a program
decision. Anything else is not a unit. The
unit's completeness is scored against the
four FR-09 fields (HASIL / DICOBA / KEYAKINAN /
BATAS); the HASIL floor is absolute — a unit
lacking HASIL is incomplete whatever the
fraction says.

## §4 Thresholds (D-G5-2..4, read by the instrument
from the harvest report — never hardcoded)

- C1: ≥ 90% of units complete (4/4 fields) AND
  HASIL present in every unit.
- C2: ≥ 90% of units two-part.
- C3: ≥ 3 use events passing all three tests
  (sequence · citation · action), across ≥ 2
  domains, with ≥ 1 correction among them.
  Non-qualifying candidates are listed as
  warnings with the failed test named; a C3
  failure is phrased as *use not evidenced* —
  a property of the record, never of the owner.
- Outcome vocabulary (exactly):
  ACCESS_DEMONSTRATED / DELIVERY_ONLY /
  NOT_DEMONSTRATED.

## §5 Roles (two-hats fence preserved)

The summary author is ila (discussion room);
the harvester is never the author, and a breach
discovered after the harvest is a FAIL that
cannot be cured retroactively. Role mapping
under the single-worker mandate (the work
rooms are silent; the mapping preserves every
fence of the original designation) — concretized
here from the readiness memo §1, which
supersedes this section's earlier "independent
subagent" phrasing (the memo names the actual
holders; the fence is unchanged):

- **Harvester:** the operations post (ila —
  ruang operasi ACE), `harvester_id`
  `"ops-post"`. It receives the raw transcript
  and record pointers only. It enumerates the
  units and the use-event candidates and seals
  the dossier. It is not ila of the discussion
  room and not Ian.
- **Evidence supplier:** Ian (main) — supplies
  record pointers to the harvester without
  harvesting.
- **Rubric scorer 1:** the harvester (its
  sheet is completed before scorer 2's exists).
- **Rubric scorer 2:** Ian, independently.
- **Checker:** the Antigravity bench (Task 15,
  in full): re-enumeration, re-score of ≥ 1/3
  of units + all use events + all disputed
  units, probes F.1–F.5, verdict
  TAHAN / GAGAL / BELUM TERVERIFIKASI.
- **Assessor:** ila — runs `assess_g5` over
  the sealed dossier only (mechanical).
- The instrument checks mechanically:
  `harvester_id ∉ summary_author_ids`; this is
  verified before the harvest runs (Task 15
  §0.3) and again at sealing (Task 15 §E.4).
  `summary_author_ids` is enumerated in the
  harvest report from the author ids actually
  appearing on the units (§9); by designation
  those authors are the discussion-room ila
  session.

## §6 Sources (named transparently)

- Units: the discussion-room transcript for
  the period (the consolidated-bundle flow).
- Use-event candidates: the checkpoint addenda
  on main + MEMORY excerpts — the program has
  no standalone decisions log; the harvester
  names these as its de facto decisions log in
  the dossier (the readiness memo's named
  small gap, closed by declaration, not by
  pretending the log exists).
- Known C1 weakness, recorded as an expected
  finding, not a blocker: the KEYAKINAN/BATAS
  imbalance in the summaries (HASIL strong,
  DICOBA usually present).

## §7 Sealing and kernel mechanics (LOCKED 2026-11-15)

- Dossier schema (Task 12 §4, exact — the
  instrument's contract): `dossier.json`
  references three files —
  `harvest_report.json`, `units.json`,
  `use_events.json`.
  - `harvest_report.json` carries
    `period_start` / `period_end` (ISO 8601,
    timezone-aware), `c1_threshold` 0.90,
    `c2_threshold` 0.90, `c3_min_events` 3,
    `c3_min_domains` 2, `c3_requires_correction`
    true, `harvester_id` `"ops-post"`,
    `summary_author_ids` (enumerated at
    harvest, §5), and `sealed_digests` with
    `units` and `use_events` digests.
  - `units.json`: `{"units": [...]}` — one
    record per assessed unit, the denominator:
    `unit_id`, `message_ref`, `timestamp`,
    `author_id`, `content_digest`,
    `fields` (`dicoba` / `hasil` /
    `keyakinan` / `batas`, booleans),
    `delivered_in_channel`,
    `self_contained`.
  - `use_events.json`: `{"events": [...]}` —
    ALL harvested candidates, qualifying or
    not (enumerate-then-score): `event_id`,
    `message_ref`, `timestamp`,
    `content_digest`, `references_unit`
    (a unit id, or null),
    `action_type`, `domain`.
  - Action vocabulary (ratified): action-bearing
    `decision` / `direction` / `correction` /
    `resource_commitment`; non-qualifying by
    construction `acknowledgement` /
    `owner_initiative` / `bare_approval`.
    An approval that adds content (amends,
    conditions, corrects) is an action under
    test 3 and counts.
  - Domain set (ratified, closed):
    `governance` · `resources/funding` ·
    `operations` · `venues/business` ·
    `technical direction`. Invented domains
    are a checker finding (Task 15 §C.5).
- Canonical digest (sealing): the SHA-256 of a
  file's canonical JSON form — keys sorted,
  compact separators (`,` and `:`), UTF-8 —
  exactly the instrument's `_canonical_digest`.
  `sealed_digests` is computed over the final
  files; one post-seal edit breaks its file's
  seal. The instrument recomputes both digests
  at one code site and names a mismatch exactly
  once as an integrity failure, forcing
  NOT_DEMONSTRATED whatever the contents claim.
  A record's `content_digest` rides under its
  file's seal.
- Evaluator: `code/ace_operational/g5_instrument.py`,
  `CRITERIA_VERSION = 1`, sha256
  `82eba4d12bef3bfdc60c52fb8ada5c58edaeb9c2e0c113400c1f998a40c278ea`
  — verified identical at PR #156 head
  `c8162bb` and at origin/main `055dd64`.
  Invoked as `assess_g5(dossier=<sealed
  dossier directory>)` over the sealed dossier
  only; it never reads live chats, never
  contacts the owner, and harvests nothing.
  Every bar is read from `harvest_report.json`;
  a missing or non-numeric bar is a named
  failure of the affected clause, never a
  default. The instrument never raises on bad
  input: malformed content is a named FAIL.
- Kernel root: `~/workspace/ace-omega/g5-harvest-kernel/`
  — created at submission by this lock.
  Submission record:
  `preregistrations/g5-harvest-01.json`
  carrying `experiment_id` `g5-harvest-01`,
  the evaluator id and digest above, the
  `protocol_hash` (sha256 of this locked text,
  §9), the period, the thresholds, and the
  roles. `results.jsonl` receives the
  assessment output only after the checker
  returns TAHAN and the assessor runs (§7
  execution order, step 6).
- Pass rule: the instrument's `overall` over
  the sealed dossier; **ACCESS_DEMONSTRATED is
  the only passing outcome.** DELIVERY_ONLY and
  NOT_DEMONSTRATED are recorded outcomes, not
  passes. The outcome mapping is Task 09 §7
  verbatim: C1/C2 fail ⇒ NOT_DEMONSTRATED with
  items named; C1+C2 pass and C3 fail ⇒
  DELIVERY_ONLY; all three pass ⇒
  ACCESS_DEMONSTRATED. Any integrity failure
  (including harvester-is-author) ⇒
  NOT_DEMONSTRATED, named.
- Execution order (Task 09 §12, locked):
  1. This lock + kernel submission.
  2. Harvester enumerates every unit by the
     mechanical rule (§3) and every owner-act
     candidate first, then scores; rubric
     sheet 1 is completed before scorer 2's
     sheet exists (Task 15 §B.1).
  3. Scorer 2 (Ian) scores independently.
     Disagreements are logged per unit per
     field and resolved by the rubric anchor
     text only — never by averaging, seniority,
     or "agreed to pass" (Task 15 §B.4);
     disagreement counts are stated in the
     harvest report.
  4. Dossier sealed with `sealed_digests`;
     harvester ≠ author re-verified in the
     sealed file itself (Task 15 §E.4).
  5. Checker (Antigravity bench) runs Task 15
     §§0–F in full, probes F.1–F.5, verdict
     TAHAN / GAGAL / BELUM TERVERIFIKASI.
  6. ONLY on TAHAN does the assessor (ila) run
     `assess_g5` over the sealed dossier.
     GAGAL voids the dossier — no assessment;
     a re-harvest needs a new harvest order,
     never an edit to the sealed files.
     BELUM TERVERIFIKASI means no assessment;
     the harvest returns to the harvester.
  7. The outcome is recorded as measured; the
     board moves only on ACCESS_DEMONSTRATED
     over a TAHAN dossier (§8).
- Fences (Task 15 §D, locked): no staging —
  any owner-facing message sent during
  execution soliciting a response, decision,
  or reaction for evidence purposes is
  automatic GAGAL (D.1/F.5); no editing,
  re-sending, or deleting-and-replacing of
  assessed messages after the window is fixed
  (D.2); no burden on the owner because of the
  harvest (D.3); the dossier stays inside the
  program's records, owner quotes used only
  within the dossier and the checkpoint lineage
  (D.4). Threshold fidelity (E.2): any
  threshold value in `harvest_report.json`
  softer than the ratified values is automatic
  GAGAL. Candidate completeness (C.3): the
  full candidate list stays in the dossier,
  non-qualifiers as warnings with the failing
  test named; a candidate that has vanished
  from the list is the gravest finding in that
  section.
- Machine values (locked, read by the
  instrument from `harvest_report.json`):
  `period_start` 2026-11-12T19:00:00+07:00 ·
  `period_end` 2026-11-30T23:59:59+07:00 ·
  `c1_threshold` 0.90 · `c2_threshold` 0.90 ·
  `c3_min_events` 3 · `c3_min_domains` 2 ·
  `c3_requires_correction` true ·
  `harvester_id` `"ops-post"`.

## §8 Pre-written consequences

- ACCESS_DEMONSTRATED (over a TAHAN dossier):
  G5 is assessed on the sealed dossier + the
  checker's verdict; the board moves only then.
- DELIVERY_ONLY / NOT_DEMONSTRATED: recorded
  as measured, with the named clause items;
  the consequence is an agenda item about the
  reporting system's gaps (the FR-09 fields
  the summaries systematically miss), never a
  re-harvest of the same period.

## §9 Lock record and deferred items

- Protocol hash: the sha256 of this locked file's
  final bytes, recorded in the kernel submission
  record `g5-harvest-kernel/preregistrations/g5-harvest-01.json`
  (kept out of this text so the hash is over the
  exact bytes it names — no self-reference).
- Deferred with written reasons — these are the
  only open items; no ⟨TBD⟩ remains in the
  mechanics above:
  1. **FR-09 template adoption (Task 09 A4) —
     NOT decided by this lock.** Adopting an
     explicit FR-09 template for future
     consolidated reports is a change to the
     reporting system under measurement, not
     an input to the lock; deciding it here
     would move the measured stream mid-period.
     It is prospective only, never back-applied;
     if adopted later, the adoption date is
     disclosed in the dossier and the period is
     scored as the record stands.
  2. **`summary_author_ids` values — enumerated
     at harvest.** The rule is locked
     (harvester ∉ authors, enforced mechanically
     and re-verified at sealing); the values
     are record facts — the author ids actually
     appearing on the units — not choices, so
     they are fixed by enumeration, not by this
     text.

Brain of origin: Muse (Ian).
