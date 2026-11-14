# ANTIGRAVITY TASK 14 — DRAFT TEXT: G4 APPLICATION PREREGISTRATION (kernel-ready)

Status: **DRAFT TEXT — NOT SUBMITTED.** Author: Antigravity
bench room, 2026-11-13 (no Gemini). Sources: PR #136 Part I
and the ratified G4 application dossier design
(`ANTIGRAVITY_TASK_08_G4_APPLICATION_DOSSIER_DRAFT.md`,
decisions D-G4-1..5 ratified as design 2026-11-13); the G4
instrument build brief (Task 10) fixes the scoring schema
this text is written against. Pair to Task 11 (the G3
application preregistration draft).

**This text is not a preregistration. No protocol hash exists
for it. G4 remains NOT_ASSESSED.** It becomes submittable
only when every blocker in §9 has closed; the fields still
open are marked ⟨TBD-AT-SUBMISSION⟩ and are mechanical
(digests, ids, seeds, names), never substantive.

---

## 1. Hypothesis (falsifiable)

**H1.** A successor variant that never ran discovery, given
the materialised operator catalog (§2) as inherited data,
solves materially more held-out capability tasks than the
identical successor without it — by the margins fixed in §6 —
on a fresh-seed grid universe neither arm has ever touched.

H1 is **falsified** if any §6 condition fails: the margin,
the WITH-arm floor, the WITHOUT-arm attribution ceiling, or
the control no-regression rule. The outcome is then
`LINEAGE_ONLY` (the archive remembers; inheritance in use is
not demonstrated) — a publishable measured outcome, reported
with the same prominence as a positive one. No re-run until
green is permitted under this registration.

## 2. The inherited artifact (identity by digest)

The **v4 admitted operator catalog** (D-G4-1): per grid
defect class, the admitted operator keys and chains recorded
in `evidence/operator_discovery_v4.json` (bounds_off_by_one:
3 operators + 1 chain · dist_step_2: 1 operator ·
returns_start_distance: 1 operator + 1 chain · wall_char_x:
1 operator), **materialised** (blocker B2) into a standalone
canonical artifact file: JSON of the admitted keys/chains per
class in their exact recorded string forms, canonically
ordered, with a SHA-256 digest.

- Artifact name: `operator_catalog_v4` ⟨materialised form⟩.
- Artifact digest: ⟨TBD-AT-SUBMISSION — computed at
  materialisation; independently reproducible byte-for-byte⟩.
- **Discovery record (D-G4-2, ratified):** the v4 stage
  evidence (`evidence/operator_discovery_v4.json` + its
  driver record) is accepted as C2's discovery record, with
  its provenance stated in the dossier: it is measured stage
  evidence with an admission rule (an operator admitted only
  if it fixes ≥2 independent pool tasks), not a
  kernel-preregistered run. The capability record in the
  dossier carries the same name + digest as the materialised
  artifact; identity is by digest, never by name.

## 3. The actors (lineage)

- **Predecessor:** the Stage I/v4 discovering configuration,
  registered as a candidate in a dedicated `PopulationArchive`
  root created for this dossier (not the pilot archives),
  identified by its module identity and its §2 run record.
- **Successor:** a **fresh** archive candidate whose parent
  link names the predecessor, whose solver configuration is
  the greedy solver + the authored baseline catalog — the
  same code the predecessor's baseline arm used — and which
  has **never invoked discovery**. Candidate ids:
  ⟨TBD-AT-SUBMISSION⟩.
- **Inheritance event:** the §2 artifact is delivered to the
  successor as data; the runner verifies its digest against
  the lineage record at load (mismatch aborts the run as an
  integrity failure). *Use* = applying admitted keys/chains
  through `apply_operator` / `apply_chain`. *Discovery* =
  any `discover_*` call; the run log must make the absence of
  discovery calls auditable, and the evaluation report
  attests `discovery_invoked: false`.
- The archive's integrity verification (hash chain clean)
  over these records is part of the dossier; a broken chain
  fails C1 by name.

## 4. Evaluation universe and sets

- **Universe:** `grid_generalization.build_universe(seed =
  ⟨TBD-AT-SUBMISSION⟩)`, a fresh seed disjoint from every
  prior run (Stage F rounds, v1–v4 discovery, pilots). The
  universe must pass the Stage F v3 protocol's validity
  gates before the run (catalog-control validity line; null
  control at zero); a universe failing its gates invalidates
  the run, as Stage F's first two rounds invalidated
  themselves — recorded, not repaired silently.
- **Capability set:** the universe's `new_only` single-defect
  tasks in the four discovered classes; **n ≥ 40** required.
  If the chosen seed yields fewer, a second seed is added by
  amendment to this text **before** any run — never after
  seeing scores. Mixed 2-defect tasks are run and reported
  separately; they do not enter the §6 rule.
- **Control set:** the universe's `catalog_control` tasks,
  both arms.

## 5. Arms and procedure

- **WITHOUT arm first** (the conservative order), then WITH:
  two separate processes, no shared state, no cross-task
  memory in the solver, identical tasks, solver, and budgets.
- **WITH arm:** the identical successor + the §2 artifact
  loaded by digest.
