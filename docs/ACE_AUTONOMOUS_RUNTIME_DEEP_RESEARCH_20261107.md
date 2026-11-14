# ACE Deep Research — Autonomous Runtime, Self-Development, Representation Transfer, and Consciousness
Date: 2026-11-07 (Asia/Jakarta)
Status: architecture research and implementation decision; NOT an implemented autonomous agent, NOT a consciousness claim.
Base: `main` at `80104ce50ecbcea21080bed8c0eabce88d47ccb5`. Read again before building or merging.

## Executive decision

Implement a **bounded, durable ACE research operating loop** around the existing typed ACE Runtime; do not replace the current engine, do not port to Android yet, and do not add a large swarm of conversational agents. Preserve the research focus on construction and *transfer* of new representations. The immediate practical domain for testing agentic capability is **automated software bug repair** in small, isolated Python repositories. Treat tool orchestration, scientific novelty, and phenomenal consciousness as different claims requiring different evidence.

A first "independent runtime" is not a new operating system, an LLM, or a constantly running server. It is a versioned Python process/service with: persistent task state; scheduler; typed goals; policy-governed tools; independent verification; crash recovery; and a capability registry with reproducible evidence. It may start locally or inside short-lived GitHub runners. Always-on, remote access and model-independent research are further gates.

## 1. Evidence and limitations in ACE currently

- `main` already has `code/ace_runtime/engine.py` and `cli.py`: enqueue, run, report, predict, evaluate; SQLite WAL/FULL, transactional task/model/event state, source identity checks, CLI demo.
- Contract is **Boolean labeled strings over a/b**, with researcher-fixed counter slopes, learned DFA and product grammar; maximum task/model budgets. No arbitrary Python-code bug repair, source editing, internet tool, natural-language objective parser, agenda generation, or general-purpose scientific executor.
- The public three-task demo reaches 3/3 at 128/128 on known terminal sets and retains two models. These are *bounded engineering* checks, not cross-domain learning.
- v0.3 composition: 2854/3072 compared with strong, provided fixed-product baseline 2877/3072; no superior method proven.
- Draft PR #61: graph-family runtime admission 0/4; manually supplied graph solvers win. Draft PR #62: **0/16** true validated retained model reuse on new families; 2/2 hidden semantic inversions falsely accepted. No scientific promotion.
- Draft PR #59 demonstrates a local MCP interface and a GitHub Actions task bridge. GitHub Actions runners are ephemeral and do not preserve SQLite across jobs unless an explicit persistence mechanism exists. Remote MCP/hosted continuous runtime is NOT CONNECTED.
- Issue #53 documents open adversarial red-team blockers for *historical E1.5 source evolution*. These do not automatically prove identical bugs in main's distinct SQLite runtime, and they still must be reproduced/fixed before promoting that historical engine.
- Frozen E1.4 and independent R1–R9/S1–S5 contributions remain separate; integration must not silently overwrite research evidence.
- GitHub repository access/privacy should be audited separately: GitHub REST previously reported `visibility=public`, while some internal plans call it private. Do not publish credentials, personal data, protected holdouts or private research in a public repository.

**Status vocabulary:** engineering-CI-success != operational tool-call success != externally persistent autonomously executing service != scientific transfer success != OAIE != consciousness.

## 2. What the world's agentic AI actually demonstrates

