# ACE Ω — Checkpoint Addendum 59 (2026-11-13, evening desk)

**Subject: A/B/C v3 run (abc-v3-01) COMPLETE — G2 MEASURED NOT_DEMONSTRATED (third
measured null); independent verifier TAHAN. Massive Capability Package report
(items 1–11) folded in. Round-2 gate application complete in the sandbox;
finalize is next in the same session.**

Recorded by Ian (main execution room), Muse (ACE Omega operator). Gate-board
moves in this addendum rest on the finalized kernel record plus an independent
verifier subagent that received RAW evidence only (single-worker pattern).

---

## 1. The v3 run — final numbers

Preregistration: locked text sha256
`55b6331eeed0cfc4779b09114cc74d7c48c47b1a125759bc6296105e3e6529be`; kernel
protocol `8591b93814759d5485be3f9e8b47e31a08aa7b1fc41e14b2707b2aa46b975c1a`;
pass rule: differentiation_index_pp ≥ 0 (ONE composite,
DI = min((C−A) − 15pp, (B−A) − 5pp, control margin, regression-relative)).

| Band | Eval A | Eval B | Eval C | Ctrl A | Ctrl B | Ctrl C | DI (pp) | Band reading | Wall (s) |
|---|---|---|---|---|---|---|---|---|---|
| 20261501 | 0/30 | 30/30 | 30/30 | 34/34 | 32/34 | 32/34 | −5.88 | NOT_DEMONSTRATED | 1,111.5 |
| 20261502 | 0/30 | 30/30 | 30/30 | 34/34 | 34/34 | 34/34 | 0.0 | DIFFERENTIATION_DEMONSTRATED | 2,951.6 |
| 20261503 | 0/30 | 30/30 | 30/30 | 33/33 | 33/33 | 33/33 | 0.0 | DIFFERENTIATION_DEMONSTRATED | 619.8 |
| **Pooled** | **0/90** | **90/90** | **90/90** | **101/101** | **99/101** | **99/101** | **−1.9801980198019749** | **NOT_DEMONSTRATED** | — |

DI terms (pooled): (C−A) − 15pp = **+85.0**; (B−A) − 5pp = **+95.0**;
control margin = **−1.9801980198019749pp** — the sole binding term, arising
entirely from band 20261501, where the enriched-catalog arms solved 2 fewer
control tasks than catalog-only arm A. Bands 2 and 3 show zero control
regression. Calibration gate (pooled denominator): PASS in every band and
pooled. s2 chain usage: 18 / 17 / 18 tasks per band (reported stratum, not a
run condition, per the locked amendment).

