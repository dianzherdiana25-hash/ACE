# ACE Durable Research Autonomy Specification & Verification (P3)

**Date:** 2026-11-07  
**Subsystem:** `code/ace_research_agenda`  
**Target:** Open-Ended Autonomous Intelligence Evolution (OAIE) Groundwork  
**Authority Boundary:** Bounded Authority, CPU-only (\$0 budget), Read/Stage-for-Review  
**Status:** `VERIFIED_EMPIRICALLY` (Engineering & Resilience); `SCIENTIFIC_CAPABILITY_VALIDATED = False`  

---

## 1. Context & Motivation (Issue #70 P3)

In previous iterations (Fase 9), the Autonomous Research Agenda Coordinator (`code/ace_research_agenda/coordinator.py`) ran inside an ephemeral `tempfile.TemporaryDirectory`. When the OS process was killed or finished, all autonomy task states, episodic self-model calibrations, and archive journals were wiped from disk.

Under real-world autonomous operations, an AI agent must endure:
1. Process interrupts and restarts (SIGKILL, container preemption, host reboot).
2. Multi-session execution across distinct operating system processes.
3. Idempotent continuation without repeating already completed, refuted, or abstained research hypotheses.
4. Cryptographic integrity of state across process boundaries (HMAC chained journals in `Autonomy`, `ExperienceMemory`, and `ResearchArchive`).

---

## 2. Architecture & Design

### 2.1 Workspace Structure
A durable research campaign operates inside a durable workspace directory containing three isolated, WAL-journaled SQLite databases and an atomic JSON checkpoint:

```
<workspace_dir>/
  ├── autonomy_ws/
  │   ├── autonomy.db         # Leased goals, step escrow, HMAC signed receipts
  │   └── .autonomy_key       # 32-byte secret HMAC key
  ├── selfmodel_ws/
  │   ├── episodes.db         # Episodic memory, self-reflection records, calibration
  │   └── .memory_key         # 32-byte secret HMAC key
  ├── archive_ws/
  │   ├── research_archive.sqlite3 # Hash-chained scientific verdicts (both positive & negative)
  │   └── .agenda_key         # 32-byte secret HMAC key
  └── agenda_checkpoint.json  # Atomic checkpoint with cumulative step/cpu counts & cycle logs
```

### 2.2 Resumption Semantics
When `run_durable_autonomous_research_campaign(workspace_dir, ...)` or `AutonomousResearchCoordinator(..., workspace_dir=...)` starts:
1. **Durable Discovery:** It inspects `ResearchArchive.list_records()` and `agenda_checkpoint.json`.
2. **Idempotent Filtering:** Hypotheses already present in `archived_records` (supported, refuted, or abstained) are excluded from `remaining`.
3. **Metacognitive State Transfer:** When proposing and ranking hypotheses, `MetacognitiveEvaluator` queries `ExperienceMemory`, which loads prior refutations (such as `HYP_02_PALINDROME_DFA_LIMIT_PROBE_A` failure) across process restarts. This ensures `HYP_03` is immediately recognized as an empirical failure risk and abstained in the resumed process without human intervention.
4. **Cycle Continuation:** `start_cycle = prior_cycle_count + 1`. The coordinator resumes cycle indices contiguously (e.g., cycles 3–5 after cycles 1–2).
5. **Crash Resilience:** Every cycle atomically commits to the SQLite WAL archive and writes an fsynced `.tmp` checkpoint before replacing `agenda_checkpoint.json`.

---

## 3. Empirical Verification (`test_durable_resume.py`)

The durability harness was verified with three multi-process integration tests:

| Test Case | Scenario | Verification Result |
|---|---|---|
| `test_two_phase_stop_and_resume_separate_processes` | Process A runs cycles 1–2 and exits. Process B spawns in a fresh subprocess and completes cycles 3–5. | **PASS** (Zero duplicate hypotheses; `HYP_03` abstained via persisted memory; contiguous HMAC chain across 5 cycles; all loop gates passed). |
| `test_idempotent_resume_on_completed_campaign` | Re-invoking campaign on completed workspace. | **PASS** (0 additional cycles executed; idempotent return with intact archive). |
| `test_checkpoint_state_tamper_detection` | Tampering with archive key or sqlite row. | **PASS** (Fails closed with `IntegrityError`). |

---

## 4. Scientific Honesty & Release Gate Blockers

As required by the Project Charter:
- `scientific_status`: `NOT_ASSESSED`
- `release_status`: `BLOCK_RELEASE`
- `oaie_established`: `False`
- `SCIENTIFIC_CAPABILITY_VALIDATED`: `False` (Blocked because hypothesis templates remain fixed, single-seed probes are small-N, and durability is an engineering resilience property, not proof of open-ended evolution).
