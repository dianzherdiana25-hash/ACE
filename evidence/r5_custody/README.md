# R5 — custody verification from inside the sandbox (2026-11-14)

The custody chain for the lineage-guard confirmation run, documented
end to end:

1. **Requirements** — `handover/CUSTODY_REQUIREMENTS_LINEAGE_GUARD_20261114.md`
   (Ian's frozen R1–R5 requirements for the sandbox custody home).
2. **Population manifest** — `handover/CUSTODY_POPULATION_MANIFEST_20261114.json`
   (80 files, 1,049,673 bytes, tree digest
   `c02221775c2b81117effb93b204cccd0aaaa930e166e4a9c3883cf1d233fc6c2`).
   The population was transferred, verified at destination, lost in a
   platform snapshot rollback (2026-11-14 ~02:56 WIB), and restored
   under the owner's automatic-restoration rule; destination
   verification matched exactly both times.
3. **R5 evidence** — this directory. Ian verified the restored
   population from inside the sandbox (host `2887726280f4`, Python
   3.12.3, via the D402 MCP door), writing only under
   `/workspace/r5-ian/`:

   - `r5_record.json` — the full R5 record. Verdict: **PASS, all
     four steps.**
     (1) In-place sha256 check: 80/80, 0 problems, tree digest
     exact, no extras — and an identical re-check after all work
     proves the population stayed pristine.
     (2) Import isolation: every harness module resolves under the
     custody tree.
     (3) Re-gate in a scratch copy: invariance gate PASS 4/4
     (Stage-0 anchors reproduced); uncapped control reproduces the
     failures EXACTLY (catalog_control-020: 410 calls,
     catalog_control-021: 159 calls, both never_generated,
     unsolved); verdict COMPARISON_VALID.
     (4) Timing probe: discovery re-run of spent Stage 3 band
     20261601 in 1,317.63 s through the MCP door (inside the
     service's ~1-CPU cgroup — a door-bound number; the SSH door
     sits outside that cgroup); catalog digest
     `e5c7875d5e742bc4ca317569afa6a4b7a88f9aa0ea706ee99675d0d8c2d9a09c`
     exact against the official Stage 3 record (PR #192).
   - `gate.json`, `ctrlreg_stage3_intervention.json` — the scratch
     re-gate outputs, copied from the sandbox unchanged.
   - `regate.log`, `probe.log` — the run logs, unchanged.
   - `tools/` — the three instruments used (manifest checker,
     import-isolation probe, discovery probe), as run.

Custody files are currently root:root 700 (restored through the MCP
door, which cannot chown); an operator-side ownership fix is required
before future SSH-door custody use. The clean-logout item remains the
hard gate before the first sealed run in this home.
