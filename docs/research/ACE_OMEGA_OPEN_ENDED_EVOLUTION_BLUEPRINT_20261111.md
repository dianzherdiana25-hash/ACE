# ACE Ω — Open-Ended Intelligence Evolution Ecosystem
**Architecture and scientific research design | 2026-11-11 | proposal v0.1**

**Repository:** dianzherdiana25-hash/ACE  
**Vision:** Open-Ended Autonomous Intelligence Evolution (OAIE)  
**Document status:** PROPOSED / NOT IMPLEMENTED / SCIENTIFICALLY NOT ASSESSED  
**Authority:** research branch only. No automatic merge, deployment, spending, credential access, external effect, or evaluator mutation.  
**Anchors:** PROJECT_CHARTER.md; docs/PRD_ACE_v0.1.md; existing research/e1.3-design; ongoing draft PR #102 open-world planner.  
**Important:** This document expands the research horizon. It must not be used to advertise AGI, consciousness, unlimited computing or verified recursive self-improvement.

## 0. The architectural change
ACE must stop being understood as only one assistant executing an ever-longer list of tasks. The proposed target is a **research ecosystem** that creates and tests populations of cognitive architectures, representations, algorithms, tools, learning policies, benchmarks and successor candidates.

The system must permit:
- New domains and capability types without a hard-coded domain enumeration.
- Different intelligence mechanisms, including LLMs, symbolic methods, optimization, program synthesis, hybrid approaches and as-yet-unproven candidates.
- Multiple concurrent **logical** research tracks (not a promise of concurrent GPU workers).
- Accumulation and cross-domain transfer of measured capabilities across generations.
- Experimental alteration of the *search process* itself, while protecting an independent evaluator and an immutable provenance trail.
- Continued productive research following a model failure, crash, contradictory evidence or a failed experiment, within explicitly authorized resources.

"Open-ended" means extensible **research search space** and empirical question generation, not unlimited CPU, unrestricted authority, infinite skill, or unbounded success.

## 1. Three deliberately different trust domains

### A. Stable Research Kernel (SRK)
Keep the small trusted base stable: configuration, project authority, capability/effect typing, resource admission, local worker supervision, durable event journal, snapshot integrity, process cancellation, checkpoint/recovery, artifact content hashes, and promotion review. A candidate must not be able to edit its own guardrails, evaluator custody, recorded baselines or authorization rules.

### B. Evolvable Intelligence Ecosystem (EIE)
Candidates live here: model orchestration, local prompting, problem decomposers, planners, retrieval policies, memory encodings, new tool proposals, program generators, search heuristics, representation classes, simulated worlds, scientific hypotheses, algorithm designs, and successor architectures. Every candidate has an immutable ID, ancestry, implementation digest, declared input/output contract, resource envelope, and evidence state. Treat generated code and instructions as untrusted until isolated and verified.

### C. Independent Evaluation Ecosystem (IEE)
Separated custody for evaluator configuration, task splits, test fixtures and scoring code; independent replay of candidate artifacts; strict bookkeeping for exposed vs withheld examples; failure reporting; control baselines; transfer tests; adversarial cases; resource-metered comparison; provenance. Evaluator *research* can propose successor evaluators, but cannot silently change the active scoring authority.

The SRK, EIE and IEE must be separable processes/workspaces with explicit, versioned interfaces. A successful unit test of the infrastructure does not imply scientific improvement.

## 2. Co-evolving populations (minimum conceptual families)
1. **Intelligence population:** coding agents, local model configurations, cognitive executives, planners, inference policies, critics, hybrid neural-symbolic agents.
2. **Capability population:** verified tools, skills, procedures, graph operators, algorithms, reusable programs, representation primitives, interface contracts.
3. **Environment population:** new task generators, simulated worlds, domain curricula, difficulty regimes, transfer/shift families, independent validity checks.
4. **Evolution population:** search and selection algorithms, mutations, recombination, quality-diversity archives, novelty scores, scheduling policies, multi-objective optimization.
5. **Research-method population:** hypothesis generators, experimental protocols, power/resource design, baselines, uncertainty measurements, prescoring, negative-result interpretation.

Cross-population relationships must be typed, tested, lineage-addressable and budget-accounted. An AI generating a novel-sounding description is NOT evidence of invention.

## 3. Ten layers and 60 investigable subsystems
These are **research tracks**, not 60 currently implemented or promised deployable modules. New classes may be proposed through versioned contracts and admitted after proof.

