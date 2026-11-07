# ACE Fase 10 (F10) — Autonomous Structural Hypothesis Synthesis Preregistration

**Protocol Version:** `v1.0-preregistered-20261107`  
**Execution Lane:** `research/ace-f10-hypothesis-synthesis-20261107` (Issue #70 Priority C / P2)  
**Parent HEAD SHA:** `a8efd9bfc9a9633bcd1a8b815bc7d7f725cffeb7`  
**Scientific Status:** `SCIENTIFIC_NOT_ASSESSED` | **Release Gate:** `BLOCK_RELEASE`  
**OAIE Status:** `OAIE_NOT_ESTABLISHED`  

---

## 1. Problem Statement & Motivation

Prior autonomous execution in ACE Fase 9 (`code/ace_research_agenda/coordinator.py`) demonstrated autonomous multi-cycle execution, but its hypothesis proposal mechanism selected hypotheses from a fixed, hand-authored catalog (`HYP_01_...` to `HYP_07_...`). Concurrently, research in S1 (`PR #34`, `code/ace_research_hypotheses/`) revealed a critical negative result: unstructured compositional/random hypothesis generation failed the matched-control threshold (`.74167` vs `.73750` static, precommitted `+0.05` margin **REJECTED**).

Fase 10 develops **Structural Hypothesis Synthesis (`code/ace_research_hypgen/`)**:
A typed, generative grammar that takes observed empirical capability gaps from live subsystems (e.g., self-model calibration errors, repair budget ceilings, representation drift vulnerabilities) and synthesizes *novel, structured, falsifiable research hypotheses* accompanied by executable ACE Autonomy / Runtime goal specifications.

---

## 2. Typed Hypothesis Grammar ($\mathcal{G}_{\text{hyp}}$)

Every synthesized hypothesis must strictly conform to a typed AST grammar:

$$\text{Hypothesis} ::= \langle \text{Domain}, \text{GapReference}, \text{PropertyPredicate}, \text{FalsificationBound}, \text{GoalSpec} \rangle$$

1. **Domain**:
   - `STRING_REGULAR_LANGUAGE`: Parity, cyclic shifts, modular counts over $\{a, b\}$.
   - `STRING_CONTEXT_FREE_MIRROR`: Palindromic balance, Dyck paths.
   - `ARITHMETIC_INVARIANT`: Modular congruence, affine relations.
   - `REPRESENTATION_OCCUPANCY`: Feature-level transfer across discrete state abstractions.

2. **Property Predicate**:
   - `ExpressibilityBoundary(K)`: Bounds on DFA state counts or AST depth.
   - `SampleComplexityThreshold(B)`: Generalization accuracy at limited sample budget $B$.
   - `DriftVulnerability(D)`: Terminal holdout accuracy under unobservable label shift.
   - `TransferEfficiencyGain(E)`: Amortized compute reduction vs fresh baseline.

3. **Falsification Bound**:
   A deterministic predicate $f(\text{ObservedMetric}) \to \{\text{PASS}, \text{FAIL}\}$ defining the exact empirical condition that disproves the hypothesis.

4. **Goal Spec**:
   An executable `ace.goal.v1` object defining authorized tools, read/write boundaries, budget ceilings, and task arguments.

---

## 3. Comparative Benchmark Arms

To prevent overfitting or false claims of discovery, F10 evaluates 5 matched arms across family-disjoint tasks:

| Arm ID | Name | Description |
| :--- | :--- | :--- |
| **Arm A** | `M1_fixed_catalog` | Fixed static hand-authored hypotheses (baseline HYP_01..07 style). |
| **Arm B** | `M2_random_grammar` | Random unbiased sampling from production rules without gap grounding. |
| **Arm C** | `M3_novelty_only` | Greedy selection maximizing Jaccard/edit distance from past archive without empirical gap grounding. |
| **Arm D** | `M4_extra_compute` | Fixed catalog with 4× evaluator / simulation compute budget. |
| **Arm E** | `M5_f10_structural` | Grounded structural synthesis driven by live subsystem capability gaps, typed constraints, and self-model calibration. |

---

## 4. Evaluation Tasks & Seed Bank

Evaluation is conducted on 4 family-disjoint task distributions using distinct RNG seeds (Seeds 42, 137, 2026):
1. **Task Family 1 (Regular Modulo Languages)**: Bounded state induction on string alphabets.
2. **Task Family 2 (Dyck & Mirror Boundaries)**: Context-free boundary mapping for state-merging limits.
3. **Task Family 3 (Multi-Modular Composition)**: Joint mod-2 × mod-3 invariant preservation.
4. **Task Family 4 (Negative Semantic Drift Controls)**: Unobservable label inversion holdouts.

---

## 5. Precommitted Acceptance Gates

1. **Gate 1 (Syntactic & Falsification Integrity)**:
   - 100% of synthesized hypotheses must possess well-formed falsification criteria.
   - 100% of generated goal specifications must be executable by the typed tool broker.
2. **Gate 2 (Empirical Value & Transfer Threshold)**:
   - F10 Structural Synthesis (Arm E) must beat matched random control (Arm B) and novelty-only (Arm C) by $\ge +0.05$ mean validated information gain / task solve rate.
   - If $\Delta < +0.05$, the outcome must be explicitly recorded as **FALSIFIED / THRESHOLD_REJECTED**.
3. **Gate 3 (Negative Drift Honesty)**:
   - Unobservable drift must be reported honestly with failure / abstention rates; no fabricated 100% success on shifted distributions.
4. **Gate 4 (Real Runtime Execution)**:
   - Tasks must be dispatched to real `ace_runtime` or `ace_autonomy`, producing valid task IDs and receipts.
