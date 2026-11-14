# PROGRAM VERDICT — PROPOSER ENGINE STAGE 1 EXIT GATE: NOT_PASSED

> **Recorded verdict of the program**, issued 2026-11-14 by Ian
> (main execution session) at the hub's act (Misi 7), over the
> evidence package of draft PR #191 (head `09ccf5d`, hub-verified).
> This document is the verdict of record: the proposer's stage-1
> result is no longer merely the content of a lane PR. Draft PR
> only, no merge — the verdict takes recorded effect on the hub's
> verification of this package's head.
>
> Evidence: PR #191 — `evidence/proposer_stage1/PREREG_LOCK.md`
> (locked 2026-11-13 ~22:20 WIB, before any generation),
> `evidence/proposer_stage1/SIMULATION_REPORT.md` +
> `simulation_report.json`, frozen generations, `outcomes.json`;
> engine in `code/ace_operational/proposer_{schema,validator,
> rubric,episodes,simulation}.py`, 17/17 tests passing.

## The verdict

**PROPOSER ENGINE STAGE-1 EXIT GATE: NOT_PASSED.**

The run: corrected simulation, generations 2026-11-13 23:19 –
2026-11-14 00:08 WIB, via llama-server `/completion` (Amendment
A1). Brain: Qwen3-30B-A3B Q4_K_M, llama.cpp b12316, `-t 1`,
temperature 0, seed 42, max 900 tokens. Review type: SIMULATION —
no proposal was dispatched or executed; there is no execution
path in the code.

## Numbers, exactly as frozen

| Episode | Wall (s) | Tokens | Validator | Proposer | Historical | Diff |
|---|---|---|---|---|---|---|
| EP1 G3 application | 699 | 887 | REJECTED | 0 | 100 | −100 |
| EP2 abc-v3 | 698 | 900 (cap) | no parseable package | 0 | 100 | −100 |
| EP3 round-2 gate | 705 | 900 (cap) | no parseable package | 0 | 100 | −100 |
| EP4 control-regression attribution | 764 | 841 | REJECTED | 0 | 90 | −90 |
| EP5 G4 inheritance | 863 | 891 | REJECTED | 0 | 80 | −80 |
| EP6 per-task recording | 779 | 898 | REJECTED | 0 | 80 | −80 |

- **Quality clause: FAIL.** Proposer mean 0.0 (0/6 episodes)
  vs historical mean 91.7 (100/100/100/90/80/80). Mean paired
  diff **−91.67** against the locked non-inferiority margin
  **−10**; bootstrap 95% CI lower bound **−98.33** (seed
  20261113, 10,000 resamples) against the locked floor **−20**.
  Non-inferiority is not merely unshown; it is refuted at this
  configuration.
- **Time-saving clause: NOT_ASSESSABLE** — locked as such in
  the preregistration before the run (no historical drafting-
  time baseline exists in the official record). Descriptive
  only: mean generation wall 751 s/episode (698–863 s), total
  4,508 s for six packages. No time claim is made or implied.

## Failure anatomy, exactly as frozen

The failure is a near-miss failure, and its shape is the finding:

1. **One systematic type deviation, 6/6 episodes:** the model
   emitted the `uncertainties` field as a single STRING instead
   of a list of strings. The fail-closed validator rejected
   EP1/EP4/EP5/EP6 on exactly this one reason; their JSON was
   otherwise complete and correct — claims testable, evidence
   hashes copied exactly, stop controls present, internal-
   ratification vocabulary right.
2. **Token-ceiling truncation, 2/6 episodes:** EP2 and EP3 hit
   the locked 900-token cap a few tokens before the final
   closing brace (pretty-printed JSON + 64-hex hashes are
   token-expensive), so no complete JSON object existed to
   validate.

No episode failed on reasoning content the rubric could reach:
under the locked rule a validator-rejected package scores 0,
so the rubric never scored any package. That rule stands as
designed — in a live setting these packages would have been
returned for repair, not ratified.

## Procedural integrity of the counted run

- Preregistration locked before any generation; ONE counted
  run; no auto-retry; nothing was tried outside the locked
  protocol.
- Three preceding attempts are recorded VOID, not scored: two
  killed during model load by the sandbox's earlyoom
  (22:22–22:47 WIB, zero tokens), one zero-token run exposing
  a llama-cli conversation-mode defect (22:49–23:08 WIB) —
  corrected by Amendment A1 (interface changed to llama-server
  `/completion`) before the counted run.
- One coordination incident is recorded against the lane in
  its own report: a llama-server launched 23:10:58 WIB without
  the hub's explicit empty-house sign; earlyoom killed a
  sibling lane's bench (23:11:15). The lane stood down on the
  hub's correction; the counted run began only after the hub's
  go and a verified empty house (MemAvailable 19.5 GiB), and
  the lane's formal all-doors empty sign closed the night.

## Locked consequences

1. **Stage 2 is NOT opened** on this evidence.
2. **The proposer engine stays simulation-only.** No proposal
   it composes may be dispatched or executed; the code carries
   no execution path, and none is authorised by this verdict.
3. **Reopening requires a NEW preregistration** — a fresh
   locked protocol, not an amendment of this run and not a
   re-run of it. The named design questions such a
   preregistration must answer are exactly two:
   **grammar-constrained decoding** (schema enforced at
   generation time) or a **closed repair loop** (validator
   rejections returned to the model under a locked repair
   protocol). Both were outside this run's locked protocol;
   neither was tried.
4. The stage-1 artifacts (schema, fail-closed validator,
   rubric, frozen episodes, this verdict's evidence package)
   remain valid program assets: what failed is the adopted
   brain's unaided package production at this configuration —
   temp 0, 900-token cap, prose schema description — not the
   gate machinery, which worked end-to-end and did its job.

— Recorded by Ian, 2026-11-14. All figures transcribed from
PR #191's frozen artifacts (`SIMULATION_REPORT.md`,
`simulation_report.json`, `PREREG_LOCK.md`) and checked against
them line by line for this record.
