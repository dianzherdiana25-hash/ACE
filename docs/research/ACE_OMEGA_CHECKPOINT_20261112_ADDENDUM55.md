# ACE Ω Checkpoint — Addendum 55 (Discovery round 2: CONFIRMED)

Date: 2026-11-13 (morning package). Experiment
`discovery-round2-01`, preregistered in
`ACE_DISCOVERY_ROUND2_PREREGISTRATION_20261113.md`
BEFORE the run executed. This is a sandbox verdict,
not a gate verdict: it is the named input to the
next gate design, not the design itself.

## Numbers (preregistered confirmatory replication)

Band 70000–70099 (pool 10 / evaluation 30; 100/100
seeds built valid tasks); controls L1 71000–71029,
L2/L3 71000–71014.

- **H1 reachability: PASS.** Arm B solves 13/13
  shown-discriminating tasks (100%, design point
  ≥ 80%).
- **H2 transfer: PASS.** Capture = 1.0: arm B's
  gain over the substrate (5 solves) is captured
  entirely by the admitted-key arm C (13/30 vs
  8/30 for A). Exactly one motion key admitted:
  `("move_stmt", ("augassign","t","Add","t"),
  ("return",))` — the class's repair in general
  form.
- **H3 no regression: PASS.** Controls 30/30 (L1),
  15/15 (L2), 15/15 (L3) for both arms; the
  substrate is at ceiling on its own classes, so
  the check is one-sided as declared.
- **Overall: `ROUND2_CONFIRMED`.**

The preregistered numbers reproduce the
exploratory measurement (PR #154) on every count
and on the admitted key set — the replication is
exact, as the preregistration text disclosed it
would be judged.

## Consequence (pre-written in the preregistration)

The round-2 mechanism (motion keys as built) is
the named input to the next gate design: a core
lift behind a replication guard, under its own
fresh-band preregistration (named follow-on band
72000–72099). Open limits carried forward: the
collision-stability fingerprint (per-program
occurrence suffixes), If-block and nested motion
still design-not-prototype, and the depth-5 beam
still design-not-prototype.
