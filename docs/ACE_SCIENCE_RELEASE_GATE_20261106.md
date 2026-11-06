# ACE coordinator — evidence-integrity and release-admission gate (2026-11-06)

**Decision: `BLOCK_RELEASE`.** This is an **actual exact-head GitHub Actions result**, not a planned verification. The CI job itself is successful because the guard correctly detects the scientific blockers and forbids automatic promotion.

## Verified evidence and source

- Coordinator branch PR #50; exact tested code HEAD `418d5edf2a161f80a9b803d9e293f8bb31b0b58b`.
- [GitHub Actions run #42154620876](https://github.com/dianzherdiana25-hash/ACE/actions/runs/42154620876) **completed SUCCESS**, four jobs green, including the new `coordinator-science-admission` after three independent pinned research replays.
- New source: `tools/ace_science_release_gate.py`; adversarial tests: `tools/test_ace_science_release_gate.py`, **11/11 PASS** (Python 3.13 runner).
- The gate independently reconstructs the 24 H7 seeded target patterns, each of their 128 train +128 validation +256 natural +256 balanced strings, string SHA256 split hashes, full H7 and enlarged-grammar candidate fits, fixed baseline selection, terminal scores, first-error witnesses, acceptance and aggregated accuracy. **12,288 terminal method predictions per method family** are checked by recomputing each H7 record; no call to the H7 learner or source evaluator. It reads previously generated raw JSON, not paid/new external labels.
- Original unmodified pinned public reports: H7 SHA256 `6cbd2d5ff2b2894bf0cca6e3cd328f28800ccbff5631331371c9f0759590b000`, R1 high-state SHA256 `3a63234ab34d977b98ddfa9393e0419e854d876d5b91b9d86db6624df15d4e0a`, R8 null SHA256 `ab137f587eaf134482ce745778a48cc2b81a537be525c8627d4b15e591643d7f`. Changing even JSON whitespace invalidates the pin.
- Release receipt `science_admission.json`: exact SHA256 `0dfc07d3f3cf2dcee2c4363e803848bb2c2d55ccb71d54b34785297a07923d76`, 624 bytes, independently read from GitHub Actions artifact `ace-science-admission-hold` ID `13473368485` (ZIP digest SHA256 `90226c02eb4a21179f582007c27a66f3a6de0bce89e822776579ef10a1597eb5`).
- Tests mutate H7 per-task score, target feature acceptance, per-task semantic abstention, aggregate precision and the open-world gate; alter R1 drift outcome or R8 zero-null false-pass count; and tamper or omit receipt bytes. All such conditions are **rejected**, not silently downgraded. Earlier PR #50's in-source H7 study was run twice with byte-identical result JSON.
- The release gate's result is `engineering_evidence=PASS_INDEPENDENT_PUBLIC_REPLAY` (independence of *auditor implementation*, **not** independence of *evaluator ownership*), `scientific_decision=NOT_ASSESSED`, `promotion_decision=BLOCK_RELEASE`. External sealed evaluator `NOT_AVAILABLE`; Red Team P1 source release blockers tracked in [Issue #53](https://github.com/dianzherdiana25-hash/ACE/issues/53).

## Strict interpretation

Three different propositions must not be conflated: (1) evidence bytes and replay calculations match, **yes**; (2) this confirms out-of-class autonomous ability, **no**; (3) release and source candidate promotion are safe, **no**.

R1 H7 measured 8/8 five-gram accepted (100% balanced) but 0/16 novel six/seven-gram features accepted (50% balanced fallback). Natural accuracy on seven-gram worlds was high (93.26%) only because true target patterns were uncommon: a raw-accuracy measurement trap. R1 high-state DFA experiment had only 5/24 clean tasks >=90% and no drift-safe final abstention. R8's known-zero-effect null diagnostic still showed **9/512 false passes**. A zero false-pass claim is a scientific integrity violation, not a passing measurement.

The `coordinator-science-admission` CI job **depends on all three evaluation jobs and consumes the actual generated artifacts**, not hard-coded summary numbers alone. It verifies published SHA pins before recomputing H7. This allows parallel research to continue without making a passing *test workflow* an implicit promotion signal. A future source/policy change requires its own protocol, sources, new evaluation evidence and revised admission gate; simply editing the literal expected decisions or pin hashes is not acceptance.

## Release and security limitations

This **is not** a general-purpose end-to-end runtime guard for deployed ACE; it exists only as a separate workflow on a draft coordinator branch. A malicious actor with code-write permission could change the gate and workflow; repository branch protection and independent reviewer approval are additional obligations. GitHub Actions artifacts and SHA256 integrity do not authenticate the external evaluator's identity, provenance, or sealed independence. The source experiment banks and all outputs are now public and cannot become new blind holdouts.

**Do not merge** PR #50 automatically. **Do not** modify `main`, scientific E1.4 freeze, or source research teams. The next integration acceptance gate is independent evaluator custody plus Codex/Red Team remediation of P1 race/replay/external receipts (Issue #53), full historical regression (Issue #17), and native isolation or explicit environment block. OAIE has not been established.
