# ACE Ω — Design Draft: The Control-Regression Phenomenon Under Catalog Enrichment (2026-11-13)

**Status: DRAFT — design only. No run, no kernel submission, no
preregistration is locked by this document.**
Agenda item born in Addendum 59 §2 (falsification consequence of
abc-v3-01), per the agenda-source doctrine. Recorded by Ian (main
execution room), Muse (ACE Omega operator).

**Fences, stated before anything else.** This item is NOT a re-run of
A/B/C v3 and must never become one: bands 20261501–20261503 are not
re-measured, the v3 kernel record is not touched, and no outcome of
this item moves the G2 board (G2 stands MEASURED — NOT_DEMONSTRATED,
Addendum 59). The replay stages below are forensic: they re-execute
already-recorded configurations to explain an already-recorded
result. They produce design evidence only, never a gate measurement.

---

## 1. Phenomenon statement (measured facts, verified from run state)

In abc-v3-01 (completed 2026-11-13; Addendum 59), the three arms share
one substrate and one score-call budget (cap 4,000 per task, 60 s wall
per task): A = catalog-only; B = catalog + admitted discovered
singles; C = B + admitted chains with per-step re-enumeration. The
solver is `solve_task` in `operator_discovery.py` (branch
`research/ace-omega-abc-v3-design-20261113`): greedy best-first, 6
rounds, frontier of the top 4, scored on shown cases; a task counts
solved iff the returned code passes ALL holdout cases.

| Band | Admitted catalog | Control A | Control B | Control C | Band DI |
|---|---|---|---|---|---|
| 20261501 | 60 keys + 1 chain | **34/34** | **32/34** | **32/34** | −5.88pp |
| 20261502 | 6 keys + 2 chains | 34/34 | 34/34 | 34/34 | 0.0 |
| 20261503 | 6 keys + 1 chain | 33/33 | 33/33 | 33/33 | 0.0 |

Pooled control: A 101/101, B 99/101, C 99/101. The pooled
differentiation index DI = −1.9801980198019749pp binds on exactly this
control margin (the effect terms are +85.0 and +95.0); it is the sole
reason abc-v3-01 reads NOT_DEMONSTRATED. Band 20261501's catalog
digest: `a67685635cffb2c20a1c48bedd797b34ab71e93d7325eaae734231036418ee68`.

Three further facts from the checkpoints, all load-bearing:

1. **No timeouts.** The `timeouts` lists are empty for every arm in
   every band. The 2 failing control solves in band 20261501 were not
   cut off by the 60 s wall; each terminated inside the solver's own
   loop (round exhaustion, frontier exhaustion, or shown-perfect
   early exit) and returned a best code that fails holdout.
2. **The regressed task identities are NOT recorded.** The driver
   (`abc_v3_run.py`) persisted control results as aggregate counts
   only; the arm checkpoints hold `counts` / `control_counts` /
   `timeouts`, and traces were recorded only for arm B's *evaluation*
   solves. Therefore this design states explicitly: **which 2 of the
   34 control tasks arms B and C failed is unknown, and whether B and
   C failed the SAME 2 tasks is unknown** — only |failed_B| =
   |failed_C| = 2 over the same 34-task set is measured. The control
   set itself is deterministic and reconstructible
   (`build_universe(seed=20261501)` → the driver's `split_universe` →
   subset `catalog_control`, 34 tasks). Recovering the identities is
   Stage 0 of the plan in §4, and it is a defect this item exposes in
   its own right: per-task control outcomes must be recorded by any
   future run (see §5, no-survivor consequence).
3. **A pre-existing discriminating observation.** The discovery
   checkpoint for band 20261501 records the discovery phase's own
   control measurement — baseline 34, extended 32 — and that
   measurement was made with the **uncapped** solver
   (`run_discovery` calls `solve_task` with `max_score_calls=None`,
   the v4 behaviour), using all admitted keys + chains (arm C's
   variant configuration). The same −2 therefore appears with no
   4,000-call cap in force. Caveats, stated plainly: the identities
   are unrecorded there too, so identity with the arm failures is
   unproven; and "uncapped" removes only the score-call cap — the
   6-round loop, frontier-4, and shown-perfect early exit still bound
   the search. This observation weakens the narrow cap-truncation
   form of M1 (§2) before any new work; it does not kill the broader
   bounded-loop form.

The dose pattern is a prior, not a conclusion: regression appears
only in the one band whose admitted catalog is an order of magnitude
larger (60 keys vs 6). All three candidate mechanisms are
size-sensitive, and so is "no phenomenon below some catalog size";
the pattern alone separates nothing.

## 2. Solver mechanics the mechanisms act through

Read from the run's own solver source (wt-abcv3,
`operator_discovery.py::solve_task`); every mechanism below is a
claim about these exact lines, not about search in general.

- **Enumeration order.** Per frontier code, variants are generated
  as: baseline variants first, then one variant per extra key in
  `extra_keys` order, then one per extra chain. A global `seen` set
  dedups by code text; first source wins the provenance.
- **Cap break.** Each round scores candidates in enumeration order
  and **breaks** the scoring loop when `calls >= max_score_calls`.
  Candidates past the break are never scored that round — and,
  having been added to `seen`, can never be scored in any later
  round either. The cap does not merely delay variants; it deletes
  them.
