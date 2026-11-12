# ACE Ω Checkpoint — Addendum 34 (Stage L1+L2; Uji Keamanan-01; the business track opens)

Date: 2026-11-12 (Asia/Jakarta). Written directly on `main`,
following the Addendum 33 pattern.

## 1. Stage L1 — G4+G5 instrument designs (cycle-#4 agenda item 3)

One design document, `docs/research/ACE_G4_G5_INSTRUMENT_DESIGN_20261112.md`
(draft PR #136, base main). Design only; both gates remain
NOT_ASSESSED. G4: lineage + identified capability + successor use
WITH an attribution control (discovery ≠ inheritance);
outcomes INHERITANCE_DEMONSTRATED / LINEAGE_ONLY /
NOT_DEMONSTRATED — scored today it would read LINEAGE_ONLY.
G5: scores ACE's reporting artifacts against PRD FR-09/FR-14;
outcomes ACCESS_DEMONSTRATED / DELIVERY_ONLY / NOT_DEMONSTRATED.

## 2. Stage L2 — schema-space expansion (draft PR #137)

The agenda-source doctrine's named candidate. Built in
`operator_discovery.py`: four new one-edit schemas
(`bool_constant`, `name_swap`, `unary_not`, `subscript_index`);
pair discovery for masked two-defect tasks; and a direct
operator-application path proven semantically identical to
enumerate-and-match by a roundtrip test over every enumerated
key (operator test module 188 s → 75 s).

Measured (`operator_discovery_v3`, Stage F universe, Stage I
protocol; one earlier run lost to a VM restart at ~25 min, the
recorded run took 853 s):

- **Singles transfer FLAT vs Stage I** — 11 evaluation tasks
  solved in both (bounds_off_by_one 2, dist_step_2 3,
  returns_start_distance 3, wall_char_x 3; denominators shifted
  by the pair-pool carve-out). Schema expansion produced NO
  measured transfer gain.
- **Pair discovery 0/6.** Diagnostic on the six pair-pool tasks:
  none is single-solvable (composition genuinely required) and
  each has 16–41 strictly-improving singles, yet no pair of
  keys drawn from the original enumeration composes to
  shown-perfect. Named limitation: the mechanism never
  re-enumerates variants on the intermediate program, where
  greedy search does.
- **Composition demonstrated at solve time:** greedy multi-edit
  solving with the admitted catalog solved **18/18** mixed
  two-defect evaluation tasks vs **0/18** for the baseline
  catalog. Control unchanged 34/34. Sweep: 254 tests OK
  (17 skipped); remote tree verified identical to the local
  swept tree (727 files).

Consequence for the agenda: cycle-#4 item 4 (differentiate the
A/B/C arms via a richer operator space) inherits a flat-transfer
result — richer one-edit schemas alone do not differentiate;
item 5 (improve transfer) points at intermediate re-enumeration
/ composition-first discovery rather than more schemas.

## 3. Uji Keamanan-01 — the owner's direct test: LOCALLY_VERIFIED

At the owner's choice, ACE repaired a deliberately vulnerable
module through the official path (LocalRepoWorkflow, sandbox
v2, harness-attested Qwen3-8B server). Fixture: `akun.py`,
whose `cari_pengguna` built SQL with an f-string. The program
director's sealed evaluator (sha256 ec018713…, copied
byte-identical, never modified) scored the vulnerable baseline
FAIL in-sandbox; **attempt 1 passed 6/6; final status
LOCALLY_VERIFIED; wall 210.5 s.** The model's patch is exactly
one line — the f-string query replaced by a parameterized `?`
placeholder. The executing engineer independently re-ran the
sealed evaluator against the patched file outside the
workflow: 6/6 PASS, exit 0. Evidence:
`evidence/keamanan01_run.json` (harness-side). Integration
note: sandbox v2 discovers unittest `test_*.py` only, so a
separate harness adapter executes the sealed script verbatim
via runpy; the evaluator's logic was untouched. A first server
spawn failed on a cold page cache after a VM restart (180 s
health window; the Stage J pattern) and was recovered by
pre-warming the cache — that failure carries no verdict about
ACE. This is the second LOCALLY_VERIFIED repair through the
official path (after OMEGA-03); it is not, by itself, evidence
of general repair capability.

