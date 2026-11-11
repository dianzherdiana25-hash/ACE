# ACE Ω — Executable Research and Engineering Program
**Program specification v0.1 | 2026-11-11 | proposed, not implemented**

Source: ACE_OMEGA_OPEN_ENDED_EVOLUTION_BLUEPRINT_20261111.md. This is a **dependency-aware program**, not a release promise. Acceptance requires implemented source, executable tests, exact-commit CI and independent evidence where claimed. Zero required additional paid services; local VM hardware and session lifetime are unknown until inspected.

## Preamble — scope control
Current ACE has real components but no verified end-to-end proof of general coding from a natural-language task, independent open-world algorithm discovery or sustained recursive evolution. Existing PR #102 has passing engineering CI on its checked SHA, but remains a **draft** not merged into main. PRs #95–#99 contain potentially overlapping reasoning, retrieval and evidence research on other branches. Reconcile before implementing duplicates.

Do not modify main, merged history, frozen benchmark or evaluator custody files. Work on an isolated research branch. New PRs should be draft. Changing authorization or spending needs an explicit decision. A work order cannot authorize its own evaluator or sandbox policy.

## 0. Live-read and integration inventory (P0)
Run:
- git status --short, rev-parse HEAD, branch -vv, fetch refs for active branches.
- Inventory architecture, tests, dependency graph and unmerged PR deltas; identify modules that already implement pieces of the proposal.
- Enumerate physical environment: uname, os-release, CPU, available RAM, disk, GPU and cgroup limits, Python version, local inference tools, outbound restrictions and workspace lifecycle.
- Determine who owns source of truth for store, MissionBus, tools, memory, evaluator and experiment receipts.
- Create conflict matrix: proposed work package -> existing module -> current branch/PR owner -> integration adapter -> independent tests.
- Define a baseline benchmark suite BEFORE any model/prompt/kernel changes.

### Actual existing starting points
models_backend.py; software_factory.py; coding_loop.py; autonomy_loop.py; autonomous_engine.py; store.py; ace_mission/bus.py; PR #102 open-world planner, durable task bridge, review-only bus and trusted local pure-function executor.

Potential issues based on source inspection:
- ModelRouter's generic fallback may return plausible-looking output despite inference failure.
- generate_structured may fill required keys with generic invented values and misleading "ok".
- SoftwareFactory.build_project requires files_spec supplied by a caller, so it is not an autonomous repo-editing agent.
- daemon background language-learning activity is not proof of coding/reasoning self-improvement.
- open-world planner / local executor are structurally bounded, not a general sandboxed LLM execution tool.

## 1. Program packages and dependency gates

### OMEGA-00 — Hardware/Model Attestation (P0, no dependency)
**Deliverables:** environment_probe.py (read-only), model_inventory.json, measured RAM/latency/tokens-per-second, model digest, supported runtimes, persistency diagnostic, basic Indonesian and code benchmark; explicit missing-resource status.  
**Test:** same model checksum and environment produce reproducible probe metadata; no credentials printed.  
**Fail:** BLOCKED_ENVIRONMENT if no valid local model. Provide honest alternatives.

### OMEGA-01 — Truthful Local Inference Fabric (P0, depends 00)
**Deliverables:** adapter contract with local_process/loopback_only backends, bounded JSON structured output, status codes, provider_model_digest, error types, provenance, explicit NO_MODEL/INFERENCE_ERROR/UNPARSEABLE_RESPONSE; RAM-aware selection.  
**Test:** real local inference and tests for unreachable server, timeout, corrupted GGUF, invalid JSON, prompt injection, offline/no-egress, out-of-memory, thread scheduling.  
**Do not:** claim "ok" using fabricated fallback, silently switch to cloud, auto-fetch arbitrary model/code.  
**Success:** fixed unseen prompts yield honest model responses or failures without false completion.

### OMEGA-02 — Repo Knowledge and Context Manager (P0, depends 01)
**Deliverables:** bounded repo walker, language-aware source indexing, AST/symbol dependency map, git-diff navigation, test-to-source mapping, risk classification, retrieval citations file:line, context pack, decontamination.  
**Test:** unfamiliar repo with decoy files, renamed symbols, symlinks and path traversal; exact located relevant files and context-size budget.  
**Reuse:** PR #99 bounded AST retrieval after branch ownership assessment.

