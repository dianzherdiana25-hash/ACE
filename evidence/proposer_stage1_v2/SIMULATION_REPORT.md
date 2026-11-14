# PROPOSER ENGINE STAGE 1 V2 — SIMULATION REPORT (2026-11-14)

- **Schema:** `ace.proposal.v1` (`PROPOSER_JSON_SCHEMA` sha256 `096bef9b674c137b37ba482c55e139c5f9963b1d1d143e37729ab58a78fe055c`)
- **Brain:** `Qwen3.5-4B-Q4_K_M.gguf` (`llama-server b12316`, `-t 4`, `-c 8192`, `--reasoning off`, `temp=0.0`, `repeat_penalty=1.08`, `seed=42`, `max_tokens=1300`)
- **Reopening Basis:** `PR #199 §3` (preserving `PR #191` / `PR #199` Stage 1 v1 `NOT_PASSED` on `Qwen3-30B-A3B` unchanged as historical v1 record).

## Arm Summary

| Arm | Validator Accepted | Mean Proposer | Mean Historical | Mean Diff (>= -10) | Bootstrap 95% CI Lower (>= -20) | Quality Clause | Time Clause | Exit Gate Verdict | Mean Wall (s/ep) |
|---|---|---|---|---|---|---|---|---|---|
| `grammar_only` | 6/6 | 99.17 | 91.67 | +7.50 | +0.83 | **PASS** | NOT_ASSESSABLE | **PARTIAL** | 201.83 |
| `grammar_plus_1_repair` | 6/6 | 99.17 | 91.67 | +7.50 | +0.83 | **PASS** | NOT_ASSESSABLE | **PARTIAL** | 201.83 |

- **Speedup vs Stage 1 v1 (`Qwen3-30B-A3B` `751s/ep`):** `Qwen3.5-4B` achieved `201.83s/ep` (`3.72x` faster per episode under `-t 4` grammar-constrained decoding).

## Per-Episode Breakdown (`grammar_plus_1_repair` / `grammar_only`)

| Episode | Wall (s) | Repaired? | Accepted | Proposer | Historical | Diff |
|---|---|---|---|---|---|---|
| `EP1-G3-APPLICATION` | 191.42 | False | True | 100.0 | 100.0 | +0.0 |
| `EP2-ABC-V3` | 178.69 | False | True | 100.0 | 100.0 | +0.0 |
| `EP3-ROUND2-GATE` | 199.59 | False | True | 100.0 | 100.0 | +0.0 |
| `EP4-CONTROL-REGRESSION-ATTRIBUTION` | 219.84 | False | True | 95.0 | 90.0 | +5.0 |
| `EP5-G4-INHERITANCE` | 218.68 | False | True | 100.0 | 80.0 | +20.0 |
| `EP6-PER-TASK-RECORDING` | 202.77 | False | True | 100.0 | 80.0 | +20.0 |
