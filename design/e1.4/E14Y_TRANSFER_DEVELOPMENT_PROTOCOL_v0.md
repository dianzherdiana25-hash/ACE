# ACE E1.4y — cross-task operator-form transfer (public prescore development protocol)

**Written on 2026-11-05 before the 40-operator score run.** This is author-designed/public development; NOT a sealed confirmatory scientific bank or independent review. The long-term OAIE goal is NOT demonstrated.

## Testable engineering question
Can a policy that induces a finite **compositional operator form** from three separately paid predecessor graph tasks use that representation on **previously unseen motif pairs**, with fewer *target-stage* queries than cold learning? Does it fail visibly when the form is outside its provided grammar? Count *all source and target labels*, and compare retained target-stage performance without treating additional source labels as free.

## Inputs and custody
- Legal graph model: branching forward DAG ≤16 nodes/edges, two distinct matching routes, integer tolls, pair cost grid `[4,18]`, 120 ordered sorted values.
- Finite researcher-authored grammar: AST primitives `add, sub, mul, mod, eq, ge` and bounded constants. A family of `base(lo+hi) + amplitude*predicate(gap)` trees is *generated*, with periodic-residue and gap-threshold predicates. Duplicate *semantic* signatures removed on full legal grid. The formula *shape* and vocabulary are supplied; do not claim open-ended primitive invention.
- Three source task motif-pair IDs fixed at `(0,5,10)`. Target motif-pair IDs fixed at `(18,22)`. Each source oracle purchase is charged to its own per-task cap of four. The source program is shared but each task has its own distinct motif pair; target pair IDs are provided. **No source motif learning is claimed**.
- 40 operator IDs frozen deterministically by seed `202611051617`: 20 residual, 14 threshold, 6 out-of-grammar stress functions. Each operator becomes two target worlds, five modes each = **400 target arms**.
- Target intervention cost pairs use the *66-point* grid with `hi<=14`, held-out probes use *54 disjoint points* with `hi>=15`, six probes per target world. Probes include alternating disjoint-branch and shared-prefix DAG topologies.
- Each target arm has a fresh SQLite four-label journal. Labels are audited with a historically independent DFS graph-route evaluator. The worker/policy does not receive truth or held-out probe labels.

## Predeclared controls
1. `transfer-direct`: accepts source uniquely identified form without target purchase; upper diagnostic on transfer trust, not robust.
2. `transfer-verify2`: two purchased target checks before accepting transferred form. Still not a universal unknown-operator guarantee.
3. `cold-new`: new finite grammar, up to four target interventions, minimum three labels for acceptance, no source artifact.
4. `cold-old`: earlier five-node compositional grammar without residual and threshold primitives; same target cap.
5. `sham-transfer`: deterministically shifted incorrect inherited form, two paid target checks.

## Primary readouts / decision convention
Report **exact signature recovery on all 120 grid points**, wrong accepted, abstention, target purchased/replayed labels, *source labels separately*, accepted probe coverage and errors, per stratum. A transfer advantage is only an engineering observation unless a properly matched **total-cost** control with identical task information budget is available. A transfer false acceptance on out-of-grammar operators is retained as a negative result. Scores cannot be tuned after bank freeze. Final decision label always `PUBLIC_DEVELOPMENT_NOT_SCIENCE / NOT_ASSESSED`; historical E1.4t HOLD and natural HOLD unchanged.

## Limits
- Source tasks share the true operator by construction; independent natural task transfer untested.
- Forms and bounded syntax manually supplied, outsider names also chosen by author.
- Full code/tests and bank hashes must be read back on exact GitHub branch; source tests run locally, *not* native Bubblewrap security.
- The bank is public rather than sealed independent; no claim of population performance, genuine autonomous scientific discovery or OAIE.
