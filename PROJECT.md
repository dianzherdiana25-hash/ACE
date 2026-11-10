# Project: ACE Autonomous Intelligence Evolution (PR 100 & PR 101 Completion)

## Architecture
ACE operates as an open-ended, fully offline autonomous intelligence system.
The system is structured into 8 modular architectural layers:
1. **CLI & Runtime Interface** (`ace.py`, `code/ace_runtime/cli.py`): Entrypoint supporting 25 subcommands (`chat`, `do`, `web`, `deliverables`, `models`, `bridge`, `continue`, etc.).
2. **Durable Operational Store** (`code/ace_operational/store.py`): SQLite with WAL journaling managing 15 relational tables with monotonic lease epochs and crash recovery.
3. **Indonesian Language & Intent Engine** (`code/ace_operational/language.py`): Multi-turn conversational processing, negation handling, domain intent classification, and chat response synthesis.
4. **Autonomous Coding Loop & AST-Gated Execution** (`code/ace_operational/coding_loop.py`): Program synthesis, AST verification, atomic write with lease checks, test-driven validation, and verified execution receipts.
5. **Local Inference & Model Routing** (`code/ace_operational/models_backend.py`): Local GGUF models on `llama.cpp` (`llama-cli`, `llama-server`), streaming SHA256, dynamic RAM budget, circuit breakers, and offline egress enforcement.
6. **Autonomy, Knowledge Frontier & Worker Delegation** (`code/ace_operational/autonomy_loop.py`): Gap discovery and deduplication, 4-tier anti-stagnation pivot ladder, and worker order verification.
7. **Anime Studio Web UI & Story Projection** (`code/ace_operational/web_server.py`, `code/ace_operational/story_projector.py`): Mobile-responsive UI (320px viewport), dual-block layout (Chat + Activity Story), SSE event streams, 5 avatar companion states, and task controls.
8. **Universal Installer & Packaging** (`install.sh`): Multi-profile installer (`local-complete`, `host-assisted`, `core`, `offline-bundle`), CLI launcher generation, and transactional WAL backup/rollback.

---

## Feature Inventory
All features mined during Phase 0 Survey mapped to milestones:

| # | Feature / Contract | Description | Milestone | Source |
|---|---|---|---|---|
| 1 | F01 - F24 Foundation Deliverables | 24 core contractual deliverables covering runtime, autonomy, web UI, CLI, installer | M3 | ACE_ANTIGRAVITY_EXECUTION_CONTRACT |
| 2 | A01 - A64 User Acceptance Scenarios | 64 operational scenarios across conversation, coding, memory, concurrency, offline | M3 | ACE_MASTER_PROMPT Appendix A |
| 3 | INST01 - INST24 Installer Contracts | 24 installer specifications for profiles, caching, idempotency, updates, rollbacks | M3 | ACE_MASTER_PROMPT Appendix W |
| 4 | WEB01 - WEB24 Web UI Contracts | 24 specifications for anime localhost web server, SSE streams, task controls | M3 | ACE_MASTER_PROMPT Appendix AC |
| 5 | AUTO01 - AUTO16 Autonomy Contracts | 16 autonomy specifications for gap discovery, worker delegation, pivot ladder | M3 | ACE_MASTER_PROMPT Appendix AC |
| 6 | G01: Real Local GGUF Inference | Replace static text with live llama.cpp HTTP/CLI inference in Indonesian | M3 | ORIGINAL_REQUEST § 8 |
| 7 | G02: Structured Output Repair | Robust JSON extraction, repair of missing brackets/commas, schema validation | M3 | ORIGINAL_REQUEST § 8 |
| 8 | G03: Genuine Coding vs Trivial Stubs | General coding task repair loop instead of returning trivial status stubs | M1 | ORIGINAL_REQUEST § 8 |
| 9 | G04: Novel Domain Prompt Routing | Fix intent classification so novel tasks route to general coding, not expense_tracker | M1 | ORIGINAL_REQUEST § 8 |
| 10 | G05: Worker Order Lifecycle Pre-Flight | Pre-flight test validation for candidate code to prevent math hallucination test flakes | M2 | ORIGINAL_REQUEST § 8 |
| 11 | G06: Offline Model & Egress Guard | Zero-cost 100% offline enforcement; block egress attempts | M3 | ORIGINAL_REQUEST § 8 |
| 12 | G07: Web UI Interactivity & Control | SSE streaming, client message dedup, task pause/resume, responsive anime UI | M3 | ORIGINAL_REQUEST § 8 |
| 13 | G08: Installer Execution & Rollback | Real install.sh execution with smoke tests and WAL database rollback | M3 | ORIGINAL_REQUEST § 8 |
| 14 | G09: Cold Subprocess Crash Recovery | Persistent SQLite WAL recovery across independent Python subprocess launches | M3 | ORIGINAL_REQUEST § 8 |
| 15 | G10: Streaming GGUF Header & RAM Safety | Stream SHA256 chunk-by-chunk and inspect first 4 magic bytes without loading model to RAM | M3 | ORIGINAL_REQUEST § 8 |
| 16 | G11: Atomic Lease Fencing & Lock | Verify epoch lease and preimage SHA256 before atomic replace | M1 | ORIGINAL_REQUEST § 8 |
| 17 | G12: Installer WAL Backup & Pip Safety | Transactional SQLite backup API for WAL mode and pip fail-safe recovery | M3 | ORIGINAL_REQUEST § 8 |
| 18 | E2E Testing Suite Verification | Complete 808-test pass verification, adversarial stress testing, zero mock bypass | M3 | Master Prompt & Survey |
| 19 | Forensic Integrity Audit | Comprehensive audit veto check for authentic implementation | M4 | Master Prompt & Orchestrator Rules |

