# ACE R3-v4 / v4b — structural edit credit vs novelty (exploratory negative)

2026-11-06. Independent research directory only. No ACE runtime modifications; no changes to main or E1.4. This study extends a previously observed negative R3-v3 public synthetic study. Both the original v4 credit-arm failure and the v4b post-hoc correction are preserved in separate JSON records.

## Question and falsifiable claim

Can data-driven attribution of a *structural edit's marginal training improvement* guide evolution of a typed Boolean graph more accurately per unit of compute than uniformly sampling the same structural edit operators? Does rewarding an edit's acceptance as a **new graph** avoid the incentive to repeatedly delete gates?

The design compares (1) a fixed-connectivity 27-operator catalog, (2) existing greedy topology evolution, (3) v3 cost-aware structural exploration, (4) uniform structural edit selection, (5) a UCB policy using parent-versus-child training error as operator credit, and (6) a post-hoc novelty-aware UCB variant with +0.15 for accepted graphs and -0.15 for rejected proposals. All candidate programs are immutable DAG data with AND, OR, XOR; five binary inputs, maximum five gates. No executable candidate code is generated or executed.

The budget is **240 scored candidates**, **750 total proposals**, and **9,000 counted gate operations** per task case; split **18 training, 7 validation, 7 test**. All methods share points and task labels for paired comparison. Two seeds for six previously visible development functions and two families of six procedurally generated graphs (fork/join and sequential chain), for **36 task-seed cases per arm**. This is author-visible synthetic research, not a sealed, independently held-out benchmark.

## Results (mean test accuracy, n=12 task-seed cases per bank)

| Arm | Development | Fork/join | Chain | Sum gate work (three banks) |
|---|---:|---:|---:|---:|
| Fixed wiring config | 77.38% | 57.14% | 58.33% | 62,316 |
| Greedy | **78.57%** | 57.14% | 86.90% | 297,183 |
| V3 cost-aware | 59.52% | 57.14% | 77.38% | 315,055 |
| Uniform structural edits | 71.43% | **69.05%** | 86.90% | 300,532 |
| UCB credit edits (v4) | 65.48% | 58.33% | 80.95% | 75,993 |
| Novelty-aware UCB edits (v4b, post-hoc) | 72.62% | 58.33% | **88.10%** | 308,303 |

Accuracy across 36 task-seed cases is 75.79% for uniform edits versus 73.02% for novelty-aware credit: **-2.78 percentage points** for novelty at **+2.59% gate work**. Since samples are small, dependent by task and author-designed, this is a descriptive falsification of the stated pilot claim, **not** a population generality statement. On the fork/join family, novelty is -10.71 pp vs uniform; on the chain family it is +1.19 pp (only one additional correct prediction among 84 held-out points).

## Root cause for the v4 credit failure

On fork/join (12 cases), naive credit makes **3,582** `delete` proposals with **only one accepted** as a distinct candidate. In contrast, uniform selection admits **2,835** scored graphs total, vs **1,131** for naive credit. Rewarding short-term changes in training accuracy creates a perverse preference for near-zero-cost deletions, even when repeated deletion yields duplicate/uninformative candidates. This is an observed incentive failure, not a proof that edit attribution generally fails.

Adding novelty credit mostly repairs exploration (more unique candidates compared with v4), but its search is still not reliably accurate across architectures. It has a different realized gate-operation cost than the controls despite the same maximum, so this is **not** an equal-actual-compute causal estimate. The v4b fix was devised after seeing v4 results; its chain family was run without tuning on chain scores, but tasks are still public and not independently administered.

## Engineering evidence and reproducibility

- Full local test suite: **44/44 PASS** (32 retained v1-v3 tests plus 8 v4 and 4 v4b tests).
- Separate local CLI replay: **216/216** v4b records match stored full JSON, including task, seed, arm, chosen graph and gate work.
- **120/120** earlier v4 records remain identical when projecting away the new v4b arm.
- Holdout-label inversion does not change graph selection, candidate pool SHA256 or credit counters in direct tests.
- Three v4b banks SHA256: development `8abd96d8337de2e49f60a04c639f7fb07b5083816c9aa233d43c9a17a8fba53c`; fork `b662447e017f8d471fbf13eac268262e14e2d96d3f0508fd89f8ef7c8b3db97e`; chain `ce638abaf17a4d89f6dee144cad6b6dc2c04879c1c8a56ae645d820de5638fb5`.
- Limits: these are **same-source local replay checks**, not independent implementation, OS-secured sandbox, cross-platform CI, statistical guarantee, or live ACE self-modification.

## Exact commands (Python 3.10+, stdlib)

```bash
PYTHONPATH=code python -m unittest ace_research_architecture.test_study ace_research_architecture.test_v2 ace_research_architecture.test_audit_v2 ace_research_architecture.test_proposal_v3 ace_research_architecture.test_credit_v4 ace_research_architecture.test_credit_v4b -v
PYTHONPATH=code python -m ace_research_architecture.verify_credit_v4
PYTHONPATH=code python -m ace_research_architecture.credit_v4 --bank chain --seeds 2 --output /tmp/r3-v4b-chain.json
```

**Decision:** preserve negative result; do not merge PR #44 or promote R3 into the ACE engine. The next scientific gate requires independently curated unseen tasks, preregistered evaluation, and comparisons matched by **actual** gate-work (not only identical ceilings).
