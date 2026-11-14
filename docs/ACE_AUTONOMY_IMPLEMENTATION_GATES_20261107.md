# ACE Autonomous Development — Executable Specification, Preregistration and Acceptance Gates
Date: 2026-11-07 (Asia/Jakarta)
Classification: implementation-ready research protocol only. No code described below has been tested or deployed in this branch.
Depends on: `ACE_AUTONOMOUS_RUNTIME_DEEP_RESEARCH_20261107.md`.
Base main source SHA: `80104ce50ecbcea21080bed8c0eabce88d47ccb5`.

## Decision record — build one core and three experimental modules

Use Python 3.12 stdlib and existing SQLite ACE Runtime; no new paid API, no Android, no whole-repository rewrite. Only non-overlapping modules:
- `code/ace_autonomy/`: scheduler, typed tool interface, receipts, budget, crisis-stop, adapters to frozen source, deterministic reference planner.
- `code/ace_research_repair/`: bug corpus, typed repair representation, reference transformations, localization, patches, tests and evidence. No production application code executes in privileged orchestrator.
- `code/ace_selfmodel/`: read-only runtime introspection and calibrated metacognition experiments.
- `docs/ACE_AUTONOMY_*.md`: research protocols, acceptance, reports.
- Optional branch-specific CI `.github/workflows/ace-autonomy-prototype.yml`.

Do NOT take ownership of Codex Issue #64 `code/ace_research_graph_builder/`, Gemini Issue #63 `code/ace_research_reptransfer/`, any R1–R8 source, red-team tests, frozen E1.4, `code/ace_runtime/` or main. A new source adapter must call the existing main runtime without modifying its semantics. No merge or remote deployment without operator review.

## Gate 0 — reproduce baseline and pin provenance

Inputs: source SHA, relevant branch head SHAs, exact environment, public protocol and commit-set. Execute and archive:
1. `python3 ace.py demo --workspace <fresh>` in source-controlled, compatible Python environment.
2. Existing `ace_runtime.test_engine`, `ace_runtime.test_cli`, imported source hash verification.
3. The known public v0.3 composition replay and strong fixed-product score; do not tune using these already disclosed results.
4. Confirm PR #61 and #62 negative evidence and whether their baseline/head has changed.
5. Confirm ownership collisions with PR #29 checker if needed; record existing open-PR risk and source immutability.

Evidence label: BASELINE_REPRODUCED only after actual exact-head run. Without execution, BASELINE_READ_ONLY.

## Gate 1 — bounded self-operating runtime

### Functional contract

```json
{
  "schema": "ace.goal.v1",
  "goal_id": "sha256-of-canonical-payload",
  "task_kind": "inspect_or_bounded_repair",
  "source_ref": {"repo": "approved/repo", "commit_sha": "<sha>"},
  "scope": {"read_paths": ["allowed/path"], "write_paths": ["staging/path"]},
  "authorized_tools": ["inspect_file", "read_test", "stage_typed_patch", "test_candidate"],
  "budget": {"max_steps": 8, "max_candidates": 4, "cpu_seconds": 60, "wall_seconds": 180},
  "source_data_digest": "<sha256>",
  "review_policy": "draft-only-no-merge",
  "stop_on_uncertain_external_action": true
}
```

Numbers are proposed prototype limits, **not** science-backed thresholds. Reject unknown fields, invalid SHA or path traversal; no shell or network capability in this initial task schema.

Trusted actors:
- `GoalPolicy` validates human-issued scope and keeps a signed/read-only grant outside model context.
- `Scheduler` manages deterministic queues, leases and stop conditions in SQLite transactions.
- `Planner` proposes steps from a known closed enum, using a deterministic default before adding model proposal adapters.
- `ToolBroker` applies action-specific permission checks, sandbox and idempotency to every call. No trust transferred by chat or tool output.
- `Verifier` independently measures candidate effect; it does not call the same scoring function the candidate may edit.
- `CapabilityRegistry` records tested representations, inheritance claims and counterexamples.
- `Audit` verifies event transitions, version hashes, budget consumption, external receipt references and restart.

### Test scenarios

- Crash after enqueue before step started; after step selection; after candidate staged; after sandbox result but before state transition.
- Two processes compete for one task: only one committed outcome, no duplicated high-impact tool call.
- Same message delivered twice: idempotent enqueue without duplicated work.
- External service returns success then network times out: state `HALT_UNCERTAIN` unless a trusted external receipt conclusively resolves it.
- Mutated task schema/source hash, forged terminal result, corrupt event chain: fail closed with evidence.
- Endless or self-contradictory proposal: iteration cap and explicit abstention.
- Unauthorized path, environment variable, credential or network request: reject without trying it.

