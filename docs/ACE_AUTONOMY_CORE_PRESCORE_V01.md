# ACE Autonomy Core v0.1 — acceptance registration

Base main: `80104ce50ecbcea21080bed8c0eabce88d47ccb5`, tree
`b805e4670be8c8ada0fb02dada450535039995d6`. Specification: draft PR66
`620069344c3f6fd9a04f7dbd6860bc35b0073318`, both deep-research and implementation
gate documents read on 2026-11-07. This registration adopts Gate0/Gate1 before
scoring the new acceptance harness. It makes no scientific-superiority claim.

H-A: a bounded, deterministic provider can complete approved source inspection,
trusted test execution or a call to the unchanged binary ACE runtime without
human instructions between each step. An independent host verifier must check
every tool receipt before success and capability registration.

Reject the engineering acceptance if any enumerated test fails: duplicate goal
delivery, restart after task reservation/receipt/staging, concurrent workers,
source changes, mutable or replayed receipt/state rows, missing objective steps,
unauthorized tools/paths, model-provided fake success, budget exhaustion,
cancellation, or ambiguous external effect followed by automatic retry.

Default ceiling:8 steps,4 staged candidates,1 retry per local step,180 wall
seconds,60 measured process/child CPU seconds. These are proposed engineering
limits, not science-backed optimal settings. Only trusted fixed core tests run;
untrusted staged code is never executed by the autonomy broker.

Operational success is SUCCEEDED or STAGED_FOR_REVIEW according to the objective,
not automatic merge, deployment or scientific promotion. Local pure/idempotent
actions may recover; an external action without a conclusive receipt stops in
HALT_UNCERTAIN. A host-side key seals receipts, state and checkpoints; a malicious
owner able to restore an entire valid database plus key is outside the local
integrity contract. No public endpoint, paid provider or always-on service.

Run source-exact baseline regression, all autonomy unit/integration/fault tests,
an actual two-worker test and subprocess crash, then an exact-SHA Actions run.
Archive a sanitized operational report and source fingerprints, never private
keys. Reproducibility compares semantic outcomes; workspace-specific HMAC keys,
clock readings and CPU timings are expected to differ.

Scientific NOT_ASSESSED; OAIE, unrestricted repair, new representation classes
and phenomenal consciousness remain unestablished. Native repair execution needs
its own verified sandbox and is blocked until then.