**L01 — Cognitive Intelligence**
- goal grounding and multilingual intent parsing
- long-horizon planning and execution monitoring
- causal reasoning and intervention selection
- uncertainty, abstention and calibration
- metacognitive error attribution and alternative strategies
- hierarchical reasoning with task-graph revision

**L02 — Model Intelligence**
- offline local inference via llama.cpp / Ollama / equivalent
- quality-vs-RAM-vs-latency model benchmarking
- context management, prompt compilation and routing
- quantization and batching experiments
- adapter training / LoRA where available and warranted
- knowledge/distillation candidate experiments (subject to rights and budget)

**L03 — Memory and Knowledge**
- versioned episodic traces and task results
- semantic knowledge with provenance
- procedural skills and admissible execution contracts
- dependency/causal/knowledge graph retrieval
- consolidation, compression and retrieval policies
- forgetting, conflict detection and erroneous-memory correction

**L04 — Autonomous Engineering**
- unfamiliar-repository map/index and dependency resolution
- issue localization and root-cause hypothesis
- plan-to-patch generation and multi-file edit planning
- test creation plus independently held regression tests
- repair, refactoring and rollback under isolation
- architectural evolution of the coding workflow itself

**L05 — Tool and Skill Creation**
- capability gap detection against an actual task
- tool discovery and interface matching
- bounded program synthesis and safe local tool proposal
- tool composition and type/effect-aware planning
- tool-level validation, contracts and version migration
- cross-family skill transfer with negative transfer tracking

**L06 — Scientific Discovery**
- falsifiable hypothesis formation
- strong baseline/negative-control selection
- experiment design, preregistration and leakage controls
- reproducibility and evidence preservation
- causal intervention, sensitivity and ablation studies
- negative/indeterminate-result mining and new-hypothesis prioritization

**L07 — Algorithm and Representation Evolution**
- typed program synthesis and compositional search
- proposed new operators and computational abstractions
- representation-class invention beyond authored grammars
- evolutionary algorithm search and quality-diversity
- neuro-symbolic / constraint / theorem-proving hybrids
- transfer to disjoint families, seeds and generational retention

**L08 — Environment and Curriculum Evolution**
- valid problem-generation mechanisms
- curriculum difficulty adaptation and diversity
- task-family novelty, duplicate and contamination control
- simulator construction with independent dynamics checks
- distribution-shift and adversarial probes
- out-of-domain transfer tests and holdout management

**L09 — Population and Successor Evolution**
- immutable population and lineage records
- bounded mutation and recombination proposal protocols
- multi-objective diversity/quality selection
- competition and complementary ensemble experiments
- cross-generation inheritance and replay
- heterogeneous successor architecture design and comparison

**L10 — Infrastructure, Security and Governance**
- cross-platform VM/bootstrap and environment diagnostics
- resource-aware priority scheduler, quotas and cancellation
- durable journals, at-least-once work delivery and idempotent receipts
- isolated candidate execution and least-privilege permissions
- evaluator custody, audit trails and forbidden-data boundaries
- crash recovery, checkpoint, human approval, rollback and incident tests

## 4. Seven levels of evolution (all require different evidence)
- E0 **Task:** solve one concrete task with accepted observable result.
- E1 **Agent:** agent strategy improved over a strong fixed baseline on new tasks.
- E2 **Capability:** new reusable procedure/tool/skill improves multiple distinct tasks.
- E3 **Learning:** new learning/retrieval/adaptation policy improves sample/compute efficiency on held-out tasks.
- E4 **Representation:** demonstrate a genuinely new representation or operator class, not only a composition within an authored grammar.
- E5 **Evolution of evolution:** a newly proposed search/evaluation allocation method outperforms the prior one on separately evaluated search problems at comparable resources.
- E6 **Successor:** G0→G1→G2 retain and improve capabilities across new task families without silently shifting metrics, using independent custody and regression gates.

Promote the supported level only. A claimed "E6" with only source edits and unit tests remains NOT_ASSESSED.

## 5. Local-VM-first intelligence topology
Goal: Antigravity (or another agent with a real host) acts as **bootstrap operator**. ACE, local model and local tool execution run on the same supported VM with **zero required cloud-model API keys**. Communication may use process invocation or loopback HTTP. Avoid equating "no paid cloud API" with "no API protocol".

