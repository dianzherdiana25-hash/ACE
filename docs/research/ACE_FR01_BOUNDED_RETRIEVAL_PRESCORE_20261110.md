# ACE FR-01 bounded repository retrieval — preregistered protocol

Date: 2026-11-10. Base: PR #98 exact SHA `b72c18b856cccd8cb8a46a86e15b128be42701b3`.
Branch: `research/ace-fr01-bounded-retrieval-chat-20261110`. Owner: ChatGPT FR-01 read-only pilot.

## Scope and constraints

Extend existing `ace_code_agent.codebase_reader.CodebaseReader` with a bounded, read-only repository indexing/retrieval capability. Reuse the standard library Python AST and Git's tracked/untracked-but-unignored file enumeration; do not create a new solver, memory, or planner. No candidate source execution, AI external calls, daemon changes, main merge, historical evidence edits or paid services.

This is an **FR-01 engineering slice**, NOT the complete issue-to-patch autonomous coding workflow. Candidate execution remains BLOCKED_ENVIRONMENT until containment is proven. Concurrent state ownership work in `research/ace-atomic-self-dev-state-20261110` remains independent.

## Falsifiable hypothesis

H1: bounded lexical + structural retrieval finds the correct bug-relevant symbol/file at rank 1 in at least 3/3 preregistered disposable synthetic fixtures, including a decoy with high lexical overlap. Refuted if any positive target is not rank 1, source parser executes candidate code, or deterministic replay differs.

H2: controlled repo traversal excludes Git-ignored untracked sources, traversal through symlinks, oversized files and paths above configured maximum depth; respects file/time limits. Refuted by any restricted path included or budget bypass.

H3: this read-only index can be queried after creating a separate interpreter/process, without provider assistance or persistent mutable state; the result is identical under fixed source HEAD and limits. Refuted by differing ranks/output other than measured wall-time.

## Controls

B0: lexical-only ranker. B1: structural-only ranker. I1: hybrid ranker. Tests must report rank-1 and recall@3, plus timing and file-count measurements. Report a negative/decoy case explicitly; do not tune against independent terminal data. Fixture tasks are public development diagnostics, not an independent scientific benchmark. Semantic embedding retrieval remains MISSING until independently justified.

## Resource/security budget

Git is invoked using a fixed argv without shell, with a 10-second timeout. No candidate imports or execution. AST parsing only, maximum 1,000 Python files by default, max 128 KiB/file, configurable depth <= 32, and elapsed budget 15 seconds. Return compact JSON instead of source-text dumps. Standard library Python 3.12/3.13 on Linux/Termux. Avoid symlink traversal and reject path escapes. CI has a focused exact-head regression on both Python versions.

## Engineering acceptance

1. Public fixture regression suite green (positive, decoy, ignore, symlink, size/depth, parse error, deterministic tie, memory cap).
2. Real ACE repo smoke scan has bounded cost and produces nonempty symbols; no untrusted code execution.
3. GitHub Actions checks run on the exact implementation SHA with recorded conclusion.
4. No claim of 40% SWE-bench, new representation class, scientific superiority, AGI, or OAIE.
5. Scientific `NOT_ASSESSED`; release `BLOCK_RELEASE`; `EXTERNAL_AI_EXPERIMENT_NOT_RUN`.

If any gate fails, retain the failure and fix only on this isolated branch.