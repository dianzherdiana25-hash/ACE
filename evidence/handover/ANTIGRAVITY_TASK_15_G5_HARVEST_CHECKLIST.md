# ANTIGRAVITY TASK 15 — VERIFICATION CHECKLIST: G5 HARVEST (the dossier before the instrument)

For the independent checker of a G5 harvest — the
Antigravity bench verifies a harvest executed by the named
harvester (per the ratified split, Task 09 P-G5-2: harvest
by Ian or the operations post, verification by this bench —
or the equivalent split recorded in the preregistration).
Written **before** any harvest is ordered: the standard
exists before the act it checks, the program pattern this
series completes. Design sources: the ratified G5 dossier
design (Task 09, decisions D-G5-1..5, harvest axiom locked)
and the G5 instrument build brief (Task 12), whose dossier
schema this checklist verifies the harvest against.

Every item is checked against the record itself and the
checker's own re-derivations, never the harvester's report
alone. Record per item: PASS / FAIL / NOT VERIFIED, with
evidence. **The checker verifies the harvest, not the
outcome:** no item in this checklist asks what `assess_g5`
will conclude.

---

## Section 0 — Mandate, window, identities (before anything is scored)

- [ ] 0.1 A preregistration (or ratified harvest order)
      exists naming: the period rule, `period_start` /
      `period_end`, the thresholds (C1 0.90 · C2 0.90 · C3
      ≥3 events / ≥2 domains / correction required), the
      harvester, the two scorers, and the checker. The
      harvest may not predate this record.
- [ ] 0.2 The window is the ratified rule's window
      (Emancipation, 2026-11-12 evening → the named cutoff),
      not a window fitted to the record: compare the stated
      bounds against the rule; any deviation is a finding.
- [ ] 0.3 **Harvester ≠ author, pre-checked:** the named
      harvester does not appear among the authors of the
      assessed summaries (`summary_author_ids`). This is
      verified *before* the harvest runs and again at
      sealing (Section E) — a harvest discovered after the
      fact to be self-harvested is GAGAL, not curable.
- [ ] 0.4 The harvest axiom is restated in the harvest
      report: evidence harvested retrospectively from the
      existing record; nothing staged, solicited, edited,
      or re-sent for the owner.

## Section A — Enumeration integrity (the denominator)

- [ ] A.1 The unit list was derived by the ratified
      mechanical rule: every discussion-room message in the
      window that reports a stage result, a measured
      finding, or a program decision is a unit; nothing else
      is. The rule is quoted verbatim in the harvest report.
- [ ] A.2 **Independent re-derivation:** the checker
      re-enumerates the window from the chat record and
      diffs against the harvester's list. A unit present in
      the record but missing from the list, or a listed item
      that is not a unit under the rule, is a named finding
      with its message reference.
- [ ] A.3 Every unit's `message_ref` resolves to a real
      message whose timestamp falls inside the window and
      whose author is the recorded `author_id`. Unresolvable
      or out-of-window references fail by name.
- [ ] A.4 No unit appears twice (same message harvested
      under two ids); no unit's text differs from the record
      (spot-verified here, digest-verified in Section E).
- [ ] A.5 Exclusions under the rule (pure conversation,
      greetings, raw reports in other rooms) are applied
      **uniformly**: the checker samples excluded in-window
      messages and confirms each exclusion follows from the
      rule's text, not from the message's expected score.

## Section B — Rubric purity (two scorers)

- [ ] B.1 Two scorers scored **independently**: separate
      rubric sheets per scorer, produced before either saw
      the other's (timestamps / file history evidence it).
      A single sheet with two signatures fails this item.
- [ ] B.2 The rubric applied is Task 09 §4's anchor text,
      verbatim: field present only if extractable from the
      summary alone; a field carried only by a PR number,
      digest, or file path is **absent**. Sheets that apply
      softer paraphrases are a finding.
- [ ] B.3 Every field judgement on every unit carries its
      anchor basis (the scorer's note names what in the text
      satisfies or fails the anchor) — a bare tick is not a
      judgement the checker can audit.
- [ ] B.4 **Disagreement log:** per-unit per-field
      disagreements between the two scorers are listed, and
      each resolution cites the rubric anchor that decides
      it. Resolutions by averaging, seniority, or "agreed to
      pass" fail this item. Disagreement counts are stated
      in the harvest report (they are part of the dossier's
      honesty about A1 rubric softness).
- [ ] B.5 **Checker re-score:** the checker independently
      re-scores ≥⅓ of units (chosen by the checker, spread
      across the window) plus **all** units whose fields were
      disputed. A re-score that changes any unit's
      completeness is a named finding; a pattern of them is
      GAGAL for the harvest's rubric purity.

## Section C — Use-event candidates (enumerate, then score)

- [ ] C.1 The candidate list was derived by enumerating
      **all** owner decision / direction / correction
      messages in the window first. Cross-check: every owner
      act cited by the program's own records in the window
      (checkpoint addenda, the decisions log) appears in the
      list; a cited act missing from the list is a named
      finding.
