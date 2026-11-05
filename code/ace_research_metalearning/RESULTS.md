# R4 Public-Development Results (not confirmatory)

The protocol and four prescore records were committed before any OOD evaluation was executed in the JavaScript tool isolate. Separate GitHub commits record this result. All 4 seeds; 48 unique OOD tasks per seed; 24 inputs per task; k = 0,1,2,4,8. No OS-level Node test/CI was run in this session because container and Python runner were unavailable. In-isolate `selfTest` passed with 10 assertions and seed-0 semantic replay matched exactly. Code was generated from the very same function bodies that executed in the isolate, but an independent exact-GitHub-HEAD run remains required.

## OOD accuracy on unqueried inputs, pooled equally across 4 seeds
- scratch: k4 65.70%; k8 65.40%; first-hit censored 5.760; target-pair-ops 52800; target label purchases 1536
- static_transfer: k4 59.92%; k8 59.92%; first-hit censored 8.109; target-pair-ops 0; target label purchases 0
- static_finetune: k4 69.58%; k8 70.38%; first-hit censored 5.880; target-pair-ops 52800; target label purchases 1536
- simple_meta: k4 67.58%; k8 70.96%; first-hit censored 5.380; target-pair-ops 154944; target label purchases 1536
- learned_meta: k4 67.81%; k8 71.06%; first-hit censored 5.359; target-pair-ops 154944; target label purchases 1536
- learned_random: k4 66.98%; k8 69.34%; first-hit censored 5.729; target-pair-ops 52800; target label purchases 1536

H1 prespecified >=+5 percentage points over scratch AND strongest transfer/meta baseline, at k4. Observed learned-minus-strongest-control = **-1.77 percentage points**; status: **REJECTED / NEGATIVE RESULT**. Do not use this as scientific confirmation. Learned source/validation full-label exposures across four meta-training repetitions: 5568. Additional meta-fit pair work: 2466192. The total-cost accounting is materially worse for learned model than scratch; target-stage sample efficiency and end-to-end compute efficiency are different comparisons.

## Cautions
1. OOD bank is author-visible and seed-defined, rather than sealed independently.
2. No paired confidence intervals, independent evaluator, or true-world transfer.
3. Candidate kernels and search hyperparameters were researcher-authored; only weights were learned.
4. The FNV checksum is not cryptographic and does not protect rollback or adversarial journal changes.
5. Exact Node CLI and GitHub CI not run; use `node --test` and replay before engineering acceptance.

See raw per-seed and per-family numbers in `results.json`.
