# G3 APPLICATION PREREGISTRATION — submission text

Experiment: `g3-application-01`. Status: **SUBMISSION
TEXT** — the bench Task 11 draft as amended at lock-in
(2026-11-13) under the coordinator's ratifications.
Every ⟨TBD-AT-SUBMISSION⟩ field of the draft is filled
below; every substantive amendment is enumerated in
§0 and traces to a ratified decision or a measured
record. On kernel submission, the returned protocol
hash is recorded in the checkpoint lineage (Addendum
50). **Until that hash exists, this is not yet a
preregistration, and G3 remains NOT_ASSESSED.**

## 0. Amendments to the Task 11 draft at lock-in

- **A1 (§4 rewritten).** The draft's pricing table
  rested on the Task 07 initial census (216 programs)
  and CAP-1/2/3. The official B-3 census over the
  frozen generator counts **2,857 unique programs**
  (Addendum 47); the caps were re-derived and
  **retired as non-binding** (Addendum 48, ratified by
  the coordinator). §4 below is the re-derived table.
- **A2 (§5.2 replaced).** The draft's P4 step foresaw
  hardening levers and a D6 shipping substitution.
  What actually happened, in order: the catalog
  calibration fired the ≥90% gate (36/36, Addendum
  48); the coordinator **rejected** both of the
  draft's fallback shapes (shipping substitution;
  locking as-is) and instead ratified ONE new defect
  class at the dossier-construction level —
  `statement_order` — with three fences (dossier
  layer only, freeze untouched; calibration before
  lock under the same gate; strata declared). The
  class was constructed and calibrated (Addendum 49):
  baseline 20.8% on the constructed stratum — the
  gate **passes** there. §4 and §5 carry this.
- **A3 (§6 completed).** A single composite metric is
  defined (§6.3) so the kernel's verdict derivation
  can intake the rule as ONE metric (bake-off 01
  lesson: prose conjunctions cannot be recorded).
- **A4 (§10 closed).** All eight blockers are closed
  with named artifacts (§10).

## 1. Hypothesis (falsifiable)

**H1.** The frozen operator-discovery mechanism (§2),
applied unchanged to two distinct task families —
grid (source) and pricing (target) — discovers, from
each family's own discovery pool, an admitted catalog
that improves that family's solver on held-out
evaluation tasks by the margin fixed in §6.

