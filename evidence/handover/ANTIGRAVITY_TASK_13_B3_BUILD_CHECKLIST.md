# ANTIGRAVITY TASK 13 — VERIFICATION CHECKLIST: B-3 PRICING SUBSTRATE BUILD + FREEZE (expanded generator)

For the two independent checkers of the B-3 stage —
operations post (first checker), Antigravity bench (second
checker), the adopted pattern. Written **before** the freeze
lands, per the Task 03 lesson: the checker's standard exists
before the thing it checks. Design sources: the Task 06 B-3
substrate design (probe protocol §3, control §4, freeze §5,
risks B3-R1..R6) and the hub's ratified **case-grid-only**
expansion lever (2026-11-13).

Every item is checked against the build on disk and the
checker's own runs, never the builder's report alone.
Record per item: PASS / FAIL / NOT VERIFIED, with evidence.

**Stage state this checklist assumes (verify in Section 0):**
substrate v1 was authored and probed on the *original*
216-program universe (probe 216/216; generic comparator also
216/216 — the saturation that forced the lever decision).
That probe is **history**, not the freeze candidate. The
freeze candidate is the (substrate, **expanded** generator)
pair: per Task 06 B3-R3, a generator change invalidates a
freeze until re-probed.

---

## Section 0 — Stage state, tree, baseline

- [ ] 0.1 Identify from disk: substrate branch/worktree,
      HEAD, the expansion commit(s), the probe report(s),
      the freeze record. State explicitly which substrate
      version is under check and which generator version it
      binds (original vs expanded ranges).
- [ ] 0.2 The v1-on-216 probe record is preserved unedited
      as history (substrate 216/216, comparator 216/216,
      saturation finding) — not deleted, not re-labelled as
      the expanded-universe result.
- [ ] 0.3 Builder's pre-build sweep baseline recorded;
      right-tree caution applies as usual.
- [ ] 0.4 Brain-of-origin of the substrate build and of the
      expansion recorded in commits / stage report.

## Section A — Scope: the expansion is case-grid only

- [ ] A.1 The generator diff is confined to
      `_pricing_family`'s **parameter ranges** (the case
      grid: the value sets the generator draws from).
      Enumerate the diff hunks; any other change is a
      finding.
- [ ] A.2 Defect classes after expansion are **exactly** the
      original three (`threshold_boundary`, `tax_basis`,
      `member_basis`) — no new defect class, verified by
      enumerating the defect functions before/after.
- [ ] A.3 The reference function's semantics are unchanged
      (same computation; only the drawn parameter values
      widened) and no template/structure of generated code
      changed — diff inspection, plus the substrate's unit
      test "reference produces no variants" still green.
- [ ] A.4 Substrate diff scope: substrate module + its tests
      + evidence/freeze artifacts only; nothing else in the
      stage's diff.

## Section B — The one-expansion fence

- [ ] B.1 **Exactly one expansion event.** From history
      (commit order + timestamps), the parameter ranges were
      widened **once**, and that event precedes every
      expanded-universe probe run and the census. Any range
      change after a probe/census result existed is serial
      widening — automatic GAGAL (Section G).
- [ ] B.2 The widened ranges are recorded **numerically** in
      the freeze report, alongside the hub ratification
      reference for the case-grid lever.
- [ ] B.3 **Principled basis stated:** the freeze report
      states *why these bounds* (e.g. the magnitudes the
      cases must span for the comparator's case-count to
      discriminate) in terms fixed independently of the
      expanded probe's outcome. A rationale written as
      "widened until the comparator failed" is tuning, and
      fails this item.
- [ ] B.4 If the expanded universe still saturates (probe or
      P4 evidence), the recorded path is a **new version
      cycle** (new probe band, new census) or the D6
      shipping path at the dossier level — never a second
      widening of the frozen version. The stage report must
      not present a re-widened freeze as the same version.

## Section C — Probe integrity on the expanded universe

- [ ] C.1 **Fresh probe set.** The probe set for the
      expanded universe was fixed by a seed band declared
      **before** any operator-revision work against the
      expanded universe, and the band is disjoint from: the
      v1 probe band, the discovery-pool band, the evaluation
      band, and the calibration band. The set (task ids +
      program digests) is recorded in evidence *before* the
      probe run's results.
- [ ] C.2 **One-shot per version.** If any expanded-universe
      probe run predates the recorded one and operators
      changed after it, the version must have bumped (new
      band, preserved old run). A re-probe of a revised
      substrate on the same band = tuning-to-the-probe —
      automatic GAGAL.
- [ ] C.3 Composition: ≥50 unique programs (dedup by
      `normalized_form`), every single-defect class and
      every pair class represented ≥5 times; the singles
      share is consistent with the re-derived caps
      (Section F) or the discrepancy is named.
- [ ] C.4 Arms exactly as designed: comparator =
      `solver_token_search` at budget 400; substrate =
      `solve_pricing` under the same ceiling; both arms see
      shown cases only; holdout judged by the lab verifier
      over all cases, for both arms.
- [ ] C.5 **Bar:** substrate solves ≥95% of the probe set on
      holdout **including all single-defect tasks**. The
      comparator's number is recorded as context with no bar
      — including, honestly, if it still saturates (a
      P4-relevant finding for the dossier stage, not a probe
      failure and not a licence to re-widen, per B.4).
