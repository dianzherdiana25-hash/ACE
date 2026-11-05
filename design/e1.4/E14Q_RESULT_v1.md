# E1.4q — one weighted query for motif discrimination

**Packed query GO. NATURAL_HOLD.** The [freeze](https://github.com/dianzherdiana25-hash/ACE/commit/5966f7d506e15be4e51a42c5e52fdb91ca348ea0) locked the bank, protocol and implementation. Twelve blocks of four supplied candidates generated 48 paired truth worlds. The independent unit is a block. All arms ranked up to eight offers and purchased at most one cost label.

| Condition | Strategy | Fully correct worlds | Full four-world blocks | Covered probes | Labels |
|---|---|---:|---:|---:|---:|
| Shared prefix | Packed | 24/24 | 6/6 | 192/192 | 24 |
| Shared prefix | Chain | 6/24 | 0/6 | 84/192 | 24 |
| Shared prefix | Random branching | 5/24 | 0/6 | 66/192 | 16 |
| Mixed prefix | Packed | 12/24 | 0/6 | 144/192 | 24 |
| Mixed prefix | Chain | 6/24 | 0/6 | 84/192 | 24 |
| Mixed prefix | Random branching | 4/24 | 0/6 | 56/192 | 16 |

All arms made zero incorrect accepted predictions because the truth was always in the supplied version space. In shared-prefix blocks, three weighted routes yield three distinct non-null costs. A null response isolates the remaining candidate. Mixed-prefix blocks can fit only two disjoint routes under the graph contract, so two of four hypotheses are still compatible after a null response. Abstentions are counted through uncovered probes.

Per purchased label the selected shared-prefix packed graph used 15 nodes and 16 edges, the same structure budget as selected random branching. The single chain used 9 nodes and 8 edges. Mixed-prefix packed used 16 nodes and 16 edges. All 36 worker calls ran with native Bubblewrap. Audit recomputed graph costs, ranking, updates and probes and verified deterministic replay across all 12 blocks. The recovered E1.4 regression passed 110/110. [Verification](../../evidence/e14/e14q_verification_v1.json).

This is evidence about query construction given a supplied candidate set. The richer oracle and structure consume more graph work per label than the chain, so this pass does not lift E1.4o's original graph-chain HOLD. A separate bank can test whether positive diagnostic receipts make a stored artifact safer to use when target semantics shift.
