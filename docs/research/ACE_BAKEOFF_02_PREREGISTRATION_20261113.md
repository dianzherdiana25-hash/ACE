# BAKE-OFF 02 PREREGISTRATION — FINAL TEXT (NOT YET LOCKED)

Experiment: `brain-bakeoff-02`. Status: **FINAL TEXT —
composed 2026-11-13 by Ian from the PR #153 draft,
the ratification prep
(`evidence/BAKEOFF02_RATIFIKASI_PREP_20261113.md`), and
the hub's ratification decisions. This text is NOT
locked and NOT submitted: kernel submission happens
only on the hub's next ratification act, with the
lock-time steps of §8.5 then executed in order.**

Ratification record: design acted on through hub
decisions of 2026-11-13 (selection ordered, owner
download approval given, validator semantics decided
PER-PROPOSAL 16:07 WIB); the instrument-A reading
decided by hub decision 2026-11-13 19:50 WIB =
**Reading S (strict)**, recorded in §3 and §5.

## 1. Hypothesis (falsifiable, one sentence)

Meta-Llama-3.1-8B-Instruct Q4_K_M matches the
incumbent Qwen3-8B's reliability bars on instruments
A/B/C while running strictly faster on instrument B
(design §1 C-6 form). A fail on any bar falsifies
the succession claim; the candidate is then recorded
as a measured candidate that did not pass, and the
incumbent stays on duty. No re-run until green.

## 2. Candidate

- Candidate: **Meta-Llama-3.1-8B-Instruct Q4_K_M** —
  file `Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf`,
  4,920,739,232 bytes, SHA-256
  `7b064f5842bf9532c91456deda288a1b672397a54fa729aa665952863033557c`
  (== official LFS oid), repo
  `bartowski/Meta-Llama-3.1-8B-Instruct-GGUF`,
  revision `bf5b95e96dac0462e2a09145ec66cae9a3f12067`.
  Named by the selection memo
  (`handover/BAKEOFF02_MEMO_SELEKSI_20261113.md`) as
  the only challenger with a real falsifiable claim
  under C-1…C-6; losers recorded there. Owner
  download approval given via hub 2026-11-13
  ~15:58 WIB. **Custody gate PASSED:** dry-intake
  record `evidence/bakeoff02_intake_record.json`;
  artifact ACCEPTED on the VM 2026-11-13 ~16:31 WIB
  (size + SHA-256 match, GGUF magic verified);
  sandbox copy SHA-256-verified identical.
- Incumbent (baseline candidate): Qwen3-8B Q4_K_M,
  5,027,783,488 bytes, SHA-256
  `d98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785`.
- Excluded by identity: Qwen3-4B Q4_K_M
  (`7485fe6f…f5`, measured fail in bake-off 01 — not
  re-run as-is, design C-1) and the corrupted 14B
  partial on disk.

## 3. Instruments (unchanged from bake-off 01, C-2)

One attempt per instrument; the incumbent's proven
router configuration (temperature 0.3, max_tokens
700, timeout 900 s) through the attested server on
the VM path, exactly as bake-off 01; papers-over
differences are forbidden. Sandbox benchmark numbers
are a different environment and do NOT enter this
bake-off; the speed bar is instrument B's wall on
the VM path.

- **A** — director cycle on the fixed packet (same
  packet as bake-off 01), judged by the pinned
  hardened validator (§4) under its operative
  PER-PROPOSAL semantics. **Bar (Reading S, hub
  decision 2026-11-13 19:50 WIB): the reply counts
  as ACCEPTED iff the validator rejects ZERO
  proposals.** Per-proposal semantics governs the
  validator's records and behaviour; the succession
  bar keeps bake-off 01 stringency so margins stay
  comparable across the series.
- **B** — B2A-02 dossier decision over the
  harness-computed comparison table (same packet).
  Bar: decision_score 4/4 under the hardened
  validator; any citation violation inside the
  decision reply rejects the decision, and a
  rejected decision scores 0 (unchanged under
  either §B reading of the prep: the decision is a
  single unit whose support must be clean).
- **C** — sealed Keamanan-01 repair fixture. Bar:
  6/6 cases, LOCALLY_VERIFIED, one attempt.
- **Speed** — instrument B wall strictly below the
  incumbent's recorded 535.6 s.

## 4. Validator (pinned, design §2)

