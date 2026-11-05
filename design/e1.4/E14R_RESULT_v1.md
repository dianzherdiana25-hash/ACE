# E1.4r — qualify an inherited motif using a diagnostic receipt

**Mapped GO. Robust HOLD. NATURAL_HOLD.** The [freeze](https://github.com/dianzherdiana25-hash/ACE/commit/ef3ff7ddbb49ecd09de90c8038472225b7b294ff) locked 12 inherited artifacts and 60 paired target worlds with fresh graphs. All 12 artifact digests were rederived from their original E1.4p evidence. This reused persisted capability with zero new source labels. Each arm bought one target label per world.

| Target truth | Packed | Targeted chain | Passive |
|---|---:|---:|---:|
| Identity, fully correct worlds | 12/12 | 12/12 | 12/12 |
| Flip of last event, fully correct worlds | 12/12 | 0/12 | 0/12 |
| Flip of penultimate event, fully correct worlds | 12/12 | 0/12 | 0/12 |
| Same-length complement, wrong accepted probes | 0/120 | 0/120 | 48/120 |
| Shorter rule, wrong accepted probes | 51/120 | 51/120 | 51/120 |

The packed policy covered all 360 mapped probes correctly. Both diagnostic policies abstained on all 120 same-length complement probes. In every shorter-rule world the cheaper exact route matched both the short rule and the identity interpretation. The packed policy accepted the wrong motif on all 12 such worlds. Its 51 errors include both missed paths and incorrect costs when a cheaper path contains only the shorter word. The covered count and false positives remain in the raw records.

Across 12 independent lineages, mean query size was 14 nodes and 15 edges for packed, ten and nine for chain, and 14 and 15 for passive. Each arm used 60 labels over the paired worlds. Score and replay used native Bubblewrap and matched on the deterministic record. The audit recomputed lineage digests, validated 216 worker calls, and independently checked all query costs and probe outputs. [Verification](../../evidence/e14/e14r_verification_v1.json).

A post-score structural audit enumerated 3,200 pairs of a lineage and a possible shorter binary motif of length at least five. Of these, 217 could return one of the three declared receipt costs and 110 could imitate the identity receipt. These counts describe the stored query graphs. They are neither a prevalence estimate nor a separate performance gate. [Alias audit](../../evidence/e14/e14r_posthoc_alias_v1.json).

The mapped gate supports autonomous selection among human-supplied interpretations and rejection of the tested same-length complement. For a broader grammar the observed cost remains compatible with alternative lengths. Future qualification can keep those alternatives in the version space and use a separately budgeted counterexample query or abstain while ambiguity remains. Robust inheritance and the autonomous graph-chain loop remain on HOLD.
