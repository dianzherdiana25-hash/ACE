# ACE E1.4w — bounded compositional program search (PUBLIC DEVELOPMENT)

**Date: 2026-11-05. Status: postdevelopment documentation, NOT A PRESCORE FREEZE. Scientific result NOT_ASSESSED.**

## Research questions

1. Can a successor infer *expression structure*, rather than only numeric coefficients, from bounded paid oracle observations?
2. Can an independently purchased MAX-rule predecessor learn a reusable motif-pair artifact without receiving the successor's cost rule?
3. Does a conservative in-language evidence threshold prevent false acceptance when the target uses a wholly unrepresented semantic operator?
4. Are results preserved when decisions come from a genuine separate-process worker given only purchased evidence?

## Provided prior knowledge, not learned

The scientist provides the 28 possible pairs of three-event motifs and the DSL constructors `{lo, hi, 0, 1, 2, +, ×, min, max}`. Bottom-up enumerative synthesis considers trees of at most five nodes. Deduplicating functional signatures on the bounded cost grid (4..18) yields **68 unique size≤5 programs**, versus **17 size≤3**. This is a compositional grammar search, not automatic invention of a new primitive or architecture. These exact domain limits, paired path rules and graph generator are synthetic.

## Predecessor and successor

The predecessor receives graph-cost labels from a task defined by the **MAX** of two distinct motif-bearing path costs. It selects queries without being told the hidden pair or the successor's operator. The source budget is at most **four purchased labels per pair**, and each source journal is distinct from every successor journal. When the pair cannot be identified, the inherited policy abstains instead of manufacturing a motif. Each successor strategy receives at most four additional target labels; paid negative `None` receipts are counted. Source and successor share the same synthetic motif vocabulary but have different cost operators, so this is narrow typed transfer only.

## Design and controls

- Main: 12 source motif pairs × 12 program functions within the DSL + 4 outside-DSL forms = **192 worlds**, crossed with six strategies = **1,152 arms**.
- Main control arms: safe 3-label certificate, eager 1-label acceptance, random query strategy, compact 3-node grammar, true-pair upper bound, sham-pair inheritance.
- Adversarial extension: 8 outside-DSL functions × 12 pairs × six strategies = **576 arms**.
- Postscore far-distance versus adjacent-cost canary: 288 arms each over the same 12×24 old worlds. The policy selection was informed by earlier failures: **not an unbiased confirmatory comparison**.
- Additional adversarial family: 8 further non-DSL operators × 12 pairs × three policies = **288 arms**. This family was created after the previous canary outcomes, and is **not independently held out**.
- Source query offer comparison: 28 source pair tasks × original 70-graph versus expanded 420-graph offer pool = **56 source-only arms**.
- Cold worker replay: 192 main worlds × four strategies = **768 arms**, each action in an unshare/chroot worker process. Native Bubblewrap security review NOT completed.

Total **3,416 execution arm records**, including explicit replays of the same worlds. **384 distinct target world definitions**, not 3,416 independent target distributions. All runs use a fixed deterministic algorithm and seeds but most test data and policy variants are author-selected, not blinded.

## Oracle custody and audits

Each purchase durably writes a pending record in SQLite before invoking the oracle; another purchase is blocked until the pending receipt is settled. Per-graph node/edge/event costs are derived from physical topology. A separate DFS route walker and iterative AST evaluator reconstruct receipts, source and target labels and probe responses in five in-process development groups. The 12 isolated-worker batches compare deterministic decisions, bought-label counts and probe outcomes with independently executed in-process references; a worker sees the typed pair and observations only, not truth, evaluation oracle, bank or probe labels.

Local environment native `unshare/chroot` passes eight isolation canaries per batch, but it is **not an independently certified replacement for Bubblewrap**. No full historical exact-head GitHub regression has been run. Source code and preserved data, logs and SHA-256 manifests form an auditable exploratory checkpoint rather than a final scientific acceptance artifact.

## Prohibited extrapolations

No OAIE, autonomous successor architecture, unbounded grammar invention, general natural-language transfer, formal soundness of a finite-evidence certificate, independent semantic sign-off or scientific GO. Preserve frozen E1.4t HOLD and all earlier E1.4 GO/HOLD decisions. No changes to ACE `main`, Tod or sealed E1.3 materials.
