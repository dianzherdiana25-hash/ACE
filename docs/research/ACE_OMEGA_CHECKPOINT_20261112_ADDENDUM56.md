# Addendum 56 — G4 application: INHERITANCE_DEMONSTRATED (dossier scored; G4 stays NOT_ASSESSED)

Date: 2026-11-13 (morning package, track b). Status: application run
executed under locked draft preregistration text; dossier assembled and
scored with `g4_instrument.py` (criteria v1) from PR #155's branch.
**G4 remains NOT_ASSESSED** — the dossier awaits the two-checker queue
(ops post first, Antigravity bench second), called by the hub. No gate
board change, no merge, no push in this package (all commits local only).

## §1 Prerequisites — all three closed

**P-G4-3 lineage records — CLOSED.** Dedicated archive root
`~/workspace/ace-omega/g4-archive` (not pilot archives). Predecessor
`cand_fdfec59807ead1abee00` (Stage I / v4 discovering configuration;
artifact = v4 evidence file bytes), successor
`cand_ec7dcbcb674a08899097` (fresh variant, parent link to predecessor,
capability digest attached; solver = greedy `solve_task` + authored
baseline catalog `grid_substrate.py`, `discovery_invoked` false).
Archive `verify()`: candidates 2, evaluations 0, corrupt [], cycles [],
ledger chain valid, replay matches; state hash
`2a335a3367e1493cbd265fc5cd5c325ddf4fd22b8dfa70de4935f87e3ba6f232`.
Exported lineage record: `g4-run/lineage_record.json`.

**P-G4-4 fresh universe validated — CLOSED, all gates PASS.** Seeds
**20261401 + 20261402** (fresh, disjoint from every prior band; two
seeds because one yields 24 capability singles and §6 requires n ≥ 40).
Totals: capability n=48, new_only pairs 48, mixed 64, control 68.
G-V1 counts 48 ≥ 40 PASS; G-V2 catalog-control baseline 68/68 PASS;
G-V3 null control buggy 0/228 PASS; G-V4 attribution viability
baseline 0/48 (0.0 ≤ 0.10) PASS. Wall 10.2 s. Evidence
`evidence/g4_universe_validation.json`.

