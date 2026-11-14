# ACE G4 + G5 Measurement Instruments — Design (Stage L1, design only)

Status: DESIGN. This document defines how G4 and G5 will be
measured. It claims no result. Both gates remain
**NOT_ASSESSED** until dossiers are assembled and scored by
implementations of this design. (Director cycle #4, agenda
item 3.)

## Part I — G4: lineage and inherited capability

PRD v0.1, §3: **"G4 — Evolusi: menyimpan silsilah varian dan
membuktikan bahwa varian penerus dapat menggunakan kemampuan
yang ditemukan pendahulunya."** — Store the lineage of
variants, and prove that a successor variant can use a
capability its predecessor discovered.

The clause has two halves with different evidence species:
lineage *storage* (an engineering property of the archive) and
*inheritance in use* (a research-evidence property — the PRD
§3 distinction applies: storing is not using).

### Operational definitions

- **Variant:** an identified solver/mechanism configuration in
  the population archive (OMEGA-08), with a recorded parent
  link (or a recorded root).
- **Discovered capability:** an artifact a variant produced
  through a measured discovery process — e.g. an admitted
  operator from Stage I — identified by name + digest, with
  its admission evidence attached.
- **Successor:** a variant that did not itself run the
  discovery process for that capability (a fresh instance or a
  sibling/descendant lineage entry). If the "successor"
  re-discovers the capability itself, that is discovery, not
  inheritance.

### Clauses (fail-closed; dossier of sealed evidence)

- **C1 — lineage stored and auditable.** The dossier's lineage
  record links predecessor → successor with the capability
  artifact attached; the archive's integrity check passes
  (hash chain / audit clean).
- **C2 — capability identified with admission evidence.** The
  capability artifact's identity (name + digest) matches the
  record of its measured discovery (e.g. the Stage I admission
  record: fixes ≥2 independent pool tasks, transfer measured).
- **C3 — successor use, with attribution control.** A
  preregistered, audited evaluation shows: (i) the successor
  *with* the inherited artifact scores above the preregistered
  margin on held-out tasks requiring that capability; and
  (ii) the same successor *without* the artifact scores at
  baseline on the same tasks. Both arms are required — without
  the control, the effect cannot be attributed to inheritance.

### Outcomes

- **INHERITANCE_DEMONSTRATED** — C1–C3 pass.
- **LINEAGE_ONLY** — C1–C2 pass, C3 not demonstrated: the
  archive remembers, but no successor has been shown to use
  what it remembers. (This is the honest current reading if
  scored today: operators are archived with lineage, and
  Stage I measured transfer across *tasks* by the discovering
  configuration itself — not use by a successor variant.)
- **NOT_DEMONSTRATED** — lineage incomplete or capability
  unidentified, missing items named.

## Part II — G5: owner accessibility

PRD v0.1, §3: **"G5 — Aksesibilitas: pemilik dapat membaca
ringkasan hasil dan keputusan penelitian melalui HP, tanpa
kewajiban meninjau implementasi teknis."** Supported by FR-09
(summaries in Indonesian: what was tried, the result, the
confidence level, the limits of interpretation) and FR-14
(comparisons, resource status, and evolution history on a
phone screen). G5's evidence species is a *delivery and
comprehension record*, not an experiment report; the
instrument scores ACE's reporting artifacts, not impressions.

### Clauses (fail-closed)

- **C1 — a compliant summary exists for the assessed unit.**
  For each assessed stage/decision, a summary artifact exists
  carrying all four FR-09 fields (tried / result / confidence /
  limits) in Indonesian, in plain language. A missing field is
  a named failure.
- **C2 — phone-delivered without a technical detour.** The
  summary reached the owner through a channel they read on
  their phone (in current practice: the discussion-room
  reports), and understanding the result and the decision from
  the summary alone requires opening no code, PR, or technical
  document.
- **C3 — comprehension evidenced by use.** The record shows
  the owner acting on summaries alone — a decision, direction,
  or correction issued in response to a summary, whose content
  references the summary's claims (not implementation
  details). This is the clause that separates "summaries were
  sent" from "the owner can read and use them", and it is
  scored from recorded owner responses, never assumed.

### Outcomes

- **ACCESS_DEMONSTRATED** — C1–C3 pass for the assessed
  period's units.
- **DELIVERY_ONLY** — summaries exist and were delivered
  (C1–C2) but no recorded owner use evidences comprehension.
- **NOT_DEMONSTRATED** — summaries missing fields or missing
  entirely, items named.

Design-stage observation (not a score): current practice
already routes every stage result to the owner as an
Indonesian discussion-room summary, and the owner's direction
amendments (Rp0 discipline, multi-brain sovereignty,
Emancipation) were decided from those summaries without code
review — plausible C3 evidence. It stays an observation until
an implemented instrument scores a defined dossier; among
other gaps, today's summaries are not uniformly structured
against the four FR-09 fields, which C1 would score strictly.

## Implementation note

Both scorers follow the G1 instrument's shape: pure functions
over evidence-file paths, per-clause verdicts with named
missing items, a criteria version, and adversarial tests
(broken lineage chain, successor that re-discovers instead of
inheriting, missing control arm, summary missing the
confidence field, delivery without recorded use).
