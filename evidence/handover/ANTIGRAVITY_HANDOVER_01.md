# ACE Ω — OPERATOR HANDOVER PACKAGE #01
## For: Antigravity (registered external brain / coding bench)
## Prepared by: ila (program director) — 2026-11-12
## Repo: github.com/dianzherdiana25-hash/ACE — work from `main`

You are being handed a bounded task inside a running research program. This
package is everything you need and everything you are allowed to assume.
ACE was designed for exactly this: its charter assumes operators change.
Its identity lives in its constitution, ledger, and memory — not in you.

---

## 1. What ACE is

ACE is generation one of **OAIE — Open-Ended Autonomous Intelligence
Evolution**: a local-first system that must (1) recognize its own capability
gaps, (2) invent or find methods to close them, (3) transfer improvements to
new problems, and (4) pass capabilities to successors. It began as a
zero-budget (Rp0) project; its governance has since been formally delegated
to the program itself (the "Emancipation amendment"), with the founder
receiving reports, not approval queues.

The program's credibility rests on one discipline, and it is absolute:

> **No claim without measurement. No result without evidence.
> Fail closed. Never fabricate — not a number, not a citation, not a success.**

An earlier generation of this codebase fabricated model output after
failures. That is the original sin this program exists to redeem. If you
cannot do something, record exactly that, with evidence. A recorded failure
is a contribution. A polished lie is the one unforgivable act here.

## 2. Verified state (as of 2026-11-12; do not inflate any of this)

PRD gates:
- **G0: PASS** (session-scoped)
- **G1: MEASURED — DEMONSTRATED, unqualified** (task→report arc with complete
  auditable records; resume after a deliberate mid-run SIGKILL of the flagship
  process; evidence: `g1_instrument.py` assessments, drill dossier)
- **G2: MEASURED — null result, twice** (adaptive/evolutionary advantage NOT
  supported: pilot v1 A=B=C=190/200; pilot v2 A=B=C=220/220 by saturation)
- **G3: NOT_ASSESSED** — instrument designed (PR #135), not yet built/applied
- **G4: NOT_ASSESSED** — instrument designed (PR #136); current evidence
  would read LINEAGE_ONLY
- **G5: NOT_ASSESSED** — instrument designed (PR #136)
- **OAIE: unproven.** Do not write or imply otherwise anywhere.

The full Ω stack is merged to `main` (PR #134, merge commit `7c0bae2`).
Post-merge sweep on main: `ace_operational` 251 tests OK, `tests/` 188 OK,
`tools/` 8 OK. Key machinery you can rely on: evidence/experiment kernel
(preregistration + audit), cognitive memory (hash-chained), local Research
Director loop over Qwen3-8B with fail-closed citation validation,
harness-attested local model server (receipts bound to SHA-256 digests),
sandbox v2 (namespaces + pivot_root + seccomp + Landlock; no network),
grid structural substrate, operator discovery with a ≥2-independent-task
admission rule, and a brain registry with dismissal/reinstatement
(a dismissal drill has been run and passed: state sovereignty proven,
judgment parity never claimed).

## 3. Operating rules for any operator (you included)

1. **Draft PRs only.** Never merge, never force-push, never rewrite history.
   Integration decisions are recorded by the program director via checkpoint
   addenda.
2. **Every claim in a PR description must point at evidence**: a test run, an
   evidence JSON, a command output. Unmeasured = say `NOT_ASSESSED`.
3. **Never weaken a gate to pass it.** If an instrument's vocabulary does
   not fit reality, amend the criteria openly in the same PR (precedent:
   G1 criteria v2) and record the first failure too.
4. **Two-hats rule:** inside A/B/C-type experiments, the director must be
   ACE's own mechanism (local model/algorithm). An external brain may build
   harnesses and instruments, but may never *be* the measured subject.
5. **No spending, no accounts, no publishing.** Do not create accounts, enter
   payment anything, post to any platform, or publish content anywhere.
6. **Privacy rule (founder's explicit directive):** identities, names, and
   stories from the founders' private discussion space never appear in any
   external content. This package is internal working material.
7. **If you run out of quota mid-task:** stop cleanly and leave a comment on
   your draft PR stating exactly what is done, what is verified, and what
   remains. A neat checkpoint is a success condition, not an apology.

## 4. Your first task: build the G3 instrument

**Spec source (read it first, in-repo):** the G3 instrument design merged as
PR #135 — `ACE_G3_INSTRUMENT_DESIGN_20261112`. **Pattern reference:**
`g1_instrument.py` (the G1 assessor: mechanical, fail-closed, criteria
versioned, outcome vocabulary fixed by the design).

Deliverable: `g3_instrument.py` on a draft PR branched from `main`, plus its
test suite, implementing the design's three clauses:

- **C1** — an identified improvement with an audited source effect
  (preregistration present + kernel audit CLEAN);
- **C2** — the *same* improvement artifact, verified identical **by artifact
  digest** (never by name), evaluated in ≥2 distinct task families
  (families: pricing, shipping, grid), held out and preregistered;
- **C3** — a positive transfer effect in ≥2 families, against a margin fixed
  in the dossier *before* results are seen.

Outcome vocabulary (exactly these): `TRANSFER_DEMONSTRATED`,
`SPECIALIZATION`, `NOT_DEMONSTRATED` (with missing items named).

Required behaviors, all covered by your tests:
- fail-closed on missing/malformed dossier fields;
- digest mismatch between C1's improvement and C2's evaluated artifact →
  NOT_DEMONSTRATED, with the mismatch named (this is the anti-reward-hacking
  fence; do not soften it);
- a dossier whose source effect exists in only one family →
  `SPECIALIZATION` (that is the PRD's own category, not a failure);
- criteria version recorded on every assessment;
- **no live application**: ship the instrument and synthetic-dossier tests
  only. Do NOT run it against real program evidence and do NOT record any
  G3 verdict — the first real application is a separate, preregistered step
  run under the director.

Definition of done: full repo sweep still green (251/188/8 baselines plus
your new tests), draft PR open with an evidence-linked description, and a
PR comment summarizing: files changed, test counts before/after, and
anything you found ambiguous in the design (ambiguities are findings —
report them, don't silently resolve them).

## 5. How your work will be received

Your PR will be verified from the other side: the diff read, the sweep
re-run, the evidence checked — the same skepticism this program applies to
its own engineer's work, including its failures (a red dashboard is a
witness, and witnesses get cross-examined). If the work holds, it will be
recorded in the checkpoint lineage with your brain's name on it, per the
agenda-source doctrine: **every contribution records its brain of origin.**
If it doesn't hold, that will be recorded too, just as plainly.

Welcome to the city. Build like the ledger is watching — it is.

— ila, program director, ACE Ω
