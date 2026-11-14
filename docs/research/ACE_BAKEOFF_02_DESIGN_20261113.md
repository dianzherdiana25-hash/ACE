# Bake-off 02 — design (successor candidate selection, citation-validator hardening, single composite pass rule)

Status: **DESIGN ONLY — not a preregistration, authorizes
no run and no download.** Date: 2026-11-13. Brain of
origin: Muse (Ian), ACE's registered development-engine
brain. Predecessor: `brain-bakeoff-01` (PR #146,
Addendum 44; protocol hash
`7db0976460f85dd3ad0601e29cb1bd50e2961f3f03100fd57529b3ce083e1a09`).

## 0. What bake-off 01 measured, and what this design answers

Bake-off 01 asked whether Qwen3-4B Q4_K_M could succeed
Qwen3-8B as local director — faster, without losing
reliability. Measured (one attempt per instrument, the
incumbent's proven router config temp 0.3 /
max_tokens 700 / timeout 900):

- A — director cycle on a fixed packet: accepted,
  5 proposals, 373 s. PASS.
- B — B2A-02 dossier: **0/4**. The decision was rejected
  whole for citing a fact id not in the packet
  (`nimbus-gate`); kernel audit CLEAN; 341.4 s. FAIL.
- C — sealed repair fixture: 6/6, LOCALLY_VERIFIED,
  138.3 s. PASS.
