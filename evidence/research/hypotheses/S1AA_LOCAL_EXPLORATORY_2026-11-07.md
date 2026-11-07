# S1-AA exploratory local execution — 2026-11-07
Preregistration commit: 691b599bf1301fa7741b25f4cc80a09e6760b7cf (before local scoring).
Method: observation-only Beta(1,1) per-feature adaptive query selection; matched random, static lexicographic, diversity max-min Hamming. Public synthetic 4-bit query vectors, 8 labels/arm/world, 128 seeds per split and 4 oracle scenarios. Separate seeds: development 0..127; evaluation 10000..10127. No frozen ACE data or paid oracle.
**Evaluation false acceptance / 128 worlds**:
- nominal conjunction: adaptive 1, random 0, static 38, diversity 0.
- shifted XOR: adaptive 3, random 0, static 0, diversity 0.
- random-label adversarial: adaptive 0, random 2, static 0, diversity 1.
- all-zero indistinguishable oracle: all four methods 0 false acceptance and 0 false rejection.
Development false acceptance: nominal adaptive 1/random 10/static 24/diversity 0; shift adaptive 4/random 0/static 0/diversity 0; random-label adaptive 2/random 0/static 0/diversity 2.
Accounting: 4096 arm-world trials, 32768 synthetic evaluator labels, 376832 candidate-scan proxy, 0.425980168 process CPU seconds (local), 0 paid labels. All arms label-matched; CPU per arm not matched.
Decision **REJECT**: adaptive cannot attain >=20% reduction vs both random and diversity on both nominal and shift evaluation. Counterexample: shifted XOR causes adaptive to miss errors in 3 worlds where random and diversity miss none. True Shannon information gain was not measured; empirical Brier calibration values are descriptive only, not mutual information.
**Reproducibility limitation**: source code executed in local Python environment, not yet committed to GitHub; exact-SHA replay/independent confirmation NOT done. This document is a truthful summary, NOT exact-head reproducible evidence. Preserve NOT_ASSESSED and all frozen locks. No merge or deployment.