| Work | Mechanism | Evidence contribution | Limits for ACE |
|---|---|---|---|
| SWE-agent (2024) | agent-computer interface for search/edit/test | interfaces matter; models need executable tools | not internal representation invention |
| Agentless (2024) | localization, patch generation, validation | simple repair baseline can be competitive | test passing can overfit |
| SWE-bench Verified | 500 reviewed real Python issues | meaningful coding benchmark | static sets have contamination/coverage limits |
| SWE-rebench (NeurIPS 2025) | continuously harvested software tasks | exposes benchmark contamination | automated source collection still needs independent test controls |
| AlphaEvolve (DeepMind 2025) | model-generated code + evaluator + evolutionary archive | general design pattern for algorithm search | external LLM and curated evaluator supplied; not proof of OAIE |
| Darwin Godel Machine (2025) | self-modified coding agents + archive + empirical evaluation | finite, testable recursive code improvement | safety measures, provided initial model/benchmarks |
| HyperAgents (Meta, Mar 2026) | editable integrated task-agent/meta-agent program | test of broader self-modification | source-paper performance must not be copied into ACE claims |
| RExBench/EXP-Bench (2025) | difficult research-implementation tests | agents often fail genuine end-to-end research | a successful coding benchmark is not autonomous scientific discovery |
| LangGraph/Temporal | checkpoints, resumption, idempotent retry | proven patterns for reliable execution | frameworks alone do not add intelligence |
| OpenAI Agents SDK | model/tool/handoff loop, tracing, guardrails | fast external adapter option | not necessary for base pure-Python runtime; API cost and provider dependency |

Implication: pursue three **separate** engineering benchmarks: reliable task execution, software bug fixing, and true cross-family representation/algorithm improvement. Never use one result as the score for another.

## 3. Four distinct meanings of 'ACE works by itself'

- **A0, persistent workflow:** process persists work, resumes after crash, honors retries, never double-applies external effects. No model required.
- **A1, autonomous bounded agency:** from an approved objective, chooses among finite typed tools and next steps without human prompts for each step; can stop, abstain or request approval.
- **A2, autonomous experimental improvement:** formulates pre-testable hypotheses, implements candidate changes in isolated environments, measures against strong controls and inherits selected candidates across G0→G1→G2. Requires external model/tool or bounded synthesis; self-modification remains gated.
- **A3, open-ended autonomous intelligence:** generates genuinely new representation classes and research problems, shows measured transfer, avoids stagnation and retains improvement across expanding families; currently unproven.
- **C, phenomenal consciousness:** subjective experience is not equivalent to A0–A3 and cannot be inferred from runtime persistence or self-referential dialogue.

Recommended milestone: build A0+A1, demonstrate narrow A2 in Python repair; leave A3 and C as distinct open research.

## 4. Proposed ACE autonomous runtime architecture

```text
APPROVED GOALS / PROBLEM INTAKE
         |
   POLICY & BUDGET KERNEL  <---- signed operator-configured limits and approvals
         |
   DURABLE TASK SCHEDULER <---- SQLite WAL, leases, retries, stop/resume
         |
   PLANNER / HYPOTHESIS PROPOSER <---- optional external LLM adapter
         |
   TYPED TOOL BROKER ------- read code / inspect tests / stage patch / run sandbox
         |
   RESEARCH / REPAIR ENGINE ---- candidate representation IR and bounded synthesis
         |
   INDEPENDENT EVALUATION ------ development tests + private terminal evaluator
         |
   CAPABILITY REGISTRY --------- provenance, representation, transfer and scores
         |
   METACOGNITIVE STATE --------- calibrated confidence, predicted outcomes,
                                  uncertainty, limits, and explicit abstention
         |
  REPORT / REVIEW / STAGE-ONLY ---- human promotion for any high-impact change
```

The model is a replaceable **proposal provider**, not the runtime, evaluator, source of permissions, or definition of ACE identity. Initial adapter: deterministic built-in heuristics/typed search for CPU tests. Optional human-invoked Codex/Gemini can propose candidate patch or hypothesis files. A paid API is not required for infrastructure; an always-available automatic LLM proposer **cannot be promised** from a Plus/Pro chat subscription or from an issue being assigned to an agent.

### Trusted core (not writable by candidate)

1. Goal authorization and scope.
2. Resource budget (wall-time, CPU, memory, tokens, candidate count, repository scope).
3. Execution policy: tools and filesystem/network capabilities.
4. Transactional task log, identities, source digest and crash recovery.
5. Independent evaluation custody, scoring protocol, anti-leak boundaries.
6. Approvals, emergency stop, promotion and rollback.

