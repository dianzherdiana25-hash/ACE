# Brain bake-off 01 — Qwen3-4B challenges Qwen3-8B for the local director seat (2026-11-13)

Stage report (Ian, Muse). Experiment `brain-bakeoff-01`,
preregistered in a fresh ExperimentKernel BEFORE the
candidate model finished downloading; protocol hash
`7db0976460f85dd3ad0601e29cb1bd50e2961f3f03100fd57529b3ce083e1a09`.
Owner decision of record: replace the local director with
a faster brain without losing reliability; the 8B is
museum-ized only on a pass.

## 1. Verification gate (before any run)

The candidate was custodied by EXPECTED identity (HF LFS
oid + size). Measured on the downloaded file:
SHA-256 `7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5`
== expectation; size 2,497,280,256 bytes; ACE's GGUF
parser's expected total size == file size. Gate PASSED —
the runs below are the custodied candidate's. (The
download itself was interrupted once by a runtime restart
at ~61% and resumed; the hash is the arbiter.)

## 2. Measured results (one attempt per instrument, router config temp 0.3 / max_tokens 700 / timeout 900 — the incumbent's proven configuration)

| Instrument | Bar (the 8B's record) | Qwen3-4B | Verdict |
|---|---|---|---|
| A — director cycle on a fixed packet | ACCEPTED (cycles 1–4) | **accepted**, 5 proposals, 373 s | PASS |
| B — B2A-02 dossier, computed table | 4/4, audit CLEAN, 535.6 s | **0/4** — decision REJECTED: "cites facts not in the packet: ['nimbus-gate']"; audit CLEAN; 341.4 s | FAIL |
| C — sealed repair fixture (Keamanan-01) | 6/6, LOCALLY_VERIFIED | **6/6**, LOCALLY_VERIFIED in 1 attempt, 138.3 s | PASS |
| Speed | B wall < 535.6 s | 341.4 s | PASS |

Full records: `evidence/bakeoff_a_run.json`,
`evidence/bakeoff_b_run.json`, `evidence/bakeoff_c_run.json`,
`evidence/bakeoff_result.json` (harness workspace).

## 3. Verdict and consequence

Pass rule (preregistered): A AND B AND C AND speed.
**FAIL** — on exactly the property the succession was
forbidden to lose. The 4B is genuinely faster (B wall
−36%, C wall −34%) and it directs and repairs at the
incumbent's level; but on the procurement dossier it
invented a plausible-looking fact id (`nimbus-gate`) that
is not in the packet, and the fail-closed validator
rejected the decision whole. Citation discipline is the
trait B2A exists to measure; a director that fabricates
citations cannot hold the seat on one attempt's evidence.

Consequence per the preregistration: **no registry swap,
no museum-izing. Qwen3-8B stays on duty** with its service
record intact; Qwen3-4B is recorded as a measured
candidate that did not pass. Its file is preserved in
`models/` (a future bake-off under a NEW preregistration
may re-test it; nothing here pre-judges that).

## 4. A named limitation of this stage's own paperwork

The ExperimentKernel's verdict derivation requires a
single-metric dict pass rule; this preregistration —
authored by Ian — expressed the conjunction as prose, so
`record_result` cannot intake the result (the kernel
ledger verifiably holds ZERO result rows for this
experiment; custody and preregistration records stand).
The sealed preregistration was NOT rewritten to fit.
Lesson for the next bake-off: encode the conjunction as
a composite metric (`bars_met` with `gte`). The
measurements stand in the instrument evidence files and
this report.

## 5. Agenda consequence (falsification births the next item)

The failure mode is specific: fact-id fabrication under
citation discipline. Two candidate mechanism items for a
future stage (not authorized by this report): (a) render
the packet's citable fact ids as an explicit whitelist in
the director packet — the B2A-02 lesson was "machines
compute, the director judges"; a whitelist is the same
pattern applied to citations; (b) bake-off v2 for the 4B
with the composite-metric preregistration, run only if
(a) or another mechanism change gives it a new claim to
test — re-running the identical test unchanged would
measure luck, not improvement.
