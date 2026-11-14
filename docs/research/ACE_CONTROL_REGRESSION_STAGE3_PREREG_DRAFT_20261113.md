# ACE Ω — Stage 3 Preregistration DRAFT: One-Variable Intervention on the Control-Regression Mechanism (2026-11-13)

**Status: DRAFT — text only. NOT locked, NOT ratified, and no
official run is authorised by this document.** Execution waits
for internal ratification (hub act) per the framing correction
in PR #173 §10: ratification is ACE's own constitutional
discipline; the owner receives reports, not approval requests.
Prepared in the regression-control lane from the design draft
PR #173 (§7 one-variable discipline, §8 evaluation rules), the
Stage 0–2 evidence (PR #174) and the inoculation battery
(PR #175, untouched by this item).

## 0. What is already locked (not reopened by this draft)

- Stages 0–2 are complete. The band-20261501 control
  regression (A 34/34, B 32/34, C 32/34) is causally
  attributed to ONE distractor key —
  ('name_swap', (5, 2, 3, 0, 1, 4), 'nc') — necessary for
  both failures (leave-one-out restores both tasks), with
  dose onset exactly at the key's entry into the prefix
  catalog (between k=24 and k=48; position 31), order axis
  inert (8/8 permutations, byte-identical scored multisets).
- Mechanism as attributed: search-path diversion — under the
  full catalog, arm A's winning code is NEVER among the
  scored variants (Stage 1). M1a (cap truncation) is dead
  (cap never hit; capped == uncapped). M2's named
  shown-perfect signature was absent. What remains OPEN —
  and what Stage 3 exists to close — is the bounded-loop
  question in its §7-split form: would more ROUNDS alone,
  or a wider FRONTIER alone, have recovered the witnesses
  despite the diversion? The executed Stage 1 harness
  covered the distractor and order axes; the budget-axis
  counterfactual in the design (§4 Stage 1(i)) was specified
  as a combined doubling and was not executed in that form.
  This draft supersedes that combined form with the §7
  split, which is strictly more informative.
- This item is NOT a re-run of A/B/C v3, moves no gate
  board, and touches no sealed instrument (v3 kernel,
  frozen evidence packages read-only; inoculation battery
  unmodified).

## 1. Development-band preparation (this lane, measured)

Harness: evidence/ctrlreg_stage3_intervention_harness.py
(dev witnesses only). Results:
evidence/ctrlreg_stage3_intervention.json.

- Logging-invariance gate (§7.2): PASS, 4/4 comparisons
  (2 witnesses x arms A/B, capped). Stock solver, parameterised
  solver without logging, and parameterised solver with full
  logging return identical sha256 / solved / score-call
  counts / provenance traces, and reproduce the Stage 0
  anchors exactly (A: 6504b23b…; B: dcfb155f… / 6577e3ee…).
  Catalog digest a6768563… asserted; 'nc' key at position 31.
- Uncapped control cell (§8(d)): REPRODUCES the failure on
  both witnesses — solved=False, score calls 410 / 159
  (identical to the capped Stage 0 record; the cap is again
  non-binding), returned hashes identical to the Stage 0
  failing returns, termination frontier_empty on both
  (020 after round 6, frontier sizes [1,2,1,1,2,0]; 021
  after round 3, [1,1,0]). Comparisons below are therefore
  readable under §8(d).
- rounds_only (12 rounds, frontier 4): NO recovery on either
  witness, and the outcome is byte-identical to control
  (same calls, same returned hash, same frontier
  trajectory). The raised round limit never binds: the
  search terminates by frontier exhaustion at exactly the
  stock round on both tasks. Extra rounds are unreachable
  capacity for this mechanism.
- frontier_only (6 rounds, frontier 8): NO recovery on
  either witness, likewise byte-identical to control. The
  widened frontier never binds either: the frontier holds
  at most 2 members in any round of either witness (the
  score >= best filter, not the width, is what empties it).
- True-path classification (§7.3): never_generated — in
  EVERY round of EVERY cell, on both witnesses. This is
  sharper than Stage 1's "never scored": the winning code
  is never even produced as a candidate, because candidates
  are generated only from frontier parents and the baseline
  lineage leaves the frontier in round 1 (frontier size 1
  after round 1; the round-1 improving step is the 'nc'
  key's, per the Stage 0/1 traces). On these witnesses the
  phenomenon is not pruning and not budget: it is
  generation-side lineage loss.

Interpretation, labelled as such: M1b is dead in BOTH split
forms on the development witnesses (the design's §5 kill
rule — doubling rounds/frontier does not recover — now
executed in the §7 split form). Any solver consequence
aimed at round or frontier budgets has no purchase here.
What binds is frontier MEMBERSHIP in round 1 — which
lineage survives to generate round 2. This is why §2.4's
predictions and §2.6's pre-written consequence below are
stated in lineage terms, not budget terms.

Development results inform this draft's predictions; they
are NOT Stage 3 evidence and are never reported as such.

## 2. Stage 3 design (fresh band, for ratification)

### 2.1 Band and catalog
- Fresh seed band: this lane PROPOSES 20261601–20261603
  (three consecutive seeds, disjoint from 20261501–20261503
  and from every band used in Stages 0–2 development work).
  Ratification fixes the seeds and includes a collision
  check against the program's run registry; the ratified
  seeds are recorded here before any run.
- Per band: universe built by the v3 census procedure
  (build_universe -> split_universe, byte-identical code
  path); catalog admitted from THAT band's own discovery
  phase (same admission rule as abc-v3-01); catalog digest
  recorded per band before solving.
- Control set: that band's catalog_control subset, with
  PER-TASK control outcomes recorded by construction
  (task id x arm x solved x termination reason x score
  calls x returned sha256) — the §5 standing consequence,
  applied here from the start, not retrofitted.

### 2.2 Arms (one-variable discipline, §7.1)
All arms solve the SAME control tasks under the SAME
admitted catalog of their band, UNCAPPED score calls
(§8(d) form), identical logging (the gated harness):
  S  stock:        rounds=6,  frontier=4
  R  rounds_only:  rounds=12, frontier=4
  F  frontier_only: rounds=6, frontier=8
No arm raises both variables. No other solver parameter
differs between arms. The solver under test is the
parameterised harness solver whose default-configuration
equivalence to the stock v3 solver is proven by the
logging-invariance gate on the development witnesses
(§1); the gate is re-run on each fresh band's first two
control tasks before that band's arms are read, and a
gate failure voids the band (stop, record, report —
§7.2 discipline).

### 2.3 Distractor condition
The fresh bands' own admitted catalogs may or may not
contain a diverting key. To keep the mechanism under test
present by construction rather than by luck, each band is
run in two catalog conditions:
  clean    — the band's admitted catalog as discovered;
  infected — the same catalog plus the registered 'nc'
             distractor key injected at the END (the
             inoculation battery's injection form, PR #175;
             presence test, order measured inert in Stage 1).
Arms S/R/F x conditions clean/infected = 6 cells per band.
The clean condition is the no-harm control: an intervention
that "recovers" by degrading clean-condition performance
is a regression, not a remedy (§8(a): benefit and
control-protection are read PAIRED, with search cost
visible — score calls and wall per task reported per cell).

### 2.4 Predictions (registered in advance)
P1 (diversion reproducibility): in the infected condition,
arm S fails at least one control task that the same band's
clean condition solves, OR the phenomenon does not
reproduce on fresh bands and Stage 3 closes as
NOT_REPRODUCED (a result, recorded as such — no band
fishing: the three bands above are the whole design).
P2 (one-variable inertness, dev-informed): if P1 fires,
NEITHER R nor F recovers the infected-condition failures
of S (recovery = §2.5) — the development witnesses show
both interventions as byte-identical no-ops, because both
limits fail to bind before frontier exhaustion. Recovery
by either arm on a fresh band contradicts the development
record and reopens attribution (it would mean the fresh
band's failure has a different binding constraint);
recovery by both is additionally declared NON-SPECIFIC.
P3 (true-path signature): for every task S fails in the
infected condition, the per-round ranking trace of the
clean-condition winning code (identity from the clean
condition's own returned_sha256 for that task — the
fresh-band analogue of arm A's hash; holdout never used
for identification) classifies as never_generated — the
sharpened Stage 3-prep signature (§1). A classification of
generated_never_scored on a failed task weakens the
lineage account to the Stage 1 form; a
scored_pruned_below_frontier classification on a majority
of failed tasks contradicts the diversion account
entirely and reopens attribution before any consequence
is drawn.

### 2.5 Recovery criterion and reading rules (§8)
- Recovery is per-task: SOLVED under the intervention arm
  (returned code passes ALL holdout cases) where arm S
  failed, same band, same condition. Hash equality with
  any other arm's solution is recorded for information
  only and is NEVER the criterion (§8(c)).
- A comparison is readable only if, in the same band and
  condition, arm S's infected cell still shows the P1
  failure pattern and its clean cell solves those tasks
  (§8(d) analogue: the control must reproduce before the
  comparison is read).
- Costs are part of the result: an arm that recovers at
  >3x the median score calls of arm S on the same tasks
  is reported as recovery-at-cost, and any solver-design
  consequence must carry that cost in its statement.
- Controls reused across stages are development data
  (§8(b)): the fresh bands' control sets are retired from
  future confirmatory use once Stage 3 has run on them.

### 2.6 Stops and fences
- Gate failure (logging invariance) on any band: stop
  that band, record, report; no silent re-instrumentation.
- Non-reproduction across all three bands: close as
  NOT_REPRODUCED with the full record; no additional
  bands, no parameter variants.
- No solver change is implemented by Stage 3 itself.
  Pre-written consequence, specialised by the §1
  development record (superseding the budget forms of
  PR #173 §5 for this mechanism, which the split tests
  killed): IF Stage 3 confirms P1 + P2 + P3 on the fresh
  bands, the design consequence is a GENERATION-SIDE
  lineage guard — at least one frontier slot reserved
  for the best baseline-provenance candidate per round,
  so the catalog-only lineage can always keep generating
  — to be specified and A/B-tested as a separate
  preregistered change, with the regression anchor
  (incl. the PR #175 inoculation battery) run before it
  measures anything. If instead a fresh band exhibits
  PR #173 §5's M2 shown-perfect signature (absent in all
  development work so far), the §5 selection-guard form
  applies unchanged. The fresh bands' traces decide
  which form; this draft does not pre-select beyond the
  dev-informed default.
- Harness version for the official run: the committed
  prep harness PLUS one named extension — per-round
  frontier provenance composition in the round log (the
  prep round log records frontier size and cutoff, not
  provenance) — re-gated on the development witnesses
  (gate must PASS again, §7.2) before any fresh band is
  touched. The extension is observation-only by
  construction and the re-gate is its proof.
- Bands 20261501–20261503 are never re-measured; the v3
  kernel record and all sealed evidence stay untouched.

## 3. What ratification is asked to decide
1. The fresh seed band (three seeds) in §2.1.
2. The infected-condition construction in §2.3 (registered
   'nc' key, end injection) — or clean-only, accepting
   that P1 may not fire.
3. The 3x cost ceiling in §2.5 as the recovery-at-cost
   reporting threshold.
Nothing else. On ratification, execution belongs to the
main execution room (Ian) as a sealed run; this lane's
harness and development record are the handover package.
