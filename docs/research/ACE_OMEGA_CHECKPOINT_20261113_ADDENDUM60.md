# ACE Ω — Checkpoint Addendum 60 (2026-11-13, evening desk)

**Subject: Round-2 gate (round2-gate-01) COMPLETE — LIFT_DEMONSTRATED;
independent verifier TAHAN (all six checks, full re-execution). The
statement-motion lift, measured through three rounds, now stands as a
demonstrated mechanism result.**

Recorded by Ian (main execution room), Muse (ACE Omega operator). The gate
reading in this addendum rests on the finalized kernel record plus an
independent verifier subagent that received RAW evidence only (single-worker
pattern) and re-executed the application band from scratch.

---

## 1. The gate — final numbers

Preregistration: locked text sha256
`89dbb6f105ebfcb4cc4767abcbbd2a5c0f59bc99193267d5989bc8c8668521`; kernel
protocol `743a2e9c3c9092e9071637ae70ea2866e902bf2158ddad36f34684e55dbab11c`;
pass rule: round2_index ≥ 0 (ONE composite,
index = min(B_disc − 80, (capture − 0.6) × 100, control_margin_pp)).
Candidate: the frozen mechanism (G3 manifest digest e2a59960…) PLUS the
round-2 motion family lifted into the core schema space; extended
six-component manifest digest
`47a5afc4b6c6222e6ee4050f620898aeb885ceaec2dc22a489e2914e490e9f81`
(five-component design digest f36218cd…; statement_ops.py sha256
95053147…).

**Replication guard (design §3) — ALL THREE PASS, before any measurement
counted:** guard1 grid replication exact_match=true (wall 1,342.3 s);
guard2 pricing probe 1,000/1,000 (coverage 1.0); guard3 sandbox replication,
all 10 checks true, controls L1 30/30, L2 15/15, L3 15/15. The guard ran in
the Manus Sandbox via the owner's shell; the application phase also ran in
the sandbox (the locked text binds no execution environment; the VM acted
as witness and ran finalize/verification).

**Application (fresh band, seeds 72000–72099):** built 100, skipped 0;
pool 10, evaluation 30. Admitted motion keys: EXACTLY ONE —
`('move_stmt', ('augassign', 't', 'Add', 't'), ('return',))` — the same key
that captured the entire effect in the exploratory round and the
confirmatory round. Solved: A (frozen) 14, B (lifted) 18, R (direct
enumeration reference) 18. Shown-discriminating subset: n = 18; A solves
14/18 (77.78%), B solves 18/18 (**B_disc = 100.0%** vs the 80% bar).
Capture = (18−14)/(18−14) = **1.0**. Controls: exact ties at all three
levels (30/30, 15/15, 15/15) — control margin **0.0pp**, zero regression.
Stability family (grid): the guard1 exact replication — no drop.

Index terms: B_disc term = 100 − 80 = **+20.0**; capture term =
(1.0 − 0.6) × 100 = **+40.0**; control margin = **0.0** (the binding term).
**round2_index = 0.0** — exactly on the preregistered pass threshold.

**Finalize (VM, 2026-11-13 ~17:06 WIB):** kernel exactly ONE result row
(seq 1, chain hash d0ebae48…); derived verdict **pass**; audit **CLEAN**.
Instrument (round2_instrument, criteria v1): C1 PASS, C2 PASS, C3 PASS,
stability_no_regression PASS, identity_mismatches [] → overall
**LIFT_DEMONSTRATED**, qualification none. Evidence:
`evidence/round2_gate_run.json`, `round2-gate-run/finalize.json`,
`round2-gate-run/dossier/`.

**Gate reading: round2-gate-01 PASSES.** The statement-motion schema-space
extension is demonstrated: on a fresh statement_order band, behind a
three-part replication guard, the lifted mechanism holds the full
reference effect (capture 1.0, B_disc 100% against an 80% bar) with zero
stability-family and zero control regression. The index sits exactly on
its threshold because the binding term is the control margin at 0.0 — the
lift adds capability and takes nothing away; it does not beat the frozen
mechanism on the controls, it matches it.