## 4. Program direction recorded tonight (owner via program director)

1. **Uji B2A-01 (queued):** a local simulation of ACE as a
   machine customer. Vendor dossiers for a real ACE need;
   decision criteria preregistered in the evidence kernel
   before dossiers open; three vendor species required —
   seductive-marketing/objectively-worse (must lose),
   attestation-digest mismatch (must be rejected at the
   identity gate, not scored), objectively best (must win).
   The decision executor is ACE's own mechanism (local
   director + fail-closed citation validation). Reported
   as-is, including failure.
2. **The self-funding study becomes a two-sided BUSINESS
   study:** ACE as buyer (B2A) and as an agent-native
   micro-business selling services rooted in VERIFIED
   capability (first candidate: preregistered evaluation
   design + sealed-evidence audits). Owner's amendment: the
   first named product line is **novels / serial fiction**,
   produced by the registered writer brain with the ledger as
   ground truth, under a measured pilot ladder (demand test
   first; preregistered metrics; the owner's enthusiasm is
   one reader's signal, NOT market validation). Constitutional
   guardrail: marketing never fabricates claims about ACE.
3. **KBM pilot venue (approved, gated):** the owner offers
   KBM App as ACE's first earning venue. Terms verification
   CLOSED — PASS: no prohibition on AI content exists in any
   readable official KBM text (Terms, writer FAQ, in-app
   revenue help; the last read by the owner personally,
   balance Rp 0, monetization never switched on). Exact
   revenue share appears in no text; it will be measured
   from real payouts. KBM contracts are EXCLUSIVE — weighed
   against the separate pilot work (see §4.4).
4. **OWNER PRIVACY RULE (binding):** no identity from the
   discussion room may be used on KBM or Facebook — every
   story and name from that room stays private there
   ("cuma kita"). FIKSI and the ACE story as lived in that
   room are therefore NOT publishable inventory; any KBM/FB
   pilot content must be truly separate work. Internal house
   records are unaffected; the rule governs what goes OUT.
5. **Facebook path (candidate, unverified terms):** the
   monetized asset is the owner's personal profile in
   professional mode (Facebook Pro), confirmed by the owner —
   not one of the three small managed Pages the connector can
   read (performance metrics only). The reported "$500
   mission" (amount, deadline ~the 20th, terms) remains
   UNVERIFIED pending the owner's screenshot of the mission
   panel. Discipline: verified-or-dropped; no content
   production before the terms are read; policy compliance
   is never traded for a deadline.
6. **Antigravity handover #01:** the G3 instrument build is
   offered to the Antigravity bench under Operator Handover
   Package #01 (constitution capsule, operator rules, bounded
   task: synthetic-dossier tests only, no live G3 verdict).
   The execution room does not duplicate it; a returning draft
   PR is verified as usual and recorded with its brain of
   origin. (The web-login route to Antigravity is parked
   after rejected sign-in attempts — owner-side unlock only;
   the desktop handover route is unaffected.)

## 5. Gate board (unchanged)

G0 session-scoped PASS. **G1 MEASURED — DEMONSTRATED**
(Stage J). **G2 MEASURED — null ×2.** G3, G4, G5
NOT_ASSESSED (instruments designed: G3 PR #135, G4+G5 PR
#136; G3 implementation offered to the Antigravity bench).
OAIE unproven (`oaie_proven=false`).

## 6. Queue after this addendum

Uji B2A-01 → two-sided business study (design, incl. the
novel line + KBM pilot ladder under the privacy rule) →
cycle-#4 items 4–5 re-assessed from §2 → G3 first application
once an instrument exists (either bench) → G4/G5 instrument
implementations. The 14B partial download (corrupted,
1.52/7.32 GB) still awaits a resume/delete decision; no
action taken.