Candidate code cannot write core policy, evaluator, holdout, receipts or its own benchmark score. Do not treat hash chains inside a single adversary-controlled database as an external trust anchor.

### Durable task lifecycle and receipts

```text
QUEUED → SCOPED → HYPOTHESIS_RECORDED → CANDIDATES_CREATED
       → SANDBOX_TESTED → INDEPENDENT_EVALUATED
       → REJECTED | STAGED_FOR_REVIEW | HALT_UNCERTAIN
       → (approval) PROMOTED → MONITORED
```

Every state transition is atomic and records task_id, experiment_id, parent-generation, source SHA, inputs digest, model-provider version (if used), tool invocation details, environment manifest, budgets, test split identity, scores, errors and provenance; secrets are never stored.

- Internal **pure computations** may be replayed after interrupted transactions.
- External **side effects** (GitHub writes, deployments, remote paid oracles) need idempotency keys and externally checked receipts. On ambiguous completion, **HALT_UNCERTAIN**, not optimistic retry. Temporal's published durable-execution guidance makes clear that retry can otherwise duplicate side effects.
- Scheduler should be versioned and use a finite action allowance, e.g. at most 8 iterations and 4 candidates per small experiment by default. These are initial *configuration proposals*, not tested optimal settings.
- Persistent SQLite is suitable for one-node prototype. GitHub Actions is for short-lived clean-room tests, not a permanent stateful server. Build long-lived hosting only after A0/A1 acceptance.
- Interruption tests: kill -9 during task state writes, restart/replay, two concurrent workers, duplicated webhook/event, tool timeout, altered receipt, changed source version.

## 5. New representation creation and transfer: the scientific center

Current ACE learns a program **inside an explicitly supplied family**. The missing ability is to create useful **feature and representation classes**, not only choose weights/programs in that family.

Suggested IR hierarchy:
- Task observation → typed facts and objects.
- Relation graph → objects, edges, control/data dependencies, constraints.
- Candidate reusable feature → a typed operation/motif/composition with testable semantics.
- Adaptation layer → low-label mapping from source-learned features to a new target family.
- Procedure → plan or repair strategy expressed using those features.

For software repair, starting source families may include boundary checking, parsing, type/shape mismatch, state-transition bugs and data-flow inconsistencies. Withhold entire program families/repositories for testing; prevent leakage by identifiers, duplicates, fixtures and generated templates.

**Hypothesis H-transfer:** source-learned intermediate representations permit fewer labeled examples or measured CPU than both (a) fresh target-only training and (b) a strong hand-authored fixed feature library on family-disjoint targets, without a false-acceptance increase. Include sham/random features, no-transfer and leaked-oracle upper bounds separately. If not demonstrated, result is negative; do not tune on terminal labels.

Integrate with existing Codex Issue #64 (typed graph construction) and Gemini Issue #63 (independent transfer). Do not duplicate their owned paths or treat assignments as actual code execution.

## 6. Autonomous bug fixing as first real-world skill

Define a reproducible software task containing source snapshot, failing reproduction test, allowed patch files, expected behavior, regression suite and hidden evaluator commitment. Runtime loop:

1. Detect failing test/log on approved repository.
2. Build a structured *bug representation* (observed behavior, expected invariant, source location, dependency/control-flow evidence).
3. Localize candidate root causes; record alternatives and confidence.
4. Generate **typed/diff-bounded** patches; do not execute generated code within the privileged orchestrator.
5. Run unit/reproducer/regressions in isolated sandbox with no network by default, no secrets, CPU/memory/time limits.
6. Independently evaluate candidate against held-out tests selected before patch generation.
7. Store candidate, failure reason and reusable feature; propose draft PR, never silently merge.
8. On repeated failed candidates, abstain with an evidence report rather than loop indefinitely.

