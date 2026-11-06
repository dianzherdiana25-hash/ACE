# ACE Graph-Family Transfer — source-preserved public study, preregistration v1

**LOCK BEFORE CODE, TESTS OR RESULTS (2026-11-06).** Research source: `dianzherdiana25-hash/ACE` `main` commit `80104ce50ecbcea21080bed8c0eabce88d47ccb5`. Study isolation: new `code/ace_research_graph_transfer/` and `docs/ACE_GRAPH_TRANSFER_*` plus one dedicated workflow. Do not change ACE runtime, R1–R8/S1–S5 ownership, frozen E1.4, Tod, main or PR #59/#60. No deployment, merge, paid evaluator or foreign network.

## Scientific question and falsifiers

**Does the existing ACE Runtime v1 / compositional string learner demonstrate meaningful out-of-distribution generalization to graph-theoretic tasks?** Instead of another string-count task, test graph s-t connectivity and undirected bipartiteness. A graph is given to ACE using a stable **lossless lower-triangular adjacency-bit serialization** (`a` = edge, `b` = nonedge), no task label, predicted answer or oracle-computed feature. Thus ACE receives authentic topology as raw data yet only sees its existing string API; the actual original ACE runtime and `c.fit` are imported **without modification**. We predict (and openly allow) a negative result, given the current finite grammar. Do not claim mere lossless serialization implements general graph reasoning.

Second diagnostic: a new **researcher-authored typed graph program library** `{s_t_reachability_by_BFS, is_bipartite_by_two_color}` selects one program via training + validation, never receiving task name as input. This is a **fixed-library method selection comparator and engineering demonstration**, not an ACE-invented graph primitive. Compare against *both* original source fixed-product and source DFA plus graph-native exact solvers. It is valid if the library wins; novelty claim remains **FALSE** because its candidates were supplied by researcher.

## Frozen tasks, splits, budget

Two families, exactly:
1. `undirected_st_connectivity`: an undirected graph has a path from node 0 to node n−1 (BFS ground truth).
2. `undirected_bipartite`: the graph admits a valid two-coloring of all connected components (two-color BFS ground truth).

No loops or multiple edges. Encode each edge (i,j) for 0≤j<i<n in row-major triangular order, as `a` if present, `b` if absent. Train graphs have n=4, 6 bits; validation n=5, 10 bits; final OOD graphs n=7, 21 bits. Node IDs are meaningful only for connectivity terminals 0 and n−1; bipartite truth is label-invariant for all vertices.

Two seeds **20261121** and **20261122**; all four (family × seed) instances separate; no adaptive task choice after scoring.

- TRAIN per world **16 distinct graphs**, 8 positive/8 negative selected uniformly without replacement from exhaustive 2^6=64 graphs using `Random(910000 + seed + family_index)`. No length-based leakage between train and other splits. Prefix trie maximum 63 nodes under 16 length-6 strings.
- VALIDATION per world **64 distinct graphs**, 32 positive/32 negative chosen from exhaustive 2^10=1024 graphs with a separate `Random(920000 + seed + family_index)`. No repeated graph labels in world.
- TERMINAL per world **128 graphs** comprised of 64 base random n=7 graphs (32 positive,32 negative) plus **one nontrivial permutation of interior vertices [1..n−2] applied to each**. Require resulting encoding distinct and no duplicate among all 128; if not, reject/retry the base. Base graphs drawn as Bernoulli edges p=0.35, conditioned solely on label balance, with public deterministic `Random(930000 + seed + family_index)`. Exactly 100000 attempts per world cap; failure `HALT` rather than revising task conditions. The paired terminal labels must be identical; both families 64 positives and 64 negatives. Interior relabelling keeps s=0,t=n−1 fixed for connectivity.
- This means **4×(16+64+128) = 832 labeled graph observations**, 512 terminal instances which are never used for candidate selection. Each terminal pair shares graph isomorphism; **effective independent terminal base graphs only 64 per world**, so report clustered-pair limitations and no naive binomial significance claims.
- Source algorithms may abstain/not stage. Never infer performance on rejected tasks from selected candidate alone. Report **coverage** and **conditional terminal correctness** separately.

## Four bounded comparison systems

