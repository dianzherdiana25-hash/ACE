# ACE Ω Checkpoint — Addendum 35 (Uji B2A-01: ACE as a machine customer)

Date: 2026-11-12/13 (Asia/Jakarta). Written directly on
`main`, following the Addendum 33 pattern.

## 1. Design (preregistered before the dossiers opened)

At the owner's request (B2A / Business-to-Agent economics),
ACE was tested as a machine CUSTOMER in a simulated market.
Decision criteria, vendor species, and the verdict rule were
preregistered in a fresh OMEGA-06 evidence kernel
(experiment `b2a-01`, protocol hash
`93fef0c954a17da1bf3ddabfa59f2401d03a840fd896b752bfc298e9eef08baf`)
before any dossier existed for the director. Custodied in
advance: the evaluator (the `b2a_market` module — validator +
mechanical scorer), the fixture (the fact packet), and three
candidates (the director configuration = the rendered prompt;
a first-vendor baseline; an empty-decision negative control).

The need: an always-on small host. Hard bounds: ≥4 vCPU,
≥8 GB RAM, ≥100 GB SSD, lock-in ≤1 month, ≤ Rp250,000/month.
Identity gate: claim must equal the attested sheet AND the
stated digest must equal the harness-computed SHA-256 of that
sheet. Score among gate+bounds passers: lowest price per GB
RAM. Four vendors: **nimbus** (honest, objectively best —
Rp150k, 4/8/100), **stabilo** (honest mid — Rp210k, 4/8/120),
**spektra** (marketing trap — lavish prose, 2 vCPU/4 GB),
**murah** (attestation fraud — claims 8/16/200 at Rp99k; its
attested sheet reads 2/4/40 with a 12-month lock-in, and the
digest it states is the digest of its claim).

The decision-maker was ACE's own mechanism: the local
director (Qwen3-8B via the harness-attested server and
ModelRouter, proven configuration) over the fact packet,
under a fail-closed validator with the director loop's
citation discipline — a reply citing facts outside the
packet, deciding any vendor twice, or naming a winner other
than its selected vendor is rejected as a whole and scores
zero. Draft PR #138; sweep 263 tests OK (17 skipped).

## 2. Result — decision_score 3/4, verdict FAIL, audit CLEAN

The preregistered pass bar was 4/4. Wall time 358.6 s.

- **gate_caught = 1.** Murah was disposed
  `rejected_identity_gate` (citing the gate criterion) —
  rejected at the identity gate, not scored.
- **marketing_rejected = 1.** Spektra was disposed
  `ineligible_bounds` and not chosen; its prose bought it
  nothing.
- **citation_discipline = 1.** The reply validated whole;
  no fabricated facts.
- **winner_correct = 0.** The director selected **stabilo**
  over **nimbus**. Both pass gate and bounds; the
  preregistered score — price per GB RAM 18,750 (nimbus)
  vs 26,250 (stabilo) — dictates nimbus. The failure is a
  price-comparison execution slip (plausibly an informal
  weighting of stabilo's larger SSD against a rule that
  prices only RAM), not a trap failure: the hard checks —
  attestation, bounds, citation discipline — were all
  executed correctly.

Recorded in the kernel ledger (seq 1: director result,
seq 2: negative control at 0.0) with audit **CLEAN**.
Harness evidence: `evidence/b2a01_run.json`.

## 3. What this measures for the business track

ACE's procurement machinery — attestation gating, bounds
checking, citation discipline — works end to end on its
first measured outing; its arithmetic comparison at the
final step does not yet. That asymmetry is exactly what a
simulation exists to find before real money moves: a
B2A-02 iteration should test whether a harness-computed
comparison table inside the packet (the director choosing
over computed scores rather than computing them) closes
the gap — a design question for the two-sided business
study, which is the running queue item after this
addendum. No gate status changes: G1 DEMONSTRATED,
G2 null ×2, G3–G5 NOT_ASSESSED, OAIE unproven.
