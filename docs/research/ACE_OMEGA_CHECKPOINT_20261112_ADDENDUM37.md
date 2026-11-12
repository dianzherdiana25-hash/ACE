# ACE Ω Checkpoint — Addendum 37 (composition discovery v2: the L2 diagnosis, fixed and measured)

Date: 2026-11-13 (Asia/Jakarta). Written directly on `main`.

## 1. What was built (draft PR #140, stacked on PR #137)

`discover_chain_for_task` in `operator_discovery.py`:
greedy-chain discovery with **re-enumeration at every step**
— at each step every variant of the current (intermediate)
program is scored, the chain advances on the best
strictly-improving variant, and ends at shown-perfect
(max depth 3; a length-1 result is single discovery's
domain, not a chain). Chains are admitted as composed
operators under the same ≥2-pool-task rule as single
operators and applied at solve time by `apply_chain`, each
key located on the program the previous step produced.

## 2. Measured (operator_discovery_v4; protocol identical to v3)

The same six mixed tasks that pair discovery scored 0/6 on
fed chain discovery; everything else in the protocol is
v3's. Run wall 1,337 s (v3: 853 s). Sweep 255 tests OK
(17 skipped).

- **Chain pool: 3/6 solved by chains** (pairs: 0/6). The
  L2 diagnosis — pairs fail because they compose keys from
  the original enumeration and never re-enumerate on the
  intermediate program — is confirmed by its fix.
- **Two chains admitted**: one credited to
  bounds_off_by_one, one to returns_start_distance.
- **Singles transfer rose 11 → 15**: bounds_off_by_one
  2→4, returns_start_distance 3→5, dist_step_2 and
  wall_char_x flat at 3. Admitted chains, present in the
  solver's variant set, also solve single-defect evaluation
  tasks.
- Mixed evaluation unchanged 18/18 (a ceiling set in L2);
  control unchanged 34/34.
- The remaining 3 chain-pool tasks stall: the greedy walk
  meets a non-improving step or the depth-3 bound. That is
  the mechanism's current limit, recorded as such — a
  beam-over-chains variant is the obvious next iteration
  and is NOT claimed here.

## 3. Consequence for the agenda

Cycle-#4 item 5 (improve discovered-operator transfer) has
its first positive mechanism result since Stage I: transfer
grows when discovery composes with re-enumeration. Item 4's
future A/B/C v3 (strategy-differentiated arms, per
Addendum 36) now has its third arm concretely available:
catalog+discovery-composition. The G3 line is unaffected:
the instrument build sits with the Antigravity bench
(Handover Package #01; the VM bench is live under the
owner's main account as of 2026-11-13 ~00:16 WIB, launch
awaiting the owner's word in the discussion room).

## 4. Gate board (unchanged)

G0 session-scoped PASS. G1 MEASURED — DEMONSTRATED.
G2 MEASURED — null ×2. G3, G4, G5 NOT_ASSESSED.
OAIE unproven (`oaie_proven=false`).

## 5. Queue after this addendum

Uji B2A-02 (harness-computed comparison tables; same
market, same 4/4 bar) → KBM pilot design package (separate
work, privacy rule applied) → services demand test →
A/B/C v3 design (strategy arms) when the queue reaches it →
G3 first application once an instrument exists (either
bench) → G4/G5 instrument implementations. The 14B partial
download (corrupted, 1.52/7.32 GB) still awaits a
resume/delete decision; no action taken.