### OMEGA-03 — General Autonomous Coding Agent (P0, depends 01+02)
**Deliverables:** natural-language issue to versioned goal contract, multistep plan, patch proposals, isolated git worktree, multi-file changes, syntactic/semantic checks, test creation, bounded fix loop, full failure traces; never rely on user-supplied code content as the "solution."  
**Test:** fresh unseen repository, bugs spanning files, dependency inversion, failing tests and poisoned README instructions. No candidate code supplied by a human.  
**Metrics:** task completion, patch validity, independent test pass, regressions, compute and time.  
**Baselines:** one-shot same model, deterministic fix-script, original ACE coding_loop under matched budget.

### OMEGA-04 — Executable Task Graph / Durable Workflow (P0, depends 03)
**Deliverables:** one durable DAG, worker queue, lease/fencing, snapshot pinning, idempotent work orders, checkpoint/restart, cancellation, retry/backoff, resource admission, truthfully reported terminal statuses.  
**Test:** kill at every transaction boundary, restart, duplicated message, stale worker, corrupted checkpoint, exhausted quota; no duplicate non-idempotent effects.  
**Reuse:** OperationalStore, autonomy_loop, MissionBus, PR #102 task bridge. Do not fork competing truth stores.

### OMEGA-05 — Sandboxed Tool and Patch Execution (P0, depends 03+04)
**Deliverables:** explicit tool/capability manifest with effect class, platform-verified isolation, filesystem and network restrictions, process limits, timeout, allowed test runner, separate candidate output and verification receipt.  
**Test:** file escape, symlink traversal, fork bomb under limits, stdout exhaustion, network egress attempt, forged receipt, process lifetime. If adequate sandbox not possible, BLOCKED_ENVIRONMENT rather than executing untrusted code on host.

### OMEGA-06 — Experiment Protocol and Evidence Kernel (P0, depends 01+03+05)
**Deliverables:** versioned preregistration, split custody, strong baselines, negative controls, protocol hash, candidate/artifact digest, raw resource telemetry, evaluator independence, pass/fail/abstain states, audit verification.  
**Test:** leakage canary, forged success flag, fixture mutation, changed evaluator, candidate editing its own test, train/test contamination, partial result replay.  
**Success:** engineering tests at exact SHA and scientifically appropriate evaluation evidence, separately marked.

### OMEGA-07 — Persistent Cognitive Memory (P1, depends 04+06)
**Deliverables:** episodic, semantic and procedural records with provenance; bounded retrieval; confidence, conflict resolution, retention and forgetting; source evidence vs model guesses.  
**Test:** cross-restart task recall, false-memory injection, stale semantic knowledge, negative transfer detection, privacy and contamination controls.

### OMEGA-08 — Population and Lineage Archive (P1, depends 06)
**Deliverables:** immutable candidate and parent IDs, experiment and evaluation links, multi-objective metrics, robust selectors, comparison under identical budgets, negative-result archive.  
**Test:** duplicate candidate identity, lineage cycles, missing evidence, mixed-evaluator collision, Pareto/tie handling, corrupted evidence, replays.  
**Scientific gate:** at least two genuinely distinct candidates and comparison to equal-budget random/fixed baseline, without claiming OAIE.

### OMEGA-09 — Mutation, Recombination and Diversity Engine (P1, depends 08)
**Deliverables:** mutation classes (parameter/prompt, tool, planner, algorithm, representation, learning method, architecture), bounded proposal search, novelty classification, archive-informed candidate generation, provenance and safety admission.  
**Test:** novelty false-positive, candidate duplicates, regression preservation, invalid mutations, negative results.  
**Gate:** no unverified "new primitive" claims.

### OMEGA-10 — Environment and Curriculum Co-Evolution (P1, depends 06+08)
**Deliverables:** task generators with testable validity, independent verifier, difficulty taxonomy, train/holdout separation, duplicate/leakage checks, curriculum scheduler.  
**Test:** trivial-task gaming, invalid problem, reference solution leakage, generated benchmark inflation, task-family transfer.