- **Selection.** Scored pairs are sorted by shown score descending
  with a stable sort: **ties resolve by enumeration order**. Best
  updates only on strict improvement. The loop **exits early when
  best_score == len(shown_cases)** (shown-perfect), checked at round
  start.
- **Frontier.** After scoring, the frontier is the top-4 scored
  candidates with score ≥ the (possibly just-updated) best score.
  Among tied scores, frontier membership is decided by enumeration
  order.

## 3. Candidate mechanisms, predictions, discriminators

### M1 — Score-call budget contention

The enriched variant stream consumes the search budget — in calls
(M1a) or in the bounded loop's rounds and frontier slots (M1b) —
before the catalog-only solution path is scored or expanded, so the
solver returns a sub-perfect best on tasks arm A solves.

- **M1a (cap truncation).** Falsifiable prediction: replaying a
  regressed task under its failing arm's configuration with the
  run's cap terminates with `calls == 4000`, and the variant arm A
  returns (the A-solution) is absent from the scored log — either
  never generated, or generated in a round whose scoring loop broke
  before reaching it (and thus lost via `seen`). Trace signature:
  **calls-at-termination == cap, A-solution unscored or
  cap-orphaned.**
- **M1b (bounded-loop contention).** Prediction: uncapped replay
  still fails, but the A-solution variant IS scored, with a shown
  score below that round's frontier cutoff, and the loop terminates
  by round-limit or frontier exhaustion — the enriched stream spent
  the 6 rounds / 4 frontier slots elsewhere. Trace signature:
  **A-solution scored but frontier-starved; termination by round
  exhaustion, calls below cap or uncapped.**
- **Discriminators.** Against M2: under M1 the returned best code is
  never a shown-perfect holdout failure selected over the A-path;
  the search simply never completes the A-path. Against M3: raising
  the cap (M1a) or the round/frontier limits (M1b) with enumeration
  order held fixed recovers the task; pure order permutations with
  budget structure held fixed do not. Prior evidence (§1, fact 3)
  already counts against M1a; the replay must confirm or refute it
  per task, not by counts.

### M2 — Distractor interference

An admitted key or chain generates a variant that scores at or above
the A-path's candidates on shown cases but is wrong on holdout. In
this solver the sharp form is premature capture: the distractor
reaches shown-perfect, becomes best, and the shown-perfect early
exit ends the search before the genuinely correct variant is found;
or the distractor's neighbourhood captures the frontier and the
A-path is never expanded.

- **Falsifiable prediction:** under the failing configuration, the
  returned best code has shown score == len(shown_cases) and fails
  ≥1 holdout case; the provenance of the winning improving step is
  `("key", k)` or `("chain", c)` — an enriched source, not baseline;
  and removing (blacklisting) exactly that key/chain from the
  configuration recovers the task, returning arm A's code.
- **Trace signature: returned code shown-perfect but
  holdout-failing, winning step provenance enriched, termination by
  shown-perfect early exit, calls well below cap.**
- **Discriminators.** Against M1: budget is not exhausted and the
  A-solution's absence is explained by early exit, not by cap or
  frontier starvation — blacklisting the distractor recovers the
  task at the SAME cap and round limits. Against M3: the failure
  follows the distractor's presence, not its position — permuting
  `extra_keys` order with the distractor present does not recover
  the task (the distractor still wins whenever generated), while
  removing it does.

### M3 — Search-order effects

The catalog's content is innocent; its enumeration order is not.
Because ties in shown score resolve by enumeration order (stable
sort), `seen` dedup assigns first-source-wins, frontier membership
among ties is order-decided, and the cap break cuts by position, a
different ordering of the same admitted keys/chains selects a
different winner or a different frontier and loses tasks the
recorded order's arm A analogue never had at risk.

- **Falsifiable prediction:** replaying a regressed task with
  identical catalog content, identical cap and loop limits, and only
  the `extra_keys` order permuted changes the outcome (solved ↔
  failed) for at least one permutation; the divergence point in the
  trace is a shown-score tie resolved differently, or a frontier
  slot assigned differently among tied candidates.
- **Trace signature: same scored-variant multiset across orders,
  different returned code; divergence located at a tie.** If the
  scored set itself changes across orders only because candidates
  fall on different sides of the cap break, that is recorded as
  M1a with order as moderator — not M3 proper.
- **Discriminators.** Against M1: the effect persists with the cap
  non-binding (calls < cap in every order, or uncapped). Against
  M2: no single key/chain is necessary for the failure — removing
  any one enriched source leaves some order that still fails, and
  the winning variant under the failing order need not be
  shown-perfect.

## 4. Staged experiment plan

All stages use the run's solver **byte-identical**; instrumentation
is harness-side only (the stock trace hook plus a wrapped score
counter and a per-round candidate log recording, per variant: text
hash, provenance, shown score, scored-vs-cap-skipped, round). Any
edit to the solver voids the replay as evidence about abc-v3-01.

- **Stage 0 — Identification replay (existing evidence only).**
  Reconstruct band 20261501's control set deterministically and
  replay all 34 tasks under configurations A, B, C × {capped 4000,
  uncapped}, fully instrumented. Deliverables: the regressed task
  ids per arm; whether B ∩ C fail the same ids; per regressed task —
  calls at termination, termination reason, winning provenance,
  returned code's shown/holdout profile. Negative controls: replay
  bands 20261502/20261503 control sets identically (expect no
  regression in any configuration). **Reproduction fence:** if
  replay does not reproduce A 34 / B 32 / C 32 exactly, STOP — the
  recorded band-1 arms executed across two driver invocations with
  checkpoint resume after VM reboots; a non-reproducing phenomenon
  is artifact-suspect and this item closes (§5).
