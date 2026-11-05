# E1.4t — postscore exact-motif semantic audit and hindsight falsifier

**Date:** 5 November 2026  
**Status:** POST-SCORE DEVELOPMENT AUDIT PASS, diagnostic HOLD unchanged, scientific NOT_ASSESSED. This is not an amended frozen scoring protocol or an independent scientific sign-off.

The original E1.4t evaluation relied on six held-out weighted-graph probes per world. A deterministic, postscore verification script now reconstructs the actual **accepted word** from the worker terminal trace and independently checks all training examples, purchased receipts, qualification evidence, exact motif equality and all six original held-out probes. It verifies 240 distinct world×strategy arms and replays the same examination on the separate 240-arm run. Five independent tampering classes (receipt ID, label, exact word, scored outcome and terminal/arm coverage) are rejected in local tests.

## New finding — one unsafe exact-motif acceptance despite agreeing probes

- Case: `rare:10:integrated`, the sole wrong exact accepted motif among 240 arms.
- The six prescored probe results agreed with the accepted candidate, so the old `errors=0` field did **not** imply the accepted motif was the true motif.
- The new postscore exact-motif audit detects **1 wrong exact accepted / 1 probe-indistinguishable alias** in both the score and independent fresh-ledger replay. This finding does **not** alter the original scores or the held-out probe set.
- A hindsight distinguishing chain graph was constructed whose SHA-256 is `787f75eeab1eb900de8675bb94ec84e05ba720aba481179282e3e28f74478b8a`. The erroneous hypothesis predicts weighted graph cost **8**; the actual oracle returns **None**. Exactly two *additional postscore counterfactual oracle evaluations per audited run* were used, one for truth and one for the accepted hypothesis. These are **not** target-label purchases within the frozen four-label cap.

This is a *counterexample to semantic robustness of the accepted motif*, not evidence of an unbiased discovery policy. The targeted witness was chosen **after** observing the failure. Therefore it must inform a separate future benchmark that is newly frozen before scoring; it cannot be inserted into E1.4t to claim improved performance or obtain GO post hoc.

## Verification and custody

- `tools/ace_e14t_semantic_audit.py` independently reconstructs accepted outputs from raw bank truth and worker trace, using trusted evaluator graph semantics and raw SQLite receipts. The worker never receives the postscore witness.
- `tools/test_ace_e14t_semantic_audit.py` provides **11 adversarial regression tests**; **80/80 total local tests PASS**, combining the earlier 69 and these additional 11.
- `evidence/e14/e14t_postscore_semantic_audit_v1.json` preserves full 240-arm score and replay semantic checks and the explicit falsifying graph. Both original score and replay remain immutable, as does the prescore bank and its lock.
- **Limitations:** same author, public bank, no independent full-system threat model, full historical 114-test checkout regression pending; no claims of OAIE, learned source artifact, unknown new primitive, or independent semantic acceptance.

**Decision:** Continue research with scope limits, audit exact word correctness separately from probe accuracy, add adversarial negative test families to a *new independently frozen bank*, count all new counterfactual oracle labels separately, and retain E1.4t diagnostic HOLD.