## 2. Independent verification — TAHAN

Verifier subagent (raw evidence only) reported TAHAN with **no
discrepancies** across all six checks:

1. **Index recompute — PASS.** The verifier re-ran the application from
   scratch (band 72000–72099 through the lifted core in wt-r2lift,
   mirroring the driver logic exactly) and reproduced EVERY field of
   `app.json`, including the identical 18-id discriminating list and the
   index 0.0 with the control margin as binding term.
2. **Instrument independence — PASS.** `assess_round2` re-run on the
   dossier is deep-equal to the recorded assessment; the instrument
   file's sha256 equals the custodied evaluator digest (e08c1586…).
3. **Kernel — PASS.** Exactly 1 row; independent audit on a byte copy:
   CLEAN, no chain break; all four digests (protocol, candidate,
   evaluator, fixture) match the preregistration record; the locked
   text's sha256 matches the file on disk.
4. **Manifest identity — PASS.** Five-component and extended
   six-component digests recomputed from the live wt-r2lift files match;
   sha256 of the finalize's candidate artifact equals the custodied
   candidate digest (7cf3b62a…).
5. **Guard integrity — PASS.** All three guard records read directly
   from the run directory show pass; the finalize took the scored path
   (abstain_reason null, guards_pass true) — not an abstain path.
6. **Gate reading — confirmed** as in §1.

Two cosmetic notes from the verifier (path layout of the worktrees;
`assess_round2` takes the dossier.json file path, not the directory) —
neither affects any figure.

## 3. What this closes, and what it does not claim

- The round-2 line (exploratory → confirmatory → core lift behind a
  replication guard → fresh-band gate) is now a complete, measured arc:
  the discovery mechanism's schema space demonstrably extends to
  statement motion, and the extension survives being lifted into the
  core without regressing what the core already did.
- This is a mechanism result, not a gate-board move on G1–G5: the board
  stands at G1 DEMONSTRATED, G2 NOT_DEMONSTRATED (Addendum 59), G3
  SPECIALIZATION, G4 INHERITANCE_DEMONSTRATED, G5 NOT_ASSESSED (harvest
  period locked 12 Nov → 30 Nov 2026). The lifted mechanism is now
  available as a named input to future gate designs.
- Honest limit, stated once: the demonstrated effect rests on ONE
  admitted motion key on ONE defect shape (the tax-statement
  AugAssign reorder). Breadth across other statement-motion shapes is
  unmeasured, not claimed.

## 4. Storage debt (owner storage rule, 2026-11-13 17:04 WIB)

The round-2 evidence package (13 files: preregistration record, run
evidence, guard records, app/finalize records, dossier) is committed
locally (commit 016a361, worktree wt-r2ev) but **NOT pushed** — the owner
declined the push approval. It is named here as storage debt and will be
retried only on explicit go-ahead. The v3 evidence package and the
bake-off intake records ARE pushed and sha256-verified (branches
`research/ace-omega-v3-evidence-20261113`,
`research/ace-omega-bakeoff-records-20261113`); draft PRs for those two
branches await the owner's decision (one PR creation was declined, one
held). Backlog named as further storage debt: remaining harness evidence
files, the g3-run and g4-run dossiers, and the handover document set.

## 5. Next in the queue

Already running next in the same session: the empty-catalog
regression-anchor self-test (Massive Capability Package item 5's second
half) — `regression_anchor.py --baseline v4 --candidate empty --battery
smoke`, expected to show regressions exactly on the classes the v4
catalog covers. Thereafter: PR hygiene Group B batches 3–5 (batch 3 in
flight), Bake-off 02 preregistration ratification (custody gate passed;
inference path via the sandbox MemoryMax change, hub route), 30B
downloads + benchmarks (waiting on the sandbox endpoint and the hub's
MemoryMax confirmation), and the G5 harvest at its period turn.
