# CUSTODY REQUIREMENTS MANIFEST — Lineage-Guard Run Home (FROZEN, Ian, 2026-11-14)

Status: FROZEN requirements. This manifest is the
acceptance test for the sandbox custody at
/workspace/ace-custody-lineage-guard (created empty
2026-11-14 ~00:31 WIB, ubuntu:ubuntu 0700). Custody
population is a separate permission; a run permit is
a separate act again. Nothing here authorizes either.

## Verified starting facts (ila firsthand, 00:28–00:31)

- Muse VM reaches the sandbox via tailnet proxy
  (CONNECT :3130), ubuntu@100.93.61.37, host key
  SHA256:dTIOo1efhJZqd7jqtbqHUsS18HFm+8dxEcZZPUNMN7M
  (pinned after match with the operator-verified key).
- SSH sessions land in user.slice session scopes —
  OUTSIDE sandbox-mcp.service's cgroup; cpu.max =
  "max 100000", memory.max/high = max at session,
  user-1000 and user.slice levels; affinity 0–7,
  getconf online = 8. (Affinity/no-visible-cap is
  NOT a guaranteed core — performance is proven by
  the re-gate timing, not assumed.)
- Python 3.12.3 at /usr/bin/python3. Disk 70G, 18G
  avail at snapshot. Custody dir empty.

## R1 — Code custody (content-identical, hash-proven)

The custody must contain, byte-identical to the
Muse-VM originals (sha256 manifest computed by Ian
at population time, verified inside the sandbox
before anything runs):
- wt-abcv3/code/ace_operational/ (the solver package
  as used by every 2026-11-13 sealed run),
- abc_v3_run.py (PR #181 + #187 hardened lineage),
- the Stage 3 instrument set: harness_ext.py,
  stage3_official.py (reference instruments),
- the lineage-guard harness + its preregistration
  (added when built; this manifest freezes the
  RULE, not the guard's file list).

## R2 — State and anchor custody

- abc-v3-run-state/discovery_20261501.json (frozen
  dev-band catalog source; digest a6768563…),
- regression anchor artifacts + the PR #175
  inoculation battery files (the guard consequence
  in PR #184 §2.6 runs anchor + battery BEFORE it
  measures anything — they are custody, not cargo),
- Stage 0–3 evidence records needed by the gate
  constants (hashes live in harness code; the
  records are the audit trail).

## R3 — Environment

- Python 3.12.x, stdlib only (the solver stack has
  no third-party dependency as run on 2026-11-13;
  population must re-verify by import in isolation).
- No network access used by any run process.
- Run footprint is small (Stage 3 process RSS
  ~45 MB); NO model loads under this custody —
  model RAM windows stay on the named-window rule.

## R4 — Detached persistence (must be DEMONSTRATED)

loginctl shows Linger=no for user ubuntu: detached
survival is NOT assumed. Before any run permit, a
sleeper test must pass: launch a detached sleeper
(nohup or equivalent) writing a heartbeat file
inside the custody dir, close ALL SSH sessions,
wait, reconnect, and show the process alive with
heartbeat advancing. The mechanism that passes
becomes the named launch mechanism in the run's
record. If none passes, the operator enables
linger or provides a system-level unit — the run
does not improvise around this.

## R5 — Verification from inside (Ian, before measuring)

In the populated custody, in order:
1. sha256 manifest check: every R1/R2 file matches.
2. Import isolation check (python3 -I -S plus the
   package import path) — no surprise deps.
3. The development re-gate, unchanged: logging-
   invariance gate 4/4 + uncapped control
   reproduction EXACTLY 410/159 calls on
   catalog_control-020/-021, frontier-provenance
   extension live in the round log.
4. A one-band timing probe (discovery of a spent
   Stage 3 band re-run or an equivalent bounded
   workload) so the delivered speed is MEASURED,
   not inferred from core counts.
Only then is the custody a run home; the first
sealed run there still needs its own act.

## Explicitly not covered

Model inference (A3B) custody, the dashboard/proxy
guarding (ruang khusus's post, cron unchanged), and
any change to the sandbox's other tenants. The
:18081 A3B resident's stand-down is the operator's
loose end, not this manifest's.