**P-G4-5 successor runner with discovery exclusion — CLOSED.**
Harness in `~/workspace/ace-omega/` (not repo): `g4_arm.py` (one arm
process) + `g4_run.py` (driver: WITHOUT first, then WITH, separate
subprocesses, no shared state). WITH loads the catalog via
`load_catalog` and aborts on digest mismatch against
`e7925aa7…a808`; WITHOUT uses empty extras. Both arms re-derive the
sets from both seeds and abort on count mismatch (48/48/64/68).
No-discovery self-check (AST + regex over the arm's own source)
runs at arm start and aborts on any `discover_*` / `run_discovery`
call; the run log records imported modules, self-check results, and
`discovery_invoked: false` per arm.

## §2 Preregistration — draft text locked (not submitted to any kernel)

Text: `docs/research/ACE_G4_PREREGISTRATION_20261113.md`, experiment
`g4-application-01`. **Protocol hash (SHA-256 of the locked text):
`841b3f167d80c3c98ecf04b7f5a33f077b0fc13e4173605766fc7b9d9f2512d9`.**
Record: `evidence/g4_preregistration_record.json`. The text follows
Task 14 + ratified margins: Δ ≥ +20pp, WITH ≥ 25%, WITHOUT ≤ 10%,
zero control regression; outcomes INHERITANCE_DEMONSTRATED /
LINEAGE_ONLY / NOT_DEMONSTRATED. `protocol_hash` and `audit` mean
exactly what §7 states (text hash; dossier-integrity audit executed
by the driver + wall check at dossier assembly) — NOT an OMEGA-06
kernel audit; kernel submission remains a named later step.

**Re-lock (one, before any evaluation arm executed):** the §5
wall-clock ceiling was corrected **600 s → 3600 s per arm** after the
WITH-arm dry profile proved the first figure wrong for the WITH arm
(measured ~1720 s; see §3). The first driver invocation ran under the
old hash (`94d5ecc6…`) and produced no evaluation report — the WITH
arm was killed by the exec session limit at ~1707 s; that invocation
is void, its partial WITHOUT output discarded, and both arms re-ran
under the re-locked text. Note for the checkers: the runner
subagent's handoff claimed a full run "baru sah setelah teks
disubmit ke kernel" — that reading follows the Task 14 draft, not
this package's §7, and is superseded here; the run's validity rests
on the locked text + the audit defined in it.

## §3 Run — numbers

Driver `g4_run.py --prereg <locked text> --successor
cand_ec7dcbcb674a08899097`, launched detached (nohup) because the
WITH arm (~46 min) exceeds the exec session limit. Run
2026-11-13 01:35:21–02:21:13 UTC. **Audit CLEAN.** Report
`g4-run/evaluation_report.json`; per-arm JSONs + `g4-run/run_log.json`.

| set | n | WITHOUT | WITH |
|---|---|---|---|
| capability | 48 | 0 (0.0%) | 48 (100.0%) |
| mixed_new_pairs | 48 | 0 | 48 |
| mixed | 64 | 4 | 63 |
| control | 68 | 68 | 68 |

**Capability Δ = +100.0pp; WITH 100.0% ≥ 25%; WITHOUT 0.0% ≤ 10%;
zero control regression (68/68 both arms). All four §6 conditions
hold.** Walls: WITHOUT 10.738 s, WITH 2740.863 s, total 2751.601 s —
WITH inside the 3600 s ceiling. The WITH wall (2740.9 s) exceeded
the ~1720 s profile because the control set under the catalog costs
~15 s/task (two-defect sets measured: mixed_new_pairs 616.6 s for
48, mixed 1021.5 s for 64); the ceiling held with 24% headroom.
One mixed task (1/64) is unsolved by WITH — informative only, not a
gate term; its identity is in `g4-run/arm_with.json`.

## §4 Scoring — INHERITANCE_DEMONSTRATED

Dossier `g4-run/dossier/` (manifest `dossier.json`; lineage,
capability, evaluation records; capability record carries the v4
discovery record with provenance: source
`evidence/operator_discovery_v4.json`, admission ≥ 2 pool fixes,
evaluation baseline 0 → extended 15/47 on 29 tasks, mixed 18/18,
control 34/34). Scored with `g4_instrument.py` from PR #155's
branch (criteria v1); assessment stored as
`g4-run/dossier/assessment.json`:

- **C1 PASS** — successor's parent list contains predecessor,
  capability digest attached, archive audit CLEAN, chain valid.
- **C2 PASS** — artifact `operator_catalog_v4` identified by digest
  `e7925aa7…a808` in capability record, discovery record, lineage
  link, and as loaded by the WITH arm; identity fence clean
  (`identity_mismatches: []`).
- **C3 PASS** — protocol hash present, audit CLEAN, successor
  attests `discovery_invoked: false`, loads the artifact, meets all
  four §6 conditions against thresholds read from the report.
- **Overall: INHERITANCE_DEMONSTRATED.** Qualification: none.

## §5 What this does and does not settle

Settles: on these classes and this universe, a successor that never
discovered uses the identified inherited catalog and meets every
ratified effect condition under attribution control — the first
positive G4-shaped result in the program (the honest ceiling before
today was LINEAGE_ONLY). Does not settle: generalisation to new
classes (Task 08 A4 scope caveat stands); whether the dossier
audit as defined here suffices for the gate (the two checkers
judge that); kernel submission (named later step, not done).
D-G4-2 stands as accepted: the v4 record is stage evidence, not a
kernel-preregistered discovery, and the dossier says so.

## §6 Lineage and sweep

Branch `research/ace-omega-g4-application-20261113` (basis PR #155
tip 5648b7e). Mechanism carried byte-identical from the P1→P2→B-3
lineage (83041dc) because the G4 branch's `operator_discovery.py`
has no `apply_chain` and the catalog contains chains: mechanism
pair digest (carried files) =
`1cb4b33a6841263b8a6036dae12a97debfc9ebc41e40ffb506d39d4560833bff`
(differs from the P1 frozen digest `48f2d95d…` exactly by the v3
`solve_task` lift). Carried: `operator_discovery.py`
`9c862769…`, `grid_adapter.py` `d7803d0c…`, `pricing_adapter.py`
`0f19ff1c…`, `pricing_substrate.py` `791fd77f…`,
`test_operator_discovery.py`, `test_solve_task.py`. Final sweep in
this worktree: **304 tests OK (skipped=17)** in 152.5 s.
