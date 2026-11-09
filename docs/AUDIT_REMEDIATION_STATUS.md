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
