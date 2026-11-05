# ACE Research R4: Prespecified meta-learning study (public development)

Base: `965640786cbf2f8adcd89eb1d980945f78c2da77`; branch: `research/chat-r4-metalearning`. Owns only `code/ace_research_metalearning/`. No E1.4 source/data/decision touched.

## Falsifiable H1
A kernel-based learned evidence-update rule plus learned exploration coefficient, meta-optimized across **threshold** and **interval** task families using only training and validation families, produces at least a +0.05 absolute increase in OOD mean unqueried accuracy at k=4 against **both** scratch/random 1-nearest and the stronger of static-finetune/simple-meta baselines, across 4 predeclared seeds. No significance claim if threshold is missed. Record k=1,2,4,8, Brier loss, fraction >=80% unqueried accuracy, and right-censored adaptation step (9 if not reached through k8).

## Protocol and isolation
Domain is 24 binary points per task. 38 train tasks from threshold and interval, 20 validation tasks from reverse-threshold and outside-interval, 48 OOD test tasks from periodic, two-window and sparse generators, per seed 0/1/2/3; all complete truth vectors unique across all partitions per seed. Family tags never enter the target learner, only the benchmark scorer. Test labels enter only purchase and scoring, never candidate training or validation. Task generators and protocol are available to the author: public DEVELOPMENT benchmark, **not** an independently sealed holdout. Fixed outer-loop 18 candidate feature-weight vectors; select top four on train, then one on validation; no retuning on OOD. Full source/validation labels are available for outer-loop training (meta-data costs must be reported). Static transfer uses the empirical source label prior and zero target queries; static-finetune updates a fixed rule with target examples. Scratch uses nearest-neighbor plus random acquisition. Simple-meta is fixed proximity+uncertainty acquisition. Learned-random ablates acquisition.

## Freeze/score contract
First commit the code, tests, protocol and frozen JSON records containing only train/validation-tuned parameters and reproducible OOD generator checksums. **Only then** run `scoreFrozen` and commit positive or negative results. No claim of cryptographic tamper protection: the checksum is noncryptographic FNV32. Logical work counts all evidence-pair operations and all candidate predictions; training work is counted separately. Runtime is local JavaScript isolate where used; full Node execution and CI are independent gates.

## Reproduction
```sh
node code/ace_research_metalearning/study.mjs test
node --test code/ace_research_metalearning/test_study.mjs
node code/ace_research_metalearning/study.mjs freeze 0 /tmp/r4_seed0_prescore.json
node code/ace_research_metalearning/study.mjs score /tmp/r4_seed0_prescore.json /tmp/r4_seed0_result.json
node code/ace_research_metalearning/study.mjs verify /tmp/r4_seed0_prescore.json /tmp/r4_seed0_result.json
```

## Limitations
Binary 1D concepts, small source families, homogeneous synthetic tasks and finite hand-authored kernel dictionary. Optimizing continuous mixture weights is meta-learning of a limited **update rule**, not unbounded algorithm invention. Source datasets are exposed in full; there is no claim of equal total training cost. No deployment, no new primitive, no OAIE claim.
