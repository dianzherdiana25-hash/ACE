# ACE Evolution Work Order: `evo-0001-97a2a8bf`

- **Generation**: `1`
- **Finding Key**: `unguarded_verified_true::code/ace_operational/sovereign_runtime.py::<module>`
- **Kind / Severity**: `unguarded_verified_true` (`HIGH`)
- **Order SHA-256**: `30e9cd1a79a868bf754bd6f34fee4c0daaea264593a851e5b94074f285f964b7`

## 1. Objective
[HIGH] Unguarded hardcoded `'verified': True` found at line(s) [517] in code/ace_operational/sovereign_runtime.py.

### Observed Evidence (`code/ace_operational/sovereign_runtime.py:L517-L517`)
Unguarded hardcoded `'verified': True` found at line(s) [517] in code/ace_operational/sovereign_runtime.py.

**Recommended Action:**
Replace unguarded hardcoded `'verified': True` at line(s) [517] in code/ace_operational/sovereign_runtime.py with empirical behavioral verification or fail-closed error handling.

### Measured Pre-Edit Metrics
```json
{
  "lines": [
    517
  ],
  "unguarded_verified_true_count": 1
}
```

## 2. Allowed Target File(s)
- `code/ace_operational/sovereign_runtime.py`

## 3. Strictly Forbidden Custody & Upstream Paths
Do NOT modify any of the following paths (automatic fail-closed rejection):
- `code/ace_autonomy/`
- `code/ace_host_controller/`
- `code/ace_mission/`
- `code/ace_runtime/`
- `docs/UPSTREAM_SOURCES.json`
- `evidence/`
- `tools/`

## 4. Anti-Theater & Quality Constraints (AST-Enforced)
- Do NOT hardcode `'verified': True` fallback/literal bypasses in non-test code.
- Do NOT introduce silent `except: pass` or `except Exception: pass` handlers.
- Do NOT delete assertions or insert trivial constant assertions (`assert True`, `assertEqual(1, 1)`).
- Any newly created unit test module must contain >= 2 non-trivial assertions and >= 1 `test_*` method.
- No-op or syntactically broken edits will fail closed and be quarantined.

## 5. Acceptance Verification Commands
- `PYTHONPATH=code /usr/bin/python3 -m unittest ace_operational.test_sovereign_runtime -v`
- `/usr/bin/python3 tools/verify_sources.py`

Then ask ACE to verify & ratify your patch via:
```bash
PYTHONPATH=code python3 -m ace_operational.oaie_cli --workspace ".ace_evolution" evolve-verify --repo-root "."
```
