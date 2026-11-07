# ACE Bounded Autonomy Prototype — Chat Engineering Lane
Date: 2026-11-07. Branch: `engineering/chat-ace-autonomy-prototype-20261107`.
Inherited preregistration: `d545083a5f0e9ddbb311511658b69121906378c9`, Codex `docs/ACE_AUTONOMY_CORE_PRESCORE_V01.md`.
Intended destination: draft PR, not main merge, deployment, or scientific claim.

## Implementation performed

`code/ace_autonomy/core.py` is a bounded **deterministic**, non-LLM goal dispatcher. It has:
- Fixed ordered goal steps and schema `ace.goal.v01`, maximum eight steps.
- Allowed tools only: `inspect_file` (read-only, max 64 KiB, checkout path check), `ace_status`, and `ace_demo`.
- The latter two call the **real** `ace_runtime.engine.Runtime` and original `ace_runtime.cli.demo`, rather than faking a model or capability.
- SQLite WAL/FULL, transactional goal transitions, HMAC-SHA256 hash-linked goal receipts, source pinning to orchestrator/core engine, idempotent goal enqueue, cancellation and a restart-safe one-step worker loop.
- Actual two-process worker test, state and HMAC tamper tests, source-change rejection and injected transaction rollback.
- Separate CI workflow for Python 3.12/3.13, source provenance verification, regression and public ACE demo replay.

## Status boundaries

**This is an A0 engineering spike only.** It does not create novel representations, detect software bugs, write patches, choose a research agenda, use external LLM providers, support hosted MCP, run forever, or demonstrate subjective consciousness / OAIE. The public `ace_demo` (3/3 tasks, two capabilities) is known prior evidence only. No unseen-family scientific evaluation is included.

The step sequence is supplied by the operator. `inspect_file` reads only and returns the digest/byte count, not arbitrary source text to a model. `ace_demo` is a fixed, bounded, replay-idempotent local educational action. **There is no arbitrary command execution or external side effect adapter**.

## Limitations and remaining acceptance gaps

- This prototype serializes the entire action within an SQLite write transaction. That safely controls two cooperative workers but is a scalability limitation; a production scheduler needs owner leases, externally mediated tool state and proven uncertain-effect recovery before external tools may be enabled.
- The HMAC key is locally stored in the trusted workspace, NOT an external immutable trust root. A privileged adversary can rewrite key and database. Concurrent first-ever workspace key initialization is not proven robust; pre-create trusted workspaces before competing workers.
- The tool-set is intentionally closed and the maximum step count is enforced. The preregistered CPU and wall-clock limits are **not yet preemptively enforced**, because this prototype only executes trusted bounded actions. Do not promote this as satisfying the full Codex Gate 1 acceptance.
- A path is canonicalized before opening, but `inspect_file` is not a race-resistant file-descriptor-based sandbox. A hostile repository could alter a symlink concurrently; only use trusted source checkouts until a hardened file opener exists.
- The deterministic planner cannot autonomously discover a new research agenda; it executes a preapproved workflow, and therefore does not meet A2/A3.
- There is no host-side separate audit service; a local key is enough to detect ordinary corruption but not a hostile key rewrite.
- The official original ACE demo and independent unit suite must pass at exact head in GitHub Actions; local tests alone do not prove the integration.
- No guarantee of execution in Antigravity: this branch is a GitHub delivery for review and can be cherry-picked or independently reproduced there.

## Minimal example

```python
from ace_autonomy import Autonomy
goal = {
  "schema": "ace.goal.v01",
  "name": "verified ACE baseline",
  "steps": [
    {"tool": "inspect_file", "path": "README.md"},
    {"tool": "ace_demo"},
    {"tool": "ace_status"}
  ]
}
with Autonomy("./ace-autonomy-work") as a:
    gid = a.enqueue(goal)
    while True:
        report = a.run_one(gid)
        if report is None or report["status"] in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            break
    print(a.report(gid))
```

Run with `PYTHONPATH=code` from an exact checked-out ACE repository.

## Next steps for Gemini Argon (worktree isolated)

1. Read and code-review this **draft**, do not copy unverified claims. Run `ace_autonomy.test_core`, original ACE runtime tests and source checksum verification.
2. Fix concurrency on first workspace initialization; add real subprocess forced-exit/crash test and source-race tests.
3. Implement remaining Gate 1 budget enforcement and an immutable external-action receipt contract **without enabling arbitrary untrusted code execution**. On ambiguous external result, fail closed with `HALT_UNCERTAIN`.
4. Require a separate scientific protocol before proposing or scoring representation/self-improvement results. Keep Antigravity R9 local patch independently auditable; do not merge it into this branch.
5. Record actual exact-head run URL, job counts, SHA and receipt in a follow-up report; do not call a queued/in-progress workflow passing.