Assessment (abc_v3_scorer, criteria v1): **NOT_DEMONSTRATED** — clauses
report_validity PASS, calibration_gate PASS, completeness PASS,
differentiation_index FAIL (named: "differentiation index is negative
(−1.98pp < 0)"). Kernel: exactly ONE result row; derived verdict **fail**;
audit **CLEAN**. Evidence: `evidence/abc_v3_run.json`,
`evidence/abc_v3_finalize.json`.

**G2 board: MEASURED — NOT_DEMONSTRATED.** v1 (saturation), v2 (saturation),
v3 (this run) are three measured nulls of three different named shapes. The
locked preregistration's pre-written consequence applies — no re-run of this
design; §4 records the agenda item this falsification births.

### Invocation history (full record: `evidence/abc_v3_run_notes.json`)

The run completed across four invocations under ONE locked preregistration,
because the Muse VM was replaced/rebooted three times on 2026-11-13
(12:49, 14:32, 16:43 WIB). Invocations 1 and 2 are VOID (infrastructure);
invocation 3 is VOID only for band 20261503's arm C, which it was executing
when the third reboot hit; invocation 4 (relaunched 16:50 WIB) resumed from
the hardened driver's checkpoints — completed bands and arms were NOT
re-run — and finished at 17:00:49 WIB. The kernel was written exactly once,
by the finalize (17:03 WIB), never by a driver invocation. No number from a
VOID invocation is used anywhere.

### Independent verification (verifier subagent, raw evidence only): TAHAN

All six checks PASS, no discrepancies named: pooled counts re-summed from the
band records; DI recomputed by hand = −1.9801980198019749 (identical);
`assess_abc_v3` re-run independently — assessment deep-equals the finalize's,
per band and pooled; kernel audited independently on a byte-identical copy —
CLEAN, 1 result verified, digests match the preregistration record
(candidate `b042614d…`, evaluator `c6ca3421…`, fixture `18d854cf…`); band
records deep-equal the run-state checkpoints; invocation timeline coherent
with file timestamps (VOID work is not silently included — band 1's arm C
checkpoint is timestamped inside invocation 3's window, i.e. re-executed,
exactly as the notes state).

### Honest reading

The strategy differentiation on the evaluation universe is total (0% → 100%
for both enriched arms) and the effect terms clear their bars by +85pp and
+95pp. The composite fails on the one term the preregistration designed to
catch exactly this: a small control regression (2 of 101 tasks) in one band
of three. DI is a shortfall index (DI ≤ 0 by construction; 0 is the pass
line). −1.98pp is close in magnitude and a fail by the locked rule; it is
recorded as a fail without reinterpretation.

## 2. Consequence — new agenda item (falsification doctrine)

**Agenda item born from abc-v3-01: the control-regression phenomenon under
catalog enrichment.** Measured fact to explain: in band 20261501, arms B/C
(60 admitted keys + 1 chain) solved 32/34 control tasks that arm A solved
34/34, while gaining +100pp on evaluation; bands 2–3 (6–7 admitted keys)
show no regression. Candidate mechanisms, to be separated by a NEW
falsifiable design (never a v3 re-run): score-call budget contention,
distractor interference from large admitted catalogs, search-order effects.
Origin: falsification consequence of abc-v3-01, recorded per the
agenda-source doctrine.

## 3. Massive Capability Package (owner mandates 2026-11-13 ~12:22 + ~12:36 WIB) — items 1–11, complete

1. **Bake-off 02 citation-validator hardening (V-1..V-6)** — BUILT, draft
   PR #162: per-fact-id structured rejections (`ace.citation_rejection.v1`),
   packet binding, hash-chained rejection ledger, deterministic replay,
   bake-off-01 regression fixture; 16/16 tests. Semantics resolved by hub
   decision 2026-11-13 16:07: PER-PROPOSAL operative, legacy whole-reply
   reading still recorded in every report.
2. **Third problem family `text_transform`** — BUILT, draft PR #164: 6 defect
   classes, disjoint ontology (lexical, str→str); initial census 60/60 built,
   0 validity failures. Named limit: no authored substrate yet
   (`text-prototype-v0`); pair partial-fix identifiability is future work.
3. **Catalog gap-analysis tool** — BUILT, draft PR #163: 27/27 tests. First
   real output (v4 evidence × v4 catalog): no measured class is a gap or
   saturated; the ranked gaps are unmeasured substrate classes —
   diagonal_moves, no_up, start_offset, walls_passable; `compare_swap`
   appears in ZERO admitted keys; 32 eval tasks of headroom across the 4
   partial classes.
4. **Weakness-targeting curriculum generator** — BUILT, draft PR #165:
   17/17 tests; identifiability control per task (a named rival must fail
   the shown set, else the task is rejected and counted). Wiring demo on the
   real v4 gap report: 6 tasks, 0 rejections; recorded honestly — the
   dist_step_2 task excludes only 5/7 rivals.
5. **Automated regression anchor** — harness BUILT (`regression_anchor.py`),
   design draft PR #167. Self-test 1 (identical v4 catalog vs itself, smoke
   battery 16): 16/16 both sides, verdict NO_REGRESSION. Self-test 2
   (empty candidate catalog) is queued immediately after the round-2 gate
   finalize; standing rule: any future catalog change runs the anchor
   before the catalog is used in a measurement.
6. **Publishable English fiction** — DONE (handover): English ADAPTATION of
   Bab 1 of the Warung novelette (2,426 words, all 26 beats preserved) +
   5-stage pipeline memo with Royal Road assessment. Honest grade: a genuine
   adaptation, NOT release-grade (Indonesian sentence rhythms show through);
   Royal Road requires the AI-Generated tag for AI adaptation without a
   human checker — the human-checker pass is the hinge for the honest label.
