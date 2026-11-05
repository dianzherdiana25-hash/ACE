# ACE E1.4v — public-development protocol: parameter induction

**Version:** v0, authored locally on 2026-11-05 before the first exploratory run. The GitHub copy was deposited **after** local scoring; it is not a cryptographically precommitted or blinded protocol. **Scientific decision remains NOT_ASSESSED.**

## Hypothesis and scope

Rather than manually supplying MAX, MIN or SUM as named alternatives, define an authored compositional family for matching two distinct weighted graph routes: \`a*min(route_cost_1, route_cost_2) + b*max(route_cost_1, route_cost_2)\`. A and B are nonnegative integers within 0..3, not both zero. A source learner may infer values from observations; a rank-two certificate requires two independent single-witness positive equations and checks all observed labels. Neither the formula family nor candidate motif vocabulary is automatically invented.

## Fixed exploratory design

- Eight historical E1.4u motif pairs: \`PAIR_SPACE[0:8]\` (not independently held out).
- Nine representable coefficient choices: (0,1), (1,0), (1,1), (2,1), (1,2), (3,1), (1,3), (2,3), (3,2); plus two out-of-basis forms, \`min+max+1\` and \`min*max\`. **88 worlds**.
- Four matched strategies per world: \`affine-naive\`, \`affine-verified\`, \`affine-challenge\` and \`legacy\` (only prior MAX/MIN/SUM plus single words), **352 arms**.
- Up to **four actively acquired source labels per world**, one source acquisition reused by all four arms and reported separately from target labels. This uses the **same target oracle**, so it is not independently learned predecessor transfer.
- Up to four additional purchased target labels per arm in a durable SQLite journal. Negative \`None\` labels are charged; each target receipt is replayed by the trusted evaluator and the resource counts are checked against graph topology.
- Six fresh-identity public graph probes per world selected without using their labels during query selection. Report **accepted** probe coverage (zero when abstained) separately from unaccepted diagnostic candidate consensus.
- Deliberately retain a strong downside for conservative guards: lower acceptance is not treated as an accuracy victory by itself. Report accepted-correct, accepted-wrong, abstain, target/source labels and probe errors.

## Postscore structural audit (separate exploratory analysis)

Use a newly authored **shared-prefix DAG** generator while the learning/query pool consists of disjoint branches. For each original world, generate six deterministic new-topology graphs and validate their oracle labels with the historical **independent DFS route implementation**. Re-run all four policies with unchanged acquisition logic; do not adapt the grammar or thresholds to these probes. This is postscore testing, not an independently frozen future set.

## Acceptance limitations

Tests measure correctness only for the specified finite grammar and synthetic public worlds. A rank certificate proves **identifiability within that functional family** but cannot eliminate entirely new operators. Source acquisition still uses the same task oracle, worker calls are in-process, and no independent native Bubblewrap validation or full historical checkout regression is established. No result in this protocol can be called scientific GO, AGI or OAIE.

## Reproduce in complete checkout

\`\`\`bash
PYTHONPATH=code:. python3 -W error::ResourceWarning -m unittest e14.test_e14v_operator e14.test_e14v_topology e14.test_e14v_topology_audit -v
PYTHONPATH=code:. python3 -m e14.e14v_study --indices 8 --output WORK/e14v-operator-development.json
PYTHONPATH=code:. python3 -m e14.e14v_topology_audit --indices 8 --output WORK/e14v-structural-postscore.json
\`\`\`

Do not change frozen E1.4t bank/score, E1.3 sealed data, ACE main or Tod. No paid compute.
