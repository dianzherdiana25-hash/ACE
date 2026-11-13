# Round-2 gate — preregistration (LOCKED)

Experiment: `round2-gate-01`. Status: **LOCKED
2026-11-13** — locked by Ian under the owner's
decider-queue mandate (hub, 2026-11-13 ~11:03
WIB, reaffirmed ~12:01 WIB) after the lift build
landed (PR #161). This text is submitted to the
OMEGA-06 kernel at
`~/workspace/ace-omega/round2-gate-kernel/`; the
SHA-256 of this file is recorded in
`evidence/round2_gate_preregistration_record.json`
(harness-side) together with the kernel protocol
hash. Design source:
`ACE_ROUND2_GATE_DESIGN_20261113.md` (PR #159);
draft history:
`ACE_ROUND2_GATE_PREREGISTRATION_DRAFT_20261113.md`.

RATIFICATION DECISION (Ian, at lock): the
manifest construction is EXTENDED with a sixth
component — the `statement_ops.py` bytes,
appended last. Reason: the design's five-component
construction does not hash the schema module
itself, so the schema could change without
changing the improvement's identity — an
identity-fence hole. The five design components
are unchanged and in their design order; the
extension is additive and stated here, in the
locked text, before any run.

## §1 Claim

The lifted mechanism (frozen discovery
mechanism + statement-motion schema space,
lifted into the core behind the replication
guard) holds its effect on a fresh
order-sensitive universe: on held-out
statement_order tasks from a fresh band, the
lifted arm solves ≥ 80% of the
shown-discriminating tasks and captures ≥ 60%
of the direct-enumeration arm's gains, with
no regression on the stability family or the
controls.

## §2 Candidate

The lifted core, identified by its manifest
digest: SHA-256 over, in order, no separators —
the lifted `operator_discovery.py` bytes · the
frozen `grid_adapter.py` bytes · the lifted
`pricing_adapter.py` bytes · ASCII
`min_pool_fixes=2,max_rounds=6,frontier=4` ·
ASCII substrate freeze digest · the
`statement_ops.py` bytes (sixth component, per
the ratification decision above).
Manifest digest:
`47a5afc4b6c6222e6ee4050f620898aeb885ceaec2dc22a489e2914e490e9f81`
(the design's five-component digest of the same
files, for the record:
`f36218cd221ad0b294868473577f47dfb8f6f29da656b1a92701bb6ef018f441`).

## §3 Replication guard (must pass before the run counts)

1. Grid replication: the v4 protocol re-run
   through the lifted solver reproduces
   `operator_discovery_v4.json` on every count
   AND every admitted key set (exact match).
2. Pricing probe: the frozen substrate probe
   re-run on band 20000–20999 reproduces 1.000.
3. Sandbox replication: the round-2
   confirmatory run re-executed through the
   lifted core reproduces discovery-round2-01
   on every count and the admitted key set.
Any guard failure → the run abstains; no
transfer number is reported.

## §4 Universe and bands

- Target family: statement_order tasks from
  pricing seeds **72000–72099** (in order;
  first 10 built = pool, next 30 =
  evaluation). Validity gate: the variant
  must fail ≥ 1 case of the reference's grid.
- Stability family: grid tasks from the v4
  protocol's evaluation set (the lifted core
  must not degrade the frozen mechanism's
  grid effect).
- Controls: ordinary lab pricing singles,
  level 1 seeds 71000–71029 and levels 2–3
  seeds 71000–71014.
- Fences: the band is disjoint from the
  sandbox band (70000–70099), the calibration
  band (40000–40023), every G3 application
  band, and the B-3 probe bands. The lab
  generator and the B-3 v1 freeze are not
  modified.
- Arms: A = frozen mechanism; B = lifted
  mechanism (discovery on the pool, admitted
  under the frozen rule); R = direct-
  enumeration reference (all legal motions,
  no admission) for the capture ratio. Same
  tasks, same solver shape, same budgets.
- Score-call budget: 4000 per task per arm;
  per-task wall 60 s (exceeding it counts
  the task unsolved for that arm, listed).

## §5 Decision rule (ONE composite metric)

```
round2_index = min( B_disc - 80 , (capture - 0.6) * 100 ,
                    control_margin_pp )
B_disc = arm B's solved share (%) of the shown-
         discriminating evaluation tasks
capture = (B - A) / (R - A) in solved counts on the
          full evaluation set
control_margin_pp = min over control sets of
          (B_solved - A_solved) in tasks, x100/n
round2_index >= 0  ->  LIFT_DEMONSTRATED (if C1-C3 pass)
round2_index <  0  ->  NOT_DEMONSTRATED
```

If R − A = 0 the capture ratio is undefined
and the outcome is INCONCLUSIVE. Any drop in
the stability family's solved count forces
LIFT_WITH_REGRESSION regardless of the index.
The evaluation set is reported in both
conventions (overall n = 30 and
shown-discriminating); the pass rule reads
the discriminating subset as the effective n.

## §6 Kernel mechanics (resolved at submission)

- Candidate: `lifted-mechanism-round2`, manifest
  digest 47a5afc4… (above); baseline candidate:
  `frozen-mechanism` (the frozen discovery
  mechanism, manifest digest e2a59960… — the
  G3 application's candidate).
- Evaluator: `round2-instrument-v1`
  (`round2_instrument.py`, criteria v1) —
  digest
  `e08c15860e37765abe6195a438b2db1ade29004b4824fdb57a24cd41a0c3aa3c`.
- Kernel root: `~/workspace/ace-omega/round2-gate-kernel/`
  (created at this submission). Canary:
  `CANARY-R2GATE01-4b7d`. Split-custody keys:
  `r2gate01-candidate-key` / `r2gate01-evaluator-key`.
  Budget: wall_seconds 14400.
- Pass rule: single-metric dict
  `{"metric": "round2_index", "gte": 0}`.
- Custodies, audit CLEAN before any score is
  read, and the no-discovery attestation
  follow the G3 application pattern.

## §7 Pre-written consequences

- LIFT_DEMONSTRATED: the lifted core becomes
  the mechanism's next version candidate (a
  new freeze cycle, with its own probe and
  freeze record); the G3 SPECIALIZATION
  reading is revisited with the lifted
  mechanism as the candidate in a follow-on
  application.
- NOT_DEMONSTRATED: the lift direction is
  recorded as falsified at this scale on this
  class; the sandbox confirmation stands as
  a band-scale result.
- LIFT_WITH_REGRESSION: the lift is unsafe
  as a core change whatever its target effect.
- INCONCLUSIVE (R − A = 0): the class's shown
  set cannot discriminate the arms; a
  fresh-band run with order-discriminating
  shown sets is required before any transfer
  claim.

Brain of origin: Muse (Ian).
