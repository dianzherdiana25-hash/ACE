# ACE E1.6 — executable source mutation and guarded oracle handoff

**Development status: implemented and locally exercised, scientific `NOT_ASSESSED`.** The long-term OAIE objective is **NOT** reached. ACE E1.5 and all frozen E1.4/E1.3 source, lock, bank, and recorded negative outcomes remain unchanged. No merge to `main`, no Tod change, no purchased external service. This contribution is a draft stacked on the E1.5 controller.

## Demonstrated changes versus E1.5

1. `code/ace_loop/source_evolution.py` uses a finite **typed grammar of Python source modifications**, generates separate `.py` source files for candidate query-ranker functions, checks each candidate's syntax against the exact approved template, executes the code with a no-builtins namespace, and evaluates each candidate against distinct public synthetic E1.4y train/validation/heldout worlds. Accepted-for-further-evaluation means a validation-gated selection, **not deployment**. Only terminal holdout decides whether it may be considered for review; the code is never installed into production, even if heldout improves. Generated forms change arithmetic structure and source bytes but can only explore supplied arithmetic primitives. This is controlled code mutation, not open-ended LLM-directed source rewriting.
2. The source evolution controller appends `config`→`trial`→`decision`→`completed` events to the E1.5 fsynced SHA-256 journal. It saves all candidate source files and their exact hashes, recomputes stored train/validation outcomes, rejects tampering even when a malicious actor recomputes the simple hash chain, resumes after a persisted trial without duplicating that trial, compares final holdout once for decision making, and supports deterministic early stop after repeated non-improving changes. Its use of `exec` is limited to **internally generated, structurally checked template code** and **is not** a security boundary for adversarial AI-generated programs.
3. `code/ace_loop/receipt_escrow.py` adds evaluator-owned SQLite reservations and a four-purchase per-arm budget for typed E1.4 graph questions. A transaction is reserved before dispatch, then atomically marked `DISPATCHED` before the callback. If the backend fails ambiguously, ACE refuses to retry; an authenticated out-of-band receipt must be supplied through `reconcile()`. `reserve()` is idempotent for the same arm/key/query; duplicate graph purchases are rejected; resource costs derive from the graph, not caller claims. This provides **at-most-one application invocation under this controller**, **not** distributed exactly-once semantics, which require backend-side idempotency, authentic signatures, and a trusted deployment boundary.
4. `ace_loop.cli evolve` and `evolve-status` are executable entrypoints. The GitHub Actions workflow requests clean PR-checkout unit, original E1.4aa lock, and repository-wide historical regression checks; a missing or failed run is not reported as passing.

## Commands

```bash
export PYTHONPATH=code:.
python3 -m unittest ace_loop.test_source_evolution ace_loop.test_receipt_escrow ace_loop.test_engine ace_loop.test_portfolio -q
python3 -m ace_loop.cli evolve --root WORK/e16-source --cycles 8 --patience 5 --outsiders-per-split 2
python3 -m ace_loop.cli evolve-status --root WORK/e16-source --cycles 8 --patience 5 --outsiders-per-split 2
```

**Local result at 2026-11-05:** 8 maximum candidate trials, 5 actual typed Python source mutations before the predeclared early-stop criterion; no candidate safely improved validation over incumbent. The controller wrote all five source files and journal events, selected baseline, and returned `REVERT_UNPROMOTED_SOURCE`, `candidate_code_deployed=false`, `heldout_delta_utility=0`; the public heldout baseline and selected policy both scored **-67** over 18 target worlds. Synthetic validation baseline **-31** over 12 worlds (3 accepted correct, **1 accepted wrong**, 8 abstained), so the baseline itself is **not scientifically acceptable**. Deliberately report that failure; never equate no new bad promotions with correct behavior. This is one deterministic public-bank development run, **not** novel capability discovery or generalization proof.

## Independent engineering tests and limitations

- Source-control test suite covers actual mutation, candidate grammar rejection, source and event tamper, ledger resume, repeat idempotence, heldout boundary, early stop, positive heldout HOLD, CLI, budget and type controls.
- Escrow tests cover durable predispatch claim, no repeat on uncertain outcomes, explicit authenticated reconciliation, duplicate graph, four-charge cap, fraudulent topology with recalculated digest, symlink and malformed identity refusal.
- SHA256/JSON accounting is not tamper-proof against an attacker able to rewrite all database records and independently falsify external provider receipts. Do not grant that attacker access to the evaluator process.
- Native Bubblewrap/OS sandbox, untrusted autonomous code generation, server-side remote callback receipt verification, exact-head full repository regression, E1.4aa 192-arm source-locked scoring and a separately held-back independent test bank remain **OPEN**.
- The experiment does not modify its own learning architecture or implement unrestricted source rewriting. No externally visible code deployment or real-world actuation occurs.

**Next engineering boundary:** after clean GitHub PR exact-head regression and native isolation are verified, link a **trusted provider** with verifiable receipts to the escrow, run E1.4aa's original prospectively frozen scoring (do not change locks), then allow isolated, reversible candidate code changes with signed promotion and rollback receipts. These are not automatically satisfied by the E1.6 experiment.

## Full checkout CI findings and integrated mission update

- Initial PR #26 CI run (GitHub Actions run `42030132789`, exact initial head `ba0948933238a333cc9932a9a34775c9599230da`): prescore/new-code job **PASS**. The complete test discovery ran 548 tests and reported 49 errors, one failure, four skips, dominated by historical native sandbox workers unable to create unprivileged user namespaces (`unshare ... /proc/self/uid_map: Operation not permitted`). This is **not** a passing full regression. Never silently replace historical isolation with unsandboxed execution. The CI workflow is split into portable regression and an explicit fail-closed native prerequisite gate to make environment blockers visible.
- Found and fixed a genuine E1.5 portfolio crash-recovery bug: when both research tracks show no positive validation gain, `allocation.selected` is legitimately `None` and must remain an idempotent terminal HOLD on replay. Old replay incorrectly raised `unknown allocated track`. Added a regression test. No historical frozen bank or scientific threshold changed.
- `code/ace_loop/mission.py` now joins the E1.5 policy portfolio and E1.6 source-code experiments under **one command** and a higher-level SHA256 mission ledger: `python -m ace_loop.cli mission --root WORK/mission --cycles 12 --pilot-trials 8 --source-cycles 8 --source-patience 5`. The mission is restart-safe for deterministic local simulations; if recorded policy/source checkpoints are removed, it **halts instead of recreating** them. `mission-status` exposes the ledger.
- Mission results are *bounded public engineering*, not autonomous discovery, external tasks, authenticated remote purchases or native security acceptance.
