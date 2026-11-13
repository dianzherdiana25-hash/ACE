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