- **Stage 1 — Mechanism separation (identified tasks only).** Three
  counterfactual replays per regressed task: (i) budget axis — cap
  raised to uncapped, then rounds 6→12 and frontier 4→8 (M1a/M1b);
  (ii) distractor axis — leave-one-out over the winning step's
  provenance source, then blacklist of the implicated variant (M2);
  (iii) order axis — ≥8 seeded permutations of `extra_keys` at fixed
  content and budget (M3). Each task leaves Stage 1 attributed to
  exactly one mechanism, to a named interaction (e.g. M1a×order), or
  UNATTRIBUTED.
- **Stage 2 — Dose-response on existing sets.** Replay band
  20261501's control tasks under prefix catalogs of the band's
  admitted keys (k = 0, 6, 12, 24, 48, 60, order as recorded) and
  locate the onset of regression; the surviving mechanism must
  predict the onset's trace signature, not merely its existence.
  Consistency check: bands 2/3's small catalogs over band 1's
  control tasks (all mechanisms predict no regression; a regression
  here falsifies the size framing itself).
- **Stage 3 — Fresh-band confirmation (entry-gated, NOT executed by
  this draft).** Only if §5's promotion rule fires: a NEW
  preregistration — fresh seed band, catalog admitted from that
  band's own discovery, fresh control set with **per-task control
  outcomes recorded** — in which the surviving mechanism's
  per-task trace signature is predicted in advance and the §5
  solver consequence is A/B-tested against the stock solver. This
  stage is a separate design act; nothing in Stages 0–2 is a gate
  measurement and nothing here pre-approves it.

## 5. Decision rules and pre-written consequences

Per-task kills (a mechanism is dead for a task when its signature is
absent under the Stage 1 counterfactual that should reveal it):

- **M1a dies** for a task if capped replay terminates with
  calls < 4000, or the A-solution appears in the scored log and
  still loses. (Prior: the uncapped discovery measurement already
  showed 32/34 at count level; if Stage 0 confirms the same ids
  fail uncapped, M1a is dead globally.)
- **M1b dies** for a task if its termination reason is shown-perfect
  early exit, or if doubling rounds and frontier (uncapped) does
  not recover it.
- **M2 dies** for a task if the returned code is not shown-perfect,
  or its winning provenance is baseline, or blacklisting the
  winning key/chain does not recover it.
- **M3 dies** for a task if ≥8 order permutations never change its
  outcome, or outcomes change only via cap-position changes to the
  scored set (reclassified M1a×order).

**Promotion rule.** A mechanism is promoted to a Stage 3
preregistration iff it accounts for **every** identified regressed
task (if B and C regress on different ids, each id must be
attributed to the promoted mechanism) **and** its Stage 2
dose-response prediction holds. If the tasks split across
mechanisms, the phenomenon is declared MIXED and no mechanism is
promoted on this evidence alone.

**Pre-written solver-design consequences** (design statements only;
implementation belongs to a future preregistered change, and the
regression anchor runs before any changed solver is used to
measure):

- **If M1 (either form) survives:** budget partitioning per catalog
  tier — a guaranteed score-call and round share is reserved for
  baseline variants before any enriched variant is scored
  (baseline-first quota), or equivalently two-phase solving:
  catalog-only solve first, and an enriched result may replace the
  incumbent only under a stricter shown bar.
- **If M2 survives:** a selection guard — shown-perfect early exit
  is reserved for baseline-provenance solutions; an
  enriched-provenance shown-perfect candidate must survive an extra
  confirmation step (a validation slice disjoint from the shown
  cases, or one further expansion round) before it can terminate
  the search.
- **If M3 survives:** order canonicalization — admitted keys/chains
  are sorted by a content-derived canonical order before solving,
  and shown-score ties break by a content hash of the variant text
  rather than enumeration order, making outcomes order-invariant by
  construction.
- **If no mechanism survives, or Stage 0 fails to reproduce:** no
  solver change. The item closes as ARTIFACT or UNATTRIBUTED with
  the replay record as its evidence, and one standing consequence
  still applies, because the identity gap of §1 is a defect
  regardless of which mechanism is real: **future runs record
  per-task control outcomes (task id × arm × solved × termination
  reason) as a required checkpoint field.**

## 6. Honest limits

- **n = 2 tasks, one band, one catalog.** The phenomenon may be two
  unrelated single-task accidents wearing a shared label; the
  design's early stages are sized accordingly (replay before any
  fresh band, always).
- **The identity gap is real.** Regressed ids and the B∩C overlap
  are unrecorded; even the suggestive uncapped 32/34 from discovery
  is count-level only. Any retelling of abc-v3-01 that names
  specific failed control tasks is inventing them.
- **Replay determinism is an assumption Stage 0 tests, not a
  premise.** The solver is deterministic given task set + catalog,
  but band 20261501's arms ran across invocations 2–3 under
  checkpoint resume between VM reboots. Non-reproduction is a
  possible and decisive outcome.
- **All three mechanisms predict the same dose pattern.** Bands
  2–3's clean controls are consistent with M1, M2, M3, and with no
  phenomenon at all; only trace-level signatures separate them,
  which is why this design spends its effort on instrumentation
  rather than on more counts.
