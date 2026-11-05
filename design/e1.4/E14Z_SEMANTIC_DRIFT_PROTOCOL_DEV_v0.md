# ACE E1.4z — prescore negative transfer under hidden semantic drift

**5 November 2026 | Author-designed public engineering bank, not independently sealed scientific validation.** Authored before scoring E1.4z. E1.4y policy and its historical prescore bank are **immutable** and reused unchanged.

## Hypothesis
E1.4y learns an operator AST in distinct source tasks and assumes the same operator applies to successor graph tasks. Test whether two **precommitted, label-blind target verification queries** detect negative transfer when the target's cost operator has changed, comparing minimal vs maximal semantic distance while holding all other resources and policy code fixed.

## Prescore design
- Source candidate programs: 20 randomly seeded semantic signatures from **previously unscored** E1.4y grammar programs (10 residual, 10 threshold) excluding the 34 original in-grammar source truths, seed 202611051639.
- For each source program, choose within same 175-program grammar a **near** different target program (minimum Hamming distance over all 120 legal sorted cost pairs), and a **far** different target program (maximum Hamming distance). Do not optimize selection after observing results. The bank retains source/target program IDs, exact distances and fixed source/target pair locations.
- One source lineage purchases at most 4 labels in each of three source tasks and is reused across *four* target worlds: near×two unseen target pairs and far×two unseen target pairs. Source label acquisition is charged ONCE, not repeated when scoring near/far and multiple controls.
- Five unchanged E1.4y controls: `transfer-direct`, `transfer-verify2`, `cold-new`, `cold-old`, `sham-transfer`; max four target labels per arm, no target/probe leakage.
- **20 source operators ×2 drift types ×2 target pairs ×5 modes = 400 arms**. Six fixed heldout cost-disjoint probes per target world. Source truth and target truth differ by design. Never score near/far target truth as if transferred source should equal target.
- Primary readouts: false acceptance (especially by verify2), correct target recovery by cold controls, abstention, source and target label budgets, heldout probe error counts and replay with independent DFS oracle.
- No advantage claim from this design: it is a deliberately adversarial **distribution shift**. A failed transferred hypothesis may be useful evidence for abstention and representation change, not proof of natural-world operator discovery.

## Custody / interpretation
Commit this protocol, code/test and bank with hash lock before any 400-arm scoring. Score batches must remain fixed, raw report and independent receipt replay archived, followed by a distinct postscore auditor commit. Native Bubblewrap and full clean repository regression remain open. Preserve E1.4t scientific HOLD and E1.4y numeric results.
