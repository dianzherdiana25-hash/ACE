# ACE chat task runner v0.1 — real ACE execution from ChatGPT via GitHub

**Status:** experimental bridge executed on a coordinator-owned development branch. Uses GitHub Actions as a task execution worker, NOT a public hosted MCP server and NOT a general intelligent agent. The user's existing connected GitHub app lets ChatGPT submit bounded data-only tasks by committing `chat_tasks/current.json` to a trusted branch, and later inspect an Actions receipt artifact. No separate paid hosting or new ChatGPT custom MCP entitlement is needed for this workflow.

## Why this route

ACE v1 is a real local Python/SQLite runtime; the MCP facade in [PR #59](https://github.com/dianzherdiana25-hash/ACE/pull/59) passed local/loopback tests, but does not yet have secure OAuth + persistent remote hosting. GitHub Actions already provides an isolated Linux runner where the actual ACE research sources can be executed without exposing a public service or creating a cloud database. Actions execution consumes the repository's normal CI minutes and artifacts retention, which can be limited by the account plan. No claim of zero resource cost.

**Do not merge to main or deploy a public service without explicit owner review.** The request runner and its branch-specific workflow can be used in this feature branch while PR #59 remains draft.

## How ChatGPT submits a task, now

1. User asks ChatGPT, for example, "ACE, jalankan uji komposisi v0.3" or provides a valid set of train/validation/terminal examples for a/b strings.
2. ChatGPT updates the exact file `chat_tasks/current.json` on `integration/ace-mcp-bridge-20261106` using the already-connected GitHub app. The workflow `.github/workflows/ace-chat-task-runner.yml` automatically triggers on branch push and checks out the precise triggering Git SHA.
3. Workflow verifies imported research source hashes, runs tests, executes `python -m ace_chat.task_runner --request chat_tasks/current.json --output ... --research-output ...` **twice**, and compares canonical receipt bytes and full experimental data where applicable.
4. GitHub Actions archives `receipt.json`, `research.json` (if generated) and `run-summary.json` as an authenticated Actions artifact. ChatGPT can use its GitHub connector to inspect run status/logs and download the exact artifact, verify hashes and summarize both successes and failures.
5. No workspace persists across GitHub Actions runs: each request creates a fresh temporary SQLite workspace, and the evidence artifact is stored for only seven days. Tasks submitted together in one batch can reuse retained capabilities *within that job*. This is **not** a cross-run lifelong-learning service, nor a replacement for permanent hosting.

## Accepted input formats

File `chat_tasks/current.json` must be valid JSON with exactly these keys:
```json
{
  "schema": "ace.chat.request.v1",
  "request_id": "ace_chat_first_research_20261106",
  "mode": "research_v03",
  "tasks": []
}
```

Modes:
- `research_v03`: replay *actual existing* counterexample-guided ACE composition experiments on 24 public synthetic trials. Compare R1 DFA, basic counter, composition and strong 35-program fixed product. This mode **does not invent a new method**, and data are public, not sealed.
- `runtime_demo`: run ACE v1 learning → validated reuse → changed meaning, 3 task scenarios; returns actual saved task receipts from a temporary workspace.
- `task_batch`: 1–4 user-supplied tasks in one temporary runtime session, each with `name`, `train`, `validation` and `terminal`. Train 1–63 labeled a/b words (at most 63 distinct prefix-tree nodes), validation 1–128 disjoint labeled words; terminal 0–128 disjoint labeled words. Strict booleans only, no invented or secret labels. A nonempty terminal dataset is used only **after** all training/validation staging decisions are frozen. Models may be reused across tasks **within the same batch**.

There is no `shell` mode, no Python code upload, no arbitrary tool URLs, and no paid evaluator. The fixed workflow invokes only checked-in, bounded ACE code, and uses `permissions: contents: read`. Inputs come from GitHub commits in the user's private repository; they are untrusted data, not instructions to the runner.

## Test and evidence requirements

Run locally from repo root with Python 3.12/3.13:

```sh
PYTHONPATH=code python -m unittest ace_chat.test_task_runner -v
PYTHONPATH=code python -m ace_chat.task_runner --request chat_tasks/current.json --output /tmp/ace-chat.json --research-output /tmp/ace-research.json
```

Workflow logs print `request_id`, SHA256 of the canonical receipt and optionally the raw research evidence. Full two-run byte equality, source provenance and all adversarial input validation tests are mandatory. All receipts declare `scientific_status=NOT_ASSESSED`, `release_decision=BLOCK_RELEASE`, `candidate_deployed=false` and `oaie_established=false`.

## Remaining steps before genuine direct MCP plugin

A managed always-available host, persistent storage with migration/backups, a reviewed OAuth/auth gateway or account-authorized Secure MCP Tunnel, ChatGPT plan/workspace permission to connect and use the tools, and actual app installation plus interactive readback. The existing PR #59 MCP server is **localhost-only by design** and must not be placed directly on a public URL. Official ChatGPT MCP support and permissions vary by plan; do not assume full write-capable custom MCP is enabled for all users.

Until those gates are cleared, GitHub Actions is a separate **GitHub-assisted execution path**: ChatGPT can request an ACE run by using connected GitHub tools, but ACE is not a native tool inside this message. Long-term durable cross-request memory requires a reviewed external state store or verified artifact handoff; do not silently claim it from a fresh Actions runner.
