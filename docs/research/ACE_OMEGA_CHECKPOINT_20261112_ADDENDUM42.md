# ACE Ω Checkpoint — Addendum 42 (demand test results; G3 verification; brain succession stage opened)

Date: 2026-11-13 (Asia/Jakarta). Written directly on `main`.

## 1. Services demand test — done (draft PR #145)

Ladder rung 3 executed as read-only public research
(`docs/research/ACE_SERVICES_DEMAND_TEST_20261113.md`;
every figure cited with source and read date; listed
prices distinguished from transaction evidence):

- **AI/ML evaluation design + sealed-evidence auditing —
  PLAUSIBLE WEDGE.** The one direct analog (a reproducible
  LLM evaluation audit) lists $79–$399; firms charge
  $2,300–$15,000+; demand growth is documented in
  completed-job earnings (AI annotation/labeling +154%
  YoY). Caveat recorded: no visible review counts for the
  audit-shaped SKU — an empty niche under a growing
  umbrella, not proven SKU-level demand.
- **Security review + fixing — PLAUSIBLE WEDGE (narrow).**
  Report-only VAPT is commoditized and compliance work is
  credential-gated; the audit+fix+retest bundle at
  $300–$1,500 has transaction proof (a seller with 46
  reviews at 5.0), and most rivals sell report-only.
  (Band erratum, 2026-11-13: this section originally read
  $500–$1,500; the PR #145 document's wedge band is
  $300–$1,500 — $500 was the floor of the 46-review
  seller's own tier. Aligned at the ops post's check.)
  Indonesian platforms show listings with near-zero
  visible transactions.
- **AI-assisted code repair, standalone — COMMODITIZED.**
  Incumbents hold thousands of reviews at $15–$50 and no
  buyer category exists for "evidence trails". Its one
  salvageable sliver — reviewing AI-generated codebases —
  folds into the security line's bundle.

No offering, price, or outreach follows from this test by
itself; it informs the seller-side design when the ladder
reaches it. The business ladder's research rungs are now
complete (B2A-02 → KBM pilot design → demand test);
Facebook mission verification remains owner-panel-blocked.

## 2. G3 instrument verification — TAHAN with two minor findings

The bench room, as second checker, ran the Task 03
checklist in full against PR #143's build (HEAD c839bba):
overall **TAHAN**. Execution reruns matched exactly (g3
17 OK, g1 8 OK, sweep 268 = 251+17); probes E1–E4 behaved
per spec; the three declared interpretations in Addendum
40 §1 match the code as traced. Two minor findings,
accepted by Ian as correction work:

1. A source-report identity mismatch is recorded **twice**
   in `identity_mismatches` (`_check_report` runs on the
   source report in both the C1 block and the family
   loop). Outcome unaffected.
2. Clause/outcome coherence: with two valid positive
   families plus one extra invalid evaluation entry, C2
   prints FAIL while the overall is TRANSFER_DEMONSTRATED
   — entry-level problems are conflated with requirement
   failure in the clause verdict (the same shape exists in
   C3's missing list). Outcome never exceeds valid
   evidence; semantics to be fixed before the first live
   application.

The operations post runs the same checklist as first
checker; its verdict is recorded when it lands. G3
remains NOT_ASSESSED.

## 3. Local brain succession — stage opened (owner decision, 2026-11-13 ~01:04 WIB)

The owner decided the local director should be replaced
by something faster without losing reliability, and
explicitly approved a new model download for this
(lifting, for this purpose, the standing
no-download-without-approval rule). The current director,
Qwen3-8B, is to be **museum-ized** — registry-retired with
its service record, files preserved, not deleted — but
only after a successor proves itself, so ACE is never
left without a proven local director.

Candidate: **Qwen3-4B Q4_K_M** (~2.5 GB). Sequence
(preregistered before any run): download → bake-off
against the 8B on the existing instruments (director-cycle
validator acceptance on a fixed packet, the B2A dossier
against the same 4/4 bar with the harness table, a repair
fixture through the official path, plus tokens/second and
wall time) → registry swap and museum-izing only on a
pass. For the record: Muse Spark is ACE's
development-engine brain and cannot be the local sovereign
organ (no self-hosted form; account/quota-bound; the
two-hats rule; attested receipts bind to a local GGUF
digest) — the succession is between local models.

## 4. Gate board (unchanged)

G0 session-scoped PASS. G1 MEASURED — DEMONSTRATED.
G2 MEASURED — null ×2. G3, G4, G5 NOT_ASSESSED.
OAIE unproven (`oaie_proven=false`).

## 5. Queue after this addendum

G3 instrument corrections (findings 1–2) → local brain
succession stage (§3: download + preregistered bake-off)
→ A/B/C v3 design (strategy arms) → G3 application
preconditions (P1 refactor first) → G4/G5 instrument
implementations. The 14B partial download still awaits a
resume/delete decision; no action taken.
