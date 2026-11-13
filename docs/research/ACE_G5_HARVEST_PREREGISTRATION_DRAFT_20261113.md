# G5 harvest — period preregistration DRAFT

Experiment: `g5-harvest-01`. Status: **DRAFT** —
this text fixes the period rule, the thresholds,
the roles, and the sealing before any harvest;
it submits nothing to any kernel and locks
nothing until the cutoff is set by the hub or
the owner (a single ⟨TBD-GATE⟩ field, §2).
Design sources: the G5 dossier design
(D-G5-1..5 RATIFIED, Task 09), the harvest
checklist (Task 15), the instrument
(`g5_instrument.py`, PR #156, criteria v1),
and the readiness memo
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
- End (cutoff): ⟨TBD-GATE — set by the hub or
  the owner at lock time, by naming a milestone;
  the draft proposes the next gate-board
  addendum after this draft as the natural
  milestone, but the value is theirs to set⟩.
- Records after the cutoff are out of period:
  the instrument reports them as warnings and
  never counts them.

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
fence of the original designation):

- **Harvester:** an independent subagent
  spawned for the harvest, receiving the raw
  transcript and record pointers only. It
  enumerates the units and the use-event
  candidates and seals the dossier. It is not
  ila and not Ian.
- **Evidence supplier:** Ian (main) — supplies
  record pointers to the harvester without
  harvesting.
- **Rubric scorer 1:** the harvester (its
  sheet is completed before scorer 2's exists).
- **Rubric scorer 2:** Ian, independently.
- **Checker:** a second independent subagent
  (raw evidence only): re-enumeration, re-score
  of ≥ 1/3 of units + all use events + all
  disputed units, probes F.1–F.5, verdict
  TAHAN / GAGAL / BELUM TERVERIFIKASI.
- **Assessor:** ila — runs `assess_g5` over
  the sealed dossier only (mechanical).
- The instrument checks mechanically:
  `harvester_id ∉ summary_author_ids`; this is
  re-verified at sealing.

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

## §7 Sealing and kernel mechanics (TBD-GATE at lock)

- Dossier schema (Task 12): dossier.json ·
  harvest_report.json · units.json ·
  use_events.json, with sealed digests over
  the sealed files (canonical form per the
  instrument: sorted-key JSON, tight
  separators, UTF-8 — one post-seal edit
  breaks its file's seal).
- Evaluator: `g5_instrument.py` (criteria v1),
  digest ⟨TBD-GATE — pinned from PR #156's
  file at lock⟩.
- Kernel root: `~/workspace/ace-omega/g5-harvest-kernel/`
  ⟨TBD-GATE — created at submission⟩.
- Pass rule: the instrument's outcome over
  the sealed dossier; ACCESS_DEMONSTRATED is
  the only passing outcome.

## §8 Pre-written consequences

- ACCESS_DEMONSTRATED: G5 is assessed on the
  sealed dossier + the checker's verdict; the
  board moves only then.
- DELIVERY_ONLY / NOT_DEMONSTRATED: recorded
  as measured, with the named clause items;
  the consequence is an agenda item about the
  reporting system's gaps (the FR-09 fields
  the summaries systematically miss), never a
  re-harvest of the same period.

Brain of origin: Muse (Ian).
