# S4-v2 observed public synthetic development result — REJECT

Pre-score protocol commit: `536df2feb1f1206a573aaf55960522f3c74d434e`. Code commit: `d117a383e199076bb3046e990a8088d53404ea0e`. Executed 2026-11-05 with local CPython equivalent source, exit 0. Re-execution of the GitHub exact-head checkout and CI is NOT verified.

**Accounting correction (disclosed after scoring):** pre-score protocol mistakenly stated 11,520 labels, assuming five development policies. Implementation deliberately runs one development probe policy (online-last) to learn the successor bit, then five policies on each of future and negative splits. Correct total is **8,448 simulated labels**: development 768, future 3,840, negative 3,840. The prespecified acceptance threshold and all success counts remain unchanged. The erroneous protocol is retained unmodified for auditability. This discrepancy reduces protocol fidelity and prohibits confirmatory claims.

Four generations × 32 tasks × 6 labels each. Successes per policy out of 768 future labels: successor 500, online-last 500, online-flip 477, fixed0 483, fixed1 499. Future gain vs strongest control: **0/768 = 0 percentage points**, below prespecified +5pp (38.4 additional successes).

Adversarial inverted-transition regime (stay=0.15): successor 470, online-last 470, online-flip 484, fixed0 474, fixed1 471. Negative gap vs strongest control: **-14/768 = -1.823pp**, within prespecified -5pp tolerance.

Inferred transition mode per generation: SAME, SAME, SAME, SAME. Inferred same transitions: 23,22,24,25 of 31 per generation. Thus the successor collapses to the online-last control, explaining its zero future improvement; this is not evidence of new algorithm or architecture.

Local process CPU time about 0.0051 seconds (machine-dependent). This is a single-seed synthetic development test, not a confirmatory statistical result. No external labels, frozen banks, paid services, deployments, main, or Tod changes.

**Decision: REJECT** for recursive improvement. Preserve S4-v1 REJECT and E1.4/E1.4aa HOLD/NOT_ASSESSED. No new self-authored code/architecture: only selection of a learned policy bit.

Next falsifiable hypothesis: With genuinely alternating nonstationary transition modes and a bounded online change-point estimator, a successor carrying calibrated transition posterior across task families may exceed a strong equal-budget online estimator on disjoint sequences. Include a deliberately mis-specified regime and precommit a complexity penalty; reject if no >=5pp future gain or negative degradation exceeds 5pp. Do not repeat the current stationary-family design.
