# ACE capability decision and Codex handoff — 2026-11-07

**Decision: continue bounded research, not release, not OAIE.** Scope: audited existing GitHub evidence and selected one non-overlapping next implementation. This is an engineering/science portfolio decision, **not** scientific validation or a merge approval.

## Live repository readback

- Origin: private `dianzherdiana25-hash/ACE`, `main` at `80104ce50ecbcea21080bed8c0eabce88d47ccb5`.
- Read all **43 open PR metadata records**, with head SHA, base ref and category recorded in [the immutable-at-commit inventory](ACE_PR_PORTFOLIO_SNAPSHOT_20261107.json). 51 repository branches at inspection. The inventory is a point-in-time snapshot; refresh before planning merge.
- Main's existing operational ACE loop is executable (`python3 ace.py demo --workspace ./ace-work`): bounded `a/b` task intake, fixed R1 DFA/counter/product grammar, training+validation admission, model retention, SQLite WAL/restart and a three-task public demo. Main exact-head verification [Actions #42167246580](https://github.com/dianzherdiana25-hash/ACE/actions/runs/42167246580) SUCCESS; this certifies that workflow's checks only.
- Original integrated v0.3 composition **2854/3072**, below strong 35-program fixed-product **2877/3072**; 6/24 admitted. Read `CURRENT_STATE.md` and `README.md` before treating prior claims as source-of-truth.
- PR #60 (unmerged) long-input, four-rule public study: composition 900/1024 versus fixed products 769/1024, but `ratio2_boundaries` composition 132/256 against fixed product 256/256; same-family DFA ties composition's largest individual-family gains. Actual Runtime admission 6/8; hidden terminal inversion 2/2 false admissions. [Run #42193104042](https://github.com/dianzherdiana25-hash/ACE/actions/runs/42193104042) SUCCESS.
- PR #61 (unmerged) **graph-generalization falsifier**: actual Runtime admits **0/4** native graph-objective tasks; typed binary string models score 258/512 composition and 297/512 DFA, while **researcher-supplied** graph-native BFS/two-color library scores 512/512. The native solvers are supplied code, NOT newly invented by ACE. [Run #42197402063](https://github.com/dianzherdiana25-hash/ACE/actions/runs/42197402063) SUCCESS.
- PR #62 (unmerged stacked on #60) persistent model-library cross-rule transfer: **0/16 target model reuses without refitting**; retained and fresh both stage 12/16, score 1536/2048 counting rejected targets as zero coverage; shifted same-observation controls **2/2** false reused at 0/256 terminal correctness. [Run #42241347553](https://github.com/dianzherdiana25-hash/ACE/actions/runs/42241347553) exact-final-HEAD SUCCESS, as independently re-read from GitHub.
- PR #59's GitHub Actions bridge executes actual task requests; hosted direct MCP ChatGPT connection, durable remote auth/storage, and remote OAuth **not established**. Do not mislabel local server tests as a hosted connector.
- PR #29 has an existing, tested **read-only GitHub PR file-collision gate**. Reuse instead of implementing a second checker. The prior snapshot there covered fewer PRs; new PR head snapshot here does not certify path non-overlap.
- Red Team [Issue #53](https://github.com/dianzherdiana25-hash/ACE/issues/53), PR #30 report unresolved **P1 problems in historical E1.5 / source-evolution branch**, including journal concurrency and external holdout repeat; these do **not** prove that current main's distinct SQLite Runtime has the same bugs. Keep E1.5/E1.6 release/merge blocked until independently retested on exact intended source.
- Gemini research assignment [Issue #63](https://github.com/dianzherdiana25-hash/ACE/issues/63) owns `code/ace_research_reptransfer/**`; at audit no submitted Gemini-authored R9 branch/PR. Issue existence alone is not agent execution.

## Portfolio triage — 43 OPEN PRs, exhaustive group assignment

See per-PR exact head/base in JSON. These group counts sum to 43; **none are auto-merge approvals**.

| Group | PRs | Count | Action |
|---|---|---:|---|
| Historical frozen E1.4 stacks | #15 #16 #18 #19 #20 #21 #22 #23 #24 | 9 | Preserve scientific provenance; **do not bulk-merge** |
| E1.5/E1.6 core, Red Team and receipt/CI stacks | #25 #26 #27 #30 #31 #32 #33 #46 #49 | 9 | **HOLD** pending #53 / exact-source security, ancestry and integration tests |
| Coordination / integration prototypes | #29 #50 #54 #55 #59 | 5 | Reuse #29 gate; source-diff #54/#55 with integrated main; #59 remote access unproven |
| Potentially superseded source snapshots | #28 #36 #38 | 3 | Reconcile with selected imports in merged #56/#58; avoid double-count |
| Independent research and falsifiers | #34 #35 #37 #39 #40 #41 #42 #43 #44 #45 #47 #51 #52 #57 | 14 | Retain evidence, evaluate independently; no automatic capability promotion |
| Decisive recent controls | #60 #61 #62 | 3 | Preserve as reference controls; enforce stronger unseen-family baselines |

`main` contains merged PR #56 (selected primitives/research toolkit) and #58 (operational runtime); this does **not** imply all still-open sibling research PRs are integrated or confirmed.

## Single scientific bottleneck to target

**Missing portable representation and method adaptation under genuinely novel task semantics.** Reuse of an exact saved program (current Runtime) is not transfer of a learning rule or representation. Passing a string DFA through a graph adjacency encoding does not teach topology. A supplied graph BFS policy reaching 100% does not establish learning/discovery.

**Priority chosen:** branch-only, bounded, typed **graph-representation construction** to learn graph structures and transferable partial computations from labeled examples; compare on unseen *graph objective families* and structure/size shifts. **Codex owns implementation** only after preregistration and branch/source isolation; **ChatGPT coordinator owns evidence/falsification audit**. Gemini R9 separately owns source-feature transfer; do not share source directories or confuse target hypotheses.

## Codex experiment brief (no coding authorized on main)

New branch: `research/codex-ace-graph-representation-20261107`, based on refreshed `main` SHA. Owned new directory `code/ace_research_graph_builder/` plus `docs/ACE_GRAPH_BUILDER_*.md` and optionally a uniquely named Actions workflow. Do not edit `code/ace_runtime/**`, `code/ace_research_graph_transfer/**`, `code/ace_research_reptransfer/**`, frozen E1.4, Tod, or other agents.

### Step 1 — preregister BEFORE code/results

Make **one earlier commit** defining:
1. Source tasks: connectivity and bipartiteness; two separate disjoint target families with explicit topology meaning (e.g., directed terminal reachability, vertex-deletion connectivity) or justify improved choices. **Do not hard-code the full target solver into the search grammar.**
2. Fixed graph sizes/encoding, sources/targets, ≥4 seeds, train/adaptation/validation/terminal splits, label budgets and hypothesis gates. No overlap, no target terminal access to candidate selection. Include vertex relabeling and adversarial counterexamples.
3. Arms: original source ACE Runtime; fresh target-only representation learner; fixed hand-authored feature/algorithm library; source-learned representation + small target adapter; random/uninformative representation; graph-native domain-solvers as an **upper-bound reference**, not a fair claim of invention.
4. Precommit measured CPU/user-time and work-unit accounting; disclose external source-training and feature discovery expense, not just target fits. No paid APIs; no model executing untrusted generated source.
5. Decide two disjoint claims: (H1) transfer beats the strongest **non-oracle matched-budget** baseline in held-out family-macro accuracy or label efficiency, with independent repeat; (H2) any candidate that is not empirically certifiable is explicitly rejected/abstains. Any hidden semantic flip with identical observable evidence must be treated as fundamentally unidentifiable, NOT 'fixed' with threshold tuning.
6. Define an independent evaluator review boundary and provenance receipts. Public synthetic replay is development, **NOT** sealed confirmation.

### Step 2 — implement in isolated files

Build (a) typed graph-operation IR with closed execution and bounded enumeration/composition, (b) source-induced reusable representation/features (do not simply select a complete researcher-authored BFS/bipartite solver), (c) a target-label-limited adapter, (d) fixed/control baselines and negative-shift sentinels, (e) validation-only selection and terminal evaluator with separate custodial implementation. Record every failing candidate and abstention.

### Step 3 — falsify and verify

At least three classes of tests: semantics/graph relabeling and exact data split; budget/integrity/replay/tamper; and negative controls including mismatched source features and misleading validation. Run *actual* fresh-checkout GitHub Actions on **exact HEAD** and original main ACE regression; preserve full raw per-case outcomes/artifact SHA256. Re-run evaluator independently if feasible. File draft PR; do not merge. **If source transfer cannot beat the controls, report REJECTED and leave candidate unpromoted.** Never claim OAIE, novel primitive type, or open-world safety unless genuinely demonstrated.

### Go/no-go policy

- **Engineering GO**: bounded deterministic source is runnable, independently verifiable, original regression intact.
- **Science GO (not yet earned)**: new task families beyond known grammar, preregistered primary gain vs strongest non-oracle matched-budget control, independent terminal evaluation, no contamination, negative controls interpreted honestly, and compute/label accounting.
- **Release GO (not yet earned)**: separate threat model, red team and no unresolved relevant safety blockers. E1.5 #53 remains HOLD independent of this isolated research code.
- **No automatic merges/deploys/source swaps/paid services**, and stop on stale HEAD, conflict, or quota exhaustion. ChatGPT/Antigravity/Codex task assignments require separate genuine tool connections or user activation; GitHub issue alone does not start an external agent.

## Next coordinator check

1. Require Codex preregistered branch commit BEFORE implementation; audit no candidate contains a fully provided solver disguised as discovered primitive.
2. Run existing PR #29 collision detector against current live portfolio if its permissions/runtime are available; otherwise report **UNKNOWN**, not safe.
3. Independently inspect exact SHA, actual CI receipts and all metric denominators; archive negative results and do not expand lanes before a credible new-family gain.
4. Keep all 43 PRs as review-only until explicit owner merge authorization; reduce portfolio by evidence-based closure only with owner approval.