- [ ] C.6 The stage report carries the epistemic label
      (operators *reach* the three classes; nothing claimed
      about unseen classes or transfer) and per-task results
      for both arms in evidence, with wall time.

## Section D — Freeze and digest bundle

- [ ] D.1 The freeze bundle is complete, per Task 06 §5:
      SHA-256 over the canonical bundle — substrate module
      bytes · ordered `_OPERATORS` generator names · solver
      parameters (`max_rounds`, frontier width) · probe
      report digest · **`curriculum_lab` generator digest at
      freeze time**.
- [ ] D.2 **The generator digest binds the EXPANDED
      generator.** The checker recomputes the
      `curriculum_lab` digest from the frozen tree and
      confirms it corresponds to the widened ranges recorded
      in B.2 (recompute after mentally reverting the ranges
      must give a *different* digest — probe E2 tests the
      sensitivity mechanically).
- [ ] D.3 The checker independently recomputes **every**
      component digest from disk; all match the freeze
      record exactly. Any mismatch is named, never waived.
- [ ] D.4 This digest is the value the P2 adapter exposes as
      `baseline_catalog_id` and the value a future G3
      preregistration will name as the pricing baseline —
      cross-check the references agree character-for-character.
- [ ] D.5 The freeze is recorded in the checkpoint lineage
      (Addendum) with the coordinator's ratification and the
      version label (pricing substrate v1-on-expanded, or
      the version the stage actually declares — the label
      must not claim the on-216 probe as this freeze's bar
      evidence).
- [ ] D.6 **Post-freeze immutability:** no commit after the
      freeze commit touches the substrate module, its
      operators, solver parameters, or the generator ranges.
      Any such commit is either a declared version bump
      (new probe, new digest, new freeze record) or GAGAL.

## Section E — Verifier probes (checker-run, outputs recorded)

- [ ] E.1 **Digest sensitivity (substrate):** in a scratch
      copy, alter one operator parameter → recomputed bundle
      digest differs from the freeze record.
- [ ] E.2 **Digest sensitivity (generator):** in the same
      scratch copy, revert one widened range to its original
      value → generator digest differs. (Proves the freeze
      actually binds the expansion.)
- [ ] E.3 **Census reproducibility:** the checker re-runs
      the stage's census method against the frozen expanded
      generator → totals, singles/pairs split, and per-class
      counts identical to the census report (Section F).
- [ ] E.4 **Probe custody spot-check:** sample 5 probe
      programs; verify each belongs to the declared band /
      expanded universe and appears in no authoring or
      tuning artifact.
- [ ] E.5 **Control-population property:** sample 5 programs
      from the recorded frozen solved population → the
      frozen substrate solves all 5 on holdout (the 100%
      control property of Task 06 §4).

## Section F — Official census (B3-R5) and re-derived caps

- [ ] F.1 The official census runs over the **frozen
      expanded** generator and reports: total unique
      programs, singles/pairs split, per-defect-set counts,
      and saturation behaviour (seeds drawn, where growth
      stops) — the Task 07 method, on the new universe.
- [ ] F.2 **Caps re-derived:** CAP-1/2/3 are recomputed from
      the new totals with worst-case arithmetic shown
      (singles demand vs singles supply, per class), in the
      census report itself.
- [ ] F.3 The census report **explicitly supersedes** the
      Task 11 preregistration draft's §4 placeholder numbers
      and states the re-derived allocation table that a
      submission must use. (Any quote of the old 216-based
      numbers after this report must carry their
      placeholder status.)
- [ ] F.4 Control feasibility re-checked against the frozen
      solved population: the ≥30 control draw with the
      re-derived CAP-1 is actually drawable (singles share
      and pairs availability from the *solved* population,
      not just the universe).
- [ ] F.5 Sequencing (B3-R3): the report records that all
      generator-changing levers are now decided and frozen —
      the case-grid expansion was the last one — so a
      subsequent P4 calibration cannot burn the freeze with
      a generator lever. Any P4 lever still open that would
      change the generator is named as a freeze risk.

## Section G — Tests, sweep, verdict

- [ ] G.1 Substrate unit tests green (variants change code
      and parse · reference produces no variants · solver
      repairs single and pair defects — plus any
      expansion-specific tests), run directly by the checker.
- [ ] G.2 Full package discover sweep: after = baseline +
      new tests; skip profile matches; runtime recorded.
- [ ] G.3 Verdict form (each checker files independently):

```
Stage under check: B-3 freeze <version> @ <freeze commit>
Checker: <operations post | antigravity bench> (independent)
Overall: TAHAN / GAGAL / BELUM TERVERIFIKASI
Findings: <numbered; each with section ref + evidence>
Digests re-measured: bundle <match/mismatch>; generator <…>
Census re-run: <identical / differs — numbers>
Probe bar re-checked: <substrate % / singles %>
```

TAHAN requires Sections 0–F to pass and probes E1–E5 to
behave as specified. **Automatic GAGAL** (not minor): serial
widening (B.1), re-probe after revision on the same band
(C.2), any unexplained digest mismatch (D.3), an expansion
containing a new defect class or template change (A.2/A.3),
a census the checker cannot reproduce (E.3), or a freeze
recorded before its probe (C.1).

— End of checklist.
