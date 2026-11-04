# ACE — no-stale, fail-visible run contract

**Scope:** scientific research commands in the ACE project; not ChatGPT/Work's platform UI. This is a local command supervisor, not a background daemon, scheduling system, or automatic compute quota expansion.

## Problem

Long experimental commands may look perpetually active even after data is produced. An uncommitted result is not a durable checkpoint. A terminal command with an unverified artifact must not be described as success.

## Contract

1. Execute one bounded stage at a time, with a named `--state` JSON file, immutable `--source-commit`, fixed command and working directory.
2. Write `RUNNING`, periodic heartbeat, then exactly one terminal state: `COMPLETE`, `FAILED`, `TIMEOUT` or `INFRA_FAILURE`. The supervisor runs in the foreground and returns a distinct exit status.
3. Persist stdout/stderr and SHA-256 for each. `COMPLETE` means the *command* exited 0; it does **not** prove that a research hypothesis holds or that the code was isolated.
4. Do not silently repeat a successful job: identical SHA and command allow safe skip. Changed command, failed command, missing/corrupted output or ambiguous `RUNNING` checkpoint requires inspection. Recovery is explicit; a still-`RUNNING` record is never automatically rerun.
5. A command timeout kills its process group. Record the failure and leave scientific results unmodified. Do not automatically retry a sealed confirmatory experiment.
6. After each terminal stage, audit result and commit to `research/e1.3-design`; read GitHub branch HEAD back. The commit is the durable checkpoint, not progress narration.
7. If GitHub update fails, preserve evidence and report `PERSISTENCE_BLOCKED`, never claim a remote commit. Never force-push or merge to main.

## Usage

```bash
# Run from a verified checkout of ACE at the intended source commit
python3 scripts/ace_progress_guard.py \
  --state /tmp/ace_e14b_replication.json --cwd "$PWD" \
  --source-commit 38b1c3b90ab8f53ae84480f60ed4d1ac603c67ea \
  --timeout 120 --heartbeat 5 -- \
  /usr/bin/python3 -m unittest discover -s code -p 'test_*.py' -q
```

This wrapper **does not** supply the E1.3/E1.4 worker sandbox. The command still needs a separately verified sandbox environment. For the frozen E1.4b replication, prefer a host with the genuine Bubblewrap tool. This chat's development reproduction used a custom replacement and must remain labeled as such.

## Decision: what to do when it stalls

- Heartbeat advances and process exists: command is active, inspect current logs; wait only within its configured deadline.
- Heartbeat stops beyond deadline or worker exits without terminal status: stop dependent work and inspect the process/checkpoint before choosing recovery. Do not overlap workers.
- Terminal failure: record exit code and stderr; fix root cause before a **new** run. Do not mutate frozen protocol in place.
- Terminal success but no remote commit: prioritize persisting audited evidence to GitHub before starting the next stage.
- Work/ChatGPT quota or UI spinner: this script cannot repair the host. Start a new active session from `CURRENT_STATE.md` and verified GitHub HEAD.

**Research interpretation:** An E1.4b development GO permits a new exploratory phase; it is not a claim of open-ended autonomous intelligence. The E1.3 NO-GO was a scientific decision, not a missing user approval.