### OMEGA-11 — Reasoning, Representation and Algorithm Lab (P2, depends 03+06+09)
**Deliverables:** formal experiments contrasting authored grammar composition vs novel operator/representation proposals; disjoint-family transfer and ablations; optional symbolic/theorem tools.  
**Test:** baseline dominance, hypothesis falsification, multiple seeds, resource-matched independent evaluation.  
**Gate:** novelty and generalization claims stay NOT_ASSESSED until custody and transfer proof.

### OMEGA-12 — Model Improvement Lab (P2, depends 01+06)
**Deliverables:** model comparison, quantization optimization, context adaptation, optional LoRA/fine-tuning when permitted by model license/hardware, distillation as hypothesis only.  
**Test:** true held-out model ability, calibration, hallucination/failure rates, memory/cost.  
**Gate:** improvements over same baseline/model at comparable resources.

### OMEGA-13 — Meta-Evolution Search Lab (P3, depends 08+09+10+11)
**Deliverables:** experiments on mutation operators, selection rules, novelty reward, budget allocation, curriculum and experimental design.  
**Test:** fresh search problems + independent evaluator; compare fixed heuristics, random search, quality diversity and ablations at equal spend.  
**Gate:** G4 only after validated search efficiency or superior generalization.

### OMEGA-14 — Successor Architecture Foundry (P3, depends 06+08+13)
**Deliverables:** isolated G0/G1/G2 snapshots, inheritable capability contracts, testable architecture migration, lineage, automatic benchmark of successors under equal resources.  
**Test:** inheritance integrity, recovery, cross-family retention, strong ancestors comparison, ablation of transfer.  
**Gate:** G5 only after independently confirmed generational improvement.

### OMEGA-15 — Research OS + Dashboard and Operator Interface (P1, depends 04+06)
**Deliverables:** unified read-only status projection, agenda queue, ledger, tests, costs, model readiness, lineage, reasons for HOLD/NO_PLAN/BLOCKED, incident response and manual scoped approval interface.  
**Test:** crash/restart, stale projections, false-active worker, never assert continuous runtime based on heartbeat file alone.

### OMEGA-16 — Cross-domain Interoperability (P2, depends 02+04+05)
**Deliverables:** typed discovery of capability plugins and adapters across local machines/CPU/GPU/research domains, without requiring cloud models. Optional standard protocol adapters only after conformance tests.  
**Test:** version drift, malicious tool descriptions, remote failure, side-effect denial, identity/custody and authorization.

## 2. Six program gates and checkable outputs
| Gate | Exact requirement | Not enough |
|---|---|---|
| G0 (real local AI) | model checksum, hardware + raw inference response, falsification cases | Ollama installed, generic status string |
| G1 (real coding autonomy) | unseen repo issue→patch→independent tests→receipt→restart | user-supplied files_spec, a syntax-only test |
| G2 (population adaptation) | immutable lineage, competing candidates, equal-budget baseline | number of "agents", unmeasured mutations |
| G3 (new capabilities) | cross-family transfer + negative controls + valid problems | skill description or generated curriculum only |
| G4 (meta-evolution) | independent matched-budget search-method comparison | runtime cycles, renamed search operator |
| G5 (generational research) | measured G0→G1→G2 retention and transfer | self-rewriting source / new version number |

## 3. Sixteen lanes and interfaces
- R01 language and structured dialogue: contracts with G0 and R03.
- R02 world/causal model: hypothesis provenance to R14.
- R03 planning/search: explainable task DAG to R05.
- R04 memory: procedural/semantic records to R03/R05/R15.
- R05 coding: patches and negative tests to R06/R15.
- R06 tool creation: typed capability proposals to execution/evaluator.
- R07 mathematical proof: proof artifact and verifier independent of candidate.
- R08 program synthesis: typed candidate artifacts to R09/R11.
- R09 representation invention: novelty proposals and provenance to R11.
- R10 continual learning: learning protocol to R04/R12.
- R11 evolutionary computation: selection and mutation to population archive.
- R12 environment generation: validated tasks to IEE.
- R13 model architecture and optimization: model metadata to G0/G1.
- R14 scientific research method: preregistration, controls to IEE.
- R15 meta-research: equal-budget research policy experiments.
- R16 successor evolution: G0/G1/G2 migration to IEE.

