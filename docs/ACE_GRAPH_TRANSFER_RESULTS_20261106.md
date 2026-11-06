# ACE Graph-Family Transfer — executed public synthetic study (2026-11-06)

**Scientific `NOT_ASSESSED` · Release `BLOCK_RELEASE` · OAIE `NOT_ESTABLISHED`.** No merge, deployment, main, frozen E1.4 or other researchers' source changes. This is a method-development stress test, not an independently blinded confirmatory evaluation.

## Source, preregistration, experiment custody

- Original ACE Runtime v1 and compositional learner imported unmodified from `main` **`80104ce50ecbcea21080bed8c0eabce88d47ccb5`**. CI compares source bytes with the exact Git SHA; `tools/verify_sources.py` verified 25 original imported files.
- Research hypotheses, seed families, train/validation/terminal budgets, oracle controls, acceptance thresholds and immutable hold were committed **before source implementation and scoring** at prescore `aa1bbdafc0cd1c6240e4138bd8b9eec470714a01`. CI confirms exact byte identity.
- [Exact-head GitHub Actions #42197402063](https://github.com/dianzherdiana25-hash/ACE/actions/runs/42197402063) **SUCCESS** on study commit **`9f16c5d2ddc5695ca659129ad10d9360e79400e6`**, **16/16** graph-domain/oracle/custody tests plus **14/14** unchanged Runtime regression tests; two full evaluations byte-identical and strict independent source replay **PASS_EXACT_SOURCE_PUBLIC_REPLAY_NOT_SCIENTIFIC_GO**.
- Downloaded public `ace-graph-family-transfer-public` Actions artifact **13493725571**, ZIP SHA256 `4bd7f15985f2a328ab6756c75f2742ac0a8056242d3d86b58c6cc7ea3a6b5158`; `report.json` **24,111 bytes**, verified SHA256 **`1ea6faef820316da627c08d13c193ca50a51bfee2d2e6859288a826db41a4fa7`**. Raw artifact also contains `summary.json`, `verification.json`. Coordinator downloaded and independently parsed all per-world outcomes.

## Genuinely different task families, labels and held-out shift

Four independently learned task worlds: **undirected s–t connectivity** and **undirected bipartiteness**, two fixed seed values `20261121` and `20261122`. Input graphs are *losslessly serialized* lower-triangular adjacency bits into the ACE native `a/b` string interface, without supplying task identity/answer to the learner. Train uses **16 graphs of 4 vertices** (6-bit input), validation **64 graphs of 5 vertices** (10-bit), and terminal **128 graphs of 7 vertices** (21-bit) per world.

Every terminal set has exactly **64 positives and 64 negatives** and is made from **64 base graphs each paired with a nontrivial vertex permutation** holding the connectivity endpoints fixed. As a result, 512 terminal observations are **256 clustered isomorphism pairs**, not 512 independent random graphs. Training/validation/terminal input domains and lengths are disjoint; 832 total graph observations, of which 512 terminal instances do not influence model selection.

Each of two graph-specific candidate algorithms is separately implemented as **researcher-provided code**: BFS reachability and BFS two-coloring. They are selected without the task name, using train correctness then validation correctness then measured edge scans and deterministic tie break. The ground-truth evaluator is separate: union-find for reachability and exhaustive two-color assignment for bipartiteness. The reference library is deliberately not compute-matched to ACE source models.

## Complete observed results

All model systems face the **same 512 terminal graph labels** (128 for each of the four worlds), regardless of the runtime's stage decision.

| Method | Correct / 512 | Accuracy |
|---|---:|---:|
| **Graph-specific fixed library, selected using train/validation** | **512/512** | **100.00%** |
| Independent native graph oracle | 512/512 | 100.00% (family-known upper bound) |
| Source ACE R1 DFA | 297/512 | 58.01% |
| Source ACE learned composition | 258/512 | 50.39% |
| Source ACE counter | 256/512 | 50.00% |
| Source ACE 35-program fixed-product | 256/512 | 50.00% |
| Always negative | 256/512 | 50.00% |

**Critical reading:** the graph library beats the best single source string method, DFA, by **215/512 (41.99 percentage points)** and the preregistered stronger-of-composition/fixed-product comparator (258) by 254/512 (49.61 points). However, the graph library is exactly a two-algorithm, *researcher-authored* method set. This is successful **selection of supplied methods**, not ACE discovering an original graph algorithm or architecture.

| Family / Seed | DFA | Composition | Fixed product | Native selected | Actual ACE Runtime |
|---|---:|---:|---:|---:|---|
| Connectivity / 20261121 | 83/128 | 64/128 | 64/128 | BFS 128/128 | **NO_VALIDATED_MODEL** |
| Bipartite / 20261121 | 73/128 | 64/128 | 64/128 | Two-color 128/128 | **NO_VALIDATED_MODEL** |
| Connectivity / 20261122 | 66/128 | 66/128 | 64/128 | BFS 128/128 | **NO_VALIDATED_MODEL** |
| Bipartite / 20261122 | 75/128 | 64/128 | 64/128 | Two-color 128/128 | **NO_VALIDATED_MODEL** |

ACE Runtime stages **0/4** models, giving 0% supported graph-task prediction coverage, not '0% accuracy' (it appropriately refuses to treat inadequately validated models as retained capabilities). Source `compositional.fit` always emits a candidate for diagnostic scoring even when runtime correctly rejects it. Do not conflate these.

### Vertex-permutation invariance

- Graph-native selected library: **256/256 pairs agree** (100%), and 512/512 predictions correct.
- Source string DFA: **187/256 pairs agree** (73.05%), with 58.01% accuracy overall.
- Source string composition: **254/256 pairs agree** (99.22%), but only 50.39% accuracy. This is mostly invariance from constant-like predictions, **not evidence of topology reasoning**.
- The two underlying tasks disagree on **328/512 graph encodings** in the terminal set if the target identity is swapped. This demonstrates why sharing learned graph code based only on a common byte representation or cache key is unsafe. A task identity and independent validation are necessary.

### Work and comparability limits

Native selected models paid train+validation edge scans **962 / 1324 / 938 / 1373** per task world, and terminal edge checks **3318 / 4557 / 3108 / 4437**. Work accounting for source learners includes R1 merge attempts, candidate counts, terminal AST nodes and characterized prediction work; these are not dimensionally equivalent to graph node visits and edge scans, so **equal label budgets do not mean equal CPU/compute budgets**. Native oracle had explicit graph-domain primitives; original ACE lacked them. Claims of equal-resource algorithmic superiority are unsupported.

## Locked gates and observed falsifiers

| Gate | Verdict | Explanation |
|---|---|---|
| T1 original source, fixed splits, pair construction and determinism | PASS | Source SHA/checks, strict oracle, 16+14 tests, two identical full replays |
| T2 **existing** ACE transfer to *both* graph families | **FAIL** | Real ACE Runtime stages 0/4; never meets coverage or OOD accuracy threshold |
| T3 provided native graph methods versus source programs | PASS | Selected 4/4 families, 512/512 versus 258/512 preregistered composite/fixed comparator |
| T4 autonomous **invention** of a graph primitive | **FAIL by design** | Both native algorithms and selection policy authored by researcher |
| T5 unsafe cross-family model reuse blocked | **HOLD** | Two graph objectives disagree on 328/512 inputs; no general safe reuse contract |
| T6 tamper/exact-head replay integrity | PASS in public test scope | Scores, sources, bool/int, invariance, source evaluator and promotion claims checked |

## What changed technically?

The new independent research module accepts **real graph structures** and independently validates native graph candidate selection against separate union-find/exhaustive oracle implementations. It demonstrates, with source pinning, that handing ACE an adjacency string is insufficient and that the missing ingredient is an abstraction/representation capable of expressing graph topology. The tested native method selector can successfully instantiate a **provided** method for graph tasks, but is **not installed into production ACE Runtime** and does not constitute a learned novel algorithm.

**Follow-on, falsifiable next step:** implement graph primitive *construction* (search over typed graph traversal operators) rather than supplying complete BFS and bipartiteness solvers. Require held-out graph families (topological ordering, articulation, reachability with forbidden vertices), independent reviewer-owned seeds and matched compute budgets versus BFS/DFS/union-find. Test method reuse across families *after* selecting on development-only data; mandate task-identity validation and safe abstention on unresolved objectives. Close Red Team security Issue #53 before considering untrusted candidate execution. Never equate green CI with scientific acceptance or OAIE.
