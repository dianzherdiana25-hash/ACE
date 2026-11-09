# Audit remediation status

Candidate execution and autonomous publication are **blocked**. A Git worktree,
a Python subprocess, an installed isolation binary, and a container marker do
not establish that the candidate process is isolated from host data or secrets.
The controller also rejects apparent worktree success because no independent
candidate-bound evaluation currently exists. This is a containment measure, not
an implementation of an isolated evaluator or proof of candidate quality.

Re-enabling these features requires a verified per-process sandbox with restricted
filesystem, network and environment; tests exercising escape attempts; and a
candidate-bound evaluation with baseline, held-out and regression checks. The
sandbox must fail closed if these controls cannot be applied.

The SMT verifier rejects programs containing loops until an unwinding bound or
inductive invariant can be proved. Callers must handle `NotImplementedError` as
an unknown result; it is neither a proof nor a counterexample. Integer division
in the SMT solver uses integer arithmetic. These changes do not establish general
soundness of the solver.

The full-system CI workflow discovers Python test modules and runs on main. CI
success on an existing commit does not prove that this branch has passed CI.

An experimental stdio-only MCP diagnostic can be explicitly enabled with
`--enable-code-diagnostic`. It runs the isolated prediction worker under bwrap
and prlimit with a network namespace, restricted filesystem, cleared environment,
CPU, memory, file-size, descriptor and wall-time limits. It uses a public fixed
parity fixture and reports the candidate and fixture SHA-256, a constant baseline,
and `promotion_authorized: false`. It is not an independent holdout, a signed
receipt, a sandbox certification, or a replacement for the disabled production
evaluator and autonomous publication gate. Startup or candidate errors fail closed.

The same explicit opt-in exposes `ace_patch_diagnostic`, which compares a fixed
supervisor-selected regression suite against baseline and append-only patched
snapshots of `code/ace_self_dev/strategy_repair.py` at committed HEAD. It records
the commit and SHA-256 hashes of the base file, patch, candidate, test output and
receipt. If baseline or sandbox startup fails the candidate is not run. These
hashes are checksums, not signatures; public tests can be gamed, and passing them
does not establish improvement or authorize promotion. Other paths, dirty working
tree patches, arbitrary test commands and automatic PR publication are unsupported.
`verify_receipt` checks for changes against the included checksum, but anyone can
recompute that checksum; it must not be used as evidence of origin or authenticity.
In the local VM, separate candidate probes for host file access, environment
inheritance, modification of the read-only tests, and network access all failed
while their baselines passed. This is a bounded test, not a general sandbox audit.

`ace_host_exchange` defines data-only host requests and candidates, bound by
canonical SHA-256 identifiers to the full base commit and fixed target. Host/model
strings are self-reported metadata, not proof of identity, and checksums are not
signatures. Opt-in stdio MCP tool `ace_host_candidate_diagnostic` verifies both
envelopes and refuses a different HEAD or patch before returning the diagnostic
receipt. It performs no LLM call, persistent ledger write, improvement validation,
promotion or publication. Operators must not place secrets in these envelopes.
