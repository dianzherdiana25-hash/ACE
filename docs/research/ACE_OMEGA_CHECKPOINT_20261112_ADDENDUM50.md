# ACE Ω Checkpoint — Addendum 50 (G3 application preregistration LOCKED)

Date: 2026-11-13. The G3 application's preregistration
is submitted to the OMEGA-06 kernel. **Protocol hash:
`5f907362e150d9cea1ef065010e11ff55592695720b5133d79d2b155aab8bb6d`**
(experiment `g3-application-01`, kernel root
`~/workspace/ace-omega/g3-kernel/`). Submission text:
`docs/research/ACE_G3_PREREGISTRATION_20261113.md`
(bench Task 11 draft as amended at lock-in; the four
amendments are enumerated in its §0). **G3 remains
NOT_ASSESSED** — a preregistration is a commitment,
not a result.

## What is locked

- **Artifact:** the discovery mechanism at the run
  lineage tip (commit 83041dc), manifest digest
  `e2a59960f8ccc7f8e991e77af99481ad603ce84c50a1b7f8299897b39c9975f8`
  under a published construction; its first two
  components re-verify the P1 mechanism digest
  `48f2d95d…b2f`. The A/B/C v3 solver lift is
  explicitly NOT part of this artifact.
- **Baselines:** grid substrate + frozen pricing
  substrate v1 (`658b9022…d21`), bundle digest
  `e5080181…73fa`. Negative control: sham arm with an
  empty catalog; any deviation invalidates the run
  (abstention, reason named).
- **Sets:** grid from a fresh universe (seed
  20261113, v4 split rule); pricing in TWO strata —
  catalog (band 50000–59999 against the frozen
  census, probe/calibration programs excluded by
  digest) and constructed (`statement_order`, 40
  evaluation singles, seeds 60000–60099) — reported
  per stratum under the coordinator's fence: a
  constructed-only positive is visible as such,
  never blended into a catalog transfer claim.
- **Rule:** per family Δ ≥ +10pp, ≥3 net-new solves,
  zero control regression; the kernel intakes ONE
  composite metric, `g3_composite_index_pp ≥ 0`
  (definition in the text §6.3) — the bake-off
  lesson applied. Instrument: PR #143 at dde75ef
  with both coordinator-ruling corrections.
- **Custody:** candidate custodian = the execution
  room; evaluator custodian = the sealed instrument
  side; distinct HMAC keys in the experiment's
  kernel root.
- **Budget:** 45 minutes wall for the whole run, or
  an abstention with that reason.

## Calibration state carried into the lock

Catalog stratum saturated (gate fired, 36/36 —
Addendum 48); constructed stratum baseline 20.8%
(gate passed — Addendum 49), with the discovery
calibration on that stratum at Δ = 0 recorded as
context. The run measures the frozen mechanism as
it is; expectations are not results.

Next: the application run itself (discovery per
family → sealed catalogs → evaluation arms as
separate processes → kernel audit → dossier →
instrument), then the consolidated report.
