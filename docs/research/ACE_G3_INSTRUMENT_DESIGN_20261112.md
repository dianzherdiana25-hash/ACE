# ACE G3 Measurement Instrument — Design (Stage K3, design only)

Status: DESIGN. This document defines how G3 will be measured.
It claims no result. G3 remains **NOT_ASSESSED** until a dossier
is assembled and scored by an implementation of this design.

## 1. The clause under measurement

PRD v0.1, §3: **"G3 — Generalisasi: menguji apakah perbaikan
berpindah ke sedikitnya dua keluarga masalah yang berbeda;
perbaikan di satu keluarga saja dicatat sebagai spesialisasi."**
— Does an improvement transfer to at least two different
problem families? Improvement confined to one family is
recorded as *specialization*.

The PRD's own framing (§3) applies: G3 is a *research-evidence*
gate, not an engineering-acceptance gate. A mechanism working
as specified does not pass G3; only measured transfer does. The
PRD preamble's warnings — selection distorted by test leakage
and reward hacking — are design constraints below.

## 2. Operational definitions

- **Problem family:** a task universe produced by one generator
  with one task/defect mechanism class (the OMEGA-10 curriculum
  sense: pricing, shipping, grid are three families). Levels,
  sizes, seeds and difficulty variants inside one generator are
  NOT families. Two families are distinct when their generators
  and solution mechanisms differ.
- **Improvement:** a specific, identified delta — a mechanism,
  substrate, operator set, or method — whose benefit over a
  named baseline has been measured in a source family. An
  improvement must exist and be identified before "transfer"
  has a subject.
- **Transfer:** the *same* improvement, unchanged, produces a
  positive measured effect in another family. Identity is
  by artifact: same name + same digest/version across family
  evaluations. Any per-family retuning, re-authoring, or
  family-specific configuration between evaluations breaks
  identity; the evaluation then measures a new improvement, not
  transfer of the old one.
- **Baseline:** the same family's task set solved without the
  improvement (the pre-improvement mechanism or a null arm),
  measured under the same custody as the improvement arm.

## 3. Clauses (fail-closed, mechanically scorable)

The instrument scores a **dossier** of sealed evidence files —
preregistered experiment reports with kernel audits — never
self-declared claims. A missing or unparseable item is a named
failure, never a default pass (the G1 instrument pattern).

- **C1 — an identified improvement with a measured source
  effect.** The dossier names the improvement artifact
  (name + digest/version) and includes a preregistered report
  (protocol hash present, kernel audit CLEAN) showing a
  positive effect over the named baseline in the source family.
- **C2 — the same improvement evaluated in ≥2 distinct
  families.** For at least two families distinct per §2, the
  dossier includes an evaluation report whose improvement
  identity matches C1's exactly, whose tasks are held out from
  the improvement's development, and whose protocol was
  preregistered before results.
- **C3 — positive transfer effect in ≥2 families.** In at
  least two of the C2 families, the improvement's held-out
  score exceeds the family baseline by the margin/decision
  rule fixed in that family's preregistration. Effects are
  counted per family from audited reports only.

## 4. Outcome vocabulary

- **TRANSFER_DEMONSTRATED** — C1, C2, C3 all pass: the same
  improvement shows a positive audited effect in ≥2 families.
- **SPECIALIZATION** — the improvement is real (C1 passes) and
  exactly one family shows a positive transfer effect. This is
  the PRD's own category, a measured result, not an instrument
  failure.
- **NOT_DEMONSTRATED** — zero families with a positive effect,
  or the dossier is incomplete (with the missing items named).

## 5. Anti-leakage and honesty constraints

- Held-out custody: evaluation tasks must not have been used
  to develop, tune, or select the improvement (the split-custody
  kernel pattern from OMEGA-06 applies unchanged).
- Preregistration before results for every family evaluation;
  the margin/decision rule is fixed there, not after seeing
  scores.
- Identity discipline (§2) is the reward-hacking guard: quietly
  re-authoring the "same" method per family is the likeliest
  way to fake transfer, so identity is checked by digest, not
  by name alone.
- A null or negative transfer result is a publishable measured
  outcome (cf. G2's two nulls), recorded as NOT_DEMONSTRATED or
  SPECIALIZATION as the evidence dictates — never re-run until
  green.

## 6. Where today's evidence stands (design-stage observation, not a score)

No dossier has been assembled; nothing here is a G3 claim. For
orientation only: the strongest current candidate improvement
is the operator-discovery mechanism (Stage I). Its measured
effect is inside one family (grid — across four defect
*classes*, which are not families), so under this design the
present state would read as at most SPECIALIZATION if scored
today. The natural first application, a separate future stage:
preregister a two-family dossier in which the discovery
mechanism — artifact-identical — is applied to grid and to a
second family (e.g. pricing expression repair), with each
family's baseline and margin fixed in advance.

## 7. Implementation note

The implementation, when staged, follows the G1 instrument's
shape: a pure scorer over evidence-file paths, an outcome
object carrying per-clause verdicts with named missing items
and a criteria version, and adversarial unit tests (incomplete
dossier, identity mismatch across families, single-family
effect → SPECIALIZATION, unaudited report rejected).
