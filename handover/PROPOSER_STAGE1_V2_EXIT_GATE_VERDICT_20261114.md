# PROGRAM VERDICT — PROPOSER ENGINE STAGE 1 V2 EXIT GATE: PARTIAL (QUALITY PASS)

> **Recorded verdict of Stage 1 v2** under preregistration `evidence/proposer_stage1_v2/PREREG_LOCK.md`
> (answering `handover/PROPOSER_STAGE1_EXIT_GATE_VERDICT_20261114.md` / PR #199 §3).
>
> **Preservation notice:** The Stage 1 v1 inaugural verdict (`NOT_PASSED` on `Qwen3-30B-A3B`,
> PR #191 / PR #199, `0/6`, mean diff `−91.67`, mean wall `751s/ep`) remains **UNMODIFIED**
> and preserved on `main` alongside `evidence/proposer_stage1/`. Stage 1 v2 was evaluated
> under a new locked preregistration (`PREREG_LOCK.md`, pre-outcome technical amendment v2.1)
> with `evidence/proposer_stage1/outcomes.json` kept strictly sealed until all 6 generations
> were frozen and committed (`390a553`).

## Verdict

- **Quality clause: PASS** (`mean_diff = +7.50 >= -10.0`, deterministic bootstrap 95% CI lower bound `= +0.83 >= -20.0`, seed `20261113`, `10,000` resamples).
- **Time-saving clause: NOT_ASSESSABLE** (identical locked condition: no historical human drafting-time baseline exists in the official record). Descriptive speed comparison vs Stage 1 v1 (`Qwen3-30B-A3B`, `751s/ep`): `201.83s/ep` (**3.72x faster**).
- **Exit gate verdict: PARTIAL** (Quality **PASS**, Time `NOT_ASSESSABLE` — highest achievable Stage 1 verdict under `PREREG_LOCK.md`).

## Measured Numbers (`Qwen3.5-4B-Q4_K_M`, `-t 4`, `json_schema` `096bef9b...`)

| Arm | Validator Accepted | Proposer Mean | Historical Mean | Mean Diff | 95% CI Lower | Mean Wall (s/ep) | Verdict |
|---|---|---|---|---|---|---|---|
| `grammar_only` | **6/6** (0 repairs needed) | **99.17** | 91.67 | **+7.50** | **+0.83** | **201.83** | **PARTIAL** |
| `grammar_plus_1_repair` | **6/6** (identical to `grammar_only`) | **99.17** | 91.67 | **+7.50** | **+0.83** | **201.83** | **PARTIAL** |

| Episode | Wall (s) | Attempt 0 Validated | Proposer | Historical | Diff |
|---|---|---|---|---|---|
| `EP1-G3-APPLICATION` | 191.42 | True | 100.0 | 100.0 | +0.0 |
| `EP2-ABC-V3` | 178.69 | True | 100.0 | 100.0 | +0.0 |
| `EP3-ROUND2-GATE` | 199.59 | True | 100.0 | 100.0 | +0.0 |
| `EP4-CONTROL-REGRESSION-ATTRIBUTION` | 219.84 | True | 95.0 | 90.0 | +5.0 |
| `EP5-G4-INHERITANCE` | 218.68 | True | 100.0 | 80.0 | +20.0 |
| `EP6-PER-TASK-RECORDING` | 202.77 | True | 100.0 | 80.0 | +20.0 |

## Answers to PR #199 §3 Design Questions

1. **Grammar-constrained decoding (`response_format=json_schema`):** Eliminates structural type deviations completely (`0/6` -> `6/6` on Attempt 0, fixing the 6/6 `uncertainties` string bug and all JSON truncations once array `maxItems` + `repeat_penalty=1.08` bound degenerate list looping).
2. **Closed 1-shot validator repair loop:** Implemented and tested (`proposer_stage1_v2.py`), with zero Attempt-1 repair calls needed in practice because `grammar_only` already achieved 6/6 valid Attempt-0 packages.

## Scope Boundary

This verdict clears the Stage 1 Quality gate in **simulation-only** mode (`no dispatch path exists`). Opening any Stage 2 staging integration remains governed by `handover/PETA_ARAH_SERIBU_TAHUN.md` addendum §5 (isolated staging harness + payload-hash-pinned internal ratification + revocation checks) under a dedicated Stage 2 preregistration.
