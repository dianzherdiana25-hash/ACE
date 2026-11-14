# ANTIGRAVITY TASK 01 — Build the G3 instrument

You are the Antigravity bench (a Gemini brain) for the ACE Ω research
program, working under **Operator Handover Package #01**:
`/home/hatch/workspace/ace-omega/handover/ANTIGRAVITY_HANDOVER_01.md`.
Read that package in full first — its rules bind this task (evidence
discipline, no claim without measurement, fail closed, never fabricate,
draft-only work, record your brain of origin).

## Workspace and branch discipline

- Workspace: `/home/hatch/workspace/ace-omega/wt-g3design` (your current
  directory). HEAD is `aa36a02` — the G3 instrument design doc stacked on
  the merged main merge commit `7c0bae2`.
- FIRST ACTION: create and switch to a new branch named
  `bench/antigravity-g3-instrument-20261113` from the current HEAD.
  Commit only on that branch.
- Do NOT push. Do NOT merge. Do NOT modify any other branch or worktree.

## Read before writing code

1. `docs/research/ACE_G3_INSTRUMENT_DESIGN_20261112.md` — the spec.
2. `code/ace_operational/g1_instrument.py` — the pattern reference
   (mechanical, fail-closed, criteria-versioned assessor).
3. `code/ace_operational/test_g1_instrument.py` — the test pattern.

## Deliverables (exactly these two files)

1. `code/ace_operational/g3_instrument.py` implementing the design's
   three clauses:
   - **C1** — an identified improvement with an audited source effect
     (preregistration present + kernel audit CLEAN);
   - **C2** — the *same* improvement artifact, verified identical **by
     artifact digest** (never by name), evaluated in ≥2 distinct task
     families (families: pricing, shipping, grid), held out and
     preregistered;
   - **C3** — a positive transfer effect in ≥2 families, against a
     margin fixed in the dossier *before* results are seen.
   Outcome vocabulary, exactly: `TRANSFER_DEMONSTRATED`,
   `SPECIALIZATION`, `NOT_DEMONSTRATED` (with missing items named).
   Required behaviors:
   - fail-closed on missing or malformed dossier fields;
   - digest mismatch between C1's improvement and C2's evaluated
     artifact → `NOT_DEMONSTRATED`, with the mismatch named (this is the
     anti-reward-hacking fence; do not soften it);
   - a dossier whose source effect exists in only one family →
     `SPECIALIZATION`;
   - `criteria_version` recorded on every assessment.
2. `code/ace_operational/test_g3_instrument.py` — tests using
   **synthetic dossiers only**, covering every behavior above.

## Hard limits

- NO live application: do not run the instrument against real program
  evidence, and do NOT record any G3 verdict anywhere. G3 stays
  NOT_ASSESSED. The first real application is a separate preregistered
  step that is not yours.
- Do not weaken the digest-identity fence for any reason.
- Do not modify files other than the two deliverables.

## Verification and reporting

- Run your new tests and `test_g1_instrument.py`; report exact pass
  counts. (Pre-change baseline for the package sweep is 251 tests OK in
  `ace_operational`; at minimum, your module's tests plus the G1
  instrument tests must be green.)
- Commit on your branch with a message that records your brain of
  origin, e.g.:
  `feat(g3): build G3 transfer instrument per PR #135 design (Antigravity bench, Gemini, via Handover Package #01)`
- Your final message must summarize: files changed; test counts
  before/after; any ambiguity you found in the design — report
  ambiguities as findings, do not silently resolve them; anything left
  unfinished.
- If you run into a quota limit mid-task: stop cleanly and leave that
  same summary of what is done, what is verified, and what remains.
