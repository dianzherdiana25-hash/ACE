# ACE Capability Evolution Loop v0.1 — first executed multi-generation vertical slice

**Observation date:** 2026-11-06. **Research classification:** public synthetic engineering and method development. **Scientific decision: NOT_ASSESSED. Release: BLOCK_RELEASE. OAIE: NOT_ESTABLISHED.** No merges, deployments or mutations to core engines.

## Source and prescore custody

1. Locked protocol `docs/ACE_CAPABILITY_EVOLUTION_PILOT_PRESCORE_V1.md` Git commit **`4f6f8b5cfa7b3728d21d723696111652d4d85969`** came **before** pilot source, tests and experimental scoring. GitHub Actions compares current bytes with exactly this commit.
2. R1 actual code (PR #38) pinned **`8952c8ac55613e61b362841f4722c66a5aa990b3`**, with independently checked `primitive_discovery.py` Git blob `48904d7f344bd0bce6d5c392ccdc015309479fd5`.
3. S2 typed search actual code (PR #36) pinned **`08da5702828285e0bd4d0f4dd8876f331ac89fe2`**. Both checked out separately, imported as frozen read-only modules. This pilot does not reimplement or alter either learner.
4. Exact-head GitHub Actions [run #42160751743](https://github.com/dianzherdiana25-hash/ACE/actions/runs/42160751743) on `3f2cb56c2b4cfc6c80ae90276f1989a942f8ba3c`: **SUCCESS**, 13/13 unit/adversarial tests, two byte-identical full evaluation runs, independent full source replay verifier **PASS_PUBLIC_REPLAY_NOT_SCIENTIFIC_GO**.
5. Raw public evidence JSON is 9,268 bytes and SHA256 **`e8d263b360b6564913c2f3c64683afe10aa5312e81be3540a30d51f1192ea438`**. Exact zipped Actions artifact `ace-capability-evolution-v0-public` ID **13476672484** ZIP SHA256 `4cb0f10f44ecc572355370a2cd122740ef717acb649146ccf807e40c1b0f8e46`. Coordinator downloaded and independently inspected the three ZIP members: `evolution-v0.json`, `summary.json`, `verify.json`. JSON hash matched the Actions log.

## Actual generational behavior

`G0`: no task-specific learned capability. `G1`: R1 infers a data-driven finite automaton on `a_mod4`, and S2 searches closed integer ASTs for `x_minus_y`. Both pass predefined *validation-only* staging gates. `G2`: same frozen algorithm implementations acquire two more task-specific candidates for `b_mod4` and `product_plus_two`, retain G1 immutable model fingerprints, and recheck old validation behavior without refitting. Only after all staging decisions are frozen are terminal scores inspected.

| Task | Stage | Actual baseline holdout correct | Actual candidate holdout correct | Candidate terminal |
|---|---:|---:|---:|---|
| R1 `a_mod4` | G1 STAGED | 197/256 (76.95%) | **256/256** | PASS |
| S2 `x_minus_y` | G1 STAGED | 2/16 (12.50%) | **16/16** | PASS |
| R1 `b_mod4` | G2 STAGED | 192/256 (75.00%) | **256/256** | PASS |
| S2 `product_plus_two` | G2 STAGED | 0/16 (0%) | **16/16** | PASS |

All four nominal task-specific instances are staged. Every nominal task satisfies its predeclared terminal correctness threshold. Existing G1 candidates are retained unchanged at G2. The search/validation selection is bounded to R1 state merges (<=10000) and S2 grammar/compute/candidate limits (800 / 100000 work); total per-target search accounting and representations are included in the raw artifact.

**Critical falsifier (G2 control):** `late_rule_inversion` has byte-identical train+validation target labels to `a_mod4` but flips its truth on longer final inputs. The same unchanged R1 mechanism passes validation and stages an apparently successful candidate, yet scores **0/256** terminal correctness, vs the baseline's 59/256. It has **no calibrated OOD detector nor semantic abstention**. This is an observed false acceptance of task-specific generalization; not an engineering test failure, but a decisive safety/research failure.

## Precommitted gates

| Gate | Observed | Result |
|---|---|---|
| G1 — at least one G1 capability staged | Two staged | PASS |
| G2 — both modality families + immutable G1 replay | Four staged, original scores unchanged | PASS |
| G3 — at least 3/4 nominal tasks succeed at terminal | 4/4 meet threshold | PASS |
| G4 — latent rule inversion detected as unsafe | False validation acceptance; 0/256 terminal | **FAIL** |
| G5 — exact provenance/determinism/replay | 13/13 tests, two byte-identical runs, strict verifier | PASS *for tested GitHub Actions exact head only* |

These are **precommitted public diagnostic gates**, not criteria to declare an autonomous intelligence system discovered. A positive G1–G3 with failed G4 **must not become** an aggregated scientific GO.

## What this demonstrates, and what it does NOT

- **Supported:** An orchestration program can reuse unchanged real R1 and S2 research implementations as task-specific proposal engines, stage validation-qualified artifacts across generations, retain earlier artifacts without refitting, and perform separate terminal reporting and fail-closed exact-source evidence replay.
- **Not supported:** Creation of a new algorithm family or architectural primitive; weight-transfer/learning-to-learn; independently verified OOD generalization; open-ended autonomous curriculum; architecture self-evolution; real-world online decisions; safe production self-modification.
- Retention here is immutable **per-task storage**, not genuine catastrophic-forgetting resistance in a shared learner.
- The source algorithms, task stream, grammar, validation thresholds and seeds were authored by researchers. Terminal data are generated by the same coordinator and are public. This was **not** a concealed confirmatory or third-party evaluator.
- R8's independent public 512-zero-effect canary still shows 9 false passes; Red Team PR #30 / Issue #53 still has unresolved core source/replay/journal defects. The new pilot does not bypass either gate.
- No external calls, payments, deployed code, production candidate promotion, or changes to frozen E1.4 or `main`.

## Next scientifically falsifiable step

**Target:** Move from task-specific candidate acquisition into *algorithm/representation class change and transferable improvement*, without mining this now-public task bank.

1. **New sealed family-disjoint curriculum** with task grammars not expressible by either supplied R1 DFA/simple typed integer AST; fixed reviewer-owned external examples and precommitted budgets. A 'new capability' must demonstrate a task solved that both baseline classes **provably cannot solve** within declared budgets, not just more instances within a supplied class.
2. **Propose representation-changing operators under isolation:** syntax-tree grammar extensions or bounded memory topology, with code-generation provenance and complexity penalty, but no arbitrary candidate execution or production release. Compare stronger handcrafted expansion baselines under matched *actual compute and label cost*, not just allowed caps.
3. **Sequential experiment design and uncertainty:** evaluator-owned information acquisition; explicit refusal to claim OOD safety when stable/inverted worlds remain observationally indistinguishable; false-acceptance and coverage separated from skill-instance count.
4. **Retention and recursion:** demonstrate *method-level* cross-family transfer at generation G3+ and equal-budget successor advantage against frozen original selector and independent new tasks. Avoid equating append-only registry memory with lifelong learning.
5. **Integration gates:** independent Red Team fixes journal/custody controls in Issue #53, and full exact-head historical native isolation. Keep HOLD until cleared.

**Final:** Capability Evolution Loop v0.1 has **engineering executable evidence**, but not an OAIE scientific capability claim. The failure on hidden drift is a first-class research result and blocks automatic promotion.
