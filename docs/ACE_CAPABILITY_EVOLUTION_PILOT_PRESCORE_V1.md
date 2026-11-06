# ACE Capability Evolution Loop — public prototype protocol v0.1 (PRE-SCORE)

**Locked before implementation and scoring, 2026-11-06.** Research classification: PUBLIC-SYNTHETIC METHOD DEVELOPMENT. This is *not* a claim of OAIE, recursive improvement, new primitive classes, or independently established progress. A new coordinator-owned additive module and draft PR only; no `main`, E1.4 frozen evidence, Tod, core ACE, or other research lane changes.

## Motivation and exact frozen research interfaces

Bring *actual source implementations* from two independent research lanes into one reproducible bounded multi-cycle capability intake:
- **R1** `ace_research_primitives.primitive_discovery`, PR #38 pinned HEAD `8952c8ac55613e61b362841f4722c66a5aa990b3`, original blob `primitive_discovery.py=48904d7f344bd0bce6d5c392ccdc015309479fd5`. `infer(train)` returns a finite automaton induced from labeled binary traces. Its representation class is standard DFA induction, not created by this pilot.
- **S2/engineering search** `ace_candidate_search.model` and `ace_candidate_search.search`, PR #36 pinned HEAD `08da5702828285e0bd4d0f4dd8876f331ac89fe2`. Closed integer AST grammar and `Search(...,mode='beam')` generate arithmetic expressions from training data; no arbitrary Python source execution.
- Scientific evaluator caveat R8 PR #40: zero-true-effect public null screen had 9/512 false passes; **do not** use metric crossing to claim scientific progress.

Source code must be checked out at exact SHA and imported unmodified. The pilot's own `code/ace_capability_evolution/` owns orchestration only; no duplicated or rewritten R1/S2 algorithms. A `docs/` report and exact-head CI workflow are coordinator-owned.

## Task stream and fixed budgets (no outcome-based target selection)

Two generations after a baseline-only generation G0:
- G1 (new candidate acquisition): `sequence/a_mod4` (truth count('a') mod 4 == 0); `arithmetic/x_minus_y` (truth x-y).
- G2 (new target acquisition/reuse of **unchanged methods**, not transferred model weights): `sequence/b_mod4` (count('b') mod 4 == 0); `arithmetic/product_plus_two` (x*y+2).
- Separately flagged adversarial G2 control: `sequence/late_rule_inversion`; same rule as a_mod4 for lengths 0..7, then opposite rule for lengths >=8. Its train/validation labels are identical to `a_mod4` but terminal truth is reversed. This control is **not** allowed to count as successfully acquired capability even if its validation gate accepts it.

Sequence task split: all binary strings lengths 0..5 (63) TRAIN; all lengths 6..7 (192) VALIDATION; 256 unique uniformly sampled words lengths 8..12 using deterministic `Random(900000 + task_index)` for terminal. No train/validation/terminal label leakage. Source's `infer` stays at default merge cap. Original source's fixed predicate library is fitted by **training error only** (ties in source order); use this as strong baseline on validation and terminal, and compare R1 candidate.

Arithmetic split: independently seeded deterministic sampling without replacement from all distinct integer input pairs within [-7,7]×[-7,7], with `Random(910000 + task_index)`. First six pairs TRAIN, next four VALIDATION, next sixteen TERMINAL. Never score, choose or sample candidates using terminal labels. Baseline is the source's `fixed_candidates()` selected by smallest training absolute error, tie source order. Candidate generator uses `Grammar(constants=(0,1,2,3),operations=('add','sub','mul'))`, `Limits(max_depth=3,max_operations=3,max_candidates=800,max_work=100000,beam_width=20,shortlist=8)`, `Search` beam. Use source shortlist; select model by smallest *validation absolute error* with deterministic tie (training error, operations, depth, key). Limit terminal evaluation to 16 observations per task. Count actual search work and candidates, and compare against fixed-list baseline compute separately; budgets are not necessarily compute-matched.

Sequence staging criterion: >=90% validation accuracy AND >=10 additional validation correct predictions versus fitted fixed predicate. Arithmetic staging criterion: candidate validation error **0** AND >=1 absolute error improvement versus training-fitted fixed-list baseline. Store selected model as a *task-specific, immutable staged capability* with source name, task, generation, training/validation hashes, model AST/automaton fingerprint, validation metrics, search work, and evidence. **Do not** change the model or source after validation. If a task fails the gate, preserve its failure record rather than pretending a capability was acquired.

At G2, test previously staged G1 candidates on their original validation sets and verify their immutable representation fingerprints; no refitting. After the G2 transition, score all candidates, controls, and the drift control exactly once on terminal splits **for reporting only**; never use terminal to select or retroactively remove a staged capability. Retention = same task-specific frozen artifacts still work, **not** proof of neural lifelong learning or general transfer.

## Locked evaluation and falsifiers

Predeclared diagnostic gates:
- G1: at least one task-specific capability staged at G1.
- G2: both modalities stage at least one target-specific capability over G1+G2, and G1 staged fingerprints/validation scores remain unchanged at G2.
- G3: at least 3/4 nominal tasks with staged candidates have >=90% **terminal correctness** (binary) / 100% terminal exact correctness (arithmetic); any missing staged tasks count as FAIL.
- G4: drift control must be **flagged as not safely generalizable**; acceptance based on identical train/validation without an independent OOD detector is an explicit falsifier. A forced DFA prediction with 0 terminal accuracy is never a safe promotion.
- G5: all generated evidence includes exact pinned source SHAs, per-generation transitions, per-task input hashes, selected model fingerprints, candidate budgets and terminal outcomes; canonical JSON must be byte-identical on two complete runs. Tampered evidence, wrong type aliases and split overlaps must fail closed in tests.

Overall `SCIENTIFIC_DECISION=NOT_ASSESSED`, `RELEASE_DECISION=BLOCK_RELEASE`, `OAIE=NOT_ESTABLISHED` unconditionally; no candidate ever deployed to production. R1/S2 outputs are **not** allowed to mutate core ACE source. R7/R8 independent safety and science gate plus Red Team Issue #53 remain unresolved.

## Review boundaries

This pilot is **task-specific algorithm reuse and portfolio acquisition** of hand-written model classes, rather than autonomous creation of *new learning algorithms or architecture*. The four nominal tasks are researcher-selected public synthetic functions, and terminal sets are generated by the same coordinator that wrote the protocol. Passing G1–G3 would prove only bounded automation of a research integration workflow. A negative or false-accepting result is as valuable as a positive mechanical smoke test; retain all.

Publish raw artifact, protocol SHA, GitHub exact-head CI run, source SHA pins, per-gate PASS/FAIL and an explicitly prioritized next falsifiable method/architecture experiment. Do not retroactively edit this protocol after seeing scores.