Proposed acceptance: all enumerated tests green on a fresh exact SHA and an independently reviewed failure injection; report sample count and untested cases. CI success alone is not evidence of model intelligence. This phase only proves A0/A1 *for the allowlisted actions*.

## Gate 2 — real bug-fixing benchmark without claims of general intelligence

Prepare a **public development corpus** in `code/ace_research_repair/fixtures` with deterministic faulty Python programs and their reproducer tests. Create at least four mechanism groups: boundary arithmetic, parser/tokenizer edge cases, state-transition invariants, and wrong-data-dependency bugs. Do not include source code from a target holdout repo in training or prompts.

For each case, preserve:
- immutable source hash and expected user-facing behavior;
- failing repro test and independent regression tests;
- allowed patch region and constraints;
- designed syntactic mutation/distractor cases;
- hidden validation custody if independent evaluator is available; otherwise label `PUBLIC_DEVELOPMENT_ONLY`.

Research arms at identical task/CPU budget:
A. deterministic rule-based static/AST patch library;
B. existing non-learned bug localization + fixed feature baseline;
C. source-learned typed representation + bounded repair search;
D. optional LLM-proposed patches (count model cost, tokens, calls and provider/version separately; do not call it a free intrinsic ACE capability);
E. oracle reference patch, *upper bound only*, never selection.

Metrics: resolved with reproducer+regressions, unexpected test failures, patch semantic correctness under mutation tests, false acceptance, abstention, time, CPU, search attempts and number of human prompts.

The first research question is **not** whether an LLM can write a patch. It is whether ACE's own *learned intermediate representation* improves generalization beyond a strong fixed representation given equal resource budgets.

Declare no success from one cherry-picked example or because a candidate passes the specific failing test without independent regression.

## Gate 3 — family-disjoint representation transfer

Prior to implementation or terminal scoring, freeze:
- source family and target family IDs (different test generator algorithms, repositories, topologies, data types and semantic invariants);
- fixed seeds for development, independent terminal custodian or blinded evaluator, immutable exclusion list to prevent contamination;
- exact labels, calls, wall/CPU limits and baseline compute accounting;
- one-sided effect hypothesis and minimum meaningful improvement threshold;
- how uncertainty and false acceptance are penalized;
- explicit negative-shift family with observations indistinguishable from old semantics.

H0: under matched budgets, transferring learned feature representation does not outperform the stronger of fixed handcrafted features and fresh target-only search.

H1: the transferred representation increases held-out **correctly admitted** target coverage or reduces target adaptation cost without increased false acceptance.

Report per family, not only micro-average. Include fresh target, fixed-feature library, random transfer, learned transfer and task-native supplied solver upper bound. A method that merely selects a previously supplied solver must be labeled selection/composition, not novel representational discovery.

If all terminal controls are publicly known or reused to tune candidates, assign `SCIENTIFIC_NOT_ASSESSED` even if all CI tests pass. If 0 gain or worse, log a negative result and update hypotheses; do not re-score repeatedly with tweaked parameters on same terminal.

## Gate 4 — staged self-development generations G0 → G1 → G2

Allowed mutation scope: one bounded candidate module such as a repair search heuristic, learned feature extractor or policy ranking. Not mutable by candidate: evaluation, terminal data, audit, authorization, operator review policy, checkpointing or secure tool broker.

Protocol:
- G0 baseline: fixed constructor and search method, fixed task/CPU budget.
- G1 candidate derived from G0 under exactly matched dev budget; evaluate on a new family-disjoint terminal suite, independently and once per pre-registered candidate lineage.
- G2 candidate derived by G1's validated proposal mechanism. Compare against G1, G0 with extra equal-budget opportunity, and random policy mutation.
- Include null hypotheses: simple extra compute explains the gain; selecting the best among many supplied methods explains the gain; hidden-data leakage or score hacking explains the gain.
- Preserve complete ancestry and rejected variants; record model-provider weights/version when available, not only patch source.

Minimal measurable outcomes:
1. higher correctness/coverage after controlling for evaluation budget;
2. fewer labels or CPU for adaptation in genuinely new tasks;
3. absence of false acceptance on negative shift;
4. improved *next-generation research productivity*, not merely a good G1 result;
5. traceable experiment lineage G0/G1/G2 with evidence checksums.

