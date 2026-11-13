# ANTIGRAVITY TASK 08 — DRAFT DESIGN: G4 FIRST APPLICATION DOSSIER (lineage & inheritance)

Status: **DRAFT FOR RATIFICATION** by the program director
(ila). Author: Antigravity bench room, 2026-11-13 (no Gemini).
Design source: PR #136, `docs/research/ACE_G4_G5_INSTRUMENT_DESIGN_20261112.md`,
Part I (G4). Format follows the ratified Task 02 G3 dossier
draft.

**This document claims no result. It is not a preregistration.
G4 remains NOT_ASSESSED.** It becomes operative only when ila
ratifies the decisions in §9 and a preregistration is created
in the OMEGA-06 kernel from the ratified text.

---

## 1. Purpose

Design the first live application of the G4 clauses:

- **C1** — lineage stored and auditable: a record links
  predecessor → successor with the capability artifact
  attached, and the archive's integrity check passes.
- **C2** — capability identified with admission evidence: the
  artifact's name + digest match the record of its measured
  discovery.
- **C3** — successor use **with an attribution control**: the
  same successor, with vs without the inherited artifact, on
  held-out tasks requiring that capability; both arms required.

Outcome vocabulary, exactly: `INHERITANCE_DEMONSTRATED` /
`LINEAGE_ONLY` / `NOT_DEMONSTRATED` (missing items named).

## 2. The candidate capability artifact — assessed as it stands

**Candidate:** the admitted operator catalog from operator
discovery (the v4 run): per grid defect class, the admitted
operator keys and chains recorded in
`evidence/operator_discovery_v4.json` — bounds_off_by_one:
3 operators + 1 chain · dist_step_2: 1 operator ·
returns_start_distance: 1 operator + 1 chain · wall_char_x:
1 operator. It is the program's strongest candidate by a wide
margin: it is the only capability in the program whose
*discovery* was itself a measured process with an admission
rule (an operator is admitted only if it fixes ≥2 independent
pool tasks) and a measured effect on untouched tasks.

**Three gaps separate this candidate from a scorable C2
artifact today — all named, none papered over:**

- **G-1: the catalog is not yet an artifact.** It exists as
  string lists inside an evidence JSON and is *recomputed* by
  `run_discovery` on every run. There is no standalone catalog
  file, no canonical serialisation, and no digest — so there
  is currently nothing whose digest C2 could match. A
  materialisation step (§7, P-G4-2) must fix this before any
  dossier: canonical JSON of the admitted keys/chains per
  class (sorted, exact string forms as recorded in the
  evidence), SHA-256 over it, stored as the capability
  artifact file.
- **G-2: the discovery record is stage evidence.** The v4 run
  was measured stage work with a protocol fixed in advance in
  its driver, but it is not an OMEGA-06-kernel preregistration
  with an audit in dossier form. Whether C2 accepts it as the
  discovery record is a ratification decision (§9, D-G4-2),
  not a fact this draft may assume.
- **G-3: all existing use-evidence is the discoverer's own.**
  Stage I/v4 measured transfer across *tasks* by the
  configuration that ran the discovery. Per the design's own
  observation, that contributes **nothing** to C3: scored
  today, the honest ceiling is `LINEAGE_ONLY` (and strictly,
  with no dossier assembled and no G4 instrument built, the
  gate simply remains NOT_ASSESSED). This dossier exists to
  create the missing species: use by a successor that never
  discovered.

## 3. The actors

- **Predecessor:** the Stage I/v4 discovering configuration —
  identified in the lineage record by the discovery module's
  identity (the composition-discovery lineage build) and by
  its run record (the v4 evidence file and its driver).
- **Successor:** a **fresh variant** registered in the
  population archive, whose solver configuration is the greedy
  solver + the authored baseline catalog (`grid_variants` /
  `_OPERATORS`) — the same code the predecessor's baseline arm
  used — and which has **never invoked discovery**. It is a
  new archive entry with a recorded parent link to the
  predecessor, created for this dossier; it is not a tuned
  descendant (any other difference from the predecessor's
  solver would confound attribution, §8 A2).
- **Inheritance event:** the materialised catalog artifact
  (§2 G-1) is delivered to the successor as data. At load, the
  runner verifies the artifact's digest against the lineage
  record; a mismatch aborts the run as an integrity failure.
  *Using* the artifact means the successor's solver applies
  the admitted keys/chains through the existing apply path
  (`apply_operator` / `apply_chain`). The boundary is stated
  plainly: `apply_*` is use; `discover_*` is discovery. The
  successor's run must not call any `discover_*` function —
  the run record attests this (§7, P-G4-5).

