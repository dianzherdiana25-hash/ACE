# ACE E1.4f — exact reproducibility handoff

Scientific result: **`BENCHMARK_HOLD_REDESIGN`**. This is a public-development benchmark opportunity test, not a sealed confirmatory result or a user-approval gate.

## Exact materials
- [Pre-score cryptographic lock](../../design/e1.4/E14F_OPPORTUNITY_PRELOCK_MANIFEST_v1.md): `5d44ed79f9e7a3cac1f0940748d3f375ecdf4385`.
- **Frozen E1.4f source code, pre-score tests and full protocol**: `code/e14/e14f_frozen_source_2026-11-04.tar.xz`. SHA-256 `2f5f365c7d7940b39cdce361c31bdb28bf448a45a8ecc2e0c1503c3257be9865`, Git object SHA-1 `d9c867040a76e8903b534dd0f0e06bd6f608e731`. This archive was uploaded **without changing its bytes** after scoring; its hash was registered before scoring.
- **Exact raw data**: `evidence/e14/e14f_public_development_v1.json.gz`, gzip Git blob SHA-1 `c3a69c31b60fc128439c99b8f953f94a1f9e0012`. Uncompressed JSON SHA-256 `ede97348d64aa879a7072bffde02a62cef661bebf4ff91166e7a92fc6acd11c5`.
- [Report](../../design/e1.4/E14F_OPPORTUNITY_RESULT_v1.md) and [verification summary](../../evidence/e14/e14f_verification_summary_v1.json).

## Safe local recreation (Python 3.10+ / standard library, no paid API)

```bash
# Begin from a clean checkout of research/e1.3-design.
# E1.4e Python dependencies in this repository are stored in a historical tarball.
tar -xzf code/e14/e14e_frozen_source_2026-11-04.tar.gz -C .
tar -xJf code/e14/e14f_frozen_source_2026-11-04.tar.xz -C .
gzip -dc evidence/e14/e14f_public_development_v1.json.gz > evidence/e14/e14f_public_development_v1.json
sha256sum code/e14/e14f_bank.py code/e14/e14f_run.py code/e14/e14f_selector.py code/e14/e14f_audit.py code/e14/test_e14f_prescore.py
sha256sum evidence/e14/e14f_public_development_v1.json
PYTHONPATH=code python3 -m unittest -v e14.test_e14f_prescore
PYTHONPATH=code python3 -m e14.e14f_audit evidence/e14/e14f_public_development_v1.json
PYTHONPATH=code python3 -m e14.e14f_run --freeze-commit 5d44ed79f9e7a3cac1f0940748d3f375ecdf4385 --verify evidence/e14/e14f_public_development_v1.json > /tmp/ace_e14f_replay.json
```

Run commands under a finite wall-time supervisor. The `--verify` command should compare canonical JSON against preserved evidence; it does **not** prove evaluator secrecy or isolation. Do not use the E1.3 sealed bank. The full E1.4 regression locally passed **84/84** after restoring E1.4c/d historical evidence inputs; a clean remote runner must include those original fixture JSON files for tests that read them.

## Next action
Read [NEXT_ACTION.md](../../NEXT_ACTION.md) and [Issue #1](https://github.com/dianzherdiana25-hash/ACE/issues/1): design E1.4g's independent opportunity-positive versus natural benchmark *before scoring*. Preserve all E1.4f negative outcomes. No Tod changes, no main merge, no Google Drive code transport.