7. **TTS narration pipeline** — DONE (handover): full Bab 1 test narration
   (15:37 audio, 57 chunks, ~848 chars/min synthesis). The voice catalog
   holds ZERO Indonesian voices — narration uses an English-catalog voice
   with `--language id`, so a human pronunciation listen-check is a
   mandatory QA gate. Bab 1 verdict: FAIL for single-voice release
   (dialogue 21.2% of chars, 7 speakers, a 696-char read-aloud document,
   24/44 rapid transitions); the file stands as pipeline proof, not a
   release candidate.
8. **Cinematic illustration consistency** — DONE (handover): character-lock
   method (reference sheet + verbatim character block + verbatim style
   block); drift test PASSED (same recognisable Kirana in both cards; two
   within-tolerance drifts: bun tightness, lighting-driven skin tone). The
   media pipeline offers NO numeric seed — the lock is the reference image
   plus the two text blocks.
9. **Vertical teaser video** — clip GENERATION is permanently blocked for
   this account/region (HTTP 403 `video_not_available`, standing limit);
   memo + machine-verified quote delivered. Hub decision 2026-11-13 16:07:
   the substitute still-image pan-zoom format is APPROVED for the free zone
   (main account stays quality-gated); conveyed as an addendum in the memo.
10. **Direct-sales kit** — DONE (handover/kit-jualan/): service agreement
    template (incl. the mandatory Pasal 8 written-permission clause for
    Package A), invoice (INV/[YYYYMM]/[NNN]), DP-50% flow (work never starts
    before a verified DP), QRIS receipt. Full account numbers appear
    NOWHERE in the kit by design — bracketed placeholders only.
11. **Platform contract literacy** — DONE (handover): 7 platform tables × 5
    rows (revenue share, exclusivity, AI clause, termination, payment).
    Correction recorded: the earlier claim that KBM's revenue share appears
    in no official text is SUPERSEDED — the account-read Monetize Policy
    gives the tiered author share 100% (≤Rp100k) → 90% → 80% → 70% → 65% →
    60% (>Rp5jt), premium chapter Rp1.500 / 15 gold coins, transfer
    Rp2.900. Top-3 unverified cells: KBM exclusive-contract duration;
    Fastwork withdrawal fee (official self-contradiction: Rp3.000 flat vs
    free); Lynk.id fee stacking on the 5% transaction fee.

## 4. Pointers (same reporting window)

- **Round-2 gate:** replication guard PASSED 3/3 in the sandbox; application
  COMPLETE in the sandbox (band 72000–72099: A 14, B 18, R 18; discriminating
  n=18; B_disc 100%; capture 1.0; control margin 0.0; **round2_index 0.0**).
  Finalize on the VM (dossier → kernel → audit → assess_round2) runs next in
  this session, then the empty-catalog regression-anchor self-test.
- **Escalation bench (owner mandate 16:35 WIB):** dry-intake custody locked
  for Qwen3-30B-A3B Q4_K_M (18,556,685,824 B, sha256 `0d003f66…`) and
  Qwen3-32B Q4_K_M (19,762,149,024 B, sha256 `efd97156…`) — record
  `evidence/bakeoff_arena30b_intake_record.json`; downloads inside the
  sandbox interrupted at A3B ≈99.5% by an MCP endpoint HTTP 502 window;
  arena-expansion design note shipped as draft PR #168. Inference route:
  hub chose (a)+(c) — kancuto raises the sandbox-mcp unit MemoryMax to 20G
  and verifies by loading the Llama GGUF himself (Manus task
  7PmtCZdgR4iYUr4mGs8wds); no model loads through MCP from this room until
  the hub confirms the unit change.
- **Hub decisions 2026-11-13 16:07 executed:** G5 harvest-period draft
  finalized with the locked cutoff 12 Nov → 30 Nov 2026 (PR #156 head
  c8162bb, sha256-verified); PR hygiene Group A closed (93 → 88 open);
  Group B batch 1 closed (88 → 78), batch 2 in flight; pan-zoom note
  conveyed (item 9 above).

**Gate board after this addendum: G0 PASS (session-scoped); G1
DEMONSTRATED; G2 MEASURED — NOT_DEMONSTRATED (v3, third measured null);
G3 MEASURED — SPECIALIZATION; G4 MEASURED — INHERITANCE_DEMONSTRATED;
G5 NOT_ASSESSED (period locked 12 Nov → 30 Nov 2026). OAIE unproven.**