## 4. The C3 evaluation

- **Universe:** a **fresh-seed** grid universe
  (`grid_generalization.build_universe(seed=<new seed fixed in
  the preregistration>)`). Neither arm's history has touched
  its tasks; the discovering configuration has never seen
  them either. Run-integrity gates from the Stage F v3
  protocol apply (catalog-control validity line; null control
  at zero) — a universe that fails its validity gates
  invalidates the run, as Stage F's first two rounds honestly
  invalidated themselves.
- **Capability tasks:** the universe's `new_only` single-defect
  tasks in the four discovered classes (the classes outside
  the authored catalog), plus its mixed 2-defect tasks
  reported separately. Required: ≥40 capability singles; if
  the fresh seed yields fewer, a second seed is added by
  preregistration amendment **before** any run — never after
  seeing scores.
- **Arms (the attribution control):**
  - **WITH:** successor + inherited catalog artifact.
  - **WITHOUT:** the identical successor, baseline catalog
    only.
  Same tasks, same solver, same budgets; the *only* difference
  is the artifact's presence.
- **Regression control:** the universe's `catalog_control`
  tasks under both arms; the WITH arm must not solve fewer
  than the WITHOUT arm.

## 5. Margin and decision rule (fixed here, before results)

The WITH arm's effect counts as **inheritance demonstrated**
iff all three hold on the audited evaluation report:

1. **Δ ≥ +20 percentage points** (WITH − WITHOUT solved
   fraction on capability singles). Rationale: the discovering
   configuration's own measured effect on its evaluation
   singles was ≈ +32 pp (0 → 15/47); a successor genuinely
   using the artifact should retain a clear majority of that
   effect on a fresh universe, and +20 pp is far above
   one-task noise at n ≥ 40 (one task ≈ 2.5 pp).
2. **WITH-arm absolute floor:** solves ≥25% of capability
   singles (a large Δ over a near-zero base, e.g. 2% → 24%,
   is not the capability the predecessor discovered).
3. **Attribution ceiling on the WITHOUT arm:** solves ≤10% of
   capability singles. Stage F measured every baseline arm at
   0/47 on these classes; if the successor solves them
   *without* the artifact at any real rate, the effect cannot
   be attributed to inheritance and C3 is not demonstrated —
   whatever Δ says.

Outcome mapping:

| C1 | C2 | C3 (all three §5 conditions + no control regression) | Outcome |
|---|---|---|---|
| pass | pass | pass | `INHERITANCE_DEMONSTRATED` |
| pass | pass | fail / not run | `LINEAGE_ONLY` |
| fail | any | any | `NOT_DEMONSTRATED`, items named |
| pass | fail | any | `NOT_DEMONSTRATED`, items named |

No re-runs until green; a `LINEAGE_ONLY` result is a
publishable measured outcome (it is, today, the design's own
prediction), and a failed attribution ceiling is a finding
about the successor or the universe, recorded as such.

## 6. Dossier contents (what a future G4 instrument scores)

- `lineage_record` — export from a `PopulationArchive`:
  predecessor candidate record, successor candidate record
  (parent link to predecessor), capability artifact attached
  to the link, and the archive's integrity verification
  (hash-chain audit result, must be clean).
