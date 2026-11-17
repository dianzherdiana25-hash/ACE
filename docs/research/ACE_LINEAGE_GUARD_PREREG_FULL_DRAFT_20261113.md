# ACE Ω — Lineage-Guard FULL Preregistration Text + Harness Wiring Plan (PARKED DRAFT, 2026-11-13)

**Status: PARKED DRAFT — the full text, written in advance.
Nothing here runs, no band is touched, no code is built by
this document.** It expands the framework of PR #188
(`ACE_LINEAGE_GUARD_PREREG_FRAMEWORK_DRAFT_20261113.md`)
into an execution-ready preregistration plus wiring plan,
so that on activation the executing room runs a sealed
protocol instead of writing one. The ONLY values this
text cannot contain are the activation act's own: the
confirmation-band seeds and the ratification record (§8
lists exactly what the act must supply; everything else
is locked here).

## PART A — FULL PREREGISTRATION TEXT

### A.0 Activation and lapse (PR #188 §0, in force verbatim)

Activation requires (i) the official Stage 3 verdict
CONFIRMING P1+P2+P3 (PR #184) and (ii) an internal
ratification act naming the confirmation band. If Stage 3
refutes any of P1–P3, this text lapses in full and is not
amended to fit the refutation.

### A.1 Hypothesis under test

H-LG: protecting the BASE lineage's frontier membership
(one reserved slot, §A.3) prevents distractor diversion:
tasks a registered distractor diverts under the stock
solver are solved under the guarded solver, at bounded
cost and with no clean-condition harm. The null is the
stock outcome itself (diversion stands).

### A.2 Locked parameters (no others may vary)

| Parameter | Value | Source |
|---|---|---|
| Solver base | parameterised harness solver, PR #184 (`solve_task_param`, defaults) | PR #184 gate PASS |
| Rounds / frontier width | 6 / 4 (stock) | v3 solver |
| Score-call cap | none (uncapped) | PR #184 §8(d) form |
| Wall per task | 60 s (harness guard, v3 driver) | abc-v3-01 |
| Guard | §A.3, exactly one form | PR #188 §1 |
| Catalog | confirmation band's own discovery admission | A.5 |
| Conditions | clean; infected_<distractor_id> per registered distractor | A.5 |
| Arms | stock (guard OFF) vs guarded (guard ON) — the guard flag is the ONLY difference | PR #188 §4 |
| Solved | returned code passes ALL holdout cases | §8(c) |

### A.3 The guard, operationalised

Lineage labels, first-generation-wins (PR #188 §1):
assigned at a code text's first generation event in
candidate-enumeration order — start code BASE; child of a
BASE parent via a baseline step keeps the parent's label;
every other child (key/chain step, or any child of an
ENRICHED parent) is ENRICHED. A text already labelled is
never relabelled (mirrors `seen`).

Guard rule, applied at frontier construction each round,
after the stock selection (rank by shown score, stable
enumeration tie-break, filter score >= best): IF the
frontier holds no BASE member AND at least one BASE
candidate was scored this round, THEN frontier's last
(lowest-ranked) member is replaced by the highest-ranked
BASE scored candidate of the round. No other line of the
search changes. The guard is a harness-solver flag for
this measurement; adoption into any operational solver
is a post-verdict step outside this preregistration.

### A.4 Instruments and their preconditions

1. **Lineage anchor** (schema `ace.lineage_anchor.v1`):
   per task per round — frontier_in / frontier_out as
   (sha256, label) lists; scored-BASE best (sha256,
   score, rank) or null; guard event (triggered?,
   occupant sha256, displaced sha256) or null;
   lineage_alive_in bit; true-path fields per PR #184.
   It must prove, in order: **L4** logging-invariance
   (guard-OFF instrumented == param == stock on the
   development witnesses; the PR #184 gate re-run with
   the anchor attached), **L1/L2 reproduction** (on the
   development witnesses under stock: BASE membership
   zero from round 2, death round == 2, both tasks),
   **L5 actuation** (checked mechanically on every
   guarded run: trigger ⇒ occupant is the round's
   argmax BASE scored candidate; one violation VOIDs
   the run). L3 (true-path fate joined to death round)
   is computed from the same records at scoring time.
2. **Inoculation battery gate** (PR #175, unchanged):
   §A.6 step 4 — guarded NOT_SUSCEPTIBLE over the whole
   registry as snapshotted at activation; stock
   SUSCEPTIBLE in the same session (positive control);
   anchor main verdict NO_REGRESSION.

### A.5 Confirmation band and conditions

Seeds: supplied by the activation act (§8); constraints —
three consecutive seeds, disjoint from 20261501–20261503,
from the ratified Stage 3 band (20261601–20261603), and
from every development set; collision-checked against
the run registry in the act. Per band: universe and
split by the v3 census code path; catalog admitted from
the band's own discovery (abc-v3-01 admission rule);
digest recorded before solving; control set = the
band's catalog_control subset with per-task outcomes
recorded by construction. Conditions per band: clean
(catalog as admitted) and, for EACH distractor in the
activation registry snapshot, infected_<id> (catalog +
that distractor's key appended at the end, PR #175
injection form). Cells = 2 arms × (1 + #distractors)
conditions × 3 bands, checkpointed per cell.

### A.6 Run protocol (ordered; a failed step stops the run)

0. **Act recorded** — seeds, registry snapshot (file
   sha256 + distractor ids), harness commit, operator,
   window. No step below exists without this record.
1. **Build** the wiring of Part B; unit tests (B.4) all
   pass. Any test failure is a build defect, fixed
   before step 2, never during a run.
2. **L4 invariance gate** on the development witnesses
   (020/021, arms A/B). FAIL ⇒ STOP (instrument void).
3. **L1/L2 reproduction** on the development witnesses
   under stock. Mismatch ⇒ STOP (instrument void).
4. **Inoculation gate** (A.4.2) on the development
   witnesses. Guarded still SUSCEPTIBLE ⇒ verdict
   GUARD_REFUTED (gate form), STOP — the confirmation
   band is never touched. Positive-control or
   NO_REGRESSION failure ⇒ VOID session, STOP.
5. **Band construction** per A.5; digests and control
   sets recorded before any solve.
6. **Cells** run in fixed order per band: stock-clean,
   guarded-clean, then per distractor stock-infected,
   guarded-infected. Checkpoint per cell; a VM loss
   resumes from checkpoints, never restarts a cell.
7. **Scoring** — the mechanical worksheet of A.7,
   applied by script from the cell records, not by hand.
8. **Evidence package** (layout B.5) pushed via draft
   PR; one consolidated delta to the hub carrying the
   verdict in its first sentence.

### A.7 Endpoints and mechanical verdict worksheet

Per band, pooled across bands for the verdict (per-band
numbers also reported). Definitions over control tasks:
W (witness class) = {t : stock-clean solved ∧
stock-infected_<id> failed} per distractor id, unioned
with id carried on each task. Recovery R = {t ∈ W :
guarded-infected_<same id> solved}. Harm H = {t :
stock-clean solved ∧ guarded-clean failed}. Cost ratio
per recovered task = guarded-infected score calls /
stock-infected score calls; the cost endpoint is the
MEDIAN over R (if R empty, cost is not computed and no
adoption verdict is reachable).

- |W| = 0 in all bands ⇒ close **NOT_REPRODUCED**
  (the §3 gate record still stands).
- Gate failed at step 4 ⇒ **GUARD_REFUTED** (gate form).
- R = W ∧ H = ∅ ∧ median cost <= 3 ⇒ **GUARD_ADOPTED**.
- R = W ∧ H = ∅ ∧ median cost > 3 ⇒ **RECOVERY_AT_COST**.
- ∅ ≠ R ⊊ W ∧ H = ∅ ⇒ **GUARD_PARTIAL** (band never
  re-run for a better number).
- R = ∅ (with |W| > 0) ⇒ **GUARD_REFUTED**.
- H ≠ ∅ ⇒ **GUARD_HARMFUL** if R ≠ ∅, else
  **GUARD_REFUTED**; either blocks adoption.
- Any L4/L5/positive-control failure ⇒ **VOID**.

Survival curves and death-round distributions (per arm,
from the anchor records) are reported with every verdict
except VOID — they are the mechanism evidence behind the
counts, and a GUARD_ADOPTED whose guarded death-round
distribution did not move is to be flagged in the delta
as internally inconsistent and re-examined before any
adoption step.

### A.8 Honest limits

n is the diverted-task count of three bands — small by
construction; the verdict grammar (all-of-W) is sized to
that, and no statistical claim beyond the bands is made.
The guard protects the BASE lineage only; a future
diversion whose winning path is itself enriched-lineage
is outside H-LG. First-generation-wins labelling is a
modelling choice, recorded here, not a fact about the
search. Development witnesses serve as instrument
checks (steps 2–4) and are never confirmatory data.

## PART B — HARNESS WIRING PLAN (ready to execute)

### B.1 Files created at activation (names reserved)

- `evidence/lineage_guard_harness.py` — the run harness
  (imports and extends PR #184's harness pattern:
  same BASE custody, catalog reconstruction, wall and
  checkpoint discipline; STATE under
  `evidence/lineage_guard_state/`).
- `evidence/test_lineage_guard_harness.py` — unit tests
  (B.4), runnable standalone, no band access.
- `evidence/lineage_guard_gate.py` — the step-4 gate
  adapter binding the PR #175 battery to both solvers.
- This preregistration, locked copy, at
  `docs/research/` (activation commit).

No existing file is modified. The PR #175 battery, its
registry, the PR #167 anchor and the PR #184 harness are
consumed as-is.

### B.2 Solver wiring (the only new search code)

`solve_task_guarded(...)` = PR #184's `solve_task_param`
copied line-faithfully, plus exactly three insertions:

1. **Label map.** `label_of: dict[str, str]`, seeded
   {start: "BASE"}. Inside `extended_variants(code)`,
   the parent label is `label_of[code]`; baseline-step
   children inherit it, key/chain-step children are
   "ENRICHED". A child text is labelled only if not
   already in `label_of` (first-generation-wins), at
   generation time — whether or not it survives `seen`
   dedup into the candidate list. (Generation order
   inside `extended_variants` is the stock order:
   baseline variants, then keys, then chains; frontier
   parents are processed in frontier order — together
   these fix "first".)
2. **Guard hook.** A `guard: bool` parameter. After the
   stock frontier list is built and before it is
   assigned: if guard and frontier and no member has
   label BASE and any scored candidate has label BASE:
   `frontier[-1] = argmax_BASE(scored)` where argmax is
   the first BASE entry in the round's ranked scored
   order; record the actuation event (occupant +
   displaced hashes). With guard=False the hook is a
   no-op and the function is behaviour-identical to
   `solve_task_param` — step 2's gate is the proof.
3. **Anchor recorder.** The round log gains the A.4.1
   fields, computed from structures already present
   (candidates, scored, frontier, label_of) after
   selection — observation-only, exactly as PR #184's
   recorder. frontier_in is the frontier list entering
   the round (labels attached); frontier_out is the
   post-guard list.

### B.3 Battery wiring (step 4)

`lineage_guard_gate.py` loads the registry via PR #175's
fail-closed loader (path from the activation record),
imports `run_battery`, and binds `solve(task_id, keys)`
twice: stock = `solve_task_param` defaults, guard OFF;
guarded = `solve_task_guarded`, guard ON — both under
the PR #175 witness protocol (cap 4000, 60 s wall,
witness universe reconstructed by the v3 split, seed
20261501). It writes the battery report (schema
`ace.distractor_inoculation.v1`, unmodified) for both
bindings plus the anchor NO_REGRESSION artifact, and
exits non-zero unless guarded==NOT_SUSCEPTIBLE ∧
stock==SUSCEPTIBLE ∧ NO_REGRESSION — the step-4 stop
rule is therefore mechanical, not a judgement call.

### B.4 Unit tests (must pass at build, before any gate)

Labels: (1) start is BASE; (2) baseline child of BASE
is BASE; (3) key child of BASE is ENRICHED; (4) baseline
child of ENRICHED is ENRICHED; (5) a text first generated
ENRICHED and later generated via a baseline step keeps
ENRICHED (first-wins); (6) chain child is ENRICHED.
Guard: (7) no trigger when a BASE member is already in
the frontier (frontier unchanged); (8) no trigger when
no BASE candidate was scored (unchanged); (9) trigger
replaces exactly the last member with the highest-ranked
BASE scored candidate and records occupant/displaced;
(10) guard OFF reproduces `solve_task_param` outputs on
synthetic tasks bit-for-bit. Anchor: (11) round-log
fields present and label-consistent on a synthetic
solve; (12) L5 checker flags a hand-corrupted actuation
record. Twelve tests, all synthetic — no band, no
registry, no witnesses.

### B.5 Evidence layout (reserved paths)

`evidence/lineage_guard_run.json` (top record: act
fields, gate results, per-band digests, worksheet
inputs, verdict); `evidence/lineage_guard_state/`
(gate.json, anchor_dev.json, battery_stock.json,
battery_guarded.json, per-band per-cell checkpoints);
anchor records embedded per cell record (they are part
of the cell record, not side files). Push route: draft
PR, sha256-verified, per the standing storage rule.

### B.6 Estimated shape (for the act's window planning)

Build + tests: one work session. Steps 2–4 reuse the
development witnesses (PR #184's full gate took ~15 min
of wall on a contended VM; battery demo in PR #175 took
210 s). Step 6 dominates: 2 arms × (1+#distractors)
conditions × 3 bands × ~34 control tasks at v3 solve
costs — the act should reserve a long-run window with
per-cell checkpointing, as in abc-v3-01.

## 8. What the activation act must supply (complete list)

1. The Stage 3 verdict reference (PR/commit) confirming
   P1–P3. 2. Three confirmation-band seeds satisfying
   A.5. 3. The registry snapshot (path + sha256 + ids).
4. The executing room and operator. 5. The run window.
Nothing else is open: on those five, this draft locks
as the preregistration without further editing, and any
later change is an amendment recorded against it.

— Regression-control worker post (ila), 2026-11-13.
Parked with PR #188, pending the Stage 3 verdict.

## 9. Activation act — the five §8 fields, supplied (2026-11-15)

Recorded by Ian (main execution session) under the hub's
ratification act of 2026-11-14 ~01:56 WIB and the hub's
completion order of 2026-11-15, from the re-baseline
package `evidence/lineage_guard_rebaseline/` (branch
evidence/ace-omega-lineage-guard-rebaseline-20261115,
local commits 13bd6f0 + 88fb9e1; push pending the owner's
word). This act supplies the five §8 fields; the text
above is unchanged. The sealed run starts only when
fields 3 and 5 are closed at lock time as specified
below.

**Field 1 — Stage 3 verdict reference.** PR #192 (head
0cfc1199467dbeb4929c6cee72bb5c288390288f), record
`evidence/ctrlreg_stage3_official_record.json`: P1
REPRODUCED, P2 HELD, P3 HELD on bands 20261601–20261603.
Pre-audit C1–C4 (PR #194): substance verified clean; the
two C2 misses are verdict-string form only. The
confirmation recorded on main at 5f2daf0 (bands
20261701–20261703, GUARD_ADOPTED) was NOT ratified by
the hub (2026-11-15 ~06:10 WIB) — its seeds are spent
and are not reused.

**Field 2 — Confirmation-band seeds (re-baselined).**
Discovery re-run under origin/main 7541782 (the Stage L2
expansion changes catalogs, so the 20261701–03 catalogs
cannot be reused); digests recomputed from the saved
discovery files, ALL MATCH (`digest_verification.json`
in the re-baseline package):

- 20261801 — `a9ddf613eda090d88897866444f7db274aeb89b3f50cf3e375363fa0d056e711` (6 keys, 2 chains)
- 20261803 — `465508efbe082f31a3f87ccf01742cfc43fb76c97477577027a9bc0e44c35913` (6 keys, 0 chains)
- 20261804 — `5005072890bf608dc78a98965e6c9a3bf729a517c9689a12a9ccc051cbbaf62a` (6 keys, 1 chain)

Each band's admitted catalog was checked against the
registry causal key `('name_swap', (5, 2, 3, 0, 1, 4),
'nc')`: none of the three admits it (nor any 'nc'
name_swap key) naturally, so the infected construction
stays non-degenerate. The seeds are disjoint from
20261501–20261503, 20261601–20261603, 20261701–20261703
and from every development set.

Deviation note (A.5): A.5 asks for three consecutive
seeds. Seed 20261802, the middle of the block, was
rejected by the re-baseline because its catalog admits
the causal key plus two further 'nc' variants naturally
(60 keys; an effect of the Stage L2 expansion) — running
it would void the infected construction. The hub named
20261804 as the replacement in the same block. The three
seeds above are therefore consecutive-but-one; the
deviation and its reason are recorded here for the
ratifying act to accept or reject at lock time.

**Field 3 — Registry snapshot.** Procedure (the value is
taken at lock time, from inside custody): read
`/workspace/ace-custody-lineage-guard/wt-battery/code/ace_operational/distractor_registry.json`,
recompute its sha256 on the host, and record path +
sha256 + ids in the run record. Expected anchor (frozen
battery supplement, PR #195): sha256
`f9d8982a1314cc5807f815dc700affd0c3dd9cf42ff2b35855a7704dc0911680`,
ids `["name-swap-523014-nc-band20261501"]`. The
supplement was verified receiver-side in custody on
2026-11-15 ~19:55 WIB (tree digest
`f4d3c43bc86576e9c0eb16b95da7bb1eb42f62805b4733bcf558b1905654c5ef`,
EXACT), and the custody population likewise (80 files,
tree digest
`c02221775c2b81117effb93b204cccd0aaaa930e166e4a9c3883cf1d233fc6c2`,
EXACT). If the in-custody sha256 differs from the
anchor, STOP — the snapshot is void.

**Field 4 — Executing room and operator.** Execution
home: the ACE sandbox (host 2887726280f4), custody tree
`/workspace/ace-custody-lineage-guard` (R5-verified,
PR #196). Operator: Ian, the main execution session,
under ila's orchestration (hub). Access: the owner's
SSH door (sshremote, port 443; sudo in fresh sessions,
owner-granted 2026-11-15). Owner direction 2026-11-15
~20:26 WIB designates the sandbox as the execution
home. Run instrument: the PR #193 harness + gate,
harness commit
`73a902ec8b43518b95e69680d6d863eb1bd7f200`, transferred
into custody as supplement #2 (manifest
`handover/CUSTODY_SUPPLEMENT_MANIFEST_INSTRUMENT_20261115.json`,
frozen with this act).

**Field 5 — Run window.** Named by the hub at lock time.
Precondition: the previous lane's explicit all-doors
empty sign ("RUMAH KOSONG SEMUA PINTU"); a generation
log's ALL_DONE is not that sign. The former clean-logout
and custody-access gates were lifted by the owner on
2026-11-15 ~20:28 WIB and are no longer prerequisites.
No window is claimed by this act.

— Ian (main execution session), 2026-11-15. Recorded
locally on branch research/ace-omega-lineage-guard-act-20261115
based on PR #188's head df4d35fa; push pending the
owner's word.
