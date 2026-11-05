# CLAUDE.md — ACE research engineering guidance

This repository is **Autonomous Capability Evolution (ACE)**, the first experimental generation toward the long-term research vision **Open-Ended Autonomous Intelligence Evolution (OAIE)**. Passing a development benchmark is NOT evidence of OAIE, AGI, or general capability transfer.

## Source of truth and startup
1. Get the fresh HEAD of `research/e1.3-design`. Never assume the checkpoint copied into a prompt is the current HEAD.
2. Read `PROJECT_CHARTER.md`, `CURRENT_STATE.md`, `RESEARCH_LEDGER.md`, `NEXT_ACTION.md`, and active GitHub Issues (especially the issue specified in the user task).
3. Inspect existing code, protocol freeze commits, and actual results before proposing a change. Do not redo experiments already recorded as complete.
4. Distinguish **engineering pass**, **scientific development GO**, **HOLD/NO-GO**, and **independent confirmation**. Respect every NATURAL_HOLD and out-of-basis safety failure.

## Responsibility and branch discipline
- Claude Code is an **independent engineering / security / reproducibility contributor**. ChatGPT Work coordinates scientific sequencing and integrates independently reviewed contributions; Codex may implement or test other workstreams. These roles do not imply live cross-model messaging.
- Work on a separate branch named `claude/<issue-number>-<short-topic>` from fresh `research/e1.3-design`. Prepare a Pull Request **targeting `research/e1.3-design`**, with exact tests, evidence, risk notes and a replay command. Do not push to `main`.
- Never overwrite changes authored by Work or Codex. Before preparing a PR, compare with the updated research-branch HEAD and rebase/reconcile carefully. Avoid editing the same files concurrently without coordination.
- Keep experimental code/banks and pre-score locks immutable after scoring. For corrected protocols, create a **new version and freeze it before viewing outcomes**; preserve negative evidence.
- Do not merge your own PR automatically. Do not alter Tod or any other repository.

## Scientific and security gates
- Keep candidate code separate from private evaluator labels, hidden probes, credentials, and network. For execution requiring isolation, use **official supported Bubblewrap** or a separately validated equivalent with actual-worker nonexposure and resource tests; a mock or simple namespace canary is not evidence of full equivalence.
- Do not open E1.3 sealed confirmation data or any sealed evaluation outside an authorized protocol. Use fresh public-development banks for exploratory work.
- Use matched label budgets and record **all** calls, initial demos, probe labels, retries, CPU, wall-time, candidate fits and memory. Provide robust baselines: task-local, no-label, sham/random, and informed reference where applicable.
- Treat synthetic/oracle hindsight as diagnostic only. Do not tune on held-out or scored outcomes.
- Run bounded commands with heartbeat/logs and explicit terminal state (`COMPLETE`, `FAILED`, `TIMEOUT`, `BLOCKED_ENV`, `BLOCKED_APPROVAL`). No invisible retry loops or speculative success claims.

## Current work division
- Active integrated scientific milestone: follow the latest **Issue #13**, not the closed historic E1.4n Issue #7. It examines **weighted branching-graph diagnosis → representation repair → guarded inheritance under one shared four-label budget**. Prior E1.4o graph-chain loop remains HOLD; E1.4s guard is demonstrated only in bounded grammar; NATURAL_HOLD persists.
- For Claude, prefer **independent engineering tasks** such as reproducible isolation preflight, bounded-runner recovery tests, regression hygiene, and audit contracts, so that Work's experimental bank/scorer can remain untouched.
- A scientific result is never accepted solely because Claude reports "done". Capture commands, terminal outputs, hash-verified artifacts, negative cases and PR diff.

## Budget and permissions
- Extra spend **Rp0**; no paid APIs, cloud runtime, secret creation, purchases or plan upgrades without explicit owner authorization. Existing plan quota is not an unlimited compute entitlement.
- Keep work confined to authorized ACE research branches; do not touch Tod, `main` or external accounts.
- User is primarily phone-based. Summarize status in Indonesian with links to the GitHub issue/PR and simple next action.
- Never claim you installed, configured, or linked Claude Code to GitHub merely because this file exists. Repository-owner authorization is a separate, explicit step.

See `docs/ACE_MULTI_AGENT_COLLABORATION.md` for concurrent-work acceptance and handoff.