H1 is **falsified for pricing** if the pricing effect
is not positive under §6; **falsified as a transfer
claim** if either family's effect is not positive
(outcome `SPECIALIZATION` or `NOT_DEMONSTRATED` per
§6's mapping). A null result is a publishable measured
outcome; no re-run until green is permitted under
this registration.

## 2. The artifact (frozen, identity by digest)

Reading M (D1): the artifact is the discovery
**mechanism core** — `operator_discovery.py` at the
run lineage tip (branch
`research/ace-omega-b3-pricing-substrate-20261113`,
commit 83041dc), the schema-space enumeration, the
admission rule (an operator is admitted only if it
fixes ≥2 independent pool tasks), the chain-discovery
bounds (composition discovery v2), and the greedy
solver loop — together with the two family adapters
that bind it, named here because the run executes
through them. The catalog discovered per family is
*output* and is expected to differ per family; the
transfer claim is mechanism transfer, stated openly
wherever results are reported.

**Artifact manifest** (construction published, per
the B-3 lesson): SHA-256 over, in order, with no
separators — `operator_discovery.py` bytes ·
`grid_adapter.py` bytes · `pricing_adapter.py` bytes
· the ASCII bytes of
`min_pool_fixes=2,max_rounds=6,frontier=4` · the
ASCII bytes of the pricing substrate freeze digest
(§3). Component digests:
`operator_discovery.py` =
`23448d8b9eb48b784f75b36113ced46e30f16a8b5ce727cba301de2cfc609708`;
`grid_adapter.py` =
`d7803d0c6bac99deed50a063fa304e41acf455062ec4a7cf123e333dd38802f7`;
`pricing_adapter.py` =
`0f19ff1cbf40c2f0f255f0bc77dcaecd39a0f2fb929e5b1237bb6018e098e72b`.
**Manifest digest:
`e2a59960f8ccc7f8e991e77af99481ad603ce84c50a1b7f8299897b39c9975f8`.**
Relation to the earlier freeze: the first two
components alone hash to the P1 mechanism digest
`48f2d95d…b2f` (Addendum 46), re-verified at lock-in
from these exact bytes. Any change to the mechanism
after this manifest is a new improvement: this
registration is void for it. (The A/B/C v3 solver
lift exists only on its own branch and is NOT part
of this artifact.)

Family machinery is **not** part of the artifact:
task generators, per-family baseline variant
generators, scorers, budgets. The two arms' variant
sources differ **exactly** by the admitted catalog
(the arm-collapse fence); both baseline identities
are named in §3 so the audit can check this.

## 3. Candidates, baseline, negative control

- **Candidate:** the §2 mechanism; per family, the
  extended solver = baseline solver + the catalog
  admitted from that family's pool.
- **Required baseline (per family):** the same
  solver restricted to the pre-discovery path.
  - Grid: `grid_variants` over the grid substrate's
    `_OPERATORS` (module `grid_substrate.py`,
    sha256
    `56fcafbd2afcbe00bed86aa4b6f4126dab8936f4408060fb5953fbebdf28ccb6`),
    bound via `GridAdapter`.
  - Pricing: the **frozen B-3 substrate v1** —
    `pricing_variants` over
    `_variants_threshold, _variants_rebase_basis`,
    freeze digest
    `658b9022681bcb9e658b7b3f1c85fd3bc8e106718dca8b5ff1fd6b8cffd6bd21`
    (Addendum 47; construction published in the
    freeze record §6) — bound via `PricingAdapter`,
    whose `baseline_catalog_id` carries that digest.
  - Baseline bundle digest (SHA-256 over
    grid_substrate bytes · pricing_substrate bytes ·
    ASCII `max_rounds=6,frontier=4`):
    `e50801814582d5066b97180faf61dbb6be73e7006e69a4f29def59d9b07673fa`.
- **Negative control:** a sham arm per family — the
  extended solver loaded with an **empty** discovered
  catalog — run on that family's evaluation singles.
  Expected: identical solved set to the baseline arm
  (±0 tasks). Any deviation is a harness-leakage
  finding: the run is invalid, recorded as an
  abstention with that reason, and no family effect
  may be scored from it.

## 4. Sets and allocation (re-derived; seed table)

All sets are pairwise disjoint — by task id for grid;
by `normalized_form` program identity for pricing —
and disjoint from every prior run's draws, enumerated
here: grid universe seed 20261112 (v4, P1 guard, v3
guard); pricing bands 5000–5999 (probe v1), 20000–
25999 (census + probe v2), 30000–30999 (P4 catalog
calibration), 40000–40023 (statement_order
calibration references). Pricing allocation draws
additionally **exclude by program digest** every
program appearing in the B-3 probe sets or in either
calibration, wherever its seed band lies. Evaluation
tasks are never touched by discovery; calibration
tasks are sealed and never reused as evaluation.

**Grid** — fresh universe `build_universe(seed=
20261113)`, split by the v4 rule (first 3 singles per
new-defect class to the pool; first 6 mixed pairs to
the pair pool; the remaining new_only tasks are the
evaluation; `catalog_control` is the control):

| Set | Size | Composition |
|---|---|---|
| Discovery pool | 12 | 3 per defect class × 4 classes |
| Evaluation | ≥40 singles + 18 mixed | held-out singles + 2-defect |
| Control | ≥30 | baseline-solvable (catalog control) |

**Pricing — catalog stratum** (frozen generator;
band 50000–59999, levels 1–3, seed order):

| Set | Size | Composition rule |
|---|---|---|
| Discovery pool | 12 singles | 4 per defect class × 3 classes |
| Evaluation | 45 singles + 18 pairs | 15 singles per class; 6 pairs per pair class |
| Control | 30 | drawn after evaluation from the remaining programs, each verified solved by the frozen substrate on all cases (the substrate-solved population) |

**Pricing — constructed stratum** (`statement_order`,
dossier construction per Addendum 49; the constructor
is part of this registration's harness, named here:
AST move of the final top-level `Add` AugAssign to
directly after the opening assignment, validity-gated
on failing ≥1 grid case):

| Set | Size | Composition rule |
|---|---|---|
| Evaluation | 40 singles | seeds 60000–60099 in order, first 40 validity-passing constructions |

The constructed stratum is evaluation-only: the
pricing discovery pool is the catalog pool above, and
the family's control is the catalog control. Results
are reported **per stratum** alongside per family
(§6.4): a positive driven only by the constructed
stratum is visible as such and is never blended into
a transfer claim over the frozen catalog.

Supply check against the frozen census (2,857
programs; 1,439 singles / 1,418 pairs): worst-case
draw 111 singles + 48 pairs plus exclusions — no
segment binds; CAP-1/2/3 stand retired (Addendum 48).

## 5. Procedure

1. **Replication guard (done, pre-freeze).** The P1
   guard reproduced the v4 record exactly through
   this lineage's core (Addendum 46 §2); the
   mechanism digest was re-verified at lock-in (§2).
2. **Calibration (done, pre-submission).** Catalog
   stratum: baseline 36/36 — gate fired (Addendum
   48). Constructed stratum, same gate: baseline
   5/24 = 20.8%, strictly inside 10–90% — gate
   **passes** (Addendum 49). The comparator and
   discovery calibration arms of Addendum 49 are
   recorded context; the application's arms are
   §3's, run fresh.
3. **Discovery:** per family, on that family's pool
   only, under split custody (§7). Discovered
   catalogs are sealed (per-family catalog digest
   recorded) before evaluation opens.
4. **Evaluation:** per family, baseline + extended +
   negative-control arms on the identical
   evaluation/control sets, same budgets, arms as
   separate processes with no shared state; scoring
   under the timeout-guard discipline (a timeout is
   a failed candidate, never a hang). Constructed-
   stratum tasks are evaluated by the same two arms
   (no separate discovery).
5. **Budget:** wall-clock budget for the whole run
   45 minutes; the kernel budget field carries it
   and the run must fit it or abstain with that
   reason recorded.

## 6. Pass rule (mechanical; verdicts derived)

### 6.1 Family effect

A family's effect is **positive** iff all three hold
on its audited report: (1) **Δ ≥ +10.0 percentage
points** (extended − baseline solved fraction on
evaluation singles — for pricing, pooled over both
strata's singles, with per-stratum figures reported
per §6.4; the report carries `margin_pp: 10.0`);
(2) **≥3 net-new solves** across the family's
evaluation singles; (3) **zero control regression**.

### 6.2 Outcome mapping (scored by the instrument)

| Grid | Pricing | Outcome |
|---|---|---|
| positive | positive | `TRANSFER_DEMONSTRATED` |
| positive | not positive | `SPECIALIZATION` |
| not positive | positive | `NOT_DEMONSTRATED` * |
| not positive | not positive | `NOT_DEMONSTRATED` |
| any item missing/malformed, digest mismatch, audit not CLEAN, negative-control deviation | — | `NOT_DEMONSTRATED`, items named |

\* Grid is the C1 source family (effect re-measured
fresh under this registration). A pricing-only
positive is recorded as a named observation — a
candidate new source effect for a future
registration — never rescored into this one.

### 6.3 Composite metric (kernel intake)

`g3_composite_index_pp` = the minimum, in percentage
points, over: Δ_grid − 10.0; Δ_pricing − 10.0;
(net-new_grid − 3) × (100 / n_eval_singles_grid);
(net-new_pricing − 3) × (100 / n_eval_singles_pricing);
and −100 × (total control regressions). Kernel pass
rule: `g3_composite_index_pp ≥ 0`, which holds iff
both families are positive under §6.1 — the kernel's
pass/fail is the numeric shadow of H1; the
instrument's outcome word (§6.2) is the dossier's
verdict and is reported with it. A negative-control
deviation or a budget overrun records **no** metric
and abstains with the reason named.

## 7. Custody and audit requirements

- **Split custody (OMEGA-06):** candidate custodian
  = the execution room (Ian, Muse — runner of the
  discovery/evaluation arms); evaluator custodian =
  the sealed evaluation side (the G3 instrument +
  dossier assembly, key held separately in this
  experiment's kernel root
  `~/workspace/ace-omega/g3-kernel/`). Each signs
  their artifact digests per the kernel's HMAC
  discipline. Evaluation seeds stay sealed with the
  evaluator custodian until the run.
- **Kernel audit must return CLEAN** over the
  registration + both family reports before the
  instrument scores anything. INCOMPLETE is not
  CLEAN and fails the dossier by name.
- Every family report carries: this registration's
  protocol hash (back-reference, must equal), kernel
  audit result, the artifact digest as evaluated
  (must equal the §2 manifest — mismatch triggers
  the instrument's hard fence), its discovered
  catalog's digest, task-id lists for
  pool/evaluation/control, per-arm solved counts and
  fractions (per stratum for pricing), `margin_pp`,
  control regression count, wall time, runner
  identity, brain-of-origin.
- The results ledger is append-only; forged or
  post-hoc edited entries invalidate the run at
  audit.

## 8. Dossier and scoring

The dossier follows the built instrument's final
schema (PR #143 at dde75ef, including the two
coordinator-ruling corrections: source report
checked once; clause verdicts from valid evidence
with surplus invalid entries as named warnings).
The grid report serves as both the C1 source report
and a family evaluation (the instrument's declared
interpretation); family identities are exactly
`grid` and `pricing`; margins are read by the
instrument from the reports. The assessment, its
criteria version, and the brain-of-origin of every
contribution are recorded in the checkpoint lineage.
ila independently verifies (diff, instrument re-run,
audit trail) before any figure reaches the owner.

## 9. Reporting commitments

Results are reported to the owner as one consolidated
report stating: the outcome word, per-family and
per-stratum numbers, the Reading-M caveat (mechanism
transfer; catalogs differ per family), the
calibration outcome, and any named failures. A null
or `SPECIALIZATION` outcome is reported with the
same prominence as a positive one.

## 10. Blockers — all closed

- **B1 (P1 refactor):** closed — PR #148; v4
  replication guard EXACT (Addendum 46); R7 closed
  in writing there.
- **B2 (P2 adapter):** closed — PR #149 (adapter +
  4 machinery tests; sweep 259 on the lineage).
- **B3 (substrate frozen):** closed — PR #150;
  freeze digest §3; verified TAHAN by two
  independent checkers; digest construction
  published (freeze record §6).
- **B4 (P4 calibration):** closed — Addenda 48 + 49;
  the ratified path (A2) replaced the draft's D6
  fallback by the coordinator's explicit rejection
  of it.
- **B5 (official census + re-derivation):** closed —
  census 2,857 (Addendum 47); §4 above is the
  re-derived table (A1).
- **B6 (instrument corrections):** closed — PR #143
  final HEAD dde75ef carries both rulings; 19
  instrument tests green on that lineage.
- **B7 (seed ranges):** closed — §4's seed table,
  with prior usage enumerated and program-digest
  exclusions named.
- **B8 (custodians):** closed — §7 names both
  custodians and the kernel root.

## 11. Submission checklist

1. §4 re-verified against the official census — done
   (A1).
2. Calibration run and recorded — done (§5.2).
3. Replication guard clean; mechanism frozen;
   manifest computed — done (§2).
4. Seed table fixed; baseline generators and
   custodians named — done (§3, §4, §7).
5. Instrument corrections confirmed — done (§8).
6. Submit this text to the OMEGA-06 kernel; record
   the protocol hash in Addendum 50.
7. Only then: discovery, evaluation, dossier,
   scoring (§5, §8).

— End of submission text. Prepared by Ian (Muse,
ACE's registered development-engine brain) from the
bench's Task 11 draft under the coordinator's
ratifications; brain of origin recorded.

## Lock-in evidence record (added 2026-11-13, hub condition (b))

The statement_order calibration evidence, stated in
full here as the hub's lock-in condition requires —
not only by reference to Addendum 49. Calibration set:
24 constructed single-defect tasks, seeds 40000–40023
(now SEALED; in §4's exclusion list alongside the B-3
probe band). Three arms, holdout-judged:

- **Frozen-substrate baseline (the application's
  baseline arm): 5/24 = 20.8%** — strictly inside the
  ratified 10–90% gate. The class is ~79%
  substrate-blind yet solvable by construction; a
  near-zero application effect on this stratum is
  therefore read as a named-cause result (below),
  NOT saturation and NOT a null by construction.
- **Generic token-search comparator: 0/24.**
- **Discovery (mechanism exactly as frozen, digest
  §2; pool 8 / evaluation 16): 11 operators admitted
  from the pool; evaluation baseline 4/16, extended
  4/16 — Δ = 0.**

Named cause, recorded BEFORE the run as a prediction:
the frozen mechanism's schema space enumerates
expression-level edits only; it contains no statement
motion, so no pool-admitted operator can express this
class's repair. The application measures the frozen
mechanism as it is; if the run confirms Δ ≈ 0 on this
stratum, that confirms this boundary prediction —
it does not explain it away after the fact. The
falsification consequence (schema-space round 2 with
statement-level operators) is the escalation
package's discovery v-next stage and is NOT opened
before this application is measured.

## Interpretation note + amendment withdrawal (2026-11-13)

**Amendment withdrawal.** A seed amendment ratified
earlier today (selection of the grid universe seed by
a size rule) is declared **VOID** by the coordinator
and is withdrawn here: it was born of a
counting-convention misreading (below). The §4 seed
table stands as locked (grid universe seed 20261113);
no active amendment remains for this registration.

**Interpretation note (not a change of any number).**
The §4 grid evaluation floor ("≥40 singles + 18
mixed") reads in the per-class aggregate convention
of this registration's own reference protocol: in
composition-discovery v4, the evaluation actually run
was 11 pure singles + 18 mixed = 29 tasks, whose
by_class aggregate (a 2-defect task counting toward
both its classes) is 47. The pure-singles reading is
structurally impossible in this universe family at
any seed — a 40-seed scan (20261114–20261153, trail
preserved in the run record) yields 23–24 new_only
singles at every seed (ceiling 4 classes × 6). This
run's grid composition, reported in both conventions
wherever it appears: **pure 12 singles + 18 mixed;
aggregate 48** — the floor is met under the
reference protocol's convention. The family pass rule
(§6) is computed per task over the exact evaluation
set; this note touches only the floor-compliance
statement, never Δ or margin. It applies to the grid
evaluation row only: pricing floors read pure and
are met purely (45 singles + 18 pairs), and the
constructed stratum stands at 40 per the lock. This
note and the withdrawal were decided in a
zero-solving state, before any arm of the run had
executed.