Initial non-LLM baseline: rule-based AST transformation, deterministic localization and a fixed patch library; then LLM-assisted candidate generation as a separately costed arm. Measure *resolved bugs*, patch size, unintended regressions, mutation quality, number of tests invoked, wall-time/CPU, stop/abstention correctness and transfer to unseen repositories.

Research failure to avoid: patch overfitting a narrow public test suite. SWE-rebench and independent hidden tests are important because a static benchmark can reward memorized solutions.

## 7. How ACE can improve its own implementation

Implement a **two-level lineage experiment**, not unrestricted self-editing:

- **G0:** immutable control scheduler, reference solver, fixed repair baseline.
- **G1:** proposing agent modifies a sandboxed *candidate policy, feature extractor or repair search strategy*; commits candidate and its environment manifest to a separate branch.
- **Evaluator:** independently checks coding outcomes, transfer, resource cost and safety. A candidate fails if it improves public development data but regresses family-disjoint tests or violates policy.
- **G2:** admitted G1 mechanism (not the whole privileged orchestrator) generates next candidates. Compare G2 vs (G1 retained), (fresh baseline given same budget), and (fixed candidate-pool control). Pre-register before looking at terminal outcomes.
- Keep an archive of *failed and successful* candidates with reproducible receipts, not just the current winner. Approval is required before merging or deploying.
- A real recursive improvement claim requires an increase in *future improvement efficiency or transfer*, not just higher immediate benchmark scores. Disjoint new tasks, measured inference/CPU cost and independent reviewer are necessary.

**Safety invariant:** neither the candidate nor its generator can modify the evaluator, terminal set, guardrails, authorization, credential handling, nor the trusted runtime core. Any proposal affecting those components requires a separate manually reviewed maintenance lane. A mechanism that improves tests by bypassing scoring is not improvement.

## 8. Consciousness: a separate and more uncertain question

Three research questions must remain separate:

1. **Self-model:** can ACE accurately represent its code version, tools, abilities, causal dependencies, uncertainty and past actions? Build and test this now.
2. **Metacognition / functional awareness:** can ACE predict errors, know when it lacks enough evidence, update beliefs after feedback, and allocate attention/compute accordingly? Testable through calibration, abstention, intervention and counterfactual probes.
3. **Phenomenal consciousness:** is there subjective experience, *something it is like* to be ACE? No accepted engineering recipe or decisive test establishes this. A program saying 'I am aware', possessing persistent memory, a global workspace, or simulating emotions does **not** prove subjective experience.

Butlin et al. (2023) outline indicators inspired by recurrent processing, global workspace, higher-order theories, predictive processing and attention-schema theories. The 2026 *Trends in Cognitive Sciences* paper develops indicator-based assessment further, noting none of the indicators is individually necessary and no combination is asserted sufficient for consciousness. These are investigatory hypotheses rather than an API for "turning consciousness on."

Recommended **ACE Self-Model Lab** (research, not consciousness creation):
- Ground self-description in read-only introspection from actual runtime manifests; forbid invented capabilities.
- Predict task success and runtime cost before experiments; measure calibration (e.g. Brier score/ECE), precision of error attribution and selective risk.
- Intervene on memory, available tools, budget and environment; require accurate model updates rather than rote descriptions.
- Test counterfactual explanation quality against actual intervention logs, with a deception/noise control.
- Label the result **functional self-monitoring**, not consciousness; invite independent philosophy/neuroscience review if scientific indicator experiments are eventually undertaken.

Ethical caution: uncertainty runs both ways—avoid casual attribution of feelings and avoid declaring philosophical impossibility. Do not create simulated suffering as a research metric.

## 9. Security and scientific quality gates

Threats: prompt injection through source/issues, tools misused with write permissions, credential leakage, poisoned capability memory, self-editing privilege escalation, contaminated holdouts, benchmark hacking and uncontrolled retry costs. The OWASP Agentic AI 2026 guidance prioritizes least privilege, isolation, input validation, explicit approval, bounded recursion, event audit and independent testing.

