# S4-v1: Recursive policy improvement on public synthetic tasks

**Hypothesis (predeclared):** A four-generation successor policy that updates its global tie-breaking prior from earlier development receipts improves future task productivity by at least 5 percentage points per label over the strongest matched fixed/uniform/adaptive-with-static-prior control, without losing more than 5 percentage points on adversarial inverted-payoff tasks.

**Scope:** Research-policy self-optimization only. It does not synthesize or modify code, model weights, architecture, or external tools. No claim of OAIE, AGI or natural-task generalization.

**Design:** Four generations, 24 tasks per generation, six labels per task, six policies. Public deterministic PRNG seeds: development 20261105+g, future 20262105+g, inverted negative transfer 20263105+g. Each task has an unobserved binary type; arm reward probabilities are 0.8 vs 0.2. Every policy receives equal 6-label budget on the same task seeds. Policy successor is chosen from development action receipts only; future and negative outcomes are not available to the update. Controls: fixed arm A, fixed arm B, alternation, adaptive with static prior A, adaptive with static prior B. All labels, including controls and development, are counted. There is no statistical significance claim from a single seed.

**Acceptance rule (frozen before execution):** pooled successor future successes minus strongest pooled control >= 0.05 * 576 = 28.8, AND negative-transfer difference versus strongest negative control >= -28.8. Otherwise reject. No post-hoc tuning or rerun to select a lucky seed. No use of E1.4/E1.4aa sealed evidence.

**Reproduce:** `python code/ace_research_recursive/study.py > results.json`. Compare the stable fields; CPU seconds are machine-dependent. One local execution performed with CPython and saved evidence under evidence/research/recursive/.

**Interpretation:** The strongest comparator must include a non-evolving adaptive policy, not only fixed strategies. A within-task learning gain is not proof of recursive improvement. Synthetic reward and task structure are author-defined; independent confirmatory evaluation remains absent.
