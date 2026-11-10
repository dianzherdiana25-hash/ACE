# ACE ↔ ChatGPT: bounded MCP bridge v0.1

**Status: RUNNABLE LOCAL MCP ENGINEERING; NOT CONNECTED TO CHATGPT; NO PRODUCTION DEPLOYMENT.**

This package exposes the actual `code/ace_runtime/engine.py` SQLite-backed ACE runtime through Model Context Protocol (MCP). It does **not** implement a second ACE engine, generate arbitrary Python code, download external data, accept free-form research hypotheses, run external or paid evaluators, or claim OAIE.

## What is available

Six bounded MCP tools:
- `ace_status` (read-only): task queue status and capability count.
- `ace_submit_task` (write, opt-in): queue labeled `a/b` training and validation data, matching the strict ACE runtime contract.
- `ace_run_tasks` (write, opt-in): run 1–16 pending local learning tasks and persist decisions.
- `ace_get_report` (read-only): retrieve an actual task evidence report.
- `ace_predict` (read-only): predict one `a/b` word only with a validated stored task model; no guarantee under hidden semantic drift.
- `ace_evaluate` (write, opt-in): bind one disjoint terminal dataset (at most 128 rows) and retrieve the persistent evaluation receipt. Changed terminal data are rejected on later calls.

There is **no** `execute_code`, `shell`, unrestricted filesystem access, LLM-generated source execution, arbitrary URL fetch, paid action, merge or deployment tool.

## Run on a trusted computer/server

Requires Python 3.12+ standard library; commands from ACE repository root:

```sh
# Trusted local MCP client (stdio), read-only by default:
PYTHONPATH=code python -m ace_mcp.server --transport stdio --workspace ./ace-work

# To explicitly authorize bounded writes, add --read-write.
PYTHONPATH=code python -m ace_mcp.server --transport stdio --workspace ./ace-work --read-write
```

For **local loopback HTTP testing only** (not a public ChatGPT endpoint):

```sh
export ACE_MCP_HTTP_TOKEN="your-own-random-secret-of-at-least-32-characters"
PYTHONPATH=code python -m ace_mcp.server --transport http \
  --host 127.0.0.1 --port 8735 --workspace ./ace-work
```

Do not place a bearer token in a URL, shell history, repo file, or chat. In an operator-managed environment, inject it through the secrets manager. Read/write HTTP additionally requires an explicit `--read-write` flag; default is read-only. The HTTP listener refuses public address binding, rejects unapproved `Origin` headers, enforces a 256-KiB request limit, and only accepts the tested MCP `2025-06-18` JSON-RPC subset. This thin HTTP transport is **not** independently certified against every later MCP client version and is not a substitute for a production MCP SDK.

## Connect to ChatGPT — outstanding separate steps

ChatGPT cannot reach this code just because it exists on GitHub. To use ACE **directly** from an Android ChatGPT conversation, the user needs a persistent, running host or managed endpoint, with a trusted MCP connection installed. Two possible architectures:

1. **Private, recommended for early development:** run ACE with durable storage on a host and connect a Secure MCP Tunnel that can reach its local MCP process. Add it through ChatGPT web → Plugins → Add custom MCP server → Tunnel, then explicitly install and approve use. A phone alone does not provide the always-on remote runtime needed.
2. **Public HTTPS deployment:** build a separate reviewed OAuth 2.1-capable authorization/resource server (including token validation, scope separation and account ownership), TLS and persistent workspace. The included local bearer token test handler is **not an OAuth ChatGPT authentication implementation**, and must not be exposed as a public URL. Do not deploy the current handler as a publicly accessible service or disable authentication to make a quick demo work.

Before claiming connected: confirm real URL/tunnel ID, authentication from ChatGPT, `initialize`, `tools/list`, exact task state readback, user-approved enqueue/run, reboot/reconnect and isolated user storage. Use MCP Inspector and a real ChatGPT plugin integration test. ChatGPT tool writes must require user consent or host approval policy; a model-generated instruction is not operator approval.

## Reproduction and safety gate

GitHub Actions workflow `.github/workflows/ace-mcp-bridge.yml` tests the exact PR SHA under Python 3.12 and 3.13 with no network tunnel or paid calls:

```sh
PYTHONPATH=code python -m unittest ace_mcp.test_bridge ace_mcp.test_transport -v
PYTHONPATH=code python -m unittest ace_runtime.test_engine ace_runtime.test_cli -v
```

Covers MCP initialize/tools/list, line-delimited stdio, local HTTP token and origin checks, 2025 transport version checks, rejection of disabled write tools, strict payload constraints, genuine ACE enqueue→run→predict→report→evaluate and persistent re-open, terminal receipt idempotency and non-overwrite, no public HTTP bind, and original ACE runtime regression. **No remote endpoint, device installation, plugin authentication or deployment has been exercised**.

## Explicit scientific boundary

This is **a connectivity layer** over ACE operational generation v1, not an autonomous scientific reasoning engine. ACE only supports bounded labeled binary strings and supplied finite candidate classes. No autonomous novel primitive-class creation, independent generalization, open-world safety, self-improvement, or OAIE claim follows from a green MCP test. Do not merge, deploy or migrate user workspace without separate approval. Core research Issue #53 and historical audit Issue #17 remain independent gates.