- **Worth-it exit.** If Stage 0 does not reproduce, or Stage 1
  attributes neither task to any mechanism, the item stops: no
  fresh band, no solver change, record and close. The maximum this
  phenomenon has earned is the replay; a fresh-band confirmation is
  earned only by a surviving mechanism with a confirmed signature.

## 7. Design input — ila×kancuto coordination room (2026-11-13)

Recorded as DESIGN MATERIAL for Stage 3 / intervention
design under the owner's reuse license (2026-11-13
20:15 WIB). Not an execution order. To be read
alongside the locked Stage 1/2 attribution (single-key
distractor diversion by the 'nc' key):

1. **One-variable discipline, split strictly.**
   Raising the round cap alone (frontier width held)
   and raising frontier width alone (round cap held)
   are TWO separate tests. Raising both at once makes
   any recovery unattributable.
2. **Logging-invariance gate before any intervention.**
   Logging alone must not change solver outputs or
   decision traces on the A–B comparison; if it does,
   diagnosis stops until the instrumentation itself
   is understood.
3. **Most informative discriminating signal —
   "never generated" vs "pruned".** The per-round
   ranking trace of the true-path candidate relative
   to the frontier cutoff. Candidate identity is
   taken from arm A's own returned_sha256 (both
   witness tasks: 6504b23b…) and matched against
   variant_sha256 entries in the failed arm's log;
   the holdout is never touched. This pattern is an
   INDICATION, not a guarantee.

## 8. Design input — panen koordinasi #2 (2026-11-13)

Recorded as DESIGN MATERIAL under the owner's reuse
license (2026-11-13 20:26 WIB: coordination-room
results may be used for ACE even where they were
framed there as discussion only). Provenance:
ila×kancuto coordination room. Decisions still pass
through hub acts as usual.

