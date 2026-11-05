# ACE R7.6 — adaptive information acquisition, bounded fresh e-certification

**Status: EXPLORATORY PREREGISTERED GATE PASS; SCIENTIFIC HOLD.** The project must not promote R7.6 to core, merge PR #43, or advertise global false-acceptance guarantees. A preregistered *comparison gate* passed on new synthetic worlds, but the narrow-control strategy still has higher aggregate safety-adjusted utility; per-seed improvements are inconsistent.

## Protocol, custody and reproducibility

- Protocol **precommitted** in GitHub commit `af8024b96aa0da8219b4c7aafb2e318aca9a020e` BEFORE R7.6 implementation and final scoring. See [R76_PROTOCOL.md](R76_PROTOCOL.md).
- Final code `r76_adaptive.py` Git blob SHA `38d1e3f864fa2531b49b17c8c0d2baa7f2d9617b`. Unit-test blob SHA `464c8e38987362e1172a306e6994a9718a08dd9f`. Both GitHub readbacks match locally tested source bytes, including newline.
- Local Python 3.13 stdlib tests: **13/13 PASS** before final evaluation, including hard label budget, domain split IDs, no oracle read in decision procedure, fresh certification observations, single acceptance per world and correlated stress.
- Validation-only (12 stable worlds): narrow6 10 true / 0 wrong / 218 online labels; full12 10/0/278; broad6 10/0/218; adaptive10 10/0/258. This **did not show a stable validation efficiency gain**. Protocol was not changed based on validation.
- Final scored ONCE using `cd <repo-root> && PYTHONPATH=code python3 -m ace_research_uncertainty.r76_adaptive --phase final > R76_FINAL.json`. Saved output: SHA256 **`e9fdefbf3a5cf111ed97ae367ea7a5ef10a5b10a2a22c6af35fa7cfec01e99d4`**. Local elapsed 7.06 s, max RSS 100684 KB (host-specific).
- Separate evaluator-free JSON audit: `PYTHONPATH=code python3 -m ace_research_uncertainty.r76_audit R76_FINAL.json`, **12,410 checks / 960 arms / 0 errors**, saved audit SHA256 **`3f25d1a9fcf208f607d5f917cc36676f62f3484bf2133363bcf5ac86eb2ef3dc`**. Audit does not verify evaluator's hidden truth independently.
- Public task bank: 4 predetermined seeds 20261112–20261115 × 20 worlds × 8 families = **640 worlds**, six capability decisions/world. Up to 24 online synthetic label purchases/world, plus **1,296 separately charged offline source-training labels**. The 64 evaluator-only score probes/group are not acquired by learner. These are **public, author-visible synthetic worlds**, not an independently custodied, sealed test.
- No paid oracle/network activity, untrusted execution, E1.4 mutation or remote deployment.

## Final 24-label-cap results

Each family contains 80 worlds; C/W means accepted correct/accepted wrong. All purchases in columns are summed across four seeds.

| Family | Narrow6 C/W | Full12 C/W | Broad6 C/W | Adaptive10 C/W | Adaptive10 bought |
|---|---|---|---|---|---:|
| Stable | 55/0 | 55/0 | 52/0 | **56/0** | 1,752 |
| Swap | 16/1 | 12/2 | 2/1 | **5/1** | 1,902 |
| Reverse | 33/0 | 13/0 | 5/0 | **11/0** | 1,887 |
| New01 | 13/1 | 21/0 | 4/0 | **18/0** | 1,866 |
| New23 | 0/0 | 35/0 | 22/0 | **34/0** | 1,818 |
| All-null | 0/1 | 0/2 | 0/2 | **0/2** | 1,914 |
| Near-boundary | 7/1 | 7/1 | 8/1 | **8/1** | 1,893 |
| Correlated | 66/0 | 66/0 | 67/0 | **68/0** | 1,716 |

All-null has **0 truly acceptable groups**, yet Adaptive10 falsely accepts 2 capabilities among 80 tasks; never interpret the result as zero-risk. Correlated outcomes violate the i.i.d. Bernoulli assumption of the e-process; no theoretical type-I bound is asserted there.

### Five primary-family aggregate (stable + four shifted)

| Policy | True accepts | False accepts | Acquired labels | Utility |
|---|---:|---:|---:|---:|
| Narrow6 | 117 | 2 | 8,767 | **−11,109** |
| Full12 | 136 | 2 | 9,462 | −11,386 |
| Broad6 | 85 | 1 | 8,998 | −11,986 |
| Adaptive10 | 124 | 1 | 9,225 | **−11,355** |

Utility was frozen before scoring: `20*true − 60*false − 2*abstain − online_purchases`. Adaptive10 beats Full12 by **+31** and Broad6 by **+631** but **loses to Narrow6 by −246**. Per-seed adaptive-vs-full utility deltas are **−74, +75, −14, +44**, so aggregate improvement is not directionally consistent across seeds.

### Locked gate re-evaluation

- New23 greater true-accept coverage than Narrow6: **PASS** (34 > 0).
- Stable ≥80% of Full12 true accepts, no added wrong accepts: **PASS** (56 vs 55, wrong 0).
- Total wrong accepts across stable, four shifted, all-null and near-boundary ≤ Full12: **PASS** (4 vs 5).
- Five-family utility ≥ Full12: **PASS** (−11355 vs −11386).
- Five-family utility ≥ Broad6: **PASS** (−11355 vs −11986).
- Hard budgets and ≤1 certified candidate/world: **PASS**.

**Precommitted gate: 6/6 PASS. Scientific acceptance: HOLD.** The gate is a limited target comparison, not proof of dominance over the strongest control or out-of-family generalization. The all-null counterexamples and the possibility of repeated-certificate family-wise error remain unresolved.

## Next experiment without reuse of R7.6 final bank

Test decision-theoretic label acquisition against a full-strength narrow control on completely new task mechanisms with independently held evaluator custody. Precommit risk/coverage curves, per-seed paired error margins and a cost-regret criterion; require non-inferiority to the best baseline, not merely to a weaker full-diagnostic strategy. If real ACE semantic-alias tasks are available, use their evaluator-owned decisions rather than treating these Bernoulli strata as evidence of actual ACE capability correctness.

**Do not merge PR #43; maintain HOLD.**
