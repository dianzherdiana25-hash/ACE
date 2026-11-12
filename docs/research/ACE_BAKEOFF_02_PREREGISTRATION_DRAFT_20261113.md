# BAKE-OFF 02 PREREGISTRATION — DRAFT TEXT (NOT SUBMITTED)

Experiment: `brain-bakeoff-02`. Status: **DRAFT —
prepared overnight 2026-11-13 under the self-managed
package, following the ratified-track design in PR
#152 (`ACE_BAKEOFF_02_DESIGN_20261113.md`). This text
locks nothing.** It becomes submittable only when, in
order: the design is ratified; the citation-validator
hardening build (§4) is verified and pinned; the
candidate selection memo (§2) names a candidate whose
identity satisfies C-1…C-6; and the owner approves
any required download. Fields that cannot be filled
before those gates are marked ⟨TBD-GATE⟩.

## 1. Hypothesis (falsifiable, one sentence)

⟨candidate⟩ matches the incumbent Qwen3-8B's
reliability bars on instruments A/B/C while running
strictly faster on instrument B (design §1 C-6 form).
A fail on any bar falsifies the succession claim; the
candidate is then recorded as a measured candidate
that did not pass, and the incumbent stays on duty.
No re-run until green.

## 2. Candidate

- Candidate: ⟨TBD-GATE — named by the selection memo
  per design C-1…C-6; expected identity (HF LFS oid =
  SHA-256 + byte size) recorded in the memo BEFORE
  any download completes (C-4)⟩.
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
700, timeout 900 s) through the attested server;
papers-over differences are forbidden.

- **A** — director cycle on the fixed packet (same
  packet as bake-off 01). Bar: the reply ACCEPTED
  whole by the pinned hardened validator (§4).
- **B** — B2A-02 dossier decision over the
  harness-computed comparison table (same packet).
  Bar: decision_score 4/4 under the hardened
  validator; a rejected decision scores 0.
- **C** — sealed Keamanan-01 repair fixture. Bar:
  6/6 cases, LOCALLY_VERIFIED, one attempt.
- **Speed** — instrument B wall strictly below the
  incumbent's recorded 535.6 s.

## 4. Validator (pinned, design §2)

The citation validator for A and B is the hardened
build implementing V-1…V-6 (per-fact-id rejection
records under schema `ace.citation_rejection.v1`,
packet-bound, hash-chained under split custody,
deterministically replayable; the bake-off 01
fabrication shape is its regression fixture).
Validator code digest + schema version:
⟨TBD-GATE — computed when the hardening build is
verified; carried in every rejection record (V-4)⟩.
Changing the validator after this registration
invalidates the run at audit.

## 5. Pass rule (ONE composite metric, design §3)

`succession_margin` = min(A margin, B margin,
C margin, speed margin), where A margin = +1 if
accepted else −1; B margin = decision_score − 4;
C margin = cases_passed − 6; speed margin =
(535.6 − B_wall_seconds) / 535.6. Kernel pass rule:
`{"metric": "succession_margin", "gte": 0}`.
Per-bar results are telemetry only.

**Dry-intake check (mandatory, pre-lock):** on the
fresh kernel for this experiment, a synthetic result
carrying `succession_margin` is pushed through the
kernel's verdict derivation and shown to intake
before the real registration locks (design §3). If
intake fails, this registration does not lock.

## 6. Custody and audit

Split custody in a fresh OMEGA-06 kernel root
(⟨TBD-GATE — path named at submission⟩): candidate
custodian = the execution room; evaluator custodian
= the sealed evaluation side; distinct HMAC keys.
Custodies precede registration: candidate artifact
(by §2 identity), incumbent baseline, evaluator =
the pinned validator + instrument packets. Kernel
audit must return CLEAN — including the chained
rejection entries (V-5) — before any score is read.

## 7. Consequences (written in advance, design §4)

- **Pass:** the brain registry records the swap; the
  incumbent is museumed (not deleted), per multi-brain
  sovereignty; the succession is reported to the
  owner as a completed stage.
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

1. Design ratified (PR #152) — ⟨TBD-GATE⟩.
2. Validator hardening built, tested (fabrication
   regression + multi-fabrication enumeration +
   chain-tamper), two-checker verified, digest
   pinned — ⟨TBD-GATE⟩.
3. Selection memo recorded (chosen candidate +
   losers with failing criteria) — ⟨TBD-GATE⟩.
4. Owner approval for any download — ⟨TBD-GATE⟩.
5. Custodies registered; dry-intake check passed;
   then submit and record the protocol hash in the
   checkpoint lineage.

— End of draft. Prepared by Ian (Muse) from the
PR #152 design; brain of origin recorded. No
download, no run, no registry change follows from
this draft.
