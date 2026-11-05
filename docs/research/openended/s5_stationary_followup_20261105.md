# S5 follow-up — stationary public synthetic falsification (2026-11-05)

Baseline main at readback: `5b0059b85055404a46adcdef305de81f5257486c`. Previous S5 negative experiment retained unchanged. Script: `code/ace_research_openended/s5_stationary_followup.py`.

## Prespecified hypothesis and design
H1: a behavior-descriptor archive QD strategy solves at least 1.10× the fraction of tasks solved by **both** greedy and random search, and strictly exceeds each, under equal 64-proposal/label budgets. Reject otherwise. The five matched arms are QD archive, greedy, uniform random, no-archive, and fixed curriculum. Four **researcher-defined** families: xor, rotate, parity, threshold, each mapping 8-bit candidate to 8-bit behavior. Objective is stationary within each arm: score `8 - bit_count(behavior)`; solved means score 8 at least once. Descriptor is behavior's high nibble. Each method gets one public synthetic label per candidate, no external oracle. Development seeds 0..11; evaluation seeds 100..111, with disjoint deterministic seed streams. Evaluation is public post-design, **not blinded**, and families are NOT held-out; no cross-family transfer claim is possible.

## Local executed result (Python stdlib)
Command: `python code/ace_research_openended/s5_stationary_followup.py > results.json` (executed on a local working copy before uploading source). 4 families × 12 seeds × 5 arms × 64 proposals × 2 splits = **30,720 candidate evaluations / synthetic labels**, 480 arms. Measured process CPU 0.021617795 s (machine-specific; no claim of independent reproduction).

| Method | Evaluation solved rate | Mean best score | Mean behavior descriptors |
|---|---:|---:|---:|
| QD archive | 0.79167 | 7.50000 | 7.45833 |
| Greedy | 0.95833 | 7.66667 | 4.83333 |
| Uniform random | 0.58333 | 7.33333 | 8.87500 |
| QD no archive | 0.58333 | 7.33333 | 8.87500 |
| Fixed curriculum | 0.66667 | 7.56250 | 7.00000 |

**H1 REJECT**: QD archive has fewer solved tasks than greedy (0.79167 versus 0.95833), despite more descriptor diversity. This is direct evidence that novelty descriptors need not correlate with solving. ID novelty is 64 for every arm, an adversarial metric artifact. The parity and threshold families have low-entropy / many-to-one behavior mappings, exposing descriptor aliasing. No inference about open-ended progress is justified from expanding this fixed four-family benchmark.

## Limitations / next falsification
All generators, fitness functions and descriptors were researcher-selected. The script measures synthetic solver labels, not external paid labels. Some arm RNG streams yield identical outputs for random and no-archive by construction, so those are **not independent baselines**. Greedy and QD have different mutation-source selection and may be sensitive to operator design. No independent clean-checkout execution, SHA-matched CI, prescore cryptographic lock, or blinded family-disjoint test has been completed. The script source local SHA256 was `d437d13e2445c5ffd73bc9f6d1bc2e4abca89786d1ff235bbcbcaaf535db5425`; local full JSON output SHA256 was `748b188aacf96f2113581f0bf278da5f72bfc17818281dc3d06760827133f93a`. Results file was not committed; reproducibility requires rerunning the committed script and comparing output **excluding non-deterministic cpu_seconds**.

Next falsifiable hypothesis (unexecuted): a behavior archive with a family-agnostic descriptor inferred from training trajectories beats greedy by >=10% on entirely unseen task-generator families, while matching the total candidate/label/CPU budget and explicitly penalizing redundant behaviors. Precommit generator splits and thresholds before scoring.

Scientific status: REJECT on public synthetic development; previous E1.4 HOLD/NOT_ASSESSED unchanged; no OAIE/AGI claim.
