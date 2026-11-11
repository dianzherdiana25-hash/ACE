# ACE Ω branch/PR audit, 2026-11-11

Read-only GitHub API audit plus local Git ancestry/source inspection. No repository source, PR state, comment, evaluator, or historical evidence was changed. Raw normalized API snapshot retained in this session at `/workspace/ace-pr-audit.json`. Canonical readback sources: [repository](https://github.com/dianzherdiana25-hash/ACE), [PR #95](https://github.com/dianzherdiana25-hash/ACE/pull/95), [PR #96](https://github.com/dianzherdiana25-hash/ACE/pull/96), [PR #97](https://github.com/dianzherdiana25-hash/ACE/pull/97), [PR #98](https://github.com/dianzherdiana25-hash/ACE/pull/98), [PR #99](https://github.com/dianzherdiana25-hash/ACE/pull/99), [PR #102](https://github.com/dianzherdiana25-hash/ACE/pull/102). The exact head identifiers below pin this audit; later branch changes require another readback.

## Integration truth

Observed main: `9ac1ac5ed328a4382f29f622a8e12109c5b4af30`.
All six requested PRs are **open draft, merged=false** in GitHub metadata. Nevertheless, `git merge-base --is-ancestor <head> origin/main` returns true for every PR #95–#99. Their heads are already in main's ancestry through other integration history; do not cherry-pick or recreate their implementation merely because the PRs remain open. PR #102 is not in main ancestry and adds 12 files relative to main.

| PR | Exact head | Original PR base | Current ancestor of main | Returned PR workflows |
|---|---|---|---|---|
| #95 | `01916ad375aebd81aaa6d027a4f4d682a0e2cde8` | #94 branch | yes | 4 success |
| #96 | `e1fdbf09da6aaec4b7a3e426771af81b989ebe1c` | #95 branch | yes | 4 success |
| #97 | `1752119003bc8e6f2937bcdb869cfcba38747710` | #96 branch | yes | 6 success |
| #98 | `b72c18b856cccd8cb8a46a86e15b128be42701b3` | #97 branch | yes | 4 success |
| #99 | `61553d33024c490ba47294f83fbffe842790893e` | #98 branch | yes | 6 success |
| #102 | `4a5febaeb8cffa1956548071524c28b256f4f4c8` | main | no | 4 success |

The workflow tool returns only the first page and PR-triggered runs. Empty combined statuses do not mean absent Actions checks. R9 uses default PR merge checkout and should not be called exact-source verification.

## Existing ownership and overlap

- #95: `ace_cognition/reasoning.py`, typed closed solver/retained executable memory; source map, audit, benchmark and raw public diagnostics. Public reasoning result 552/576 is recorded as equal to fresh-solver baseline, not superiority; no real LLM inference.
- #96: `ace_mission/{admission,bus,schema}.py`, candidate replay/empirical staging and receipt binding. Preserve the frozen MissionBus source digest and public fixture; adding an unrelated convenience argument previously broke custody checks.
- #97: `ace_core_repair/admission.py`, `ace_runtime/cli.py`, qualified fitted-arm selection and validation admission. Reuse existing abstention semantics. Public terminal score equals strong fitted-arm baseline.
- #98: `ace_self_dev/state_manager.py`, wrong/missing/stale-token rejection plus lease tests. This historical PR did not make all read/modify/write multi-process races atomic; a separate `research/ace-atomic-self-dev-state-20261110` branch exists and needs source-level reconciliation before any alternative lock redesign.
- #99: `ace_code_agent/repo_retrieval.py`, AST/symbol retrieval, Git-aware enumeration and resource/path bounds. Already in main; use it for OMEGA-02 instead of another repository indexer. It explicitly does not execute candidate source or constitute a complete coding agent.
- #102: `ace_operational/open_world_{planner,execution,task_bridge,review_bus,cli}.py`, four test modules, manifest, RFC and dedicated workflow. Planner is finite typed composition; executor invokes trusted pure in-process callbacks and same-process verification, with OperationalStore and FencedStore receipts. It is neither a code sandbox nor an independent evaluator nor an LLM coding loop. Do not let model-generated callables enter LocalAdapter.

PR #102 changed files (all added): `.github/workflows/ace-open-world-pilot.yml`; five `code/ace_operational/open_world_*.py` modules above; four `test_open_world_*.py` modules; `docs/research/ACE_OPEN_WORLD_PLATFORM_RFC_20261111.md`; `examples/open_world_capabilities.json`.

## Exact-source CI findings

For #95–#99, the focused reasoning/admission/W3/FR01 and full-system workflows explicitly check out `${{ github.event.pull_request.head.sha || github.sha }}` and compare git HEAD. Their listed source-head runs are completed success; this is engineering verification only.

For #102:

- [Full-system run 43010285250](https://github.com/dianzherdiana25-hash/ACE/actions/runs/43010285250): all six jobs success. Workflow explicitly pins exact source HEAD. Actual log of job `130487867766` confirms checkout `4a5feba...`, HEAD assertion, and **784 discovered tests** passing in 368.906 seconds on Python 3.13. Discovery includes all `code/**/test_*.py`, therefore includes new open-world tests. Additional repeated suites must not be summed as distinct cases.
- [Research run 43010285203](https://github.com/dianzherdiana25-hash/ACE/actions/runs/43010285203): both jobs success, exact-source assertion present.
- [Open-world run 43010285214](https://github.com/dianzherdiana25-hash/ACE/actions/runs/43010285214): both Python 3.12/3.13 jobs success, focused tests, CLI smoke, unchanged MissionBus blob and byte-exact fixture replay all pass. **Its dedicated workflow uses default PR merge checkout**, not source-head pinning. Exact-head coverage is supplied by full-system discovery, but this workflow itself should be strengthened in an authorized follow-up branch.
- R9 run 43010285202: success, merge-ref semantics.

PR body still says latest CI pending; live API evidence supersedes that stale statement. No PR metadata was updated.

## Neighboring branches

- Blueprint PR #103, head `2429c63175e03c6703c57a7d186d80874d31cee8`, adds exactly the four user-mandated proposal documents/manifest and is not implementation evidence.
- `research/ace-local-ai-coding-orchestrator-20261111`, head `d83f68392ccb227e904a858ac16fcb5b9d068a74`, descends from #102 and adds `agent_fabric.py`, `agent_delegation_store.py` and tests. It already has an Ollama planner plus headless worker orchestration by commit titles. Read these implementations before building another orchestration layer. No open PR for this branch appeared in the 10 newest open PR results inspected; absence from that page is not proof that no PR exists.

## Recommendations

1. Base local inference work on current main or an explicitly isolated integration branch, keep ownership of other branches intact, and import existing code through reviewed Git integration rather than replacement.
2. Reuse #99 retrieval, #96 admission and persistent receipts, and existing OperationalStore/FencedStore; add truthful local model inference at the actual ModelRouter boundary first.
3. Treat #102 only as optional structural/durable tool substrate until its source is deliberately integrated. Keep candidate code in a separate constrained execution boundary.
4. Keep G0/G1 blocked or unassessed until real local model identity, raw inference, model-produced candidate patch, isolated test output, baseline and resource receipts exist. None of these PRs alone proves OAIE or fundamental novelty.
