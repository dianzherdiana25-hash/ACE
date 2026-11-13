# BAKE-OFF 02 — RATIFICATION PREP (2026-11-13)

Prepared by Ian (main execution room) for hub ratification.
Source text: `docs/research/ACE_BAKEOFF_02_PREREGISTRATION_DRAFT_20261113.md`
(PR #153; local copy `~/workspace/ace-omega/bakeoff02_prereg_text.md`).
Status of the source text: **still DRAFT — nothing locked, nothing
submitted.** This prep resolves every ⟨TBD-GATE⟩ that evidence now
settles, and names the ONE interpretive decision that is the hub's
to make at ratification. Lock-time mechanics (kernel root, keys,
canary, dry-intake) stay lock-time, per the established pattern.

## A. Fields now resolvable (evidence-backed)

1. **Candidate (§1, §2): Meta-Llama-3.1-8B-Instruct Q4_K_M.**
   - File `Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf`,
     4,920,739,232 bytes, SHA-256
     `7b064f5842bf9532c91456deda288a1b672397a54fa729aa665952863033557c`
     (== official LFS oid), repo
     `bartowski/Meta-Llama-3.1-8B-Instruct-GGUF`,
     revision `bf5b95e96dac0462e2a09145ec66cae9a3f12067`.
   - Selection memo: `handover/BAKEOFF02_MEMO_SELEKSI_20261113.md`
     (the only challenger with a real falsifiable claim under
     C-1…C-6; losers recorded there).
   - Owner download approval: given via hub 2026-11-13 ~15:58 WIB.
   - **Custody gate PASSED:** dry-intake record
     `evidence/bakeoff02_intake_record.json`; download ACCEPTED on
     the VM 2026-11-13 ~16:31 WIB (size + sha256 match, GGUF magic);
     sandbox copy sha256-verified identical.
   - Succession claim (final wording for the locked text): the
     candidate passes all three instruments (A director cycle,
     B B2A-02 dossier 4/4 with zero citation violations, C sealed
     repair 6/6) with `succession_margin` ≥ 0 against the
     incumbent's bake-off 01 numbers.

2. **Validator (§4): PINNED.**
   - `ace.citation_validator` v1.0.0 (PR #162, commit 5f7c347);
     rejection schema `ace.citation_rejection.v1`, report schema
     `ace.citation_validation.v1`;
     ruleset_digest
     `59ce35e814d0b88f3d1d2ee3cfe3410d6ee3899dc8d99ff4ec2625ef2e689295`;
     code_digest
     `b18e9d3a25b19f2d57797fafcd27d4e8d9b1d7d10e6f530c2acd2559cc3700ba`
     (== sha256 of `citation_validator.py`); 16/16 tests green,
     including the bake-off 01 fabrication regression fixture.
   - **Operative semantics: PER-PROPOSAL** (hub decision
     2026-11-13 16:07, Ian's recommendation adopted); every report
     also carries `legacy_whole_reply_rejected`, so both readings
     remain checkable from the same evidence.
   - Known open wiring note (unchanged since the build): V-5
     custody in the build is a self-contained kernel-style hash
     chain (no HMAC split custody); appending rejection entries
     into the experiment kernel at run time is the run harness's
     job, to be exercised in the dry-intake check.

3. **Inference path (§3):** the VM attested-server path, exactly
   as bake-off 01 (incumbent's proven router configuration:
   temperature 0.3, max_tokens 700, timeout 900 s). The candidate
   file is present and accepted on the VM. **The sandbox bench
   numbers (Llama pp512 6.48 / tg128 0.63 t/s, 2026-11-13) are a
   different environment and do NOT enter this bake-off** — the
   speed bar remains instrument B's wall on the VM path vs the
   incumbent's recorded 535.6 s.

4. **Checklist (§8) state:** (1) design — acted on through hub
   decisions of 2026-11-13 (selection ordered, download approved,
   semantics decided); formal ratification of THIS text is the
   pending hub act. (2) validator — built + tested + digest
   pinned (above); an independent raw-evidence verifier pass over
   the build can be run at lock time under the single-worker
   pattern. (3) selection memo — recorded. (4) owner download
   approval — given. (5) custodies + dry-intake — lock-time.

## B. The ONE ratification decision (hub's call)

Instrument A's bar as drafted reads: the director-cycle reply is
"ACCEPTED whole by the pinned hardened validator" (A margin = +1
if accepted, else −1). That wording predates the PER-PROPOSAL
decision. Two readings:

- **Reading S (strict, Ian's recommendation):** A counts as
  ACCEPTED iff ZERO proposals in the reply are rejected (every
  proposal survives). Per-proposal semantics governs the
  validator's records and behaviour; the succession bar keeps
  bake-off 01 stringency, so margins stay comparable across the
  bake-off series (design C-2, same-instrument evaluability).
- **Reading P (permissive):** A counts as ACCEPTED iff at least
  one proposal survives. This lowers the bar versus bake-off 01
  and breaks comparability with the incumbent's recorded pass.

Ian recommends **Reading S**. Under either reading, instrument B
is unchanged in effect: any citation violation inside the
decision reply rejects the decision (score 0), because the
decision is a single unit whose support must be clean; the
per-proposal granularity shows in the rejection records.

## C. Lock-time mechanics (proposed, set at submission)

- Kernel root: `~/workspace/ace-omega/bakeoff02-kernel/`
  (fresh OMEGA-06 root, experiment-scoped, per pattern).
- Split-custody keys: `bakeoff02-candidate-key` /
  `bakeoff02-evaluator-key`; canary generated at lock.
- Custodies before registration: candidate artifact (identity in
  §A.1), incumbent baseline (identity in draft §2), evaluator =
  pinned validator (§A.2) + instrument packets (bake-off 01
  packets, unchanged per C-2).
- Mandatory dry-intake check on the fresh kernel before the real
  registration locks (draft §5); if intake fails, no lock.
- Pass rule unchanged: `{"metric": "succession_margin",
  "gte": 0}` with the draft §5 component definitions.

## D. What this prep does NOT do

No kernel submission, no lock, no run, no registry change. The
run executes at its queue turn after hub ratification of the
text (including the §B reading) and the lock-time steps in §C.

— Ian, 2026-11-13. Brain of origin: Muse (execution room).