The citation validator for A and B is the hardened
build implementing V-1…V-6: **`ace.citation_validator`
v1.0.0** (PR #162, commit 5f7c347); rejection schema
`ace.citation_rejection.v1`, report schema
`ace.citation_validation.v1`; ruleset_digest
`59ce35e814d0b88f3d1d2ee3cfe3410d6ee3899dc8d99ff4ec2625ef2e689295`;
code_digest
`b18e9d3a25b19f2d57797fafcd27d4e8d9b1d7d10e6f530c2acd2559cc3700ba`
(== SHA-256 of `citation_validator.py`). 16/16 tests
green, including the bake-off 01 fabrication
regression fixture. Operative semantics:
PER-PROPOSAL (hub decision 2026-11-13 16:07); every
report also carries `legacy_whole_reply_rejected`,
so both readings remain checkable from the same
evidence. V-5 wiring note: the build's rejection
ledger is a self-contained kernel-style hash chain
(no HMAC split custody); appending rejection entries
into this experiment's kernel at run time is the run
harness's job and is exercised in the dry-intake
check (§5). Changing the validator after this
registration invalidates the run at audit.

## 5. Pass rule (ONE composite metric, design §3)

`succession_margin` = min(A margin, B margin,
C margin, speed margin), where A margin = +1 if
accepted under §3's Reading-S bar else −1; B margin
= decision_score − 4; C margin = cases_passed − 6;
speed margin = (535.6 − B_wall_seconds) / 535.6.
Kernel pass rule:
`{"metric": "succession_margin", "gte": 0}`.
Per-bar results are telemetry only.

**Dry-intake check (mandatory, pre-lock):** on the
fresh kernel for this experiment, a synthetic result
carrying `succession_margin` is pushed through the
kernel's verdict derivation and shown to intake
before the real registration locks (design §3). If
intake fails, this registration does not lock.

## 6. Custody and audit

Split custody in a fresh OMEGA-06 kernel root:
`~/workspace/ace-omega/bakeoff02-kernel/`; split-
custody keys `bakeoff02-candidate-key` /
`bakeoff02-evaluator-key`; canary generated at lock.
Candidate custodian = the execution room; evaluator
custodian = the sealed evaluation side; distinct
HMAC keys. Custodies precede registration: candidate
artifact (by §2 identity), incumbent baseline,
evaluator = the pinned validator (§4) + instrument
packets (bake-off 01 packets, unchanged per C-2).
Kernel audit must return CLEAN — including the
chained rejection entries (V-5) — before any score
is read.

## 7. Consequences (written in advance, design §4)

- **Pass:** the brain registry records the swap for
  the measured-director role inside experiments; the
  incumbent is museumed (not deleted), per
  multi-brain sovereignty; the succession is
  reported to the owner as a completed stage. Scope
  note: this succession concerns the
  measured-director role; it does not by itself
  alter any working-brain designation made under
  the owner's model doctrine.
- **Fail:** the candidate is recorded in the registry
  as a measured candidate that did not pass, with the
  deciding bar named from telemetry; the incumbent
  stays on duty; no immediate successor attempt is
  implied.
- **Abstain** (infrastructure failure before any
  instrument completes, audit not CLEAN, validator
  changed): recorded with the reason; the
  registration is spent either way.

## 8. Submission checklist

1. Design ratified (PR #152) — DONE via hub
   decisions of 2026-11-13; instrument-A reading
   ratified (Reading S) 2026-11-13 19:50 WIB.
2. Validator hardening built, tested (fabrication
   regression + multi-fabrication enumeration +
   chain-tamper), digest pinned — DONE (§4); an
   independent raw-evidence verifier pass over the
   build may be run at lock time under the
   single-worker pattern.
3. Selection memo recorded (chosen candidate +
   losers with failing criteria) — DONE (§2).
4. Owner approval for any download — DONE; artifact
   ACCEPTED on the VM (§2).
5. Custodies registered; dry-intake check passed;
   then submit and record the protocol hash in the
   checkpoint lineage — **PENDING the hub's lock
   act. This text alone locks nothing.**

— End of final text. Composed by Ian (Muse) from
the PR #152 design, the PR #153 draft, the
ratification prep, and the hub's ratification
decisions; brain of origin recorded. No kernel
submission, no run, no registry change follows from
this text until the hub's lock act.
