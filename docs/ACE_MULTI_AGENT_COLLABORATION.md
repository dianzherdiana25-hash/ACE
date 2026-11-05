# ACE — multi-agent GitHub coordination (Work / Codex / Claude Code)

**Scope:** Collaboration workflow, not proof of scientific progress. Native Claude Code cloud sessions require the owner's separate sign-in, eligible plan, and approval of the Claude GitHub App on the **ACE repository**. Writing these files does **not** connect an Anthropic account, start Claude, or cause autonomous background work.

## Active canon
- Repository: `dianzherdiana25-hash/ACE`; protected operational research target: `research/e1.3-design`. `main` is not the PR destination.
- Fresh research HEAD takes precedence over any copied snapshot SHA. Read `PROJECT_CHARTER.md`, `CURRENT_STATE.md`, `RESEARCH_LEDGER.md`, `NEXT_ACTION.md`; see open Issue #13.
- Never assume the most recent version letter implies a scientifically accepted result. Check freeze manifests, decision reports, baseline status and remaining NATURAL_HOLD.

## Parallel ownership matrix

| Stream | Primary owner | Allowed edits | Integration gate |
|---|---|---|---|
| Research hypotheses, frozen bank and go/no-go protocol | ChatGPT Work | New versioned `design/e1.4/*` and bank only before scoring | Exact pre-score SHA, independent audit, rationale |
| Engineering / sandbox / regressions | Claude Code | Isolated `tools/`, `tests/` or new support files on `claude/*` branch | Real sandbox proof, bounded tests, backwards compatibility |
| Scorer/worker implementation or independent replay | Codex | Isolated `codex/*` branch | No scored data leakage, cost parity, all test logs |
| Integration, ledger and acceptance | Work / owner | `research/e1.3-design` only | Review each PR, rerun tests and read back HEAD |

Work and Codex can both work without a subscription to Claude; a Claude Cloud session is a separate account and usage limit.

## Claude's first bounded engineering task

1. Read Issue #13 and the E1.4o/E1.4s reports; assess whether the *current* GitHub worktree has runnable regression suites and a native Bubblewrap isolation preflight.
2. Without touching locked source/banks, produce **a small reproducible preflight and bounded regression-check contract** suitable for a separate cloud VM: verify bwrap binary and user/mount/net isolation, evaluator nonexposure, package/fixture availability, expected test exit codes and logging.
3. Report exact environment restrictions if Bubblewrap/unprivileged namespace is unsupported; **do not lower the sandbox requirement**. Do not silently run experiments in an unverified substitute.
4. Push fixes and tests to a `claude/*` branch and open PR targeted to `research/e1.3-design`; include working commands, checksums, benchmark bounds, and fail-visible `BLOCKED_ENV` when necessary.
5. If time remains, audit the experiment's four-label accounting and graph worker contracts independently, with source-line references, without changing frozen scoring logic.

**PR acceptance:** clear problem statement, no accidental data exposure, code + tests, actual run logs, exit codes, resource and label accounting, negative cases, no unauthorized edits, exact branch target, and no merge without review.

## Three-agent anti-conflict rules

- One experimental **freeze owner** per new bank/protocol. Development agents may prepare independent patches but must never concurrently edit or score the same frozen data.
- Each agent works in its own branch and does not integrate another agent's PR without approval from the designated integrator. A commit alone does not count as completed validation.
- Do not merge `main`, open sealed E1.3 data, or spend money. If the cloud tool is unavailable, record the blocker and leave an immediately resumable handoff on GitHub.
- Update the relevant issue/PR with: actual HEAD, test commands and results, artifact SHA, scientific status, blocker, next action. No hidden background promises.

## Phone-only connection steps (owner action)
1. Sign into **https://claude.ai/code** (or Code tab in Claude mobile) with a plan that supports cloud sessions.
2. Use the GitHub connection prompt and authorize the Claude GitHub App only for `dianzherdiana25-hash/ACE` when offered.
3. Select ACE and read this root `CLAUDE.md`; ask Claude to implement **the bounded first task** above, using a fresh `claude/*` branch and a PR to `research/e1.3-design`.
4. Review the PR. Return here with its URL or simply ask to synchronize ACE; never provide tokens or passwords in chat.

Official docs: https://support.claude.com/en/articles/12618689-use-claude-code-in-the-cloud and https://code.claude.com/docs/en/claude-code-on-the-web .