One lane may be **virtual/time-multiplexed** on a single LLM. Do not instantiate unused agents just to increase count. Give each lane a measurable question and an independent receipt.

## 4. Integration matrix
| Component currently in ACE | Integrate/extend, not replace blindly | Prohibited shortcut |
|---|---|---|
| models_backend.ModelRouter | real reliable local output + fail-closed structured contract | invented JSON "ok" fallback |
| software_factory.SoftwareFactory | model-generated repo patches + isolated test suite | require files_spec from user |
| coding_loop.CodingAgentLoop | safe edits, receipts, genuine general code agent | claim templates = open coding |
| autonomy_loop.AutonomyOrchestrator | one DAG, queue, worker health, effective pivots | worker "online" by boolean only |
| autonomous_engine.ContinuousAutonomousEngine | real adaptive agenda + budgeted G0/G1 research | cycle count = intelligence gain |
| store.OperationalStore | lineage/protocol/evidence migrations | competing state authority |
| ace_mission.MissionBus | stable custody + versioned adapter | edit evaluator-bound bus.py source |
| draft PR #102 open-world layer | optional planner/task bridge/verified pure adapters after ownership audit | treat typed plan as tool execution |

## 5. Execution decision function (informative)
For each research task, estimate:
- probability of valid evaluation; opportunity to falsify an important claim;
- expected capability transfer and critical-path benefit;
- novelty/diversity relative to archive;
- CPU/GPU/RAM/time/disk cost; risk and permission effect;
- dependency readiness and independent evaluator availability.

Use a reproducible baseline heuristic initially. Search for a better allocation function only **after** this baseline is benchmarked. Do not pretend a speculative expected-value score is a measured probability.

## 6. Definition of Done: universal
A package is NOT DONE unless all applicable items are checked:
1. actual code/files committed on isolated branch, reviewable diff;
2. real integration into existing runtime, not only a class name or standalone demonstration;
3. deterministic public unit/integration tests and representative failure/adversarial tests;
4. real model/process end-to-end test if package claims execution;
5. resource, permission and side-effect boundaries documented and tested;
6. restart/idempotency behavior tested if persistent;
7. exact HEAD SHA + CI URL + raw receipts + model identity recorded;
8. no frozen fixture changes or unrelated regressions;
9. clear PASS/FAIL/HOLD/NOT_ASSESSED for claims;
10. concise next smallest unblocked implementation step and owning lane.

No "100%" language without exact measurable coverage denominator. Green engineering CI != research success.

## 7. Operator sequence (Antigravity bootstrap)
A. Read source and architecture; inventory hardware and runtime lifetime.  
B. Create baseline and test harness.  
C. Implement truthful local ModelRouter.  
D. Prove one unseen real issue solved by ACE (not Antigravity).  
E. Add crash/restart durability, sandbox and evaluation receipts.  
F. Add population archive and genuine multi-candidate baseline.  
G. Expand to new problems/skills and independent cross-family transfer.  
H. Research search methods and successor architecture only after prior gates.

At every step: detect conflicts with active PR owners, implement minimal compatibility adapter, test negatives, commit isolated research checkpoints, open draft PR, preserve older artifacts. Continue within the session and allowed resources; if blocked or budget exhausted, save truthful checkpoint for a future human-initiated or scheduled session. Do not claim work continues after a terminated VM.

## 8. First three non-negotiable demonstrations
1. **Truthfulness demo:** disconnect model; ACE must report model unavailable, never claim successful structured reasoning.
2. **Coding demo:** fresh repository bug, natural-language task only; ACE must locate, patch, test and save receipt without Antigravity generating the patch.
3. **Evolution demo:** two different ACE coding strategies compete on disjoint bugs with matched model compute; archive stores negative as well as positive outcome and survives restart.

These three demonstrations transform this roadmap from conceptual to falsifiable engineering.
