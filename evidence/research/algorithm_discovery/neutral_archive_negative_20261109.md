# S2 neutral archive pilot — negative result (2026-11-09)

Prescore commit: `568439bac8fb4bd30b0476a9e3cf67b3b8837ee3`. Main source SHA: `b81c076ef0f326331f81cb9c0678d6baa3b3250f`. Implementation commit: `2c262c7190579d3987d174ac4bf98f7cf053abf9`. Local execution used Python stdlib and synthetic public task labels only. Scientific status **NOT_ASSESSED**, not a sealed or independently assessed result.

## Actual observed local pilot
24 deterministic coefficient tasks, first 8 development and remaining 16 evaluation, all 5 arms evaluated. Exact full-terminal solved counts:

| Arm | Development /8 | Evaluation /16 | Evaluation overfit /16 |
|---|---:|---:|---:|
| Two-structure neutral archive | 8 | 8 | 8 |
| Fixed DSL enumeration | 8 | 16 | 0 |
| No-mutation | 5 | 4 | 12 |
| Seeded random proposal | 8 | 16 | 0 |
| Equal-cost exhaustive | 8 | 16 | 0 |

**H1 rejected:** archive 50% vs strongest control 100% on disjoint evaluation coefficient pairs; delta **-50 percentage points**, below preregistered +10 pp. No independent discovery of operators/primitives. All 24 targets are expressible within the human-authored linear DSL. Nonlinear x*y outside-grammar control is not representable across six diagnostic inputs.

Measured local process CPU: **0.001203809 seconds** for the experiment core, excluding Python interpreter startup and JSON serialization; 3000 scored proposal slots, 18000 modeled arithmetic operations. Unique environment labels: 48 train, 24 counterexample; 96 terminal measurements; 6 additional outside-grammar diagnostic points. These are synthetic function evaluations, not purchased labels. Every arm reused the same 72 adaptation labels. CPU values are one local measurement, not an independent exact-GitHub-SHA replay.

## Deviations and threats to validity
- Prescore text incorrectly described the outside-grammar diagnostic as four additional terminal labels; actual diagnostic used six inputs (two training plus four terminal). Explicit deviation; do not treat the outside-grammar diagnostic as preregistered confirmation.
- Archive's 25 evaluation slots cycle through at most three neutral proposals, with only two distinct candidates retained; no-mutation also repeats a single candidate. Thus proposal-slot equality does **not** imply equal unique-candidate coverage, CPU, or useful search work. Fixed enumeration and exhaustive are behaviorally identical on this 25-candidate DSL, so they are not independent controls.
- Public deterministic data are researcher-authored and not independently sealed. The partition is disjoint in coefficient pairs but not in grammar or input topology; it does not establish generalization to unseen operator families. The negative control checks representational inability, not successful unseen-operator discovery.
- Local result file SHA256 `7bc6d24e0d33e7eeb7785b11565a7fa42ad5f16a1d466b08a6e00efc7fb2b576` (full local JSON rows). Exact local run results were generated before committing this report; the GitHub implementation was transcribed from that local script and has **not** been independently executed at its GitHub SHA. Treat report as local evidence only.
- The archive performs neutral coefficient mutations (structural changes within a fixed researcher-authored linear expression grammar), not open-ended operator invention.

Preserve the negative result. Do not merge or promote on this evidence. E1.4/E1.4aa and HOLD/NOT_ASSESSED remain untouched.
