# PREREGISTRATION LOCK — PROPOSER ENGINE STAGE 1 V2 (2026-11-14)

- **Status:** LOCKED BEFORE ANY COUNTED V2 GENERATION.
- **Authority & Reopening Basis:** Answers `handover/PROPOSER_STAGE1_EXIT_GATE_VERDICT_20261114.md` (PR #199 §3), which ruled Stage 1 `NOT_PASSED` on `Qwen3-30B-A3B` under prose schema + 900-token cap (`0/6`, all failing on `uncertainties` type or token-cap truncation) and required a NEW preregistration testing:
  1. **Grammar-constrained decoding** (`response_format=json_schema` enforcing `ace.proposal.v1` schema at token generation time), AND/OR
  2. **Closed validator-feedback repair loop** (fail-closed `validate_package` rejection reasons returned to the model under a bounded protocol).

## Locked generation protocol
- **Brain:** `Qwen3.5-4B-Q4_K_M.gguf` (`llama-server` build `llama-b12316`, Manus AVX-512 Cascade Lake CPU host, `-t 4`, `-c 8192`, `-fa on -ctk q8_0 -ctv q8_0 --reasoning off`).
- **Decoding:** `POST /v1/chat/completions`, `temperature=0.0`, `seed=42`, `max_tokens=1300`, `response_format={"type":"json_schema","json_schema":{"strict":true}}` (canonical `PROPOSER_JSON_SCHEMA` digest `a32a27feaeecb86754a7d2fc1f2aa189ae34440db56ccc0fe172794bc07ab5d8`).
- **Data split & anti-leakage:** Identical frozen `episodes.json` (`EP1..EP6`) and untouched `outcomes.json` from Stage 1 v1. Outcomes remain sealed during all generations and during any Attempt-1 repair.
- **Arms evaluated over frozen outputs:**
  1. `grammar_only`: Attempt 0 only (zero retries; strict non-repair comparison vs Stage 1 v1).
  2. `grammar_plus_1_repair`: If Attempt 0 fails `validate_package`, ONE closed repair turn supplying ONLY `validate_package` rejection strings (never rubric breakdown or outcomes). Otherwise retains Attempt 0 unchanged.

## Locked exit gate (identical to Stage 1 v1)
- **Quality clause:** Paired diffs (`proposer - historical`) per episode; non-inferior iff `mean_diff >= -10.0` AND bootstrap 95% CI lower bound (seed `20261113`, `10000` resamples) `>= -20.0`. Validator rejection scores `0.0`.
- **Time clause:** `NOT_ASSESSABLE` (no historical human drafting-time baseline); descriptive wall times recorded alongside speed comparison vs `Qwen3-30B-A3B` (`751s`/ep).
- **Verdict:** `PASS` only if both pass; `PARTIAL` if Quality passes and Time is `NOT_ASSESSABLE`; `NOT_PASSED` otherwise.

## Locked artifact hashes (at lock time)
- `PROPOSER_JSON_SCHEMA` canonical sha256: `a32a27feaeecb86754a7d2fc1f2aa189ae34440db56ccc0fe172794bc07ab5d8`
- `evidence/proposer_stage1/episodes.json`: `cbcc308540d65f6081d5ab6f3dd97435426e8d68c4e4145ce0e23323df6fea55`
- `evidence/proposer_stage1/outcomes.json`: `55cf613aeb4b6ee4ecb673b14a6f4b507c3c41a9f674aeebc41922fc2fa3b72f`
- `code/ace_operational/proposer_schema.py`: `572a70aa68f408a82446c72e3366634c31815930afe0c53122a3429582e0dcad`
- `code/ace_operational/proposer_validator.py`: `8af2fd214647445149834f23a1a2d2435a117caf94422aad9abede08b72b9830`
- `code/ace_operational/proposer_rubric.py`: `97f7b423b0ce9d55e8a7c8c7d27805ff7f14b3f4cceb447ba5d6806b9cfa1e25`
- `code/ace_operational/proposer_episodes.py`: `edd331fb125cb28bf4d4b6ad5617a91289c36b7f14cd83e59f6b78e9a4f3b7b8`
- `code/ace_operational/proposer_simulation.py`: `5f874bc8239bdedf1361d6467f1535c2ed25b5fe7f42d18e5486865e164652c9`
- `code/ace_operational/proposer_stage1_v2.py`: `49b15bf698ea8dcb9f89217bd8bdb302d81d902d6df1db6972c1f69f91f29bda`
