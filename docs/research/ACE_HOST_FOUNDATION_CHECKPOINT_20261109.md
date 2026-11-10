# Host-assisted ACE foundation checkpoint — 2026-11-09

Status: **BLOCKED for promotion and confirmatory research**; scientific status
`NOT_ASSESSED`; OAIE not established. Applies to the branch containing this file;
read exact commit from Git rather than treating this text as a self-reference.

## Work and observations

- PR #93 base observed at `01915dd1919be60c73cfeab19f9cdfae5b088e29`.
  Earlier `d7f5515` full-system CI failed in Python 3.12 and 3.13 with eight
  import errors due to missing NumPy. The next commit installs NumPy 2.1.3;
  that installation step succeeded, while full-system and research workflows
  were still running when checked. MCP, R9 and autonomous workflows succeeded.
- A real bwrap regression probe demonstrated that candidate module import can
  call `os._exit(0)` before tests complete. Requiring a nonempty unittest summary
  rejects the simple probe, but a candidate can print a forged summary and exit.
  Candidate and tests share an interpreter, so passing-looking candidate output
  is now `INCONCLUSIVE`, not evidence of test completion. Promotion remains false.
- Receipts record sandbox profile and test source hashes. Host-bound diagnostics
  check receipt checksum, base commit, exact target, patch digest and candidate
  bytes derived independently from the Git blob. Hashes are not signatures;
  host/model provenance is self-reported, not authenticated.
- The cross-family design in `ACE_CROSS_FAMILY_TRANSFER_PRESCORE_V1.md` was
  committed separately before experiment implementation. It remains DESIGN ONLY:
  no confirmation task bank was generated or scored.
- The live falsifier receipt is `evidence/host_foundation/forged-test-receipt.json`.
  It refers to GitHub baseline commit `22dbda2db123ece1d77b0f74830575c217d2a799`;
  the diagnostic changes in the subsequent commit were used to evaluate it.

## Verification and remaining gates

`PYTHONPATH=code python -m unittest ace_code_agent.test_patch_diagnostic
ace_host_exchange.test_contracts ace_mcp.test_bridge ace_mcp.test_transport
ace_mcp.test_code_diagnostic ace_code_agent.test_audit_regressions -q` ran in the
VM with loopback permission: **41 tests passed**. This is an engineering result,
not a scientific or open-world safety result. Adversarial reproduction confirms
output forgery remains possible and must not be interpreted as a passing test.

Next: implement an independently supervised candidate execution and test oracle,
prove a candidate cannot forge its result or read holdout labels/keys, authenticate
receipts with evaluator-owned key custody, and run negative controls. Retain
fail-closed promotion and do not run confirmatory experiments before those gates
pass. Resolve full-system CI on the exact PR head and record actual results.