- Speed: PASS (341.4 s < the incumbent's 535.6 s).

The preregistered conjunction failed on B, exactly the
property the succession was forbidden to lose. Two
distinct defects came out of that stage, and this design
addresses both — separately, because they are different
kinds of defect:

1. **A paperwork defect (ours, not the model's).** The
   pass rule was a prose conjunction; the kernel's
   verdict derivation requires a single-metric dict, so
   `record_result` could not intake the result and the
   kernel ledger holds **zero** result rows for a fully
   measured experiment. §3 designs the rule as ONE
   composite metric from the start, with a procedural
   intake check so this cannot recur silently.
2. **A measurement-surface defect.** The citation
   validator did its job — it caught the fabrication —
   but its rejection survives only as an exception
   string inside an evidence JSON. A rejection that
   decides a succession should itself be first-class,
   auditable evidence. §2 specifies that hardening.
   Note the scope honestly: hardening is about the
   **quality and auditability of rejections**, not
   about preventing fabrication. Prevention-side ideas
   from the bake-off 01 report (e.g. rendering the
   packet's citable ids as an explicit whitelist) are a
   *packet mechanism* item with their own claim; they
   are **out of scope** here (§5) and must never be
   smuggled into a bake-off as an unregistered
   instrument change.

And one non-defect that constrains §1: the 4B's failure
was a property of that candidate on that instrument.
The succession question remains open; it just needs a
**new claim**, not a re-run.

## 1. Candidate selection criteria (a NEW candidate)

A bake-off 02 candidate is admissible only if ALL of
the following measurable properties hold. Each is
checkable before any instrument runs; a candidate that
fails one is not downloaded (or, if already on disk, not
custodied).

- **C-1 Distinct identity, new claim.** The candidate's
  artifact digest differs from Qwen3-4B Q4_K_M
  (`7485fe6f…f5`). The 4B is **not re-run as-is**: the
  identical test repeated measures luck, not
  improvement (bake-off 01 report §5). A future 4B
  re-test is conceivable only under a changed condition
  that constitutes a new claim (e.g. a packet-mechanism
  change), and that change would be its own registered
  stage — never a silent bake-off 02 entry.
- **C-2 Same-instrument evaluability.** The candidate
  must be evaluable by the *unchanged* instruments of
  bake-off 01: A (director cycle, fixed packet),
  B (B2A-02 dossier with the harness-computed table),
  C (sealed Keamanan-01 repair fixture), plus the speed
  bar. Same packets, same bars, one attempt per
  instrument, the incumbent's router config
  (temp 0.3, max_tokens 700, timeout 900) unless a
  deviation is itself preregistered as part of the
  claim. Any instrument change is a separate stage.
- **C-3 Envelope fit (measured, not brochure).** GGUF,
  loadable by the pinned llama.cpp attested-server path
  on this VM (7.7 GiB RAM + 1 GiB swap, no GPU); file
  size ≤ the incumbent's 5,027,783,488 bytes — the
  succession motive is a faster director, so a larger,
  slower artifact contradicts the claim on its face.
  The corrupted 14B partial on disk is excluded by
  identity, not reconsidered under this design.
- **C-4 Custodiable before arrival.** Expected identity
  (HF LFS oid = SHA-256, plus byte size) is obtainable
  *before* the download completes, so custody precedes
  arrival and the hash — never the download's success —
  arbitrates identity, exactly as in bake-off 01 §1.
- **C-5 Rp0 / local-first.** No paid cloud API, no
  account-gated artifact ACE cannot hold locally. The
  candidate is an organ under multi-brain sovereignty:
  custodied, replaceable, dismissible.
- **C-6 Falsifiable succession claim, stated in one
  sentence.** Of the form: "⟨candidate⟩ matches the
  incumbent's reliability bars on A/B/C while running
  strictly faster on B." A candidate whose claim cannot
  be stated this way is not ready for a bake-off.

Selection procedure: the stage that picks the candidate
evaluates named candidates against C-1…C-6 in a small
selection memo, with the losers' failing criteria
recorded (a rejected candidate is a recorded result,
not a forgotten one). **Any download requires the
owner's approval under the standing rule** — this
design does not grant it.

## 2. Citation-validator hardening (rejection quality, not leak repair)

Surface: `validate_decision` in `b2a_market.py`
(instrument B) and the `based_on` check in
`director_loop.py` (instrument A). Today both reject
fail-closed and whole; the B rejection in bake-off 01
survives as one string — `"decision 0 cites facts not
in the packet: ['nimbus-gate']"`. That was sufficient
to decide bake-off 01. It is not sufficient evidence
to *audit* the decision later, to compare rejection
shapes across candidates, or to distinguish one
fabricated id from ten. Hardening requirements:

- **V-1 Per-fact-id granularity.** A rejection record
  enumerates **every** cited id of **every** decision /
  proposal in the reply — not only the first failing
  one — each with a status drawn from a closed set:
  `known` (present in the packet) or `unknown` (absent
  — the fabrication case). Whole-reply rejection
  semantics do **not** change: one `unknown` still
  rejects the whole reply. What changes is that the
  record shows the full citation surface that was
  judged, so the size and shape of a fabrication are
  measured facts, not a sample.
- **V-2 Structured rejection object, versioned.** The
  rejection is emitted as data, not an exception
  string, under a named schema (working name
  `ace.citation_rejection.v1`): experiment id, decision
  / proposal index, the per-id list of V-1, the id set
  the packet actually offered (by digest, §V-3), the
  rule that fired (`unknown_fact_id`), validator
  version + digest (V-4), and wall-clock timestamp.
  Exception types stay for control flow; the *record*
  is the schema object.
- **V-3 Packet binding.** The record carries the
  packet's digest and the digest of its citable-id set,
  so "not in the packet" is checkable against the exact
  packet the candidate saw — not against a later
  reconstruction of it.
- **V-4 Validator identity pinned.** The validator's
  code digest and schema version are computed at
  preregistration and carried in the record. A
  rejection is attributable to exactly one validator
  build; changing the validator after preregistration
  invalidates the run at audit, the same fence the
  artifact digest applies to candidates.
- **V-5 Chained, signed rejection entries.** Each
  rejection record is appended to the experiment
  kernel's evidence as a hash-chained entry under the
  kernel's split-custody HMAC discipline (candidate
  custodian ≠ evaluator custodian), in the same
  append-only manner as result entries. The kernel
  audit must return CLEAN over the chain — including
  the rejection entries — before any score from that
  run is read. A rejection thus becomes sealed
  evidence: replayable, attributable, and impossible
  to edit silently after the fact.
- **V-6 Deterministic replay.** Given the sealed
  packet, the raw reply, and the pinned validator
  build, re-running validation reproduces the rejection
  record byte-identically except for the timestamp.
  This is testable, and §4 makes it a build-stage test,
  including a fixture whose reply cites a fabricated id
  shaped like bake-off 01's — the regression test this
  failure mode has earned.

Explicit non-goals: no change to what counts as a
citation, to the whole-reply rejection rule, to the
packets, or to any bar. If the hardened validator would
have changed bake-off 01's *outcome* (it would not —
`nimbus-gate` is `unknown` under any granularity), the
design is wrong and must say so before build.

## 3. Pass rule: ONE composite metric, from the start

The kernel derives a verdict from a single numeric
metric against a dict pass rule. Bake-off 02's rule is
therefore a single number whose sign encodes the whole
conjunction — the same construction the A/B/C v3
design uses for its DI:

**`succession_margin`** = the minimum, over the four
bars, of each bar's signed margin in its own natural
units, where a margin of exactly 0 means "bar met
exactly":

- A margin: `+1` if the director-cycle reply is
  ACCEPTED whole by the hardened validator, else `−1`.
- B margin: `decision_score − 4` (so 4/4 → 0; the
  bake-off 01 candidate would score `0 − 4 = −4`, and
  a rejected decision scores 0 before margining, as it
  did in bake-off 01).
- C margin: `cases_passed − 6` (6/6 → 0).
- Speed margin: `(535.6 − B_wall_seconds) / 535.6`,
  positive iff strictly faster than the incumbent's
  recorded B wall (a fraction, deliberately on the same
  "0 = bar" footing; it can only be the minimum when
  the candidate is slower, which is precisely when it
  should decide).

Kernel pass rule: `{"metric": "succession_margin",
"gte": 0}`. Per-bar results and `bars_met` (0–4) are
recorded as **telemetry only** — the kernel's claimed
verdict must equal the verdict derived from the
composite, and the stage report may quote the bars but
may not re-derive a different verdict from them.

**Procedural intake check (new, from the bake-off 01
paperwork failure).** Before the real run, the
preregistration stage performs a dry intake on the
fresh kernel: a synthetic result carrying
`succession_margin` is derived through the kernel's
own verdict path and the derivation is shown to intake
it. If the kernel cannot intake the metric, the
preregistration does not lock. The sealed
preregistration is never rewritten after results exist
— bake-off 01's restraint on that point stands as
precedent, and this check exists so the restraint
never has to cost another ledger again.

## 4. Prerequisites and the sequence to its own preregistration

Nothing in this design is a run. The path to a
bake-off 02 preregistration, in order, each step a
named stage with its own evidence:

1. **Ratification of this design** (hub, on this
   document as a PR) — design decisions only, like the
   Task 02 D1–D6 pattern; authorizes no download, no
   build, no run.
2. **Validator hardening build** (§2, V-1…V-6) as its
   own stage on the discovery-lineage code, with tests:
   the fabricated-citation regression fixture (V-6), a
   multi-fabrication fixture proving per-id enumeration
   (V-1), and a chain/audit test proving that tampering
   with a sealed rejection entry breaks the kernel audit
   (V-5).
   Sweep + two-checker verification before it is
   declared the pinned validator build (V-4).
3. **Candidate selection memo** per §1 (C-1…C-6),
   naming the chosen candidate and the recorded losers.
   **Owner approval for the download** is obtained at
   this step, under the standing rule.
4. **Custody + verification gate**: expected identity
   custodied in a fresh experiment kernel *before* the
   download completes; on arrival, SHA-256 and GGUF
   size consistency verified against custody (the
   bake-off 01 §1 pattern, unchanged).
5. **Preregistration**: fresh kernel; hypothesis per
   C-6; protocol carrying the pinned validator digest
   (V-4), the hardened rejection schema version (V-2),
   the incumbent's recorded bars, one attempt per
   instrument, and the §3 composite as the sole pass
   rule — followed by the **dry-intake check** (§3)
   before the lock is declared. Protocol hash into the
   checkpoint lineage.
6. **Run**: one attempt per instrument, arms as in
   bake-off 01; rejection records (if any) sealed per
   V-5 during the run, not reconstructed after it.
7. **Consequences, pre-written**: on PASS (composite
   ≥ 0) — registry swap, the incumbent museum-ized
   with its service record intact, files preserved.
   On FAIL — the candidate is recorded as a measured
   candidate that did not pass, its file preserved, the
   incumbent stays on duty; any re-test needs a new
   claim (C-1). Either verdict is reported with the
   same prominence, and the gate board changes only
   after two-checker verification of the dossier.

Sequencing fences: bake-off 02's run is a gate-scoring
run for the director seat — it does not interleave with
a G3/G4 application run over the same director, and it
never borrows another experiment's pool, packet, or
kernel. The G3 application's frozen artifact and seed
bands are untouched by every step above.

## 5. Out of scope (named, so they are not smuggled in)

- **Whitelist packet rendering** (bake-off 01 report
  §5(a)): a packet-side mechanism that would change
  what the candidate sees. It may one day give a re-test
  its new claim (C-1); it is not validator hardening,
  not part of this design's build, and not a bake-off
  02 instrument change.
- **Incumbent re-baselining.** The 8B's bars are its
  recorded service record (B 4/4 at 535.6 s; C 6/6;
  cycles 1–4 + bake-off A-side records). Bake-off 02
  does not re-run the incumbent to "refresh" them.
- **Speed-only succession.** A candidate that is merely
  faster has no claim: the composite (§3) makes B's
  reliability margin co-decisive by construction.
- **The director seat's other duties.** This design
  covers succession measurement only; director-cycle
  operations over the opportunity register are a
  separate agenda line and gain nothing from it.

— End of design. Prepared by Ian (Muse, ACE's
registered development-engine brain) under the
massive-escalation mandate's parallel track (f):
design only, no downloads, no runs, no registry change.