---

## Milestones

| # | Name | Scope | Dependencies | Status |
|---|---|---|---|---|
| M1 | Novel Domain Intent Routing & General Coding (G04, G03, G11) | Fix `language.py` routing for novel prompts to `domain="general"`, wire to `execute_general_task()`, eliminate trivial stubs with prompt repair loop in `coding_loop.py`, reinforce atomic file replace with file locks | none | DONE |
| M2 | Worker Order Lifecycle Robustness & Test Stabilization (G05) | Implement pre-flight candidate validation in `autonomy_loop.py:execute_worker_order_lifecycle` to eliminate 0.5B math hallucination flakiness; ensure 21/21 tests in `test_edition4_acceptance.py` pass 100% deterministically | M1 | IN PROGRESS |
| M3 | E2E Test Suite & Adversarial Coverage Hardening | Run and verify the full 808-test repo suite; add adversarial test cases for novel coding prompts (calculator, fibonacci, text transform) proving no template fallback; verify F01-F24, A01-A64, INST01-INST24, WEB01-WEB24, AUTO01-AUTO16 | M2 | PLANNED |
| M4 | Forensic Audit & Final Victory Attestation | Full forensic audit via `teamwork_preview_auditor`; verify zero cheating, zero trivial bypass; compile final deliverables status and report victory to Sentinel | M3 | PLANNED |

---

## Interface Contracts

### `code/ace_operational/language.py` ↔ `code/ace_operational/coding_loop.py`
- `classify_intent_frame(text: str) -> dict`:
  - When text is a novel coding request (e.g., "Buatkan kalkulator", "Buat program hitung fibonacci", "Buat skrip pengubah teks"), return `intent = Intent.CREATE_OR_MODIFY_CODE`, `domain = "general"`, `domain_confidence >= 0.7`.
- `ConversationalEngine.handle_user_message(text: str) -> dict`:
  - When `intent == Intent.CREATE_OR_MODIFY_CODE` and `domain == "general"`, invoke `self.coding.execute_general_task(title=..., goal=text)` rather than calling domain template routing.
- `CodingAgentLoop.execute_general_task(title: str, goal: str, filename: Optional[str] = None) -> dict`:
  - Returns `{"success": bool, "file_path": str, "receipt": dict, "test_passed": bool, "output": str}`.
  - If initial model candidate fails syntax or runtime execution, perform up to 2 prompt-guided repair iterations with error feedback. Never write trivial status stub functions (`def selesaikan_tugas`).

### `code/ace_operational/autonomy_loop.py` ↔ Worker Verification
- `AutonomyLoop.execute_worker_order_lifecycle(...) -> dict`:
  - Before calling `submit_and_verify_worker_result`, run candidate code in pre-flight sandbox. If self-asserts fail due to model arithmetic hallucination, repair assertions or fall back to verified candidate before submission.
  - Guarantee `res["accepted"] is True` with valid execution receipt while preserving AUTO09 safety validation.

---

## Code Layout
- `code/ace_operational/language.py`: Intent classifier and conversational engine.
- `code/ace_operational/coding_loop.py`: Coding agent loop, file atomic writes, general task synthesis.
- `code/ace_operational/autonomy_loop.py`: Autonomy loop, worker order lifecycle, gap discovery.
- `code/ace_operational/models_backend.py`: GGUF discovery, llama inference, JSON parsing.
- `code/ace_operational/store.py`: SQLite WAL store with fencing leases.
- `code/ace_operational/web_server.py`: Anime web server and SSE streams.
- `code/ace_operational/test_edition4_acceptance.py`: Primary 21-test acceptance suite.
- `tests/`: 98 E2E test suites (concurrency, crash recovery, reasoning, memory, AST gate).
