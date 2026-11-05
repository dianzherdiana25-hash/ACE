# E1.5 / E1.6 source-evolution integration preflight

Status: **DRAFT / ENGINEERING_ONLY / NOT_ASSESSED**. Source PR #26 E1.6 HEAD `aba67d6c7572550b84ff464eba850cf2b6fdccc7`. Sibling PR #27 E1.5 reference HEAD `965640786cbf2f8adcd89eb1d980945f78c2da77`. No main change, science GO, candidate promotion, paid oracle, or deployment.

## Actual incompatibility

The two sibling PRs both modify `code/ace_loop/source_evolution.py` and `code/ace_loop/test_source_evolution.py`, with distinct public contracts:

- **E1.5 / PR #27**: `SourceEvolution(root)`, trusted `predict(x,y)` arithmetic AST interpreter, five hand-enumerated arithmetic candidates and simple split-wise absolute-error evaluation.
- **E1.6 / PR #26**: `SourceEvolution(root, adapter, max_cycles, patience)`, typed gene mutations producing `rank(lo,hi,turn,diversity,balance)`, E1.4y research-loop adapter and different validation/holdout semantics.

They are **not drop-in replacements**. Overwriting one file with the other silently loses one experiment and breaks its tests. This evidence is about API and evaluation mechanics only, not a semantic claim of improvement.

## Minimal non-destructive compatibility step

This branch starts from exact PR #26 E1.6 HEAD and makes **only additions**:

1. `code/ace_loop/source_evolution_e15_reference.py`: exact source bytes copied from PR #27 `code/ace_loop/source_evolution.py`, original blob SHA `8a8c2c729db3072612830c03d7bd1eb0a2371ce9`.
2. `code/ace_loop/test_source_evolution_e15_reference.py`: exact PR #27 test content except module import rewritten from `.source_evolution` to `.source_evolution_e15_reference`; original test blob SHA `9443215338ce7b33c33a0fdf882aceb7a96ebf41`.
3. An isolated check workflow only for the E1.5 reference and E1.6 existing test suites. **Do not** use this reference module as a live deployed implementation or quietly substitute it for E1.6.

Run on a fresh checkout of the integration candidate head (not synthetic merge head):

```bash
PYTHONPATH=code:. python -m unittest ace_loop.test_source_evolution_e15_reference ace_loop.test_source_evolution ace_loop.test_engine ace_loop.test_portfolio -v
```

## Integration gates still open

- Confirm exact-HEAD targeted CI check succeeds and published evidence can be linked. **Not verified at the time this note was authored.**
- PR #26 earlier run #42032051955 has a failing E1.4u portable group and blocked native sandbox due to denied user namespaces; this patch does not fix those underlying blockers.
- Independent Red Team review, receipt integration, semantic comparison across different synthetic tasks, full historical regression and trusted worker isolation are separate unpassed gates.
- This is **coexistence** and source provenance preservation, not unification of algorithms or permission to merge. Do not merge into main without explicit owner approval.

No frozen E1.4 sources or existing E1.6 source-evolution code were modified.


## Static historical regression inventory preflight (2026-11-05)

New additive `tools/ace_regression_inventory.py` parses the existing `TESTS` literal in `tools/ace_e15_regression.py` via `ast.literal_eval`; it **does not import or execute** frozen modules. It resolves `e14.*` and `ace_loop.*` under `code/`, `tools.*` under the checkout root, and returns exit 2 with `BLOCK_MISSING_MODULES` when any declared file is missing. `INVENTORY_COMPLETE_NOT_TESTED` is explicitly **not** a successful regression test. Five adversarial tests cover missing paths, valid paths without import, nonliteral manifests, invalid names, and absent manifest.

The exact-head CI step verifies that the missing historical set is precisely `u:e14.test_e14u_algebra_union` and `u-ablation:e14.test_e14u_ablation`, instead of silently deleting the requirements. If that set changes, CI fails pending review. This is **diagnostic engineering only**; no frozen test has been restored, no historical regression pass has been claimed, and native user-namespace isolation remains blocked.
