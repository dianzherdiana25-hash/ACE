# ACE E1.6 historical regression source-coverage preflight

Status: **INCOMPLETE_HISTORICAL_COVERAGE** — engineering evidence only, scientific **NOT_ASSESSED**.

This standalone coordinator contribution starts from PR #46 HEAD `0a873b99748fa6951c6771303bdbb5c9f4a0c759` (E1.5 reference on top of E1.6). It does **not** modify historical research source, E1.4/E1.4aa frozen experiments, `code/ace_loop/`, PR #26, PR #27, or `main`.

## Cause identified directly from GitHub

At PR #46 parent HEAD, `tools/ace_e15_regression.py` declares 25 test modules in nine groups, but exactly two referenced source modules do not exist in a complete 549-entry recursive Git tree:

| Group | Missing module | Missing Git path |
|---|---|---|
| `u` | `e14.test_e14u_algebra_union` | `code/e14/test_e14u_algebra_union.py` |
| `u-ablation` | `e14.test_e14u_ablation` | `code/e14/test_e14u_ablation.py` |

The remaining 23 declared modules have corresponding paths (this means **source present**, not **test passed**). The `u` group fails in E1.6 full CI; the regression runner stops before downstream groups. Native sandbox remains independently blocked by Linux user namespace permission on default hosted runner.

## This PR's implemented preflight

`tools/ace_historical_coverage.py` parses the manifest's literal `TESTS` declaration through Python AST without importing or executing the runner. It:

- Verifies exact checkout HEAD against expected SHA before reporting.
- Checks tracked Git tree presence, rejects modified tracked checkout and symlinks, refuses to count untracked stand-in test files.
- Labels groups `MISSING_TEST_SOURCE` or `SOURCE_PRESENT_NOT_EXECUTED`; reports `historical_tests_executed=0` and `historical_tests_passed=0`.
- Emits deterministic JSON containing exact manifest SHA256, group names, missing module paths and digest of canonical report bytes.
- Returns **exit 2** when coverage is incomplete, **exit 1** for integrity/tool failure, **exit 0** only when all *source files exist* (NOT when tests pass).
- Writes an immutable local receipt with exclusive creation; no remote purchases/deployment or mutations to the ACE engine.

The isolated workflow `ace-coordinator-history-inventory.yml` verifies that audit evidence matches the two known missing modules and uploads a machine-readable receipt. **A successful inventory-audit workflow means the detection code worked, not the historical regression passed.**

## Reproduction

From this PR's exact source checkout:

```bash
python -m unittest discover -s tools -p 'test_ace_historical_coverage.py' -v
python tools/ace_historical_coverage.py --root . --expected-head "$(git rev-parse HEAD)" --output /tmp/ace-history-coverage.json
# Expected: output INCOMPLETE_HISTORICAL_COVERAGE, process exit 2
```

Local synthetic-fixture adversarial tests: **16/16 PASS**. Exact-head GitHub Actions verification must be read from current workflow result; do not assert success until confirmed.

## Owner-required gates

1. Locate original scientific/protocol provenance of the two missing modules, especially Codex Issue #17. No fabricated placeholder tests and no silently shrinking the manifest to make CI green.
2. Independently audit code and results against prescore locks; full history suite must actually run on the intended exact checkout.
3. Validate native namespace isolation on a runner that provides it, without weakening the security gate.
4. Review semantic mismatch of PR #26 vs #27 and integration PR #46.
5. Keep all PRs draft until review and explicit main merge authorization.

No scientific GO, no OAIE, no full-regression certification.