- **WITHOUT arm:** the identical successor, baseline catalog
  only.
- Discovery code is not imported for execution in either
  arm's process beyond the apply path (§3 boundary).
- Budget: ⟨TBD-AT-SUBMISSION — wall-clock ceiling for both
  arms, set from the runner's measured profile at B5⟩.

## 6. Pass rule (mechanical; scored by the G4 instrument)

The evaluation report carries the thresholds as fields —
`margin_pp: 20.0`, `with_floor: 0.25`,
`without_ceiling: 0.10`, `min_capability_tasks: 40` — fixed
by this text (D-G4-3); the instrument reads them from the
report and never invents its own. **C3 passes** iff all hold
on the audited report:

1. **Δ ≥ +20.0 pp** — (WITH − WITHOUT) solved fraction on
   capability singles.
2. **WITH ≥ 0.25** — the WITH arm solves at least a quarter
   of capability singles in absolute terms.
3. **WITHOUT ≤ 0.10** — the attribution ceiling: above it,
   the effect cannot be credited to inheritance whatever Δ
   says.
4. **Zero control regression** — WITH solves every control
   task WITHOUT solves.

Outcome, scored by `g4_instrument.py` over the §7 dossier
(criteria version recorded):

| C1 lineage | C2 identity+admission | C3 (§6) | Outcome |
|---|---|---|---|
| pass | pass | pass | `INHERITANCE_DEMONSTRATED` |
| pass | pass | fail | `LINEAGE_ONLY` |
| fail | any | any | `NOT_DEMONSTRATED`, items named |
| pass | fail | any | `NOT_DEMONSTRATED`, items named |
| any digest mismatch among {capability record, discovery record, artifact as loaded} | | | `NOT_DEMONSTRATED`, mismatch named (hard fence) |

## 7. Dossier and audit requirements

The dossier follows Task 08 §6 as conformed to the Task 10
instrument schema: `lineage_record` (archive export: both
candidate records, parent link, artifact attached, archive
audit result), `capability_record` (artifact file + digest +
discovery record reference with provenance, §2),
`evaluation_report` (this registration's protocol hash as
back-reference, kernel audit result — must be CLEAN, an
INCOMPLETE audit is not CLEAN — artifact digest as loaded,
universe seed, per-arm task-id lists and solved counts on
capability/control/mixed, thresholds as §6, wall time,
runner identity, no-discovery attestation). Split custody
per OMEGA-06: the universe custodian and the runner are
different parties ⟨TBD-AT-SUBMISSION⟩; the universe seed
stays sealed with its custodian until the run. ila
independently verifies before any figure reaches the owner;
brain-of-origin of every contribution is recorded in the
checkpoint lineage.

## 8. Reporting commitments

The result is reported to the owner as one consolidated
report stating the outcome word, both arms' numbers, the
honest starting point (today's ceiling is `LINEAGE_ONLY` —
the dossier starts from there, not from zero), and the
scope caveat of Task 08 A4: this registration measures
inheritance of *this* catalog on *these* classes;
generalisation to new classes is G3's neighbouring question
and must not be quoted as answered here.

## 9. BLOCKERS — what still prevents submission today

- **B1 — G4 instrument not built.** `g4_instrument.py` does
  not exist. Build package ready (Task 10 brief + checklist).
  *Closes with:* the built instrument, verified by two
  checkers per the Task 10 checklist.
- **B2 — Catalog not materialised.** The catalog exists only
  as string lists inside the v4 evidence and is recomputed
  per run; there is no canonical artifact file or digest
  (§2). *Closes with:* the deterministic materialiser + the
  artifact file + digest, independently reproduced.
- **B3 — Lineage records not created.** No archive holds the
  predecessor → successor link with the artifact attached.
  *Closes with:* the dedicated archive root with both
  candidate records, the parent link, and a clean integrity
  verification.
- **B4 — Fresh universe unvalidated.** No seed has been
  chosen or checked against the Stage F validity gates and
  the n ≥ 40 capability requirement. *Closes with:* the
  universe validation note (§4) naming the seed.
- **B5 — Successor runner not built.** No runner exists that
  loads the artifact by digest, runs both arms in separate
  processes in the §5 order, and produces the auditable
  no-discovery run log. *Closes with:* the runner + a dry
  profile run on non-evaluation tasks.
- **B6 — Custodians unnamed.** Split custody (§7) requires
  two named parties. *Closes with:* assignments recorded in
  the submission package.

## 10. Submission checklist (when §9 is empty)

1. Build/verify the instrument (B1); materialise the catalog
   and fix its digest in §2 (B2).
2. Create the lineage archive records; verify integrity (B3).
3. Validate the fresh universe; fix the seed in §4 (B4).
4. Build the runner; set the §5 budget (B5); name the
   custodians (B6).
5. Submit this text to the OMEGA-06 kernel; record the
   protocol hash in the checkpoint lineage.
6. Only then: run both arms, assemble the dossier, score,
   verify independently, report (§7–§8).

— End of draft text. Desk work under the owner's no-idle
directive; it authorizes no run and claims no result. G4
remains NOT_ASSESSED.