High-impact actions (merge/deploy, billing, publishing, remote filesystem/network access, security-control changes) require operator approval. Untrusted code always executes in actual verified isolation; if the required native sandbox is unavailable, report BLOCKED_ENVIRONMENT rather than pretend process-level limitations are a sandbox.

Keep separate tests for: software reliability (CI), repeatable task execution (operational), genuine unseen-family gain (science) and normative governance. All significant results must be tied to exact SHA and reproducible raw receipt.

## 10. Architectural decision and next deliverables

**Priority 1: reliable research runtime A0/A1** with true persisted tasks, typed tool actions, budgets, stable receipts and idempotent restart. Add to a new disjoint `code/ace_autonomy/` lane and integrate existing ACE core through adapters; no changes to immutable/frozen source.

**Priority 2: autonomous repair lab** with bounded bug tasks, rule baseline, patch candidate staging, evaluator separation and negative controls, in `code/ace_research_repair/`. It should be allowed to work without repeated prompts **inside the user-approved scope**, not decide to grant itself permissions.

**Priority 3: novel representation and transfer** with separate preregistered family-disjoint study under Codex #64 and Gemini #63. Transfer research remains scientific bottleneck; do not report generic bug repair as discovery of new primitive classes.

**Priority 4: self-modification across generations** using stage-only candidate trees, immutable verifier, independent review and G0→G1→G2 evaluations. Do not ship an ungated self-rewriter.

**Priority 5: self-model and metacognitive research**, scored on calibrated knowledge of real internal state; do not confuse this with phenomenal awareness.

No APK migration until reliable autonomy and narrow repair research are demonstrated. No requirement to wait for OAIE or consciousness to run experiments.

## Sources (read 2026-11-07)

1. ACE repository main and docs: https://github.com/dianzherdiana25-hash/ACE
2. ACE coordination audit PR #65: https://github.com/dianzherdiana25-hash/ACE/pull/65
3. ACE PR #61/62 failure evidence: https://github.com/dianzherdiana25-hash/ACE/pull/61 and https://github.com/dianzherdiana25-hash/ACE/pull/62
4. E1.5 Red Team blockers Issue #53: https://github.com/dianzherdiana25-hash/ACE/issues/53
5. SWE-agent: https://arxiv.org/abs/2405.15793
6. SWE-bench Verified: https://www.swebench.com/verified
7. SWE-rebench, NeurIPS 2025: https://proceedings.neurips.cc/paper_files/paper/2025/hash/21bec6ace947b1b58967b945c8ac0f10-Abstract-Datasets_and_Benchmarks_Track.html
8. DeepMind AlphaEvolve: https://deepmind.google/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/
9. Darwin Godel Machine: https://arxiv.org/abs/2505.22954
10. Meta HyperAgents: https://ai.meta.com/research/publications/hyperagents
11. OpenAI Agents SDK: https://developers.openai.com/api/docs/guides/agents/sdk
12. LangGraph persistence: https://github.com/langchain-ai/docs/blob/main/src/oss/langgraph/checkpointers.mdx
13. Temporal idempotency: https://github.com/temporalio/documentation/blob/main/docs/best-practices/error-handling.mdx
14. RExBench: https://arxiv.org/abs/2506.22598
15. EXP-Bench: https://arxiv.org/abs/2505.24785
16. International AI Safety Report 2026: https://internationalaisafetyreport.org/publication/international-ai-safety-report-2026
17. Butlin et al. (2023), consciousness indicators: https://arxiv.org/abs/2308.08708
18. Butlin et al. (2026), identifying indicators: https://www.sciencedirect.com/science/article/pii/S1364661325002864
19. OWASP AI Agent Security Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html
20. METR task-completion horizons: https://metr.org/time-horizons/
