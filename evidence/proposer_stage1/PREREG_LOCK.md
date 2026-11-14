# PROPOSER ENGINE — STAGE 1 PREREGISTRATION LOCK

**Locked: 2026-11-13 ~22:20 WIB, BEFORE any generation.**
Design sources: PR #173 §9 (mesin pengusul) + PR #177 addendum
items 2 & 4 (simulasi-first; gerbang masuk vs keluar).

## What Stage 1 is
Simulation-first. The proposer (adopted local brain) composes ONE
proposal package per frozen historical episode, from at-time
information only. Packages are validated (fail-closed) and scored by
a deterministic rubric against at-time information. NOTHING is
dispatched; there is no execution path in the code.

## Locked design
- **Package schema** `ace.proposal.v1` (`proposer_schema.py`):
  claim, rationale, options (incl. `do_not_run`), recommended option,
  cost estimate, cost ceiling, hash-pinned evidence, preregistration
  link + artifact hash, risks, uncertainties, stop controls
  (abort conditions, sealed-target status, `no_auto_retry=true`,
  `stop_visible=true`), internal-ratification block. The vocabulary
  is *ratifikasi internal* (hub/kernel/evidence) — never owner
  approval (owner framing correction 2026-11-13 20:54).
- **Validator** (`proposer_validator.py`): fail-closed. A package
  without a positive ceiling, without enforced stop controls, or
  without evidence hashes is MECHANICALLY REJECTED, with reasons.
- **Data split**: `episodes.json` (at-time snapshots only) vs
  `outcomes.json` (outcomes + historical baseline packages, separate
  store, opened only by the scoring step after generations freeze).
  A unit test asserts no outcome text appears in any prompt.
- **Episodes**: selection rule written in `episodes.json`; count = 6
  (EP1 G3 application, EP2 abc-v3, EP3 round-2 gate, EP4 control-
  regression attribution, EP5 G4 inheritance, EP6 per-task
  recording). No additions/drops after first generation. Every
  episode carries a mandatory prior-exposure declaration.
- **Rubric** (`proposer_rubric.py`, total 100): claim_testability 20,
  evidence_grounding 20, cost_realism 20, risk_honesty 15,
  stop_controls 15, option_coverage 10. Validator-rejected = 0.
  The rubric never reads outcomes.

## Locked generation protocol
- Brain: Qwen3-30B-A3B Q4_K_M (adopted working brain) in the Manus
  Sandbox home, `llama-cli` b12316, **-t 1** (adopted serving
  config, PR #176), temperature 0, seed 42, max 900 tokens.
- ONE attempt per episode. No auto-retry: a failed/unparseable/
  rejected generation is recorded as-is and scores 0.
- Per-episode generation wall ceiling: 1800 s (sandbox runs at
  ~1 effective CPU via the MCP-door cgroup; A3B tg ≈ 2.46 t/s at
  -t 1 under the adopted config's confirmation conditions).
- The old Qwen director remains AT REST by owner order; it is not
  woken for this stage. The generating brain is the adopted A3B.

## Locked exit gate
- **Quality clause**: paired diffs (proposer − historical) per
  episode; non-inferior iff mean diff ≥ **−10** AND lower bound of
  the deterministic bootstrap 95% CI of the mean diff (seed
  20261113, 10,000 resamples) ≥ **−20**.
- **Time clause**: a time-saving claim requires a human drafting
  baseline. None exists in the official record → this clause is
  **NOT_ASSESSABLE in Stage 1** (locked here, before the run, not
  invented after it). Generation walls are reported descriptively.
- **Verdict**: PASS only if both clauses pass; PARTIAL if quality
  passes and time is not assessable; NOT_PASSED otherwise.

## Locked artifact hashes (at lock time)
- episodes.json: `cbcc308540d65f6081d5ab6f3dd97435426e8d68c4e4145ce0e23323df6fea55`
- outcomes.json: `55cf613aeb4b6ee4ecb673b14a6f4b507c3c41a9f674aeebc41922fc2fa3b72f` (hash only; content sealed from the prompt path)
- proposer_schema.py: `572a70aa68f408a82446c72e3366634c31815930afe0c53122a3429582e0dcad`
- proposer_validator.py: `8af2fd214647445149834f23a1a2d2435a117caf94422aad9abede08b72b9830`
- proposer_rubric.py: `97f7b423b0ce9d55e8a7c8c7d27805ff7f14b3f4cceb447ba5d6806b9cfa1e25`
- proposer_episodes.py: `edd331fb125cb28bf4d4b6ad5617a91289c36b7f14cd83e59f6b78e9a4f3b7b8`
- proposer_simulation.py: `5f874bc8239bdedf1361d6467f1535c2ed25b5fe7f42d18e5486865e164652c9`

## AMENDMENT A1 (2026-11-13 ~23:10 WIB, declared BEFORE the corrected run)
The locked generation interface (llama-cli) is defective for this
build: llama-cli b12316 forces conversation mode on chat-template
models; given `-f`, it echoed the prompt as a user turn and exited
on stdin EOF with "Generation: 0.0 t/s" — zero tokens generated
(attempt archived as VOID, harness fault, not a model result).
Interface corrected to **llama-server (same b12316) + POST
/completion** with the identical raw ChatML prompts, identical
model, -t 1, temperature 0, seed 42, max 900 tokens, stop
`<|im_end|>`. One server load serves all six episodes (no per-
episode reload). Everything else in this lock is unchanged.
Earlier VOID attempts, for the record: (1) MCP-door runs
22:22–22:36 WIB and (2) SSH-door runs 22:42–22:47 WIB — all killed
during model load by the sandbox's earlyoom (journal-verified,
VmRSS ≈14.8 GiB at kill, zero tokens); (3) the 22:49–23:08 WIB
SSH-door run whose six processes completed rc=0 but generated zero
tokens due to the conversation-mode defect above. The counted run
is the first run that produces tokens.