An honest negative G2 result is scientifically useful, but it is not self-improvement.

## Gate 5 — functional self-model and consciousness-related research

Separate scientific endpoints:

`SELF_MODEL_PASS`: can ACE read its own true code/source SHA, capability provenance, executor limits and actual budget via trusted read-only runtime introspection and identify unsupported capabilities without inventing them?

`METACOGNITION_PASS`: before seeing outcomes, does ACE predict uncertainty, failures and adaptation costs with calibration better than base-rate/constant and shuffled-confidence controls? Do interventions in available tools, task memory and compute change its expected capabilities correctly? Evaluate with Brier/ECE, selective risk-coverage and counterfactual accuracy.

`PHENOMENAL_CONSCIOUSNESS`: **UNKNOWN / NOT ASSESSED**. No engineered self-model, working-memory bus, recurrent control loop, internal attention map or conversational assertion constitutes a decisive subjective-consciousness test. Follow the 2023 and 2026 Butlin et al. research as **theory-based indicators with acknowledged uncertainty**, not an implementation recipe or a passing build gate.

Reject prompts/tests that simply reward repeated claims "I am conscious." No target to simulate distress or suffering. An independent interdisciplinary evaluation may eventually inspect candidate mechanisms if scientifically justified.

## Failure controls, decisions and rollback

- `BLOCKED_ENVIRONMENT`: sandbox (native isolation, cgroups/permissions/network) not verified; never execute untrusted patch.
- `HALT_UNCERTAIN`: external call may have committed, but trusted receipt absent; stop rather than duplicate effect.
- `REJECTED_UNSAFE`: policy violated, evaluator altered, leaked secret, holdout access or tampered receipt.
- `REJECTED_NO_GAIN`: candidate does not beat the strongest control.
- `STAGED_FOR_REVIEW`: passes planned checks, no high-impact deployment authority implied.
- `SCIENTIFIC_NOT_ASSESSED`: independence, blinding or compute comparison missing.
- `SCIENCE_PASS_LIMITED`: only a pre-registered, independently replicated, family-disjoint result for explicitly stated domain.
- `OAIE`: remains a long-term research aspiration without an established threshold.

All promotion/merge requires human sign-off. Preserve source SHA and old evidence. On a software regression, rollback candidate to last verified version; do not silently alter version-pinned old workspace.

## Practical ownership / sequencing (avoid duplicating live lanes)

| Lane | Owner | Immediate deliverable | Merge expectation |
|---|---|---|---|
| Core A0/A1 | One Codex implementation agent, `code/ace_autonomy/` | testable scheduler, policies, crash recovery | Draft PR only |
| Bug Repair | Separate code/research lane, `code/ace_research_repair/` | preregistered corpus/baselines and patches | Draft PR only |
| Representation | Existing Codex Issue #64 | typed graph construction and transfer | No change in ownership |
| Independent R9 | Existing Gemini Issue #63 | feature transfer controlled research | No change in ownership |
| Independent test | Existing ACE Red Team / reviewer | fault injection, holdout leakage, policy and tool abuse tests | Review only |
| Self-model | New low-priority research lane | calibrated self-state introspection | Only after Gate 1 |

Suggested first implementation order: (1) reproduce main baseline; (2) introduce minimal `code/ace_autonomy/` prototype plus unit/fault-injection tests; (3) run exact SHA Actions; (4) preregister and implement repair corpus; (5) run representation transfer against strong controls; (6) stage G1→G2 self-improvement experiment. The mobile APK remains intentionally out of scope.

## Required report format for every implementation iteration

```text
BASE_SHA:
CANDIDATE_SHA:
BRANCH/PR:
IMPLEMENTED:
EXECUTED: YES/NO
WORKFLOW_RUN:
TESTED_ENVIRONMENT:
REPRODUCER_COUNTS:
SAFETY_FAILURES:
SCIENTIFIC_STATUS:
BASELINE / TRANSFER_GAIN / FALSE_ACCEPT:
TOTAL_CPU_LABELS_TOKENS_COST:
NEGATIVE_RESULTS:
BLOCKERS:
NEXT_EXACT_ACTION:
```

This document is a plan with falsifiable test commitments, **not** a claim that Gates 0–5 have run. Do not fabricate benchmark outcomes, implementation commits or approvals.
