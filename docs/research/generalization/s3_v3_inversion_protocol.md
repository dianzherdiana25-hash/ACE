# S3 v3 preregistration — label-inversion selection sensitivity (PUBLIC DEVELOPMENT)

Parent: PR #51 at 3789b52af9288b2a1f7fdee71e092089431b6c6e. This study addresses the incomplete v2 leakage sentinel. This protocol is committed before runner or results. No frozen E1.4 inputs, no sealed holdout, no CI.

**Falsifiable H1:** For at least 18/24 paired seeds, inverting ONLY the 64 source-environment selection labels while preserving candidate features changes the intervention selector output; otherwise H1 is rejected. A change is sensitivity, **not proof of absence of leakage**. A deterministic no-selection-data mutation must not change selection (24/24), or the test is invalid.

**Methods:** Reuse v2 public generator, 24 seeds 51000+11*i; chain(32, fidelity .95, seed+1) and star(32, fidelity .05, seed+2), same four candidates and threshold 12 per environment. Create inverted copies (bits,1-y,marker,edge) of both source sets and rerun intervention(a,b). Do not access branch test labels or use them for selection. Matched control reruns original data. Additional adversarial test inverts labels of just chain and just star, separately. Source topology chain/star; branch OOD is excluded from this diagnostic by design. Source grammars are the original four candidate predictors; no claim of cross-grammar transfer.

**Prespecified outputs:** changed selection under dual, chain-only, star-only inversion; abstention before/after; 24 trials; selection labels 64 per condition per seed (24*64*4=6144 label presentations; 1536 unique original labels); candidate-example comparisons 4*6144=24576; CPU process time and deterministic replay digest. No acceptance or transfer claim. Any failure or negative result retained. Public development, NOT CONFIRMATORY. Stop if source mismatch.
