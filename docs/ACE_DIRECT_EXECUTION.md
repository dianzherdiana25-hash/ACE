# ACE — Direct execution and anti-stuck workflow

**Operational route for the active research session:** GitHub ACE (source of truth) -> local bounded Python (experiment/test/audit) -> GitHub ACE (versioned evidence and status). **Do not use Google Drive as an intermediate code-transfer bus.** Drive's Research Master Record remains a documentation reference, not a prerequisite for GitHub updates. Google Colab is optional for separate reproductions, not the primary runner when local Python is available.

1. Read `PROJECT_CHARTER.md`, `CURRENT_STATE.md`, `RESEARCH_LEDGER.md`, `NEXT_ACTION.md`, then read the exact GitHub HEAD and the experiment's prescoring freeze commit.
2. Build/test from a clean, locally bounded Python process. Set a timeout, capture stdout/stderr/exit code and write `COMPLETE`, `FAILED`, `TIMEOUT`, or `PERSISTENCE_BLOCKED`. Avoid infinite retries; never equate app-level "working" with experiment progress.
3. Freeze bank, seeds, source and decision thresholds in GitHub **before** opening score results. Do not tune frozen data post-score. Use separate versioned experiments for corrections.
4. Compute SHA-256 of every preserved raw artifact. Prefer direct GitHub create-blob/create-tree/create-commit/update-ref with an expected HEAD lease; use base64-encoded binary Git blobs when preserving gzip. A created blob or commit object is **not** persisted to a branch until `update_ref` succeeds.
5. Verify remote branch head, tree and evidence blob SHA readback after the write. Update status/ledger/issue; preserve both positive and negative findings. A failed persistence step must have an explicit recovery instruction.
6. No extra charges, no Tod writes, no `main` merge without consent, no E1.3 sealed evaluator access. Official isolation validation remains a separately necessary gate.

**Why the change:** previous Drive bridging added text-import/export, MIME, transfer-size, formatting and connector failure points unrelated to E1.4 scientific tests. Google Colab notebooks remain available for user-visible independent reproduction only.
