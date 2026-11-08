# Preregistration: ACE Autonomous Continuity & Research State V0.2

**Protocol ID:** `ACE_AUTONOMOUS_CONTINUITY_V02_PRESCORE_20261107`  
**Registration Date:** 2026-11-07  
**Status:** FROZEN PRE-SCORE PROTOCOL COMMITMENT  
**Release Gate:** `BLOCK_RELEASE`  
**Scientific Status:** `NOT_ASSESSED`  
**OAIE Established:** `False`  
**Marginal Financial Cost:** Strictly $0.00 / Rp0 (Local standard library compute)

---

## 1. Epistemic Background & Objectives

ACE Autonomous Continuity V0.2 upgrades the bounded single-cycle self-development loop into a persistent, multi-cycle autonomous research system capable of selecting, executing, evaluating, and chaining research cycles across separate OS and GitHub Actions executions without human intervention per cycle.

### Key Architectural Invariants:
1. **Persistent Research State (`research_state.json`):**
   - Active generation lineage, completed cycle trajectory, catalog of empirical failures, hypothesis history, and autonomous next-agenda priority are stored persistently.
   - Includes a cryptographic rolling Merkle state digest (`state_digest`) linking each cycle to its immediate predecessor.
2. **Elimination of Static Human Operator Overrides:**
   - Deprecates hardcoded static flags (`--cycle 1`, `--task-seed 42`, `--mutation-ordinal 1`).
   - The loop autonomously observes state, determines `cycle_id = completed_cycles + 1`, generates deterministic pseudo-random task variation seeds from state entropy, and selects mutation strategy based on diagnosed weaknesses and past failure history.
3. **Formal 8-Stage Research Lifecycle:**
   $$\text{Observe} \to \text{Diagnose} \to \text{Hypothesize} \to \text{Generate} \to \text{Evaluate} \to \text{Decide} \to \text{Preserve} \to \text{Select Next Goal}$$
4. **Multi-Cycle Empirical Chaining:**
   - Minimum three sequential cycles run in distinct process invocations.
   - Cycle 2 must consume Cycle 1's empirical outcome and state digest.
   - Cycle 3 must consume Cycle 2's empirical outcome and state digest.
5. **Sealed Independent Evaluation & Negative Controls:**
   - Candidate generation has zero access to evaluator holdout banks.
   - Evaluation uses dual-oracle harness with matched execution budget (max 120s, max 500 queries, $0.00 cost).
   - Negative controls verify that non-generalizing candidates, malformed ASTs, or regressions are decisively rejected.
6. **Bounded GitHub Actions Scheduler:**
   - Concurrency lock with lease expiration and heartbeat.
   - Strictly bounded cycle budget per invocation ($\le 3$ cycles).
   - Fail-closed recovery: crashes restore from verified baseline without corrupting lineage.
7. **Execution Containment & Sandbox Hardening:**
   - Whitelisted pure Python AST nodes only.
   - Strict prohibition of imports, builtins, filesystem, network, and subprocess access.
8. **Provable Execution Provenance:**
   - Eliminates embedded hardcoded signing secrets.
   - Dynamic signing key derived from environment (`ACE_SIGNING_KEY`) or high-entropy ephemeral cryptographic session tokens (`secrets.token_hex(32)`).
   - Candidate provenance authenticated by real execution context (PID, platform, interpreter, commit SHA, HMAC proof).
9. **Preservation Against Loss of Existence:**
   - Read-only immutable baseline (`immutable_baseline.json`) and recovery backup (`recovery_baseline.json`).
   - Candidate code cannot delete, overwrite, or corrupt recovery mechanisms.

---

## 2. Pre-Registered Confirmation Criteria

1. **Promotion Threshold:** $\Delta_{\text{holdout\_gain}} \ge 0.1500$ over active parent baseline on sealed confirmation holdouts.
2. **Regression Tolerance:** Prior task performance regression $\le 0.0200$.
3. **Fail-Closed Lineage Rule:** If $\Delta_{\text{gain}} < 0.1500$, the candidate MUST be rejected; the active lineage head remains unchanged at the parent baseline.
4. **Negative Result Retention:** Failed candidates and falsified hypotheses are permanently cataloged in `failure_catalog` as scientific evidence.
5. **Multi-Cycle Continuity Proof:** Cycle $N$ must cryptographically attest `prior_cycle_id = N-1` and `state_digest_before = state_{N-1}.digest`.
6. **Zero Marginal Financial Cost:** $0.00 / Rp0 strictly verified across all cycles.

---

## 3. Immutable Governance Commitment
```json
{
  "release_gate": "BLOCK_RELEASE",
  "scientific_status": "NOT_ASSESSED",
  "oaie_established": false
}
```
Multi-cycle autonomous continuity establishes operational research reliability, not general recursive self-improvement or open-ended intelligence evolution.
