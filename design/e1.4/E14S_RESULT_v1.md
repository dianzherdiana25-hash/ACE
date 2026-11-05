# E1.4s — qualify a mapped motif against shorter explanations

**Bounded qualification GO. NATURAL_HOLD.** The [frozen protocol](https://github.com/dianzherdiana25-hash/ACE/commit/613f09a024ad429bbaaef05c8fd236b615f5b65e) enumerated 888,832 source–target pairs, covering every binary source motif of length seven to nine against every binary target motif of length five to nine. Exactly 2,688 pairs were related by one of the three supplied interpretations. These are exhaustive logical cases in the defined grammar.

| Strategy and label cap | Correctly accepted mapped pairs | Wrong acceptances | Total labels |
|---|---:|---:|---:|
| One positive receipt, cap 1 | 2,688/2,688 | 18,654 | 888,832 |
| Fixed follow-up, cap 2 | 926/2,688 | 0 | 910,168 |
| Active follow-up, cap 2 | 926/2,688 | 0 | 910,168 |
| Fixed follow-up, cap 3 | 2,688/2,688 | 0 | 917,772 |
| Active follow-up, cap 3 | 2,688/2,688 | 0 | 915,718 |

A positive cost identifies one exact route in the first query. Every shorter compatible motif must occur on that route and be absent from cheaper routes. Every proper contiguous submotif lies inside the route's maximal prefix or suffix. A blank response to a shorter chain excludes its compatible motifs. A positive response contradicts the longer interpretation and the guard abstains. The active policy tests the chain covering more aliases first. At cap three this saves 2,054 labels versus fixed order, or 7.1% of follow-up labels. At cap two coverage is identical and the policies abstain on 1,762 mapped pairs.

The score and replay files are byte-identical. A separate calculation of receipt languages matched all counts and costs. The exhaustive computation used the trusted policy in-process. In a separate Bubblewrap run, 36 representative worker calls per execution matched the policy and the worker could not see the evaluator. Clean public E1.4 regression passed 114/114. [Verification](../../evidence/e14/e14s_verification_v1.json).

The guard distinguishes specified single contiguous motifs of length five to nine under an exact cost oracle. It acquires evidence and chooses from supplied interpretations. Generalization to different semantics, discovering new interpretations, and full graph recovery under a shared four-label budget remain open. The E1.4o graph-chain decision stays HOLD.