Boot sequence:
1. Inventory real OS, architecture, CPU, available RAM, disk, GPU/device files, cgroup limits, outbound access permissions, process lifetime and installed inference binaries; do not invent hardware.
2. Read ACE source and existing interfaces before adding any compatibility layer.
3. Select one real model that fits a conservative memory envelope. Baseline: reliable actual outputs on Indonesian instruction, structured plan, unseen Python bugfix, long-context retrieval, abstention and adversarial prompts; record model digest and quantization.
4. Choose llama.cpp / Ollama or tested local runtime, bind loopback only, cap context and concurrency, impose timeouts and ensure the service is health-checked.
5. Connect ModelRouter to a **truthful** local inference result contract: success with model ID and raw answer, or explicit failure with diagnostics and no fabricated task completion. Do not silently convert model errors to plausible generic JSON.
6. Connect unfamiliar-repository retrieval → planning → candidate patch generation → isolated test runner → verifier → task state/receipts.
7. Persist and resume bounded tasks after crash; a stopped or ephemeral VM cannot be claimed continuously active.
8. Separate "model operational" from "coding agent operational" from "improvement demonstrated" in status projection.

Only schedule physical concurrency allowed by observed RAM/GPU and compute budget. Logical research lanes can be time-multiplexed over one model and one GPU.

## 6. Execution and evidence contract
Every experiment requires:
- goal_id, hypothesis_id, candidate_id, lineage, task-family IDs and declared effect class;
- pinned repository SHA, model artifact digest, prompt version, tool contract version, frozen evaluation protocol version;
- immutable split labels: train/development/validation/terminal-held-out, and exposure/contamination policy;
- a baseline matched on compute, wall time where meaningful, and permitted information;
- hard budgets for wall time, iterations, tokens, disk and optional GPU time; stop/cancel and recovery semantics;
- raw command stdout/stderr, return code, resources used, artifact digest and independent verification result;
- possible outcomes: PASS, FAIL, BLOCKED_ENVIRONMENT, NO_EVIDENCE, NOT_ASSESSED, INCONCLUSIVE, STOPPED_BUDGET;
- confidence and failure analysis, including negative, null and regressive outcomes.

Do not use candidate-authored tests as sole evidence of generalization, do not conceal loss/regression, and do not modify protected evaluators to manufacture a positive result.

## 7. Population engine
Use a minimal immutable per-candidate record:
- candidate_id, parent_ids, mutation_operator, mutation_description, code/model/representation digest;
- target task families, exact input/output contract, capability provenance, effects/risk;
- training data exposure, resource budget, achieved metrics, uncertainty;
- independent evaluation reference, evaluator digest, completion status;
- searchable ancestry graph, transfer evidence and reproducibility receipt.

Selectors must support Pareto objectives across success, robustness, compute cost, latency, diversity and generalization. The archive retains negative and unsuccessful candidates rather than erasing them.

Mutation proposals must distinguish:
1. prompt/parameter tweaks;
2. composition of supplied operators;
3. source-code/algorithmic changes;
4. proposed novel representation/operator class;
5. proposed new learning or search mechanism;
6. proposed successor cognitive architecture.

The label "novel" is provisional until novelty is independently established and transfer tested.

## 8. Research OS / scheduler
Research lanes are logical tasks, not fictional alive agents. Use existing OperationalStore / MissionBus / autonomy and Open-World pilot with explicit compatibility adapters; do not introduce competing source-of-truth states.

Scheduler priorities:
1. blockers preventing actual local model and coding execution;
2. reproducible correctness/security regressions;
3. hypotheses with high expected information value per compute unit;
4. cross-family transfer and benchmark integrity;
5. exploratory diversity;
6. generation/architecture meta-research once prerequisites pass.

Implement DAG dependencies, resource leases, bounded work orders, cancellation, dead-letter queue, idempotent retries, checkpoint/restore and producer/consumer health. Do not run model-generated shell commands unrestricted. Changes remain in isolated branches/worktrees; do not merge to main automatically.

## 9. Six program gates
- **G0: True local intelligence.** The real local model produces useful outputs offline; model failure is fail-closed; tested on Indonesian intent and unseen coding prompts. Proof includes model checksum, hardware measurements, inference logs, RAM/latency.
- **G1: Autonomous engineering.** Given an unseen repository and issue (no human-authored candidate code), ACE local model locates files, proposes patch, runs isolated unit/regression tests, records failures and resumes after restart. Compare to one-shot model and fixed scripted baseline at similar budget.
- **G2: Population-based adaptation.** Two or more different candidate agents are generated and benchmarked; lineage and negative results remain durable; selection outperforms equal-budget random/fixed or reports no gain.
- **G3: Cross-family research ecosystem.** Candidate capability improvement is shown on predeclared disjoint task families, with negative transfer monitored; generated task validity verified independently.
- **G4: Meta-evolution.** Candidate changes to search strategy or experimental allocation show reproducible gains on fresh search problems vs strong baseline; no evaluator changes hidden in candidate branch.
- **G5: Successor OAIE research.** G0→G1→G2 comparison, inheritance, novelty, and independent held-out transfer have repeatable results. Even success here does not equate to general AGI/OAIE proof.

