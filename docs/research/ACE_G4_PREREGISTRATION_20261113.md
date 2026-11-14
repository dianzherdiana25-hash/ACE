# G4 application preregistration (draft text — locks the run, submits to no kernel)

Experiment: `g4-application-01`. Status: **DRAFT** — this
text fixes the run's conditions before the run executes.
It is NOT submitted to any OMEGA-06 kernel in this
package (morning-package rules: no kernel submission);
§7 states plainly what `protocol_hash` and `audit` mean
under that constraint. G4 remains **NOT_ASSESSED** until
the dossier is scored and the two checkers verify it;
the gate board does not change in this package.

Sources: bench Task 08 dossier design (decisions D-G4-1..5
ratified as design) and bench Task 14 draft text; the G4
instrument (PR #155, `g4_instrument.py`, criteria v1) and
the materialised catalog (PR #155) fix the scoring schema
this text is written against.

## §1 Hypothesis (falsifiable)

**H1.** A successor variant that never ran discovery, given
the materialised operator catalog (§2) as inherited data,
solves materially more held-out capability tasks than the
identical successor without it — by the margins fixed in
§6 — on a fresh-seed grid universe neither arm has ever
touched.

H1 is **falsified** if any §6 condition fails: the margin,
the WITH-arm floor, the WITHOUT-arm attribution ceiling,
or the control no-regression rule. The outcome is then
`LINEAGE_ONLY` — a publishable measured outcome, reported
with the same prominence as a positive one. No re-run
until green is permitted under this registration.

## §2 The inherited artifact (identity by digest)

The **v4 admitted operator catalog** (D-G4-1): per grid
defect class, the admitted operator keys and chains
recorded in `evidence/operator_discovery_v4.json`
(bounds_off_by_one: 3 operators + 1 chain ·
dist_step_2: 1 operator · returns_start_distance:
1 operator + 1 chain · wall_char_x: 1 operator),
materialised (P-G4-2, PR #155) into a standalone
canonical artifact file.

- Artifact name: `operator_catalog_v4`.
- Artifact digest:
  `e7925aa7ea0f7d766b70e2b3855b2377b017959426d370a8cba43b6eff07a808`
  (canonical JSON, independently reproducible
  byte-for-byte; loader `catalog_artifact.py` refuses
  any artifact whose digest does not recompute).
- **Discovery record (D-G4-2, ratified):** the v4 stage
  evidence (`evidence/operator_discovery_v4.json` + its
  driver record) is accepted as C2's discovery record,
  with its provenance stated in the dossier: it is
  measured stage evidence with an admission rule (an
  operator admitted only if it fixes ≥2 independent
  pool tasks), not a kernel-preregistered run. The
  capability record carries the same name + digest as
  the materialised artifact; identity is by digest,
  never by name.

## §3 The actors (lineage)

- **Predecessor:** the Stage I/v4 discovering
  configuration, registered in the dedicated
  `PopulationArchive` root `g4-archive` (not the pilot
  archives) as candidate
  `cand_fdfec59807ead1abee00`. Its artifact is the v4
  evidence file itself (artifact digest = SHA-256 of
  `evidence/operator_discovery_v4.json`).
- **Successor:** a fresh archive candidate
  `cand_ec7dcbcb674a08899097` whose parent link names
  the predecessor and whose metadata attaches the
  capability artifact digest. Its solver
  configuration is the greedy solver
  (`solve_task`, the v3 lift of the frozen mechanism's
  greedy loop — behavior-identical to the v4 mechanism
  per the PR #151 replication gate, EXACT MATCH) +
  the authored baseline catalog (`grid_variants` /
  `_OPERATORS`, digest
  `56fcafbd2afcbe00bed86aa4b6f4126dab8936f4408060fb5953fbebdf28ccb6`).
  It has never invoked discovery. Mechanism pair
  digest (carried files):
  `1cb4b33a6841263b8a6036dae12a97debfc9ebc41e40ffb506d39d4560833bff`
  (`operator_discovery.py` + `grid_adapter.py` from
  the 83041dc lineage, carried byte-identical; the
  digest differs from the P1 frozen digest
  `48f2d95d…` exactly by the v3 `solve_task` lift).
- **Inheritance event:** the §2 artifact is delivered
  to the successor as data; the runner verifies its
  digest against the lineage record at load (mismatch
  aborts the run as an integrity failure). *Use* =
  applying admitted keys/chains through
  `apply_operator` / `apply_chain`. *Discovery* = any
  `discover_*` call; the run log must make the absence
  of discovery calls auditable, and the evaluation
  report attests `discovery_invoked: false`.
- The archive's integrity verification over these
  records is part of the dossier: ledger chain valid,
  replay matches, no corrupt records, no cycles
  (state hash
  `2a335a3367e1493cbd265fc5cd5c325ddf4fd22b8dfa70de4935f87e3ba6f232`).

## §4 Evaluation universe and sets

- **Universe:** `grid_generalization.build_universe`
  over **two seeds: 20261401 + 20261402** — fresh and
  disjoint from every prior run (Stage F rounds, v1–v4
  discovery, pilots, G3 application 20261113, v3
  census 20261201, calibration 20261301, seed scan
  20261112–20261153, B-3 probe bands, statement_order
  calibration 40000–40023, G3 pricing bands, v-next
  sandbox bands). Two seeds because one seed yields
  24 capability singles and §6 requires n ≥ 40; the
  second seed is fixed here **before** the run, as
  the design prescribes — never after seeing scores.
- **Validation (P-G4-4, before this text locked):**
  all four Stage F validity gates passed, evidence
  `evidence/g4_universe_validation.json`: G-V1 counts
  48 ≥ 40; G-V2 catalog-control validity, baseline
  solves 68/68; G-V3 null control, buggy code solves
  0/228 holdout tasks; G-V4 attribution viability,
  baseline solves 0/48 capability singles (fraction
  0.0 ≤ 0.10). No generation failures on either seed.
- **Capability set:** the universes' `new_only`
  single-defect tasks in the four discovered classes;
  **n = 48**.
- **Mixed sets (reported separately, never in the
  §6 rule):** new_only 2-defect pairs (n = 48) and
  mixed (catalog × new) tasks (n = 64).
- **Control set:** the universes' `catalog_control`
  tasks (n = 68), both arms.

## §5 Arms and procedure

- **WITHOUT arm first** (the conservative order), then
  WITH: two separate processes, no shared state, no
  cross-task memory in the solver, identical tasks,
  solver, and budgets.
- **WITH arm:** the identical successor + the §2
  artifact loaded by digest.
- **WITHOUT arm:** the identical successor, baseline
  catalog only.
- Discovery code is not called in either arm's process;
  the arm script self-checks its own source for
  `discover_*` calls at start and aborts if any are
  found; the run log records the check and the
  imported modules.
- Solver budget: `solve_task` with
  `max_score_calls=None` (uncapped — the v4 behavior
  the replication gate checks); the greedy loop's own
  6-round / frontier-4 bound is the budget.
- Wall-clock ceiling per arm: **3600 s**. Set from the
  runner's measured WITH-arm profile (P-G4-5): the
  WITHOUT arm solves all 228 tasks in 10.0 s wall, but
  the WITH arm is ~170x slower on two-defect tasks
  (chains re-enumerate per step): measured per set —
  capability 48 tasks ~0 s total (3-task probe: 0.0 s
  each, all solved), mixed_new_pairs 48 tasks 616.6 s
  (48/48), mixed 64 tasks 1021.5 s (63/64), control
  profiled fast (baseline-solved). The full WITH arm
  is therefore profiled at ~1720 s (~29 min). The
  3600 s ceiling is ~2.1x that profile. An arm
  exceeding its ceiling aborts the run; the ceiling
  is a run-integrity bound, not a budget the arms are
  expected to consume. The driver records per-arm
  walls in the report; the ceiling is checked at
  dossier assembly from those recorded walls (§7).

## §6 Pass rule (mechanical; scored by the G4 instrument)

The evaluation report carries the thresholds as fields
— `margin_pp: 20.0`, `with_floor: 0.25`,
`without_ceiling: 0.10`, `min_capability_tasks: 40` —
fixed by this text (D-G4-3); the instrument reads them
from the report and never invents its own. **C3 passes**
iff all hold on the audited report:

1. **Δ ≥ +20.0 pp** — (WITH − WITHOUT) solved fraction
   on capability singles.
2. **WITH ≥ 0.25** — the WITH arm solves at least a
   quarter of capability singles in absolute terms.
3. **WITHOUT ≤ 0.10** — the attribution ceiling: above
   it, the effect cannot be credited to inheritance
   whatever Δ says.
4. **Zero control regression** — WITH solves every
   control task WITHOUT solves.

Outcome, scored by `g4_instrument.py` over the §7
dossier (criteria version recorded):

| C1 lineage | C2 identity+admission | C3 (§6) | Outcome |
|---|---|---|---|
| pass | pass | pass | `INHERITANCE_DEMONSTRATED` |
| pass | pass | fail | `LINEAGE_ONLY` |
| fail | any | any | `NOT_DEMONSTRATED`, items named |
| pass | fail | any | `NOT_DEMONSTRATED`, items named |
| any digest mismatch among {capability record, discovery record, artifact as loaded} | | | `NOT_DEMONSTRATED`, mismatch named (hard fence) |

## §7 Dossier and audit requirements (what the fields mean here)

The dossier is a directory: `dossier.json` manifest
naming `lineage_record.json`, `capability_record.json`,
`evaluation_report.json` (the instrument's schema):

- `lineage_record` — archive export: both candidate
  records, parent link, artifact attached, archive
  audit result (`g4-run/lineage_record.json`).
- `capability_record` — artifact file + digest +
  discovery record reference with provenance (§2);
  admission evidence = the v4 record's per-class
  admitted operators/chains and evaluation effect
  (baseline 0 → extended 15/47 on 29 evaluation
  tasks) under the ≥2-pool-fixes rule.
- `evaluation_report` — this text's back-reference,
  audit result, artifact digest as loaded, universe
  seeds, per-arm task-id lists and solved counts on
  capability/control/mixed, thresholds as §6, wall
  time, runner identity, no-discovery attestation.

**What `protocol_hash` and `audit` mean in this
package (stated here because no kernel submission
occurs):** `protocol_hash` is the SHA-256 of this
locked text file, recorded in
`evidence/g4_preregistration_record.json` alongside
the text's own digest — it identifies the exact text
the run executed under. The text was re-locked once
before any evaluation arm executed: the §5 wall
ceiling was corrected 600 s -> 3600 s after the
WITH-arm dry profile proved the first figure wrong
for the WITH arm (measured ~1720 s; see §5). The
first driver invocation ran under the old hash and
produced no evaluation report (WITH arm killed by
the session limit at ~1707 s); it is void and its
partial WITHOUT output is discarded — both arms
re-run under the re-locked text. `audit` is the dossier
integrity audit defined here and executed by the
run driver: archive `verify()` CLEAN + artifact
digest at load equals the lineage digest + both
arms' no-discovery self-checks passed + set counts
cross-checked against the validation note + per-arm
walls within the §5 ceiling (checked at dossier
assembly from the report's recorded walls); any
failure aborts before the report is written. It is
NOT an OMEGA-06 kernel audit. The dossier states
this plainly; the two checkers judge whether it
suffices for the gate. A kernel submission with a
kernel-issued protocol hash remains a named later
step, not part of this package.

**Custodians (roles, B6):** the universe seeds were
fixed by the validation gate before this text locked
(that order is the design's own), so what stays
sealed is the locked text itself: the coordinator
holds the text + lineage records; the runner
(`g4_run.py` / `g4_arm.py`, the mechanism) executes
the arms and computes the text's hash at run time.
The universe custodian and the runner are different
parties by construction — a person-role and a
mechanism-role — and the run log records both.

## §8 Reporting commitments

The result is reported to the owner as one
consolidated report stating the outcome word, both
arms' numbers, the honest starting point (today's
ceiling is `LINEAGE_ONLY` — the dossier starts from
there, not from zero), and the scope caveat of
Task 08 A4: this registration measures inheritance
of *this* catalog on *these* classes;
generalisation to new classes is G3's neighbouring
question and must not be quoted as answered here.

## §9 Blockers — status at this text's locking

- **B1 — G4 instrument.** CLOSED (PR #155).
- **B2 — Catalog materialised.** CLOSED (PR #155;
  digest §2).
- **B3 — Lineage records.** CLOSED (dedicated archive
  `g4-archive`; audit CLEAN; record §3).
- **B4 — Fresh universe validated.** CLOSED
  (validation note §4; all four gates passed).
- **B5 — Successor runner.** CLOSED when the runner
  is built and dry-profiled (the §5 wall ceiling is
  set from that profile; the text is re-locked
  after).
- **B6 — Custodians.** CLOSED as roles (§7).
- **Kernel submission.** NOT a blocker for the run
  under this text; a named later step. The run
  executes under the locked draft text, and the
  dossier discloses that (§7).

## §10 Execution order (this package)

1. Runner built + dry-profiled (B5); §5 ceiling set;
   this text re-locked (hash recorded).
2. Only then: run both arms (WITHOUT first), assemble
   the dossier, score with `g4_instrument.py`,
   verify independently, report (§8).

Brain of origin: Muse (Ian, coordinator) + runner
subagent (P-G4-5 build). G4 remains NOT_ASSESSED.