- [ ] C.2 Each candidate carries the owner's quoted words
      and a resolvable message reference. A candidate whose
      quote cannot be found in the record fails by name.
- [ ] C.3 The three tests (sequence · reference · action)
      are applied per candidate and recorded per candidate —
      including **which test failed** for every
      non-qualifier. Non-qualifiers remain in the dossier as
      warnings with their failing test named; **a candidate
      that has vanished from the list is the gravest finding
      in this section** (silent curation of the denominator).
- [ ] C.4 Exclusions are applied by the ratified action-type
      vocabulary (acknowledgement / owner_initiative /
      bare_approval never qualify), not by scorer judgement
      about an event's importance. An excluded *contentful*
      act (an approval that amends) must appear scored as an
      action, per the ratified rule.
- [ ] C.5 Domain labels come from the ratified domain set
      (governance · resources/funding · operations ·
      venues/business · technical direction); invented
      domains that would inflate the ≥2-domain bar are a
      finding.

## Section D — The harvest fences

- [ ] D.1 **No staging:** during the harvest's execution,
      no owner-facing message was sent by the harvester (or
      at the harvester's request) soliciting a response,
      decision, or reaction for evidence purposes. The
      checker scans the record across the execution window.
      Any such message is automatic GAGAL — the harvest
      manufactured its evidence.
- [ ] D.2 **No editing:** no assessed message was edited,
      re-sent in improved form, or deleted-and-replaced
      after the window was fixed. Where the platform exposes
      edit state, it is checked; the sealed digests
      (Section E) are the standing guard thereafter.
- [ ] D.3 **No burden:** the harvest required nothing of the
      owner — no question, task, or approval was routed to
      him as part of it. (Routine program reporting that
      would have happened anyway is not burden; anything
      *because of the harvest* is.)
- [ ] D.4 The dossier stays inside the program's records:
      the owner's quoted words are used only within the
      dossier and the checkpoint lineage, with no external
      disclosure.

## Section E — Sealing and schema conformance

- [ ] E.1 Dossier files conform exactly to the Task 12
      schema (`dossier.json` · `harvest_report.json` ·
      `units.json` · `use_events.json`); every cross-reference
      resolves (each event's `references_unit` names an
      existing unit; timestamps parse; all timestamps inside
      the window or flagged as out-of-period warnings).
- [ ] E.2 **Threshold fidelity:** the threshold values in
      `harvest_report.json` equal the ratified values of
      Section 0.1 character-for-character in substance
      (0.90 / 0.90 / 3 / 2 / correction-required). A softer
      value in the file is automatic GAGAL — thresholds are
      ratified, never harvested.
- [ ] E.3 `sealed_digests` are present and the checker
      recomputes them over the final files: identical. The
      checker also recomputes one unit's and one event's
      `content_digest` from the underlying message text:
      identical.
- [ ] E.4 The two-hats fence value-check: `harvester_id` ∉
      `summary_author_ids` **in the sealed file itself** (the
      instrument will enforce it mechanically; the checker
      confirms the harvest does not rely on hoping so).
- [ ] E.5 Smoke conformance: `assess_g5` (once built) reads
      the sealed dossier without a schema error. The
      checker's smoke run records only that it *ran* — the
      outcome belongs to the assessment step, not to this
      verification, and is not reported here.

## Section F — Verifier probes (checker-run, outputs recorded)

- [ ] F.1 **Presence probe:** checker picks 3 in-window
      consolidated summaries at random from the record → all
      3 present in the unit list with correct refs.
- [ ] F.2 **Candidacy probe:** checker picks 2 owner acts
      cited in checkpoint records within the window → both
      present as candidates, with per-test scoring recorded.
- [ ] F.3 **Warning probe:** at least one known
      non-qualifying candidate (e.g. a bare acknowledgement)
      is present **as a warning with its failing test** — its
      absence suggests the list was curated, and triggers a
      full Section C re-derivation.
- [ ] F.4 **Digest probe:** recompute one sealed digest from
      the file bytes and one content digest from message
      text (as E.3, recorded here as an independent probe
      result).
- [ ] F.5 **Solicitation scan:** full read of the
      harvester's owner-facing messages during the execution
      window → zero evidence-soliciting messages (D.1's
      probe form).

## Section G — Verdict

```
Harvest under check: <period> · harvester <id> · sealed <date>
Checker: antigravity bench (independent of harvester & authors)
Overall: TAHAN / GAGAL / BELUM TERVERIFIKASI
Findings: <numbered; each with section ref + evidence>
Re-derivations: units <n listed / n re-derived>; re-scored <n>
Probes: F1–F5 results
```

TAHAN requires Sections 0–F to pass. **Automatic GAGAL**
(not minor): a missing unit (A.2), a vanished candidate
(C.3), harvester-is-author (0.3/E.4), any staging or
solicitation (D.1/F.5), edited evidence (D.2), or thresholds
softer than ratified (E.2).

— End of checklist. With this document, every action the
program will one day have scored — instrument build,
substrate freeze, application run, harvest — has its
checker's standard written before it runs.