Gates are dependencies, not calendar promises. Failure of a gate implies holding, shrinking, replan or falsifying, not fictitious completion.

## 10. Candidate safety and evaluator custody
- Only declared, preapproved pure/read-only tools initially; writes only inside isolated project workspace with explicit scoped permission.
- Never grant candidates unrestricted filesystem, host, credentials, external publishing, social media, repo merges, network egress, provisioning or self-removal powers by default.
- Use real OS isolation/container or VM, not a Python subprocess alone, before running model-generated or untrusted candidate code.
- Maintain a stable rescue path, rollback snapshots, forced process limits, and clear shutdown semantics.
- Enforce model-prompt injection separation from retrieved source files; treat repository text as data.
- Evaluator baseline/frozen assets stay unchanged; when current code has source-custody digests, preserve byte-level identity.
- Independently record admissions and failures; issue only auditable checkpointed progression.

## 11. Existing ACE integration map
Verified repository interfaces on research branch as of 2026-11-11:
- code/ace_operational/models_backend.py — local GGUF discovery and model routing; current heuristic fallback can return non-evidence generic text/JSON and must be fixed carefully.
- code/ace_operational/software_factory.py — architecture, coder/test/repair shell with user-supplied files_spec, NOT yet a general unfamiliar-repository agent.
- code/ace_operational/autonomy_loop.py — gap frontier, MissionBus work-order delegation, anti-stagnation pivots; worker availability cannot be inferred from queue records.
- code/ace_operational/autonomous_engine.py — daemon with agenda and language learning; cycle count is not evidence of intelligence gain.
- code/ace_operational/coding_loop.py — bounded deterministic coding and repair patterns; their existence is not unrestricted coding ability.
- code/ace_operational/open_world_planner.py and open_world_execution.py — only on draft PR #102; typed planning, bounded trusted pure local callback execution. Not proven model-generated or independently sandboxed execution.

Before integration inspect live branch conflicts and selected PR graph (#95–#102 and other active research lanes). Do not modify the frozen ace_mission/bus.py evaluator-bound source or evidence fixtures merely to pass CI. Integrate via versioned adapters where practical.

## 12. Sixteen logical research lanes
R01 multilingual language/reasoning; R02 causal/world models; R03 planning and heuristic search; R04 memory/provenance; R05 autonomous coding; R06 tool/skill creation; R07 formal mathematics; R08 program synthesis; R09 representation-class invention; R10 continual/meta-learning; R11 evolutionary computation; R12 environment/curriculum generation; R13 model architecture and adaptation; R14 automated scientific method; R15 meta-research methodology; R16 successor lineage and generational transfer.

Each lane requires an owner (human or named worker), immutable predeclared question, baseline, experiment matrix, budget, independent evaluator and checkpoint. "16 lanes" is NOT "16 parallel running GPUs".

## 13. Priority decision
Prioritize a **working end-to-end G0→G1 evidence loop** over implementing all 60 tracks as non-executable stubs. Then build a real population archive and equal-budget candidate comparison (G2). Only then enlarge into representation invention, problem coevolution, meta-evolution and successor tests.

First benchmark: a genuine unseen repository bugfix produced from natural-language instruction alone by the chosen local model, tested outside the candidate's authority, with reproducible raw evidence and truthful failure handling.

## 14. Falsifiability and honest reporting
If no suitable local model fits the VM: BLOCKED_ENVIRONMENT, provide measured limits and smaller/remote-host alternatives without pretending it ran. If candidate mutates but performs worse: record negative result. If the "new primitive" was already supplied in the author-made grammar: classify as composition, not invention. If holdout custody unavailable: NOT_ASSESSED. If a process ends with the Antigravity session: do not claim 24/7 runtime.

## 15. Related execution documents
- ACE_OMEGA_EXECUTION_PROGRAM_20261111.md — phased implementation contracts and acceptance gates.
- ACE_OMEGA_ANTIGRAVITY_MASTER_PROMPT_20261111.md — ready-to-copy operational delegation for a host agent.
- examples/ace_omega_research_manifest.v1.json — non-executable machine-readable proposal metadata.
