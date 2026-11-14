# Bake-off arena expansion — design note (30B-class challengers in the sandbox home)

Status: **DRAFT DESIGN — not a preregistration,
authorizes no run.** Date: 2026-11-13. Brain of
origin: Muse (Ian), ACE's registered
development-engine brain. Parent design: Bake-off 02
(PR #152, `ACE_BAKEOFF_02_DESIGN_20261113.md`), whose
rules this note inherits except for the single
re-based criterion in §2. This change is **docs-only:
no code is added or modified, and no test sweep
applies to it.**

The downloads named in §3 were ordered by the owner's
mandate (§0), not by this note; this note designs the
arena they will be measured in, and launches nothing.

## 0. Mandate and scope

Owner escalation mandate, 2026-11-13 16:35 WIB:
maximal brain bench in the Manus Sandbox — ACE's home
(8 cores, ~24 GB RAM, 70 GB disk) — with two 30B-class
GGUF challengers downloaded into the sandbox under
the Bake-off 02 custody procedure, benchmarked there,
and admitted to a bake-off arena under the same
criteria and custody gates as Bake-off 02.

The same owner order **revokes the Qwen rest (owner,
2026-11-13 ~11:03 WIB) for the sandbox brain bench
only**. The rest stands everywhere else: VM director
cycles over the opportunity register remain rested,
and nothing in this note wakes them.

Scope of this note: the arena expansion only — one
envelope re-base (§2), the two mandated candidates
(§3), their draft claims (§4), and the gates and
sequence that would carry them to a preregistration
(§5–§6). Section 7 records, honestly and before
anything else can be read as a promise, the
infrastructure blocker that currently prevents any
measurement in the expanded arena.

## 1. What does NOT change (inherited from Bake-off 02)

Everything in the parent design carries over
unchanged, and is restated here only so the
inheritance is auditable in one place:

- **C-1 Distinct identity, new claim.** Each
  challenger differs by artifact digest from
  Qwen3-4B Q4_K_M (`7485fe6f…f5`, measured fail in
  bake-off 01, not re-run as-is) and from the
  incumbent; each carries its own one-sentence claim
  (§4).
- **C-2 Same-instrument evaluability.** Instruments
  A (director cycle, fixed packet), B (B2A-02 dossier
  over the harness-computed table), C (sealed
  Keamanan-01 repair fixture), plus the speed bar —
  unchanged packets, unchanged bars, one attempt per
  instrument, the incumbent's proven router config
  (temp 0.3, max_tokens 700, timeout 900). Any
  instrument change is a separate stage.
- **C-4 Custodiable before arrival.** Expected
  identity (HF LFS oid = SHA-256, plus byte size)
  recorded before the download completes; the hash,
  never the download's success, arbitrates identity.
  Done for both candidates (§3, §5).
- **C-5 Rp0 / local-first.** No paid cloud API, no
  account-gated artifact; each candidate is an organ
  under multi-brain sovereignty — custodied,
  replaceable, dismissible.
- **C-6 Claim form.** Each claim is one falsifiable
  sentence of the parent design's form (§4).
- **Validator hardening V-1…V-6**, as built (PR
  #162): per-fact-id rejection records under schema
  `ace.citation_rejection.v1`, packet-bound,
  hash-chained under split custody, validator
  identity pinned at preregistration, deterministic
  replay with the bake-off 01 fabrication fixture.
  Per **hub decision 2026-11-13 16:07**, the
  operative rejection semantics are **per-proposal**
  (a proposal citing an unknown id is itself
  rejected); the legacy whole-reply reading is still
  computed and recorded in every validation report,
  so both readings remain auditable. This note does
  not reopen that decision.
- **Pass rule: ONE composite metric.**
  `succession_margin` = min(A margin, B margin,
  C margin, speed margin), where A margin = +1 if
  the reply is accepted else −1; B margin =
  `decision_score − 4`; C margin = `cases_passed − 6`;
  speed margin = `(535.6 − B_wall_seconds) / 535.6`.
  Kernel pass rule: `{"metric": "succession_margin",
  "gte": 0}`. Per-bar results are telemetry only.
  The incumbent's bars are its recorded service
  record from bake-off 01 (protocol hash
  `7db0976460f85dd3ad0601e29cb1bd50e2961f3f03100fd57529b3ce083e1a09`):
  B decision 4/4 at a 535.6 s wall, C 6/6,
  A accepted. The incumbent is **not** re-baselined
  (parent design §5).
- **Dry-intake check** on the fresh kernel before
  any lock (parent design §3), and **kernel audit
  CLEAN before any score is read**.
- **Sequence discipline** (parent design §4): a
  bake-off run never interleaves with a G3/G4
  application run over the same director, and never
  borrows another experiment's pool, packet, or
  kernel.

## 2. The one change: the envelope criterion, re-based (C-3 → C-3′)

Bake-off 02's C-3 was written for the Muse VM, and
says so: *"GGUF, loadable by the pinned llama.cpp
attested-server path on this VM (7.7 GiB RAM + 1 GiB
swap, no GPU); file size ≤ the incumbent's
5,027,783,488 bytes."* Both halves of that criterion
are VM facts, and the expanded arena does not live
on the VM:

- The VM **cannot host a 30B model at all** — 7.7 GiB
  of RAM against an 18.6 GB or 19.8 GB artifact is
  not a tight fit, it is an impossibility. Keeping
  C-3 as written would exclude the mandated arena by
  definition, silently, without anyone deciding that.
- The arena's home is the Manus Sandbox: 8 cores,
  ~24 GB RAM, 70 GB disk (56 GB free at intake).
  The envelope must be stated against the machine
  that will actually hold the candidates.

**C-3′ (expanded-arena envelope, replacing C-3 for
candidates in this arena only):**

- GGUF, single file, **≤ 20,000,000,000 bytes**
  per file.
- Loadable by the same pinned llama.cpp build
  (b12316) that serves the incumbent's attested
  path — the build does not change, only the host.
- Load is **measured, not brochure**: before any
  preregistration in this arena, the candidate's
  intake bench in the sandbox records tok/s and
  load burden (resident memory, load wall) under
  that build. A candidate that cannot be loaded and
  benched in the sandbox fails C-3′ on measurement,
  whatever its file size says.
- **RAM headroom, stated:** ~24 GB total RAM against
  the largest candidate's 19,762,149,024-byte
  artifact leaves roughly 4 GB of headroom. That is
  thin. The intake bench measurement — not this
  arithmetic — is the arbiter of C-3′.

Two properties of the re-base are recorded openly,
so neither can be mistaken for a quiet softening:

1. **No bar moves.** C-3′ changes the size ceiling
   and the load-evidence requirement. The composite
   (§1) still requires reliability parity on A/B/C
   **and** a strictly faster B wall than the
   incumbent's 535.6 s. The parent design's C-3
   motive — a larger, slower artifact contradicts a
   speed claim on its face — is not repealed; it is
   left standing as the tension each §4 claim must
   survive. For the dense candidate especially, the
   speed margin is expected to be the deciding term.
   That is what a falsifiable claim is for.
2. **The speed comparison is cross-machine by
   construction.** The incumbent's 535.6 s was
   recorded on the Muse VM; candidate B walls will
   be recorded in the sandbox (8 cores). The
   inherited no-re-baselining rule (§1) keeps 535.6
   as the bar anyway. This is a known property of
   the expanded arena, recorded here rather than
   discovered after a verdict.

The VM arena of Bake-off 02 is unaffected: C-3 as
written still governs any candidate there (the
Llama 8B succession track proceeds under the parent
design unchanged).


## 3. Candidates (identities fixed at dry-intake, 2026-11-13)

Dry-intake was performed per the Bake-off 02 custody
procedure before any download: identity read from
the official Hugging Face API (`?blobs=true`) and
cross-checked against each repo's raw LFS pointer;
both reads agree byte-for-byte on size and SHA-256.
Record: `evidence/bakeoff_arena30b_intake_record.json`
(`ace.bakeoff_arena30b_intake.v1`, stage
`intake_passed`, 2026-11-13 16:45 WIB). Downloads
into the sandbox (`/workspace/ace-omega/models/`)
proceed under the owner's mandate, A3B first.

| # | Candidate | Repo (revision) | File | Size (bytes) | SHA-256 (HF LFS oid) | Shape |
|---|---|---|---|---|---|---|
| 1 | Qwen3-30B-A3B Q4_K_M | `Qwen/Qwen3-30B-A3B-GGUF` (`e4d4bafdfb96a411a163846265362aceb0b9c63a`) | `Qwen3-30B-A3B-Q4_K_M.gguf` | 18,556,685,824 | `0d003f6662faee786ed5da3e31b29c978de5ae5d275c8794c606a7f3c01aa8f5` | MoE, 30B total / ~3B active per token |
| 2 | Qwen3-32B Q4_K_M | `Qwen/Qwen3-32B-GGUF` (`938a7432affaec9157f883a87164e2646ae17555`) | `Qwen3-32B-Q4_K_M.gguf` | 19,762,149,024 | `efd971561896866f0e910cce52761ca77b1b138090c7f15fe284676d57d1f689` | Dense, 32B, all parameters active |

Both files are single-file GGUF (no split parts),
both are under the C-3′ ceiling (A3B by
1,443,314,176 bytes; 32B by 237,850,976 bytes), and
their combined 38,318,833,848 bytes fit the
sandbox's 56 GB free at intake with ~17.7 GB spare.
Blob ids (`57ede8a3…` / `f3771a8b…`) and the full
intake record are in the evidence file named above.

**No benchmark number exists for either candidate
yet** — no tok/s, no load time, no instrument
result. Any figure of that kind quoted for them
today would be invented; §7 explains why, and what
would have to change first.

Incumbent (baseline candidate, unchanged):
Qwen3-8B Q4_K_M, 5,027,783,488 bytes, SHA-256
`d98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785`.

## 4. Draft succession claims (DRAFT wording — locked only at preregistration)

Each claim is stated in the C-6 form against the
same instruments (A director cycle, B B2A-02
dossier, C sealed repair) and the same composite
(`succession_margin ≥ 0` against the incumbent's
bake-off 01 numbers, §1). The distinctive property
named after each claim is its new claim under C-1 —
the reason it is not a re-run of anything measured
before.

- **Qwen3-30B-A3B:** "Qwen3-30B-A3B Q4_K_M matches
  the incumbent Qwen3-8B's reliability bars on
  instruments A/B/C while running strictly faster
  on instrument B." — Distinctive property:
  **sparse MoE activation** — ~3B of 30B parameters
  active per token, so its per-token cost class is
  the incumbent's while its total capacity is
  nearly four times larger; the claim is that
  capacity, not per-token spend, is what the
  reliability bars were missing.
- **Qwen3-32B:** "Qwen3-32B Q4_K_M matches the
  incumbent Qwen3-8B's reliability bars on
  instruments A/B/C while running strictly faster
  on instrument B." — Distinctive property:
  **dense 32B scale** — every parameter active per
  token, the largest brain ACE's home can hold
  under C-3′; the claim is deliberately stated in
  the same strong form, and its speed margin is the
  term most likely to falsify it (§2, property 1).

A fail on any bar falsifies the corresponding
claim; the candidate is then recorded as a measured
candidate that did not pass, and the incumbent
stays on duty. No re-run until green, and any
re-test needs a new claim (C-1).

## 5. Custody gates (same gates, arena edition)

1. **Identity before arrival** — done for both
   candidates (§3): HF LFS oid + byte size recorded
   in the intake record before the downloads
   complete (C-4).
2. **Arrival verification** — on landing in the
   sandbox, each file's byte size and SHA-256 are
   verified against the intake record before the
   file is accepted as the candidate artifact. A
   mismatch means a rejected artifact: recorded,
   never custodied, never benched.
3. **Fresh kernel per experiment** — each
   candidate's preregistration opens a fresh
   OMEGA-06 kernel root in the sandbox arena;
   split custody (candidate custodian ≠ evaluator
   custodian, distinct HMAC keys); custodies —
   candidate artifact by §3 identity, incumbent
   baseline, evaluator = pinned validator +
   instrument packets — precede registration.
4. **Pinned validator** — the PR #162 hardened
   build's code digest and the
   `ace.citation_rejection.v1` schema version are
   carried in the registration (V-4); operative
   semantics per-proposal per the hub decision
   (§1). Changing the validator after registration
   invalidates the run at audit.
5. **Dry-intake check** — a synthetic result
   carrying `succession_margin` is derived through
   the fresh kernel's verdict path before the lock
   (§1). If intake fails, the registration does
   not lock.
6. **Audit before reading** — kernel audit must
   return CLEAN, including the chained rejection
   entries (V-5), before any score from the run
   is read.

## 6. Sequence (each step a named stage with its own evidence)

1. **Ratification of this note** (hub, on this
   document as a PR) — design decisions only;
   authorizes no bench and no run.
2. **Arrival verification** of the two mandated
   downloads (§5 gate 2) — in flight under the
   owner's mandate at the time of writing.
3. **Intake bench** (C-3′ evidence): tok/s + load
   burden for each landed candidate under
   llama.cpp b12316 in the sandbox, in the intake
   record's stated order (Llama 8B reference first,
   then the 30B models). **Blocked — see §7.**
   No preregistration in this arena locks before
   its candidate's bench exists, because C-3′ makes
   the measured load part of admissibility.
4. **Preregistration per candidate** — one at a
   time, A3B first (intake priority): §4 claim
   locked verbatim or amended on the record, §5
   gates executed, dry-intake passed, protocol
   hash into the checkpoint lineage.
5. **Run** — one attempt per instrument, in the
   sandbox, rejection records sealed during the
   run (V-5), never reconstructed after it.
6. **Consequences** (§8), reported with the same
   prominence for either verdict; the gate board
   changes only after independent verification of
   the dossier (the single-worker pattern: a
   verifier receives raw evidence only).

## 7. Honest blocker: nothing in this arena can be measured through the MCP door today

Stated before any of §3–§6 can be misread as a
schedule: **the intake bench (§6 step 3) and any
30B run (§6 step 5) cannot execute through the
sandbox MCP door as it is currently configured.**

Measured facts (2026-11-13): every process spawned
through the sandbox MCP endpoint — detached children
included — lives in the `sandbox-mcp.service`
systemd cgroup, whose **MemoryMax is 1.0 GiB for the
whole tree**. A llama-bench load of the 4.92 GB
Llama 8B GGUF (4,920,739,232 bytes, already resident
in the sandbox) was OOM-killed by that cgroup;
`dmesg` records the kill as `CONSTRAINT_MEMCG`.
The prlimit wrapper that once capped CPU and
address space was removed entirely at the owner's
order the same day (rlimits verified unlimited from
inside a spawned process) — the cgroup memory cap
is a separate, surviving wall. An 18.6 GB or
19.8 GB artifact does not fit through a 1.0 GiB
door, and retrying the load only reproduces the
kill deterministically.

Named routes that would unblock the bench, any one
of which suffices:

1. **The sandbox operator raises the unit's
   MemoryMax** (the same operator channel that
   removed the prlimit wrapper on 2026-11-13).
2. **A real shell outside the service cgroup** —
   e.g. the owner's verified Tailscale SSH shell
   into the sandbox (`ubuntu@100.93.61.37`), from
   which llama.cpp can be launched as an ordinary
   sandbox process with the machine's full ~24 GB
   available.
3. **A Manus Task API task** instructing the
   sandbox-side agent to run the bench and return
   the numbers as evidence.

Until one of these routes is taken, the expanded
arena's status is **BLOCKED-INFRASTRUCTURE** — a
recorded state about the door, not a result about
either candidate. **This note launches no run, no
bench, and no download**; the downloads in flight
were ordered by the owner's mandate (§0) and are
network/disk work, which the cgroup wall does not
block.

## 8. Consequences (written in advance, per candidate)

- **Pass** (`succession_margin ≥ 0`, audit CLEAN):
  the brain registry records the swap for the
  director seat; the incumbent Qwen3-8B is museumed
  (not deleted), per multi-brain sovereignty; the
  succession is reported to the owner as a completed
  stage. Where the succeeding brain lives is part of
  the record: a sandbox-resident successor means the
  director's operations run in ACE's home, and the
  VM-side rest (§0) is unaffected either way.
- **Fail:** the candidate is recorded in the
  registry as a measured candidate that did not
  pass, with the deciding bar named from telemetry;
  its file is preserved in the sandbox; the
  incumbent stays on duty; no immediate successor
  attempt is implied, and any re-test needs a new
  claim (C-1).
- **Abstain** (infrastructure failure before any
  instrument completes — including §7's wall, if a
  run were attempted through it — audit not CLEAN,
  or the validator changed): recorded with the
  reason; the registration is spent either way. An
  abstain is never reported as a candidate result.
- **Arena level:** if both candidates are measured
  and both fail, the expansion records two measured
  non-successions and closes with the incumbent on
  duty — a result, not an embarrassment to be
  retried quietly. If the §7 routes are never taken,
  the arena remains BLOCKED-INFRASTRUCTURE with two
  custodied, unverified-at-bench artifacts, and
  that too is the recorded outcome until the owner
  or hub directs otherwise.

## 9. Out of scope (named, so they are not smuggled in)

- **VM director operations.** The Qwen rest stands
  on the VM (§0); this arena neither wakes the
  director cycles nor moves the opportunity
  register's agenda.
- **Instrument changes of any kind** — including
  the whitelist packet rendering named out of scope
  by the parent design (§5 there). Same packets,
  same bars.
- **Incumbent re-baselining** — the 8B's recorded
  bars (§1) are not re-measured for this arena,
  not even on the sandbox's faster hardware
  (§2, property 2 records the consequence).
- **Further downloads.** The arena admits the two
  mandated candidates. Any additional 30B-class (or
  other) artifact needs its own owner approval,
  its own intake record, and its own claim.
- **Merging this note.** It ships as a draft PR for
  ratification discussion; nothing in it is a
  preregistration, and no kernel submission follows
  from it.

— End of draft design note. Prepared by Ian (Muse,
ACE's registered development-engine brain) under the
owner's escalation mandate of 2026-11-13 16:35 WIB
(arena-expansion track): design only, docs-only, no
downloads ordered by this note, no bench, no run,
no registry change.