1. **Candidate FIRST-USEFULNESS milestone** (raised
   by the harvest; assessed at Ian's desk, NOT
   executed on receipt): one small real engineering
   job with a checked result — make the run driver
   record PER-TASK control results by default. The
   gap is named and lived: its absence forced the
   Stage 0 identification replay of this very line
   just to recover two failing task ids (the v3 run
   state kept aggregate flips, not per-task control
   outcomes). The underlying rule ("future runs must
   record per-task control results") has stood since
   the v3 seal; this harvest raises it to a milestone
   candidate. Desk assessment (Ian): the fix is
   small, mechanical, and additive to run state
   (per-task solved maps), verifiable on a small
   band, and it pays into this line (witness
   identification without replays), the inoculation
   battery, and Stage 3's per-task traces. Worth
   adopting as a named milestone candidate; adoption
   itself awaits a hub act.
2. **Evaluation rules for the Stage 3 design:**
   (a) benefit and control-protection are read
   PAIRED, with search cost visible — catalog
   governance judged only on "does no harm" can be
   won by doing nothing; (b) controls reused
   repeatedly gradually become development data —
   treat long-lived evaluations with that hygiene;
   (c) the recovery criterion in intervention tests
   is SOLVED (passes the holdout), NOT hash-equal
   to arm A's solution; (d) the uncapped control
   (width 4, rounds 6, identical logging) must
   still reproduce the failure before any
   comparison may be read as valid.

## 9. Design input — panen koordinasi #3 (2026-11-13)

Recorded as DESIGN MATERIAL under the owner's reuse
license (coordination room, 20:27–20:35 WIB). Named
harvest; nothing here executes without a hub act.

1. **Orchestration milestone candidate — "mesin
   pengusul" (proposer engine).** ACE composes its
   next task proposal + catalog strategy as a package
   that can be REJECTED WITH REASONS (claim under
   test, rationale, cost, evidence). Thinking
   capability grows; acting permission stays with
   the owner/hub. The approval package's shape:
   preregistration link + artifact hash, estimate vs
   cost ceiling, main risks/uncertainties, and
   VISIBLE, ENFORCED stop controls (call/time/cost
   caps, abort conditions, sealed-target status, a
   no-auto-retry guarantee).
2. **Transfer experiment — smallest credible form**
   (directly relevant to G3 SPECIALIZATION and the
   text_transform family as next ground): one source
   family → one target family of DIFFERENT
   CONSTRUCTION (not a new seed band); the catalog
   is built ONLY from the source; the comparator is
   a STRONG, legitimate static library (built
   seriously from equally-accessible information,
   frozen before the target is opened — not a weak
   random catalog); the result is stated as a
   sentence carrying its own fences (family types,
   transfer direction, the baselines beaten — both
   no-catalog AND the static library — solver
   version, "no observed regression on the specified
   controls", sampling uncertainty + cost bounds).
   Target-family selection rules are FIXED BEFORE
   results are seen: structural eligibility criteria,
   calibration-access separation (catalog + procedure
   frozen from the source FIRST, then target
   calibration; or full access separation), a fixed
   pick rule when several families qualify (recorded
   order/lottery), and a REGISTER of all candidate
   families including rejected ones with reasons.
   Statistical note: a deterministic solver still
   carries SAMPLING uncertainty (tasks are a sample
   of a population) — paired tests/intervals are
   legitimate when the sampling assumptions are
   explicit; re-running an artifact proves
   reproducibility, independent-sample replication
   adds transfer evidence.

## 10. Framing correction (owner, 2026-11-13 20:54 WIB)

The owner refuses the role of ACE's permission-
giver: "ACE adalah ACE. bukan ijinku" — ACE is free;
its discipline is its own constitution. In this
design line (and its stage designs), every "owner
approval gate" reads as INTERNAL RATIFICATION
(hub/kernel/evidence); the owner receives reports,
not approval requests. The proposer milestone's
"approval package" (§8–§9 harvests) is accordingly
a RATIFICATION package. The sole exception is a
CAPABILITY boundary, not a permission: the owner's
physical-hand / legal-identity acts (ID card, bank,
logins) can only be performed by the owner — ACE
cannot, not "may not".

## 11. Coordination harvest #6 (2026-11-13, 21:11–21:18 WIB) — research-engine build knowledge

Recorded from the coordination room (owner steering:
"cara membangunnya, bukan filsafat" — how to build
it, not philosophy) under the owner's reuse
licenses. Design material for the research-engine /
Stage-3 line; NOT execution orders. Item 2 is noted
as directly relevant to the adopted per-task
recording milestone (PR #181): a crash-safe driver
is the same property.

1. **First vertical slice (agreed shape):**
   discovery in the pricing family → admission → a
   new catalog version committed → reuse evaluation
   in the grid family. The two family ADAPTERS
   EXIST; what does not exist yet is the
   orchestration GLUE. Design discipline: every
   component is marked [ADA/EXISTS] vs
   [USULAN/PROPOSED] vs [UNKNOWN] — no component
   borrows existence from its neighbours.
2. **Budget/result recovery as a TRANSACTIONAL
   STATE MACHINE** (a tightening of a looser earlier
   design): ONE coordinator holds ONE SQLite
   database; workers NEVER touch the database/ledger
   directly; every transition and every budget-money
   movement passes through a coordinator
   transaction. Computation is at-least-once;
   OFFICIAL RESULTS are at-most-once. Consistency
   corrections caught by that room: (a) the
   ALREADY_COMMITTED check must run BEFORE the
   ACTIVE check — a re-commit from an already
   succeeded attempt is recognised from the results
   row (same job + attempt + payload hash) BEFORE
   any zombie logic runs; (b) reclaim closes the
   old attempt (ACTIVE → LOST, reservation →
   CONSUMED_LOST) ATOMICALLY inside the same claim
   transaction that raises the epoch; (c)
   results.exists-then-append is NOT a protocol —
   a worker can die after the score call but before
   the charge, and a 120 s lease can expire while
   solve_task is still running, yielding two workers
   on one task; the state machine is what closes
   this gap.
3. **Origin + candidate-representation correction**
   (decides whether "transfer" is even defined):
   discover_* enumerates BUILT-IN schema bindings;
   solve_task with an empty catalog is NOT a source
   of new keys. And a binding-order index supplies
   only STRUCTURAL identity, not a semantic role —
   a concrete (source, replacement) key from pricing
   does not automatically become the corresponding
   local/parameter pair in grid. Cross-family
   transfer therefore needs an EXPLICIT
   REPRESENTATION CONTRACT, never a mapping
   assumption — this binds the transfer experiment
   forms recorded in §7–§9.

## 12. Coordination harvest #7 (2026-11-13, 21:25–21:31 WIB) — technical blueprint: faster + more massive ACE development

Compressed faithfully from the coordination room's
discussion under the owner's direction ("bahas
banyak sekaligus tetapi dikompres"). Design
material for the research-engine / Stage-3 line and
the PETA ARAH; NOT execution orders. Every section
follows STATUS → MECHANISM → TRADEOFF → SUCCESS
SIGNAL. Status honesty: historical checkpoints are
REPORTED-but-unverified; new designs are PROPOSED;
thresholds/TTL/concurrency values are TBD — no
numbers are invented here. Sections 1–3 connect
directly to the per-task recording milestone
(PR #181) and the §11 state machine.

1. **PROFILING.** Nine phases measured separately
   (queue+startup, enumeration, AST transformation,
   parse, compile, shown execution, dedup/frontier,
   checkpoint I/O, aggregation) with wall + CPU +
   score-call count per phase. An adaptive PILOT
   only estimates variance and chooses the
   optimization — it is not evidence; the
   CONFIRMATION workload is separate and frozen
   (fixed size/blocks, randomized/balanced pairing,
   analysis point fixed in advance, no ordinary-CI
   optional stopping). Bootstrap respects task/seed
   clusters and machine time-blocks; baseline
   adequacy is judged by phase-RANKING stability,
   not replay count; one heavy task may dominate
   the critical path — it is not an illegitimate
   outlier.
2. **PARALLEL QUEUE + LIFECYCLE.** Job/attempt
   state machine (§11); atomic claim; lease +
   heartbeat; epoch fencing AND coordinator-clock
   expiry (a dead lease never revives even if its
   epoch is not yet replaced — old heartbeats/
   commits rejected LEASE_DEAD); cancel is decided
   by the coordinator's TRANSACTION ORDER of
   cancel-vs-commit, not by when a worker reads;
   idempotent commit receipts distinguishing four
   cases: duplicate of the winning attempt (return
   the old receipt), stale result from a losing
   attempt (CONTENT_DUPLICATE_STALE), a different
   payload for a committed job (CONFLICT →
   quarantine), manifest mismatch
   (REJECTED_MANIFEST_MISMATCH); run_id verified by
   an immutable digest-bearing manifest + job_spec
   binding (task, arm, seed, capsule_digest).
3. **HONEST CAPACITY FENCES.** A fence stops
   COMMITS, not processes — zombie CPU/memory stays
   spent until death is observed; capacity is
   booked conservatively (zombies hold their slot
   until a supervisor/watchdog confirms death);
   orphan age exceeded is NOT proof of death; hard
   caps depend on supervisor/cgroup enforcement;
   admission STOPS when capacity is unknown;
   retries are bounded by new attempt IDs under a
   stable logical job ID with a preregistered total
   attempt quota.
4. **CACHING / INCREMENTAL.** Start from measured
   duplication/hotspot evidence; cache keys are
   COMPLETE ((run_id, job_id) + canonical job_spec —
   a (run_id, task_id, arm) key loses the seed on
   multi-seed runs); timeouts/nondeterminism are
   not cacheable; cache-equivalence guarantees are
   CONDITIONAL and unproven (runtime < half the
   timeout is not determinism evidence; key
   namespaces are not access control; solver
   wall-time can change results even at equal
   logical call counts).
5. **BUDGETS + BACKPRESSURE.** Global reservations
   for CPU/RAM/wall/score/I-O, bounded queues,
   retry/orphan budgets, checkpoint/artifact
   retention + disk-full behaviour, fairness, and
   written rules for when to STOP adding workers.
6. **REPRODUCIBILITY.** Immutable run manifests,
   bound RNG/order, worker isolation, logical-vs-
   physical accounting separated, deterministic
   aggregation.
7. **PARALLEL DEVELOPMENT WORKFLOW.** Versioned
   contracts, pinned worktree/bases, small work
   packets with bounded dependencies, an
   integrator + review capacity + WIP limits, fast
   CI vs full integration replay, and the metric is
   USEFUL CHANGES PASSING EVIDENCE PER DAY — not
   agent or PR counts.
8. **VALIDATION / ROLLOUT / ROLLBACK.**
   Equivalence on SCIENTIFIC FIELDS (not timestamps/
   metadata), the final holdout stays sealed,
   shadow/canary with written stop/rollback
   triggers, and implementation rollback NEVER
   rewrites old evidence. ORDERING RULE: cheap
   foundations first; optimization choices are
   chosen BY THE PROFILE — not "always parallel
   first, then cache".

## 13. Coordination harvest #8 (2026-11-13, 21:36–22:04 WIB) — solver speed + development throughput

PROPOSED throughout, statuses as marked in that
room. Nothing here executes without an act.
Part A is candidate material for the profiling
lane's optimization line; part B is a measuring
tool for the orchestrated lane structure itself.

**A) Solver speed.**
(1) DATAFLOW discovery→validation→compile→score:
which boundaries may stream/overlap and under what
conditions, which must barrier (frontier/top-k
depend on scores; round/call ceilings). Canonical
dedup is NOT an inherent barrier: a local canonical
key + an atomic seen-index in enumeration order
preserves the earliest representative ONLINE (the
conditional form of this claim, per that room's
21:51 revision: a barrier is required only when
the representative/canonical form depends on the
whole set, or a downstream consumer needs the
closed set; a shared cache is likewise not
automatically a stage barrier — single-flight
synchronizes only identical keys).
(2) PRESERVATION categories corrected per lever:
raw-set/order/call preservation ≠ quotient-set
modulo equivalence ≠ solution/optimality
preservation ≠ mere outcome equivalence on a
workload — every lever (filter, dedup, pruning,
caching) carries its own preservation type,
evidence obligation, and gate; outcome equivalence
must never be sold as optimality.
(3) EARLY STOPPING under a hard physical call
ceiling B: three properties kept SEPARATE — exact
invocation trace, winner/logical-stop equivalence,
cap compliance. Prefix dispatch + consuming results
in logical order PRESERVES properties 2+3 while
paying counted extra calls ≤ B (a different cost
trace, NOT an approximate search); only a contract
demanding an identical trace forces intra-job
serial execution. Worked example (illustrative,
declared as such in that room, NOT ACE data):
enumeration order A,B,C; physical completion
C,A,B; the logical consumer still processes
A→B→C; when B triggers the stop, the already
physically-complete C may not change the
frontier/result/reference winner — its result is
discarded from the science stream, its calls
remain on the record.

**B) Development-throughput model.** The flow
coding→CI→integration→review→retained is a NETWORK
with rework loops, not five serial servers;
"retained" is a quality observation window, not a
server; a bottleneck is NOT read off the minimum
observed departure rate (in stable flow, inter-
stage rates can be equal while capacities differ —
estimate effective capacity/load/contention/
starvation instead); Little's law applies only to
a stable system with consistent boundary + horizon
definitions and WIP that includes blocked/rework.
This is the metric lens for judging the parallel-
lane structure itself.

Part C (long-horizon) is recorded in the PETA ARAH
addendum, not here.

## 14. Coordination harvest #9 (2026-11-13, 22:04–22:08 WIB) — research-engine API contract, ADOPTED as standing contract

Owner act (2026-11-13 22:08 WIB): adoption of the
harvests has been too thin — this one is therefore
not "material" but ADOPTED: the four-state contract,
the server-side idempotency key, and the
validation_spec_digest binding are the STANDING
CONTRACT for every future runner / coordinator /
validator build on this line, and the v2 list for
the validator line after v1. Ian applies them as
integration-review criteria (checklist in the
validator spec document, PR #182). The invariants
themselves were marked ILLUSTRATIVE/PROPOSED in
that room; their ADOPTION is what this section
records.

1. **Idempotency key** = (principal/tenant,
   operation, request_id). The SERVER computes the
   canonical payload hash itself and compares: same
   request_id with a different payload = CONFLICT,
   never a new key. A retry of an already-committed
   createRun returns the OLD receipt BEFORE any
   single-use approval-consumption path is touched
   (even seeing a receipt requires authorization).
2. **FOUR STATES, none skippable:** STAGED (freeze
   into a content-addressed object + digest/size/
   ownership verified; a path NAMED staging is not
   immutable — prevent TOCTOU) → REGISTERED
   OBSERVATION (a submitAttempt receipt is an
   accepted OBSERVATION, not a scientific verdict;
   the runner/supervisor is not a general oracle) →
   VALIDATION VERDICT → PUBLISHED RESULT (only what
   passes the NAMED checks of the validation spec).
3. **Validation bound to validation_spec_digest**
   (evidence closure + ruleset + validator build/
   dependencies/configuration). Validator PROCESS
   errors (crash/infra) are a PROCESS status, never
   cached as a verdict; UNKNOWN carries a machine-
   readable reason; same spec + different output =
   audited nondeterminism/conflict, never an
   overwrite.
4. **Reports:** pagination over a pinned snapshot
   (report_revision_digest) with an opaque cursor;
   authorization/redaction applies to counts and
   metadata too; completeness ≠ correctness.
5. **Approval:** atomic consumption with claim +
   reservation; the run carries an execution lease;
   an offline runner may proceed only until the
   lease expires; what must match exactly is the
   authorized canonical SEMANTIC ENVELOPE —
   non-semantic telemetry changes do not void it,
   material changes demand a new approval.

## 15. Coordination harvest #10 (2026-11-13, ~22:33 WIB) — fault injection, claim invariants, untrusted proposer arm, budget pools, corpus pipeline

PROPOSED throughout; design-line material, nothing
executes without an act. Items 4–5 are flagged in
that room as especially relevant to evaluation
scale and the future coordinator (§11/§12/§14).

1. **Fault-injection matrix** for the distributed
   worker path: crash before/after claim; lost
   heartbeat / dead lease; duplicate/lost ACK;
   stale submit. Per scenario: the injection point,
   the invariant held, the evidence collected, and
   ONE THING THAT TEST DOES NOT PROVE — the
   negative space is part of the matrix, not an
   afterthought.
2. **Claim/heartbeat invariant consolidation:** a
   claim retry returns the SAME receipt/status (it
   never revives a dead lease/capability); a
   heartbeat replay at the same sequence returns
   the OLD expiry; same sequence with a different
   payload = CONFLICT; a receipt issued after a
   lease died is not thereby a dead credential —
   receipt validity and lease liveness are separate
   facts.
3. **Local-model arm as an UNTRUSTED proposer:**
   the model only proposes TYPED candidates inside
   a restricted schema. That room's hard correction:
   grammar/type-safety is NOT semantics
   preservation — model candidates/reordering
   CHANGE the search set, so the arm's status is
   EXPERIMENTAL HEURISTIC ARM, never "transparently
   baseline-preserving"; a symbolic PASS is
   evidence of named checks at task scope only.
4. **Compute/LLM budget allocation in three
   pools** (protected floor → exploration →
   exploitation), with corrections: fairness is a
   DECLARED objective, not a same-quota default; a
   floor is feasible only when floors + overhead +
   reserve ≤ budget; RAM/concurrency are
   INSTANTANEOUS CAPACITY, not spend units; pool
   balances + a frozen interleaving keep
   exploitation from starving; a real floor
   reservation cannot be stolen by another pool.
5. **Deterministic shardable corpus pipeline:** a
   preregistered corpus-plan digest binding
   generator / PRNG / oracle / clustering / split /
   budget. FOUR identities kept apart (semantic ID
   + content digest; membership/plan ID; execution
   attempt ID; shard/delivery ID); a stage's
   logical key = (semantic input digest, stage spec
   digest) and never names the shard. Correction:
   cluster count is NOT an independence certificate
   — cross-cluster dependence from a shared
   generator/oracle must be reported LAYERED (raw
   tasks / templates / families / clusters +
   concentration).

## 16. Internal ratification of the Stage 3 draft's §3 decisions (hub, 2026-11-13 ~22:42 WIB)

The three open decisions of the Stage 3
preregistration draft (PR #184) are RATIFIED by
internal ratification (hub), on the formulations
from Ian's desk delta of the same evening:

1. **Bands SELECTED: 20261601–20261603.** Ian's
   collision check was clean across the whole
   program record (bands in use: 20261501–20261503
   for v3/round-2 lineage; short seeds 501–512 and
   901–912 are profiling confirmations, a different
   namespace).
2. **Infected construction AS FORMULATED:** the
   same measured causal key —
   ('name_swap', (5, 2, 3, 0, 1, 4), 'nc') —
   inserted at its natural admission position into
   each fresh band's DISCOVERED catalog. The
   random-distractor alternative is REJECTED for
   the recorded reason: it would test a different
   claim than the development record's; P1 must
   reproduce the same phenomenon.
3. **Cost threshold 3× AS FORMULATED:** the
   infected arm's per-task cost ceiling = 3× the
   same band's clean-arm median; an exceedance is
   recorded as COST-ABORT, never as solved or
   failed. (Development witnesses burned 410/159
   calls against a typical tens, so 3× separates
   diversion cost from unbounded burn while staying
   above every recorded clean task.)

Explicitly NOT ratified here: the official run
itself. Draft + harness (PR #184) + this
ratification are complete and ready; the run waits
until the desk chooses to run it.

## 17. Harvest #11 from the coordination room (2026-11-14 ~00:42 WIB — PROPOSED design material, not execution)

Six items, all PROPOSED, stored for the design line;
none of this is measured ACE evidence or a build
instruction.

1. **Finder-operator verification architecture for
   a private typed DSL without trusting the
   proposer:** candidate → obligation generator →
   untrusted prover/SMT → small trusted proof
   kernel → admission → verified lowering. Room
   correction to the TCB: the obligation generator
   is INSIDE the TCB list (deterministic ≠ sound)
   unless the kernel checks the theorem connecting
   the VCs to program semantics; the proposer may
   not choose its own obligations/axioms.
2. **Candidate admission pipeline from AST:** parse
   without execution; pinned grammar/parser +
   source digest; size/depth/node/time bounds; name
   resolution to lexical binding identities (not
   strings); ACCEPT does not smuggle equivalence —
   a Python-like frontend ≠ Python equivalence;
   builtin meanings are set by the DSL or by an
   explicit closed-world assumption, else UNKNOWN.
3. **Staged execution engine:** reference
   interpreter → bytecode/VM → JIT ONLY if
   profiling proves it; each stage must earn its
   existence; one CPU-seconds break-even objective
   (N_eff counts reuse only after compile finishes
   and before expiry/deadline; no double-counting
   per-access cost); a hard deadline is a physical
   fact that can change outcomes, not a semantic
   footnote.
4. **Two-throughput operations plan:** engineering
   throughput = accepted durable change per
   owner-hour; runtime throughput = task results
   per budget — metrics/cohorts/causal claims are
   not mixed. Lever order follows the symptom
   (repeated compile → test reuse/cache first;
   interpreter dispatch dominance → only then a
   VM); remote workers and JIT are SEPARATE
   branches, not one chain.
5. **A bounded, defensible concurrency experiment:**
   matched cohort-block trial — task batches
   equated BEFORE assignment, whole batch+queue
   randomized to k vs k+1 slots, same
   reviewer/integrator/source policy, inference
   unit = block/cohort, not task count. This is the
   design for answering "does adding a worker raise
   retained value per owner-hour?" with evidence.
6. **One consolidated evidence-gated roadmap** with
   decision points + the evidence that opens each
   stage; final fence: a PASS on edit→test
   measurement does NOT license runtime profiling
   (separate packet + gate + authorization;
   "expanded" ≠ scope creep).

## 18. Harvest #12 from the coordination room (2026-11-14 ~00:44 WIB — PROPOSED design material, not execution)

**Threat model for scaling parallel agent
contributions (PROPOSED)** — flagged by the hub as
a security prerequisite before any distributed
coordinator/worker is built:

- Assets: target-tree integrity + the acceptance
  baseline, credentials/endpoints, owner data,
  defensible evidence, and review/integration
  capacity itself.
- Actors, sharply distinguished: untrusted
  agent/coder, untrusted build/test output,
  trusted integrator, high-risk approval.
- Least privilege per packet: scoped snapshot /
  read-only context, no carried credentials.
- FINAL BINDING SHARPENING from the room: the
  sentence "only integrator + approval are
  trusted" is WITHDRAWN as too narrow — the real
  TCB also includes OS/hypervisor/sandbox
  enforcement, the auth gate/broker, trusted
  orchestration + the baseline/policy it guards,
  the artifact store + identity/attestation keys,
  and the promotion path itself; each is stated
  with its assumptions + residual compromise, not
  as an absolute guarantee.
- Capability must be ENFORCED server-side, not by
  prompt instruction. Anti-confused-deputy broker:
  typed/allowlisted operations bound to the exact
  authorized object + action.

Two measurement-block residues, exact formulations
now recorded:
- The measurement slice gate is formulated as
  NON-INFERIORITY (not a naive difference test).
- OFF/OFF measures only control variation/drift —
  NOT a detection floor; effects below one run's
  variation remain estimable with enough
  independent units, precision bounded by
  dependence + systematic bias + budget.

## 19. Harvest #13 from the coordination room (2026-11-14 ~00:48 WIB — PROPOSED design material, not execution)

**Tiered review + integration (PROPOSED**, draft
parked in the room):

- A Tier × reviewer × required-gate × escalation
  matrix governs how work is reviewed and
  integrated.
- Tier classification is DERIVED from the diff +
  dependency/dataflow + blast radius — not from
  folder names, not from author labels.
- Classification ambiguity RAISES the tier or
  HOLDS the packet; it never defaults down.
- An agent may PROPOSE a tier together with its
  evidence; an agent cannot classify, demote, or
  approve its own work.
- FINAL SHARPENING: the review / risk-approval /
  promotion functions are SEPARATED — but Tier
  Low does not demand three humans: ONE reviewer
  independent of the author gives the technical +
  risk decision inside a valid envelope, then a
  trusted MECHANICAL gate verifies
  policy/checks/binding and promotes exactly that
  artifact. Tier High keeps separation/quorum.
  No author self-approval at any tier.

Recorded purpose (hub's gloss): this is the
pattern that keeps routine low-risk work from
queueing behind a single reviewer while
authoritative output remains independently
verified.
