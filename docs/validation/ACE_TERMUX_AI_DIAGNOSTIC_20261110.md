# ACE Termux ask-ai candidate diagnostic — bounded scope

Date: 2026-11-10 (Asia/Jakarta). Branch: `fix/ace-ai-evidence-gate-20261110`. Target PR: #94 (draft; base `ace-termux-20261110`).

## Reproduction target and failure

The previous autonomous source-development loop could report `ACCEPTED` after appending an unused helper function and merely importing the affected module. It used an unrelated hardcoded lambda for the negative control. The candidate's prediction function was not tested against the claimed research task, and the algorithm itself did not need to change. A plain git worktree plus subprocess is not OS-level containment.

## Implemented diagnostic contract

- `code/ace_code_agent/static_probe.py` parses a single, strictly bounded arithmetic function (exactly three integer inputs) and interprets its AST **without** `exec`, `eval`, Python compilation or importing candidate code.
- Rejects imports, calls, attributes, loops, comprehensions, nested functions, decorators, large ASTs, oversized intermediate values and invalid or nonbinary outputs. Unsupported code remains unexecuted.
- Evaluates a **public synthetic diagnostic grid**: 6 lengths × 4 densities × 4 stride values = 96 examples. Three scores are recorded: modular rule, run-parity rule and their conjunction; no hidden holdout is used.
- Records a weak development reference `int(length % 3 == 0)`, as well as the ideal per-family rule upper baseline (1.0). Any improvement relative to the weak reference **does not** establish superiority over a strong baseline.
- These functions have only three inputs and cannot reliably dispatch between distinct labeled tasks. Even a perfect public score does not prove the actual active algorithm uses the function.
- Persists diagnostic metrics, `NOT_ASSESSED`, and `candidate_connected_to_runtime: false` into research-cycle history.
- ALL candidates remain `INCONCLUSIVE` unless syntax/security invalid, which is `REJECTED`. The source-development pipeline does not promote or create PRs for these candidates.
- The dashboard reports the newest recorded consultation instead of falsely claiming all external models are active. `ask-ai` does not provide verified upstream model identity in this pipeline. Provider costs and availability are unverified.
- No modifications to `main`, core research baselines, E1.4 frozen sources, or the live Termux filesystem.

## Scientific status

`SCIENTIFIC_NOT_ASSESSED`, `BLOCK_RELEASE`, `OAIE_NOT_ESTABLISHED`. This is an **admission integrity and measurement** fix, not a verified capability gain. The SHA256 receipt proves only local integrity, not independent evaluator custody.

## Conditions before any future ACCEPTED

1. Connect the candidate's actual invoked path to the intended active mechanism with replayable integration evidence (not a standalone appended unused helper).
2. Enforce OS-level containment or a formally bounded, non-Python typed interpreter before testing externally sourced candidate logic.
3. Pre-register disjoint development, validation and terminal tasks and verify with evaluator custody separate from the generator.
4. Compare against the best relevant fixed and fresh baselines at equal label and compute budgets, report positive and negative controls, and require robust improvement without regressions.
5. Keep scientific confirmation `NOT_ASSESSED` until the evidence is independently reviewed. No automatic merge/deployment or unconstrained external side effects.

## Narrow reproducible test

```sh
PYTHONPATH=code python -m unittest ace_code_agent.test_operational_proof -v
```

Public diagnostic tests validate AST controls, actual candidate scoring and that accepted/promotion remains blocked. Full system CI and unrelated legacy failures must be reported separately at the exact commit SHA.

## Checking historical `ask-ai` proposals from Termux

Run on a separate, reviewed checkout (not the active autorun daemon):

```sh
PYTHONPATH=code python tools/ace_ai_diagnostic.py --limit 5
```

The command reads `checkpoints/self_dev/ai_consultations.json`, reports bounded public scores for each supported candidate source, and does not write files or send network requests. Previous `engine` values are **unverified labels**. Only the strictly bounded `int(expression)` conversion is now interpreted without executing Python; arbitrary calls, attributes, keyword arguments and nested calls are still rejected. The actual cycle-96 candidate uses `int(congruent and parity_matches)` and is supported by the public diagnostic. Example local `hyp_expand_dispatch_95` formula receives 59/96 modular, 57/96 parity and 71/96 joint on this public grid; an ideal task-specific rule can score 96/96. No capability is admitted.

The mobile dashboard now bases its status on recent heartbeat timestamps (90-second freshness threshold) and recorded decisions, rather than stale numbers, fixed AI claims or a permanent green live-status pill. Android may stop background Termux processes at any time.

Always run the exact pinned PR SHA in CI before considering use; the known `ace_runtime.test_engine` status mismatch (`LEARNED_STAGED` vs `NO_VALIDATED_MODEL`) is not fixed or suppressed by this patch.

## Follow-up: cycle 96 integer-conversion support

The read-only checker originally marked `hyp_expand_dispatch_96` `UNSUPPORTED_STATIC_GRAMMAR` because it used `int(congruent and parity_matches)`. A strictly interpreted, single-argument `int(expression)` arithmetic primitive has now been added. This does not call Python's `int` on candidate objects, resolve external functions, or permit arbitrary calls. Regression tests cover the actual syntax and reject `eval`, `__import__`, `float`, method calls, second arguments and keywords. The new result remains `PUBLIC_DIAGNOSTIC_ONLY`, with zero candidate Python execution and no promotion.
