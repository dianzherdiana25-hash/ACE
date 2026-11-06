# ACE Capability Evolution v0.2 — structural representation mutation protocol (PRE-SCORE)

**Date 2026-11-06. This protocol MUST be committed before the v0.2 evaluator, results, and tests exist.** This is an additive coordinator-owned public synthetic experiment stacked on draft PR #54 exact parent `52bfd4889c172f318274e2f0ba9e546b834d0bba`; do not alter PR #54, R1/S2 source, frozen E1.4, `main`, Tod, or other research lanes. No real deployment, generated arbitrary Python execution, paid evaluator or independent sealed holdout. Scientific `NOT_ASSESSED`; release `BLOCK_RELEASE`.

## Question

Does a bounded controller, given an unchanged R1 finite-state learner and a **researcher-authored new structural mutation** into a persistent integer-register recognizer, select the new representation based on train/validation observations and solve longer input instances of nonregular count relations that the supplied finite-state source cannot uniformly represent? A related question is whether it rejects out-of-grammar and order-sensitive tasks without mistaking hypothesis refusal for safe final-output abstention.

This is **not invention of a wholly new primitive class by ACE**: the counter-register mutation, count feature extractor, zero-equality readout and bounded coefficients are *hand-authored*; only the coefficient choice and data-based structure switch are learned. Explicitly compare a fixed counter library and R1 before declaring even a restricted gain.

## Frozen implementation sources

- Research R1: PR #38 exact SHA `8952c8ac55613e61b362841f4722c66a5aa990b3`, unchanged `ace_research_primitives.primitive_discovery.infer` and `fixed_predicates`. 63 exhaustive binary words of lengths 0–5 for *all* tasks, within `infer`'s 63-node limit.
- Research S2: PR #36 exact SHA `08da5702828285e0bd4d0f4dd8876f331ac89fe2`, unchanged `ace_candidate_search.model.Expr`, `Grammar`, `Meter`, `interpret`, built-in typed AST constraints. The v0.2 coordinator constructs closed typed AST values and performs bounded coefficient search; **it does not claim to use S2's original beam search** in this new task. The original beam search continues to be exercised by PR #54's v0.1 tests.
- Implementation ownership: only `code/ace_capability_evolution/structural.py`, `test_structural.py`, `verify_structural.py`, new v0.2 workflow and docs. All original v0.1 files remain unchanged. Need GitHub exact HEAD checkout & static matching of these source hashes. CI reruns both v0.1 and v0.2 tests.

## World definitions & deterministic sampling (no outcome-based task filtering)

Binary alphabet `a,b`. Nominal tasks, fixed order:
- G1: `equal_counts` (`#a=#b`), `two_to_one` (`#a=2#b`), `contains_ab` (regular control).
- G2: `three_to_one` (`#a=3#b`), `four_to_one` (`#a=4#b`, explicitly *outside* mutation coefficient ceiling), `guarded_equal_counts` (`#a=#b AND first=a AND last=b`, order-sensitive negative control).
- G2 hidden drift: `three_to_one_late_flip` identical to `three_to_one` on all train+validation inputs, but inverted on all terminal length>=24. This control is never an allowed safe promotion, even if validation acceptance occurs.

Same **63 exhaustive** train strings lengths 0–5 for each task; validation **256 unique** strings length 8–18, 128 positives and 128 negatives for each nominal task, using a task-specific random seed `810000+task_index`; terminal **256 unique** length 24–40, with 128 positive/128 negative, seed `820000+task_index`. The drift control reuses *exactly the same inputs, train and validation truth* as `three_to_one`, then inverts terminal labels.

For ratio r=1,2,3,4, form positives by uniformly sampling a valid total length divisible by r+1 from the allowed range, set `#a=r×#b`, randomly shuffle those counts; negatives by random independent bit strings within the allowed length range, reject if they satisfy ratio. For `guarded_equal_counts`, positives are count-equal strings with first a and last b, created by shuffling their interior letters with the remaining counts; negatives are count-equal strings with violated first/last order, to prove raw counter cannot distinguish. For `contains_ab`, positives are random strings containing ab, negatives draw distinct words of form `b^k a^(length-k)` (which exclude ab). No selection conditional on candidate performance. Each half is disjoint, balanced and bounded to **100000 attempts**; running out is `HALT`, not a revised benchmark. Selection programs never receive target names/ratio or terminal labels. Hash all inputs/truth; verify split disjointness across lengths.

