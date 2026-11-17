# EXECUTION AMENDMENT — Confirmation Run, Attempt 3

Ordered by the owner via the hub, 2026-11-15 (v1 ~21:33, v2
~21:38 WIB): cut the run's wall-clock duration by parallelizing
independent units; the SCIENCE is unchanged — verdict rules
(A.7), bands {20261803, 20261804, 20261805}, arms, conditions,
cost metric (solver-call counts, not wall-clock), hash sealing,
and the contents of every cell/arm are exactly as
preregistered in PR #188 and built in PR #193. The frozen
instrument's code is NOT modified (harness sha 4fed8054…,
gate sha b9a7d02d…, verified in pre-flight).

## Execution form (final)
1. **Per-band cell lanes (parallel):** three separate
   processes, one per band, each calling the frozen harness
   module's OWN run_band_cells for its band into a lane-private
   state dir (evidence/lane_state_<seed>/). Bands are
   independent by construction: separate catalogs, contexts,
   and per-process score recorders; no shared mutable state.
2. **Atomic placement:** a placer process copies each
   completed cell checkpoint into the official state dir
   (evidence/lineage_guard_state/) via temp-file + rename,
   after validating that the lane's file parses as JSON.
   Placement races are therefore impossible: the official run
   only ever sees complete cell files.
3. **Official run (single process, the sealed one):** the
   frozen harness in run mode under the unchanged act. It
   executes steps 0–4 itself, fresh (act checks, L4 gate,
   L1/L2 reproduction, step-4 battery with the corrected
   --battery-dir …/wt-battery/code/ace_operational), then
   step 6 loads the pre-placed cell checkpoints through its
   own checkpoint-resume path ("a loss resumes from
   checkpoints, never restarts a cell"), and steps 7–8
   (worksheet + top record) are computed by the harness
   itself. If a checkpoint were missing, the harness would
   compute that cell in-process — identical results, only
   slower.
4. **Concurrency:** lanes and the official run overlap; the
   official run's gates+battery phase (~18 min measured:
   gates ≈7.5 min from the preparation smoke, battery ≈10 min
   from the standalone step-4 proof) is the critical path.
   Estimated total from lane launch: ≈20 minutes.
5. **Determinism guard (hub condition):** one task record per
   band is recomputed in a fresh process and compared
   byte-for-byte against the lane's record (per-task records
   carry no wall-clock fields). Any divergence → STOP and
   report; the run does not proceed on mismatched cells.
   Sequential-equivalence anchors already observed: the
   preparation smoke and attempt 2 produced identical L4/L1-L2
   outcomes in separate processes; Stage 3 repeated bands
   reproduced identical results across runs (PR #192).
6. **Not cut (per hub):** control arms, the L4 gate, the
   step-4 battery, hash sealing — all execute inside the
   official run as preregistered.

Recorded by the operator before the attempt-3 run command, as
required. The pre-flight (path checks + population digest +
parallel checks) output is preserved with the run evidence.
