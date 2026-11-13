# ACE Ω — Proposer Engine, Stage 1 (Simulation-First): Design + Build Record

**Status: BUILD + INAUGURAL SIMULATION (this PR). Draft only, no merge.**
Lane: "ila — mesin pengusul ACE" (parallel-lane structure, owner
2026-11-13 22:00–22:13). Hub verifies; Ian integrates.

## 1. What was built
- `code/ace_operational/proposer_schema.py` — the rejectable package
  (`ace.proposal.v1`): claim, rationale, options incl. `do_not_run`,
  cost estimate vs ceiling, hash-pinned evidence, preregistration
  link + artifact hash, risks/uncertainties, visible enforced stop
  controls (call/time/cost ceilings, abort conditions, sealed-target
  status, no-auto-retry guarantee), internal-ratification block
  (ratifikasi internal ACE — hub/kernel/evidence; NOT owner
  approval, per the owner's 2026-11-13 20:54 framing correction).
- `code/ace_operational/proposer_validator.py` — fail-closed
  validator: no positive ceiling / no stop controls / no evidence
  hash ⇒ mechanical rejection, with named reasons.
- `code/ace_operational/proposer_episodes.py` — frozen-episode
  loader + prompt builder that reads ONLY at-time snapshots.
- `code/ace_operational/proposer_rubric.py` — deterministic rubric
  (100 pts) scoring reasoning against at-time information; it never
  reads outcomes.
- `code/ace_operational/proposer_simulation.py` — harness + exit
  gate (locked margins −10 / CI-lower floor −20, bootstrap seed
  20261113).
- `code/ace_operational/test_proposer_engine.py` — 17 tests:
  validator rejection battery (ceiling, stop controls, hashes,
  do-not-run, owner-approval vocabulary, unknown fields), outcome-
  separation test, historical-package validity, rubric behaviour.
- `evidence/proposer_stage1/` — `PREREG_LOCK.md` (design, split,
  rubric, margins, ceilings locked before the run), `episodes.json`
  (6 frozen episodes, at-time info only, prior-exposure declaration
  per episode), `outcomes.json` (separate store: outcomes +
  reconstructed historical baseline packages, labelled as such).

## 2. Fences honoured
- Simulation-first: no dispatch path exists in the code; unknown
  package fields (e.g. a smuggled `dispatch_now`) are rejected.
- Sealed instruments untouched: episodes only READ official records.
- The old Qwen director stays at rest (owner order). The generating
  brain is the adopted Qwen3-30B-A3B at the adopted serving config.
- One generation attempt per episode; no auto-retry — failures are
  recorded and score 0.

## 3. Inaugural simulation result
**EXIT GATE: NOT_PASSED** (quality clause FAIL — mean paired diff
−91.67 vs the −10 margin, bootstrap CI lower −98.33 vs the −20
floor; time clause NOT_ASSESSABLE by the locked preregistration).
All six A3B packages were rejected by the fail-closed validator or
truncated at the 900-token cap: one systematic type deviation
(`uncertainties` emitted as a string, 6/6) plus two cap
truncations. Full anatomy in
`evidence/proposer_stage1/SIMULATION_REPORT.md`. Stage 2 does not
open on this evidence; the engine stays simulation-only.

## 4. Known limits
- Historical baseline packages are reconstructions from the official
  record, not contemporaneous artifacts (declared in the store).
- Prior exposure is real: ila/Ian/owner know the outcomes. The
  design's mitigation is procedural (snapshots authored from
  pre-decision documents; rubric blind to outcomes); the A3B model's
  training predates these program events.
- n = 6 episodes: the bootstrap CI is honest about that width.
