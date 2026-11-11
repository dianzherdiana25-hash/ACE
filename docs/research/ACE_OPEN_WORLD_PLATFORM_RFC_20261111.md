# ACE Open-World Platform RFC (11 November 2026)

**Repository:** dianzherdiana25-hash/ACE  
**Base SHA:** 9ac1ac5ed328a4382f29f622a8e12109c5b4af30  
**Track:** isolated research prototype; DO NOT merge or deploy automatically  
**Scientific outcome:** NOT_ASSESSED; OAIE_NOT_ESTABLISHED

## 1. Decision and scope

ACE is a platform for **open-ended autonomous capability evolution**, not an
Android application or a collection of predetermined demo scripts. Android,
Termux, single-PC deployment, cloud VMs, GPUs, HPC clusters and remote worker
pools are OPTIONAL execution environments. No one environment defines the
cognitive architecture, the task schema, or the research scope.

"Unlimited" describes **extensible scope**, not infinite compute, infinite
knowledge, unrestricted actions or guaranteed AGI. Domains, models, modalities,
skills, tools, research questions, and successor architectures must be
discoverable and addable without patching a hard-coded list. Each individual run
still needs finite budgets, permissions, data boundaries and verifiable outcomes.

The existing charter's OAIE target is retained. This RFC does NOT claim
consciousness, AGI, ASI, self-directed AGI training, independent reasoning,
scientific discovery, or safe self-rewriting has been achieved.

## 2. Target system: open-world capability substrate

The target is a coordinated **system of replaceable components**, rather than
one enormous prompt or daemon:

1. **Intake and goal grounding:** multilingual conversations, formal specs,
   images/audio/structured inputs, user edits and uncertainty tracking.
2. **Cognitive executive:** agenda, decomposition, competing plans, world state,
   credit assignment, metacognition, critic, retry, abandonment and replanning.
3. **Typed capability graph:** arbitrary input/output type names, interface
   versions, provenance, preconditions, provider, effect class, cost estimate,
   evidence status and failure history. Absence of a capability creates a gap,
   not a fabricated result.
4. **Model fabric:** heterogeneous local/remote/hosted models, symbolic solvers,
   optimizers, theorem provers and scientific tools. Routing based on observed
   reliability, privacy, latency and compute cost; no single-vendor lock-in.
5. **Tool and agent fabric:** local Python/subprocess tools; MCP-compatible tool
   adapters; A2A-compatible task exchange; authenticated distributed workers,
   queues, leases, at-least-once delivery and idempotent receipts.
6. **Memory and knowledge:** working memory, episodic task traces, reusable
   procedural skills, semantic knowledge, provenance graphs, confidence and
   revision/forgetting policy. Separate claims from evidence and outcomes.
7. **Software engineering factory:** repository comprehension, issue analysis,
   code synthesis, isolated execution, regression, patch verification, PRs,
   controlled promotion, and rollback.
8. **Scientific method engine:** literature discovery, falsifiable hypotheses,
   preregistration, budget-controlled experiments, strong baselines, negative
   controls, independent evaluator and reproducible results.
9. **Representation and algorithm evolution:** typed program invention,
   compositional/structural search, representation-class proposals, method
   invention, transfer to withheld task families, retention G0->G1->G2.
10. **Governance and observability:** least-privilege authority, consent for
    external effects, audit logs, signed/independently custodied receipts where
    possible, transparent failure states and incident recovery.

### Deployment topology

A controller can run on Linux, macOS, Windows or a hosted service through
platform-specific adapters. CPU/GPU/cluster workers, storage, and providers are
separate resources. The controller MUST NOT assume Android paths, Termux
environment variables, one private home directory, one GPU or permanent uptime.
Portable code should use abstract interfaces and explicit dependency discovery.

MCP and A2A are candidate interoperability targets, **not claims of current
wire compatibility**. Adapt against the official published specifications,
build conformance tests, and verify authentication and version negotiation.

## 3. First implementation in this branch

File: `code/ace_operational/open_world_planner.py`.

The initial pilot is intentionally narrow and functional:

- Register arbitrary named capability contracts with input and output types.
- Represent different provider names without binding them to a device.
- Compose VERIFIED capabilities with nonblank evidence references.
- Select an explicitly bounded minimum-cost plan by uniform-cost search.
- Reject unverified capabilities and disallowed effect classes by default.
- Report NO_PLAN or SEARCH_LIMIT rather than inventing a successful action.
- Perform no code execution, remote network calls or changes to the ACE store.
- Keep domain names open; no static list of acceptable scientific or business
  disciplines is embedded in the planner.

