# PROPOSER ENGINE — STAGE 1 INAUGURAL SIMULATION REPORT

**Run date: 2026-11-13 (generations 23:19–00:08 WIB). Review type:
SIMULATION — no proposal was dispatched or executed.**
Brain: Qwen3-30B-A3B Q4_K_M, llama-server b12316 (Amendment A1),
-t 1, temperature 0, seed 42, max 900 tokens, stop `<|im_end|>`.
Machine-readable report: `simulation_report.json` (produced by
`proposer_simulation.py` from the frozen generations in
`generations/`, walls in `generations/walls.json`).

## Per-episode results

| Episode | Wall (s) | Tokens | Validator | Proposer | Historical | Diff |
|---|---|---|---|---|---|---|
| EP1 G3 application | 699 | 887 | REJECTED | 0 | 100 | −100 |
| EP2 abc-v3 | 698 | 900 (cap) | no parseable package | 0 | 100 | −100 |
| EP3 round-2 gate | 705 | 900 (cap) | no parseable package | 0 | 100 | −100 |
| EP4 control-regression attribution | 764 | 841 | REJECTED | 0 | 90 | −90 |
| EP5 G4 inheritance | 863 | 891 | REJECTED | 0 | 80 | −80 |
| EP6 per-task recording | 779 | 898 | REJECTED | 0 | 80 | −80 |

Mean proposer score 0.0; mean historical score 91.7;
**mean diff −91.67; bootstrap 95% CI lower bound −98.33**
(seed 20261113, 10,000 resamples).

## Failure anatomy (from the frozen generations, firsthand)
The result is a NEAR-MISS failure, and its shape is the finding:
1. **One systematic type deviation, 6/6 episodes:** the model
   emitted `uncertainties` as a single string, not a list of
   strings. The fail-closed validator rejected EP1/EP4/EP5/EP6 on
   exactly this one reason; their JSON was otherwise complete and
   well-formed (claims testable, evidence hashes copied exactly,
   stop controls present, ratification vocabulary correct).
2. **Token-cap truncation, 2/6 episodes:** EP2 and EP3 hit the
   locked 900-token cap a few tokens before the closing braces
   (pretty-printed JSON + 64-hex hashes tokenize expensively), so
   no balanced JSON object exists to validate.
No episode failed on reasoning content the rubric could reach —
the rubric never scored them, because validation is fail-closed
and a rejected package scores 0 by the locked rule. That rule is
doing its job: in a live setting these packages would have been
returned for repair, not ratified.

## Exit gate (locked in PREREG_LOCK before the run)
- **Quality clause: FAIL.** Mean diff −91.67 < margin −10;
  CI lower −98.33 < floor −20. Non-inferiority is not shown; it is
  refuted at this configuration.
- **Time clause: NOT_ASSESSABLE** (locked): no historical
  drafting-time baseline exists in the official record.
  Descriptive only: mean generation wall 751 s/episode
  (698–863 s), total 4,508 s for six packages.
- **EXIT GATE VERDICT: NOT_PASSED.**

## VOID attempts preceding the counted run (not scored)
(1) MCP-door and (2) SSH-door llama-cli runs, 22:22–22:47 WIB:
killed during model load by the sandbox's earlyoom (journal-
verified, VmRSS ≈14.8 GiB at kill) — zero tokens. (3) The
22:49–23:08 WIB llama-cli run: processes exited rc=0 but
generated zero tokens (llama-cli b12316 conversation-mode defect;
see PREREG_LOCK Amendment A1). One coordination incident is
recorded against this lane: a llama-server launched 23:10:58 WIB
without the hub's explicit empty-house sign pressed RAM while a
sibling lane's bench was loading; earlyoom killed that bench
(23:11:15). The lane stood down on the hub's correction and the
counted run began only after the hub's go and a verified empty
house (MemAvailable 19.5 GiB, no sibling model resident).

## What Stage 1 established
- The package schema + fail-closed validator + episode/rubric
  harness work end-to-end and are test-covered (17 tests).
- The adopted local brain, at temp 0 with a 900-token cap and a
  prose schema description, does NOT yet produce ratifiable
  packages: it needs either schema-constrained decoding (grammar)
  or a repair loop — both are Stage-2 design questions, NOT
  performed here, because the locked protocol allowed one counted
  run and no auto-retry.
- Stage 2 therefore does NOT open on this evidence. The proposer
  engine stays simulation-only.
