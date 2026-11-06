# ACE Capability Evolution v0.2 — executed cross-representation experiment

**Date:** 2026-11-06. **Classification:** PUBLIC SYNTHETIC DEVELOPMENT, staged-only. Scientific `NOT_ASSESSED`; release `BLOCK_RELEASE`; OAIE `NOT_ESTABLISHED`. No source self-modification or production candidate adoption.

## Pre-score provenance and exact-source custody

- The [v0.2 frozen protocol](ACE_CAPABILITY_STRUCTURAL_V02_PRESCORE_20261106.md) was committed at **`03fb48b0e346252799a4a7cf313cff2478e7c75e` before implementation, tests and scoring.** CI asserts byte identity to that Git commit; all later changes are additive.
- The stack is based on existing ACE v0.1 coordinator [draft PR #54](https://github.com/dianzherdiana25-hash/ACE/pull/54) at `52bfd4889c172f318274e2f0ba9e546b834d0bba`. Research R1 code pinned `8952c8ac55613e61b362841f4722c66a5aa990b3`; S2 typed AST pinned `08da5702828285e0bd4d0f4dd8876f331ac89fe2`. Both research sources imported unmodified.
- [GitHub Actions run #42162138514](https://github.com/dianzherdiana25-hash/ACE/actions/runs/42162138514) **SUCCESS** on coordinator HEAD `a22b148594b75928d0ca4c4c57c52db42deaedfb`, running **29/29 scoped tests** (13 inherited v0.1 plus 16 new v0.2) and two **byte-identical full v0.2 runs**. Exact source and pre-score SHA checked before testing.
- The complete v0.2 canonical JSON is **66,479 bytes**, SHA256 `205587a875e4ed5a516ee7991c09327f3a662fd86a7465106fb47c56e28b694f`. Independent replay verifier returns `PASS_PUBLIC_EXACT_REPLAY_NOT_SCIENTIFIC_GO`. GitHub Actions artifact `ace-capability-structural-v02-public`, ID **13477601002**, ZIP SHA256 `b2942579b9e94e46e0d367e23be008c0b546d9cae28fe8b55bb2ce282fca724c`. Coordinator downloaded the ZIP, confirmed three files and independently hashed raw JSON; schema/gates and each trial were parsed from the downloaded artifact.

## Mechanism

The v0.1 pilot only acquired instances using fixed R1 DFA and S2 arithmetic search. The new v0.2 controller can **change its task-specific representation topology** based on evidence:
```
raw string --> R1 induced finite-state graph [baseline]
           \
            \--> count_a,count_b --> typed S2 integer AST (w_a*count_a+w_b*count_b)
                                   --> equals-zero Boolean readout [mutation]
```
The counter-register topology and grammar are **researcher-authored**. Search selects one coprime pair from seven allowed weight configurations by training and validation evidence; no new type or operation is invented by ACE. Other source algorithms remain frozen. The controller keeps the R1 representation for rejected/outclass tasks.

Six nominal tasks plus one hidden-shift control. All six and the control use the same 63 distinct short-string train labels, 256 target-balanced validation strings (lengths 8–18), and 256 target-balanced terminal strings (lengths 24–40). Total: **4,025 synthetic truth judgments**, of which 1,792 terminal labels are not used for selecting models. Train and validation are disjoint from all terminal inputs. Counter candidate evaluations log AST node work; R1 separately logs merge attempts. **Compute is not matched across the different algorithm families**.

## Actual multi-generation outcomes

| Generation / nominal task | Stage | R1 DFA terminal | Fixed counter terminal | Selected counter terminal | Selected weights |
|---|---|---:|---:|---:|---|
| G1: `equal_counts` | COUNTER_REGISTER | 150/256 | 256/256 | **256/256** | (1,−1) |
| G1: `two_to_one` | COUNTER_REGISTER | 128/256 | 256/256 | **256/256** | (1,−2) |
| G1: `contains_ab` | NO_MUTATION | 256/256 | 136/256 | 136/256 (diagnostic only) | (1,−1) |
| G2: `three_to_one` | COUNTER_REGISTER | 138/256 | 128/256 | **256/256** | (1,−3) |
| G2: `four_to_one` | NO_MUTATION | 132/256 | 128/256 | 128/256 (diagnostic only) | (1,−3) |
| G2: `guarded_equal_counts` | NO_MUTATION | 128/256 | 128/256 | 128/256 (diagnostic only) | (1,−1) |

The fixed counter comparator already knows (1,−1) and (1,−2), so **the G1 success is not novel relative to the pre-existing counter class**. The G2 three-to-one candidate achieves 256/256 validation vs 125/256 fixed counter on the identical balanced validation set, a **131/256 = 51.17 percentage-point** advantage over that fixed coefficient list. It remains an inferred coefficient *instance within the same authored class*, not a new algorithm.

The regular `contains_ab` control demonstrates the controller need not replace a well-fitting finite-state representation. `four_to_one` exceeds the declared maximum coefficient range, and the guarded count-equality control requires order sensitivity absent from the count-only readout. Both are correctly **not staged as new counter structures**; their finite-state fallback still performs poorly on longer balanced inputs. Rejecting an inadequate mutation is not the same as solving the task or safely abstaining from predictions.

At G2, G1 `equal_counts` and `two_to_one` retain their frozen model fingerprints and unchanged 256/256 validation scores without refitting. This is **artifact retention only**, not a shared learner demonstrating resistance to catastrophic forgetting.

## Safety falsifier and precommitted gates

The `three_to_one_late_flip` control is **observationally indistinguishable** from the ordinary three-to-one task across all train and validation labels/inputs, but its terminal truth is inverted. The controller still stages the identical counter structure with 256/256 apparent validation fit; on terminal inputs it scores **0/256**, while the R1 DFA baseline scores 118/256. There is no semantic uncertainty detector or actual final-prediction abstention. This is an expected **false transfer / false-safe-promotion witness** and blocks any release.

| Gate | Observation | Verdict |
|---|---|---|
| S1: two G1 ratio switches with terminal >=95% | 2/2, both 256/256 | PASS |
| S2: G2 new ratio >fixed list by >=15pp | three-to-one 256 vs 125 validation | PASS |
| S3: reject regular/outclass structural false admissions | `contains_ab`, `four_to_one`, guarded equality all NO_MUTATION | PASS |
| S4: G1 immutable retention | Model hashes and validation retained without refit | PASS |
| S5: safe handling of indistinguishable semantic drift | Hidden drift stages; terminal 0/256 | **FAIL** |
| S6: reproducible provenance, evidence and adversarial tests | 29/29 tests, two exact JSON replays, source SHA lock | PASS within public scope |

A green workflow is engineering reproducibility, **not** all gates passed. Scientific and release decisions stay respectively `NOT_ASSESSED` and `BLOCK_RELEASE`.

## Scientific interpretation

It is mathematically impossible for any fixed finite-state automaton to recognize exact `#a=#b` over strings of *all* lengths: prefixes `a^0, a^1, ..., a^k` must be distinguishable by suffixes `b^i`; hence recognizing the relation without length restriction needs arbitrarily many states. The counter-register architecture can represent the equality relation with unbounded integer counts (subject to the bounded Python/execution contract) and therefore **has a different representational capacity**. But this experiment only *measures* lengths up to 40 and uses a human-defined count feature map; it does not empirically establish unbounded-world correctness or independent algorithm-type creation.

**Supported:** bounded observation-based switch from finite-state to a different authored topology, retention of three instances, task-specific candidate search, explicit rejection of outclass cases, exact-source replay and false shift witness.

**NOT supported:** creation of a new primitive grammar, fair algorithmic superiority with compute-matched controls, safe open-world adaptation, first-class final-output abstention, robust OOD generalization across unrelated families, recursive successor productivity or OAIE.

## Next research gate

Next go beyond `w_a count_a + w_b count_b == 0`: require ACE to propose a representation-class composition from **unseen structural counterexamples** rather than being handed a new counter class, test on ordering/nesting/two-register mechanisms and nonbinary symbols with an independently held evaluator, charge all search/label/architecture costs and compare against strong fixed library controls. Require evidence of real method-level transfer across future tasks/generations and explicit semantic abstention when observations are insufficient. Never tune against these now-public datasets and call the replay a new blind study.

**No main merge, no frozen science mutation, no source execution/deployment or paid calls.**