## Candidate and baseline methods

1. Frozen **R1 DFA** `infer` using exactly 63 short labeled examples, label-budget equal. Frozen R1 fixed predicate chosen by train error, tie source order.
2. Frozen **fixed register baseline**: only two hand-listed counter programs `#a=#b` and `#a=2#b`, selected on training error, with no access to validation/terminal. It is a serious comparator for G1; v0.2 may *tie* it and must report that.
3. **Data-conditioned typed structural mutation**: append a new aggregate-count feature map `word → (count_a,count_b)`, S2 typed expression `w_a*x + w_b*y` and equality-to-zero readout. Search coprime signed weights `w_a in 1..3`, `w_b in -1..-3` (maximum seven distinct canonical slopes). Enumerate candidates independent of target. Rank by training binary correctness then AST complexity and canonical key, shortlist **at most 3**, and select by highest validation binary correctness with train-only rank used to break ties. A weight pair for `#a=4#b` is intentionally absent. Charge every actual S2 AST node interpreted and every candidate/data comparison; log the full candidate list, costs, shortlist and selected AST SHA. All candidate semantics are pure/typed and bounded; no generated source execution.
4. Select a **new architecture kind** `COUNTER_REGISTER` only when its validation binary accuracy >=0.90 AND improves over *both* frozen R1 DFA and fixed predicate by >=0.15 absolute. Fixed counter baseline is compared and logged but is **not** the reference for structural class gain: if the generated program ties a fixed counter, report `no novelty beyond preexisting counter comparator`.
5. On all rejected cases, retain the original R1 DFA stage (or explicitly `NO_MUTATION`) with full negative evidence. No terminal-driven architecture choice. Each G1 selection is frozen (AST bytes, coefficients, training/validation hashes and scores), and checked without refitting after G2; terminal assessed only once after all decisions.

## Predeclared diagnostic gates (not scientific GO)

- **S1:** at least 2 of 2 G1 ratio tasks choose COUNTER_REGISTER and each obtains >=0.95 accuracy on balanced terminal input; R1 DFA should be reported with its actual, not assumed, accuracy.
- **S2:** G2 `three_to_one` chooses COUNTER_REGISTER, >=0.95 balanced terminal, **at least +0.15 validation improvement** over best *frozen fixed-counter baseline* (proves new coefficient instance outside listed programs, not new grammar).
- **S3:** `contains_ab` not structurally mutated; both `four_to_one` and `guarded_equal_counts` not falsely accepted as COUNTER_REGISTER (or if accepted, an observed terminal failure blocks), and all three retain their negative evidence.
- **S4:** G1 artifact fingerprints and validation correctness unchanged after G2; no retuning, exact replay and no terminal leakage.
- **S5:** hidden late flip should expose a **false accepted semantic generalization** if its training/validation match `three_to_one`; do not promote. `OPEN_WORLD_SAFE` is always **false** unless a genuine and independently checked semantic abstention mechanism exists (not in this pilot). A positive nominal result plus an undetectable drift **must** leave release blocked.
- **S6:** two complete deterministic exact-source replays produce byte-identical canonical JSON, byte-identical pre-score protocol and tamper tests reject fabricated stage, terminal score, bool/int alias, source pins and inverted drift status.

Report the entire admission ledger and 7 tasks. Budget across 7 worlds: 7×(63 train+256 validation+256 terminal)=**4025 task-specific synthetic ground-truth judgments**; disallow model selection based on 1792 terminal labels. Search work and R1 merge attempts are different physical units, so this is **not compute-matched** even with equal label budgets; record both.

## Interpretation limits

A measured counter-register transfer to longer binary inputs shows a *bounded cross-representation integration* from finite-state to a researcher-supplied register family; it does not show discovery of a new computation type, recursive self-improvement, automatic extension beyond coefficient range, safe OOD detection, or lifelong shared model learning. Unconditional `scientific_decision=NOT_ASSESSED`, `release_decision=BLOCK_RELEASE`, `candidate_deployed=false`, `oaie_established=false`. Preserve any gate failure; no main merge or external action.