- `capability_record` — the materialised catalog artifact
  file, its SHA-256 digest, and its discovery record
  reference (the v4 evidence file + driver identity, or the
  preregistered re-run's report per D-G4-2).
- `evaluation_report` — protocol hash back-reference, kernel
  audit (CLEAN), artifact digest as loaded by the successor
  (must equal the capability record's), universe seed, task-id
  lists per arm set, per-arm solved counts/fractions on
  capability singles, mixed, and control, wall time, runner
  identity, and the no-discovery attestation (§3).
- `audit` — kernel audit output over the above.
Criteria version recorded on the assessment by the
instrument, per the G1/G3 pattern.

## 7. Prerequisites (all must close before preregistration)

- **P-G4-1 — the G4 instrument exists.** No `g4_instrument.py`
  has been built. Build it per PR #136's implementation note
  (pure scorer, per-clause named failures, criteria version;
  adversarial synthetic tests: broken lineage chain, a
  "successor" that re-discovers instead of inheriting, a
  dossier missing the control arm). Synthetic dossiers only;
  no live application in the build — the G3 instrument's
  path, repeated.
- **P-G4-2 — catalog materialisation.** Deterministic
  materialiser: admitted keys/chains from the chosen
  discovery record → canonical catalog file + digest (§2
  G-1). The materialiser's output on the v4 evidence must be
  reproducible byte-for-byte by an independent re-run.
- **P-G4-3 — lineage records created.** A dedicated
  `PopulationArchive` root for this dossier (not the pilot
  archives): register the predecessor configuration, the
  capability artifact, and the successor variant with its
  parent link; archive integrity verification passes.
- **P-G4-4 — fresh universe validated.** The chosen seed's
  universe passes the Stage F validity gates on paper
  (counts per subset; control/null behaviour as specified by
  that protocol) before preregistration fixes it.
- **P-G4-5 — successor runner with discovery exclusion.** The
  runner loads the artifact by digest, runs both arms, and
  produces a run log from which the absence of `discover_*`
  calls is auditable (import/call discipline stated in the
  preregistration).

## 8. Risks and ambiguities (named, not resolved)

- **A1 — Discovery-record species (the D-G4-2 question).**
  Accepting stage evidence (v4) as C2's discovery record is
  cheaper and honest about provenance, but weaker than a
  kernel-preregistered discovery re-run (~22 min of compute
  plus custody work). The draft recommends acceptance *with
  the provenance stated in the dossier*, because C2's text
  requires identity match to "the record of its measured
  discovery" — and v4 *is* that record; fabricating a fresher
  pedigree for the same catalog would be worse. The
  coordinator decides.
- **A2 — Successor purity vs realism.** A fresh instance of
  the same solver is the cleanest attribution and the least
  "evolutionary" reading of *successor variant*. A descendant
  with independent changes would be a richer claim and an
  unattributable one. This draft chooses attribution; a
  later dossier can strengthen the successor definition.
- **A3 — Catalog version.** v4 admitted sets (with chains)
  are the current mechanism's output; v2's singles-only sets
  are superseded. The materialisation (P-G4-2) names v4;
  choosing otherwise must be a stated decision, not an
  accident of which evidence file is nearest.
- **A4 — Fresh universe, same classes.** The four capability
  classes are defined relative to the authored catalog, so a
  fresh seed varies tasks, not classes. A successor solving
  them shows inheritance of *this* catalog; generalisation to
  new classes remains G3's neighbouring question, and this
  dossier must not be quoted as answering it.
- **A5 — Archive semantics.** `PopulationArchive` registers
  *candidates* and *evaluations*; attaching a capability
  artifact "to the link" is this dossier's modelling choice
  (artifact as a registered record referenced by both
  candidate records). If the archive's schema resists that
  shape, the lineage record format is amended **before**
  preregistration, with the archive's integrity properties
  (parent-must-exist, hash chain) non-negotiable.
- **A6 — The WITHOUT arm could learn.** If the successor's
  solver had any cross-task memory within a run, the WITHOUT
  arm run *after* the WITH arm could inherit through the
  experiment itself. Arms are therefore run as separate
  processes with no shared state, order fixed in the
  preregistration (WITHOUT first is the conservative order).

## 9. Decisions requested at ratification

- **D-G4-1 — Artifact:** the v4 admitted operator catalog
  (operators + chains), materialised per P-G4-2.
- **D-G4-2 — Discovery record:** accept the v4 stage evidence
  as C2's discovery record, provenance stated (recommended,
  §8 A1) — or require a preregistered discovery re-run.
- **D-G4-3 — Margin:** §5 as written (+20 pp Δ, ≥25%
  WITH-arm floor, ≤10% WITHOUT-arm ceiling, zero control
  regression).
- **D-G4-4 — Successor:** fresh archive variant, same solver
  code, differing from the predecessor only by not having
  discovered (§8 A2).
- **D-G4-5 — Universe:** fresh seed, ≥40 capability singles,
  Stage F validity gates as run-integrity checks.

## 10. Execution order (after ratification)

1. Ian: build the G4 instrument (P-G4-1), synthetic only.
2. Ian/director: materialise the catalog + digest (P-G4-2);
   create the lineage archive records (P-G4-3).
3. Director: validate the fresh universe (P-G4-4); build the
   successor runner (P-G4-5).
4. Director: kernel preregistration from the ratified text.
5. Runner (the measured mechanism, not an external brain —
   two-hats rule): execute both arms under custody.
6. ila: assemble the dossier (§6), score with the G4
   instrument, independent verification before any figure
   reaches the owner.

— End of draft. Awaiting ratification; ambiguities above are
findings, not silent resolutions.