Test file: `code/ace_operational/test_open_world_planner.py`.
The test suite includes heterogeneous scientific chains, a novel registered
domain, cost optimality, forged/empty evidence metadata rejection, external
effects, cycles, search limits and device-neutral provider labels.

**Important limits:** evidence references are string metadata, not independent
attestations; contract type matching is NOT semantic validation; routing is
NOT task execution; no model generates capability contracts; no distributed
scheduler, persistent registry, migration or success criterion is added here.
The pilot must not be promoted to proven autonomous general reasoning.

## 4. Roadmap organized by falsifiable gates

### Gate OW-0: truthful capability substrate
- Add contract schemas, validators and a non-executing planner.
- Compare typed search against a baseline that picks only direct capabilities.
- Assert no false READY results for missing or unverified contracts.
- Preserve existing ACE test suites, source custody, evaluator isolation.

### Gate OW-1: integration into ACE runtime
- Bridge capability registration to OperationalStore and MissionBus using
  migrations, transactional leases, idempotent outbox and versioned receipts.
- Reuse existing gap detection and PIVOT_LADDER; do not create competing state
  authorities.
- Integrate a real executable tool adapter with approval and sandbox gates.
- Forbid promotion from self-reported pass booleans.
- Integration demonstration: new task submitted in natural language, parsed
  into an independently reviewable goal contract, planned, executed, verified
  and resumed after a simulated crash.

### Gate OW-2: open tool/model/agent interoperability
- Implement versioned protocol adapters, dynamic discovery, authentication,
  quota/cost accounting, cancel/resume, error recovery, and security testing.
- Test two genuinely different model providers and a separate worker without
  hand-coding responses or pretending unavailable providers exist.
- Prove no cross-tenant data leak, no tool prompt injection promotion, and
  no external side effects without requisite authorization.

### Gate OW-3: general coding and long-horizon reasoning
- Benchmark on previously unseen repositories and bugs; include full-file
  generation from an instruction alone, not just provided files_spec.
- Compare against one-shot LLM, scripted agent and strong coding-agent
  baselines on quality, tests, resource cost and task success.
- Holdout repository selection and evaluator ownership must be separate from
  candidate implementation.

### Gate OW-4: method discovery and generational transfer
- Preregister tests for a NEW representation class / learning rule that was
  not merely selected from an authored grammar. Record origin and complexity.
- Evaluate across new task families, multiple independent seeds, budgets
  and G0->G1->G2 inheritance, including regressions and negative results.
- If independent blind custody cannot be provided, label NOT_ASSESSED.

## 5. Initial acceptance experiment

**Hypothesis (engineering, not scientific superiority):** A typed,
evidence-gated planner can route arbitrary novel type chains without code
changes and reject unverified or unauthorized actions, while respecting
finite budgets and without executing any actions.

**Development fixtures:** dynamically named examples from astronomy,
genomics and music, a minimum-cost chain, an unverified capability,
metadata without evidence, disallowed external effects and a cycle.
**Baseline:** single-step direct capability selection (no composition).
**Evaluation:** public tests only; no confirmatory holdout. No scientific
claim from a passing unit test. Record exact commit SHA and workflow run.

**Release status:** BLOCK_RELEASE until an independent tool execution boundary,
runtime integration, failure/timeout controls and regression suite pass.

## 6. Priorities after the pilot

Focus on measured end-to-end task success, not file count, inflated capability
registries, fixed examples, "consciousness" labels, or repeated broad prompts.
The earliest meaningful end-to-end benchmark should be:

> Given an unfamiliar repository and a new issue, ACE locates the relevant
> code, proposes and implements a patch on an isolated branch, runs an
> independent test suite, records resources and results, and produces an
> auditable PR without human-supplied candidate code.

If any stage cannot run, ACE reports the missing capability and keeps the
request resumable, instead of claiming completion.

## 7. Non-goals and current authority

No direct merge to main, no overwriting frozen evaluations, no deployments,
no credential collection, no purchases, no unrestricted network or filesystem
mutation, and no autonomous release. The prototype may be reviewed as a draft
PR. Review and merge require an explicit subsequent authorization consistent
with the repository charter.
