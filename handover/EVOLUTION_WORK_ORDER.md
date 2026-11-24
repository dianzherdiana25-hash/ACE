# ACE Evolution Work Order: `evo-0001-7bc577a0`

- **Generation**: `1`
- **Finding Key**: `silent_except_pass::code/ace_cognition/substrate_guardian.py::<module>`
- **Kind / Severity**: `silent_except_pass` (`MEDIUM`)
- **Order SHA-256**: `8552ca5c05b7395c287ac93cd6d19a86ba751f8ec9eac70c5c0a568bde377702`

## 1. Objective
[MEDIUM] 5 broad silent `except ...: pass` handler(s) in code/ace_cognition/substrate_guardian.py.

### Observed Evidence (`code/ace_cognition/substrate_guardian.py:L68-L223`)
5 broad silent `except ...: pass` handler(s) in code/ace_cognition/substrate_guardian.py.

**Recommended Action:**
Replace silent `except ...: pass` at line(s) [68, 82, 110, 125, 223] in code/ace_cognition/substrate_guardian.py with explicit exception narrowing, structured logging, or error propagation.

### Measured Pre-Edit Metrics
```json
{
  "lines": [
    68,
    82,
    110,
    125,
    223
  ],
  "silent_except_count": 5
}
```

## 2. Allowed Target File(s)
- `code/ace_cognition/substrate_guardian.py`

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
- `PYTHONPATH=code /usr/bin/python3 -m unittest ace_cognition.test_substrate_guardian -v`
- `/usr/bin/python3 tools/verify_sources.py`

Then ask ACE to verify & ratify your patch via:
```bash
PYTHONPATH=code python3 -m ace_operational.oaie_cli --workspace "/home/hatch/workspace/ace-agent-workspace/handover-antigravity" evolve-verify --repo-root "."
```
