# ACE Ω Checkpoint — Addendum 51 (B-3 freeze verified by both checkers; packaging correction F-1/F-2)

Date: 2026-11-13. The B-3 freeze (Addendum 47) is now
**TAHAN from both checkers**. The bench (Task 13):
census reproduced identically (2,857; singles
479/480/480; pairs 474/471/473), component digests
exact, sensitivity probes pass, sweep 262 OK. The ops
post (first checker): census identical, probe-set v2
digest set identical, and the composite freeze digest
**recomputed from the published construction
(Addendum 47 freeze record §6) — exactly
`658b9022…d21`**. D.3 is therefore VERIFIED for the
composite itself, not only its components.

## Finding F-1 (major, packaging) — corrected

The stage lived in two trees. The true lineage is the
local stack e3c9e77 (P1) → 46a7a7b (P2) → 83041dc
(B-3). But the pushed branches for PR #149 and #150 —
created by the connector's push-files, which bases a
NEW branch on remote main, not on the intended stack
parent — carried `main`'s pre-P1, grid-coupled
`operator_discovery.py`, and lacked `grid_adapter.py`
(#149, #150) and `test_pricing_adapter.py` (#150):
on those trees the pricing adapter was orphaned code
against its core. The frozen files themselves
(substrate, generator, adapter) were byte-identical
in both trees — **the freeze is untouched; no
re-freeze**.

Correction (this addendum's date): the missing
lineage files were pushed onto both remote branches
(correction commits naming this finding). Verified
after the push: every stage file on the remote #149
and #150 branches now byte-matches (sha256) the true
local lineage — operator_discovery, grid_adapter,
pricing_adapter, test_pricing_adapter, substrate,
tests, generator. (The remote branch tips are
snapshot commits, not the local commit hashes; the
trees are the lineage's trees.) PR #148's branch was
already correct. The ops post re-verifies the
re-pushed stack independently.

Companion decision, made explicit per the ops post's
note: the uncommitted A/B/C v3 work that shared the
worktree (lifted `solve_task` + its tests) is
committed on its own branch
(`research/ace-omega-abc-v3-solver-20261113`, c5e62a8)
— the correction stack carries stage files only.

## Finding F-2 (minor, evidence hygiene) — corrected

`evidence/b3_probe_set_v2.json` carried the same
inherited stale labels as the census file ("stage" /
"seed_range" [5000,5999] for a 20000–20999 probe set).
Annotated in place with a dated `correction_2026_11_13`
entry, the same pattern as the census file; no task,
count, or digest affected (both files' digest sets
were independently re-derived by the checkers).

Standing lesson for stacked PRs in this repo: a new
branch pushed through the connector starts from
remote main — stacked stages must carry their
ancestor lineage files explicitly, and the remote
tree must be sha256-verified against the local
lineage before the stage is reported.
