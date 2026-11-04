# Aksi berikutnya untuk Work, Codex, atau chat ini

**Current:** E1.4c **HOLD**, not a user-approval gate. Source freeze `3025d7f` and unmodified v1 scores at [E1.4c result](design/e1.4/E14C_CROSS_EPISODE_RESULT_v1.md). Do **not** tune on these target results or claim causal transfer.

1. **E1.4c-v2 correction:** build all unlabeled question pools in a separate deterministic PRNG stream **before** any word-dependent demo/probe generation. Reserve them before other inputs. Add adversarial tests proving pools are invariant when target words change, while identities/splits stay fixed. Ensure old v1 score artifact unchanged.
2. Freeze v2 code/protocol as a new GitHub commit **before scoring**, then run bounded one-shot development pilot; save raw JSON and a normalized replay under a separate filename. Audit case overlap, per-stratum arithmetic, label costs, and negative transfer.
3. If no stable advantage across both S/G, do not force GO. Diagnose inability to learn useful source policies, competing hypothesis equivalence, label costs and source-target similarity. Pre-register a stronger informed-reference control and test official Bubblewrap worker isolation separately.
4. Keep [charter](PROJECT_CHARTER.md), [ledger](RESEARCH_LEDGER.md), `research/e1.3-design` only, cost Rp0, no E1.3 sealed-bank opening, and never modify Tod or `main`. Use [fail-visible runner](docs/ACE_WORKFLOW_RECOVERY.md) to avoid open-ended 'working'.