A. **ACE Runtime v1**: enqueue actual graph-encoded labeled train+validation, run once in fresh temporary SQLite workspace, inspect actual decision, predict/evaluate terminal ONLY if model staged, verify persistence and idempotent readback. All runtime models are from original repository and cannot train on terminal.

B. **Source `c.fit` learned composition**: unchanged `dfa`, `counter`, `composition`, `fixed_product` arms; select from train+validation only, then evaluate all 128 terminal graph words. Independently replay each program using original `c.replay` and require prediction agreement. Account proposal work, R1 merge attempts, candidate counts, AST nodes, terminal characters. These are **raw string representation models** applied to graph data; not graph-aware algorithms.

C. **New fixed graph-native two-program library**: implement both exact standard BFS reachability and standard two-coloring bipartiteness as pure bounded code with counted graph node visits / edge scans. Select which one to use by **max train correct, then max validation correct**; ties by fewer total observed edge scans, then a fixed lexical ID. Do not provide family name or terminal labels to the selector. Freeze selected identity prior to terminal. This method uses hand-supplied domain semantics; successful performance proves *availability/selection of relevant methods* not creation.

D. **Native oracle baselines**: use independently implemented source-truth BFS and bipartite two-coloring with a separate code path from the native candidates. Accuracy expected 100% by construction but measure it; this is an **upper bound with correct task family known**, not a compute-matched learned comparator. Always-negative baseline 50% on class-balanced terminal. Explicitly report fixed graph library selection against oracle baseline and any tie or failure.

All systems have **equal 16 TRAIN + 64 VALIDATION label presentations** per world, but are not compute matched: native solvers use structure-specific domain knowledge, R1 programs use string search; report work counters and do not claim matched FLOPs.

## Paired permutation invariance and semantic shift safety

On each terminal base/permuted pair, expected truth is identical. Report each arm's prediction disagreements across 64 graph pairs/world. If ACE runtime doesn't stage, mark invariance unavailable rather than claim passing 100%. Library has a separate invariant test for all four worlds. **Permutation invariance is an important OOD test, but passing it does not imply correct connectivity/bipartite reasoning** (constant predictors are invariant).

Negative-control `task_identity_swap`: sample *the same raw graph set* for both graph tasks, but change objective from connectivity to bipartiteness. This is a *different target* and can be observationally ambiguous. Report how many graph inputs have opposite target labels, and **never** call cross-task model reuse safe without separate validation and task-identity provenance. Terminal graphs are not allowed to be used to select candidate or route between methods.

## Locked admission criteria

- **T1:** exact original ACE source is imported, no mutation; all 4 worlds and 64 graph permutation pairs/world generate valid balanced nonoverlapping splits; native oracle agreement with generator, both source program and native solver independent replay; two complete canonical runs byte-identical; no external/paid calls.
- **T2:** ACE transferable graph competence requires **>=3/4 worlds staged by ACE Runtime, >=90% terminal correctness for each staged world**, and for each staged world **>=95% paired permutation agreement**, plus no family failing threshold. A 50% always-negative constant is not competence.
- **T3:** method-selection comparator requires graph-native selected program ≥95% terminal on 4/4 worlds **and** at least 32/512 additional correct terminal labels over the stronger of source learned composition and source fixed-product. If not, fail explicitly.
- **T4:** graph method invention **always FALSE**: the native two algorithms and selector are researcher-authored; report any benefit as *provided-method selection only*. T2/T3 PASS never counts as an ACE-created primitive.
- **T5:** reject any false claim of full scientific acceptance, open-world safety or deployed model. Registry reuse across two different graph tasks is **not** automatically permitted, even when inputs have same serialization.
- **T6:** independent tamper tests reject fabricated stage/accuracy, source pin/holdout overlap, bool/int alias, permutation disagreement masking, native oracle discrepancy, and unsafe promotion flags; exact HEAD CI and canonical replay.

**Overall status immutable:** scientific_decision=NOT_ASSESSED, release_decision=BLOCK_RELEASE, oaie_established=false, candidate_deployed=false, compute_matched=false, evaluator_sealed=false. No permanent model state between tests. A green CI is engineering reproducibility, not a new cognitive ability.
