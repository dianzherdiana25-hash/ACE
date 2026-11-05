# ACE E1.4t — bounded graph-length repair, qualification and shared-budget integration

**Date:** 5 November 2026  
**Decision: ENGINEERING_PUBLIC_DEVELOPMENT; strict diagnostic gate `HOLD`; scientific acceptance `NOT_ASSESSED`.**

This sprint moves beyond the 18-arm mapped-only smoke in PR #15 by implementing a fresh, evaluator-owned, programmatically frozen 48-world branching-graph study. This is not open-ended discovery, an independently accepted scientific claim, or a successful E1.4o graph-chain retest. Previous E1.4o HOLD, E1.4s bounded GO, robust-transfer HOLD and NATURAL_HOLD remain unchanged.

## What actually changed

- Worker now **searches for length-8/9 motifs derived from observed positive weighted DAG routes** when its length-5/6/7 model is contradicted. It does not receive target truth or probe labels. Program grammar extension is bounded and specified by its author; it does not invent new semantic primitives.
- One durable SQLite journal charges at most **four total target labels per world × strategy** across diagnosis, repair, qualification and inheritance. A settled diagnosis label is reused without buying it again. `None` is not a free answer. A crash between purchase and step trace blocks blind continuation.
- A worker stage in Linux user/mount/network/PID namespaces uses a worker-only chroot and read-only code mounts. Eight locally tested canaries passed for evaluator/home/private filesystem nonexposure, sanitized host path environment, separate PID observations, blocked external TCP and read-only system mount. **This is not a fully independently validated replacement for native Bubblewrap.**
- The new public bank contains 12 worlds for each of `reachable`, `natural`, `rare` and `out-of-grammar`, with **433 uniquely repriced graph inputs** checked against the evaluator oracle. The frozen bank's canonical SHA-256 is `4ecc55df9b12fa3ce7ab7148d85c077529637a2e9f5a38e7a7f7d80834616ec8`. Bank file and code/protocol SHA are protected by a prescore lock.
- Five controls are evaluated under the same four-label cap: `integrated`, `fixed`, `exhaustive`, `no-inheritance`, `sham`. Source prefix is intentionally synthetic and aligned, **not acquired by an independent learner**. Source acquisition cost and general transfer cannot be claimed.

## Result: 48 worlds × 5 strategies = 240 arms

| Stratum | Integrated exact recovery | Exhaustive recovery | No-inheritance recovery | Fixed recovery | Integrated labels bought |
| --- | ---: | ---: | ---: | ---: | ---: |
| Reachable | 12/12 | 12/12 | 12/12 | 0/12 | 24 |
| Natural | 0/12 | 0/12 | 0/12 | 0/12 | 48 |
| Rare | 0/12 | 4/12 | 0/12 | 0/12 | 48 |
| Out-of-grammar | 0/12 (abstained) | 0/12 | 0/12 | 0/12 | 0 |

On reachable worlds, integrated correctly covered **72/72 held-out probes**, but exhaustive, no-inheritance and sham all matched this result. The prespecified **≥3-world improvement over the strongest control** was not met. `HOLD` is therefore retained, regardless of the perfect reachable score.

On natural worlds, integrated spent **48 target labels** (four per world) and abstained in all 12. On rare worlds, integrated spent another 48, recovered no exact motifs and accepted one **incorrect exact motif**, although its six scored probes did not distinguish that motif from truth. Consequently **zero probe errors is not evidence of robust semantic correctness**. Exhaustive recovered 4/12 rare worlds. On length-10 out-of-grammar worlds all five controls abstained without purchasing labels; this conservative behavior does not establish general out-of-grammar detection.

Across the scored report: **573 purchased target labels**, 573 internally reported auditor replays, 725 initial demonstration labels and **1,440 held-out probe labels** (logical accounting per arm, not a claim that all are unique physical oracle invocations). Worker wall time is recorded. CPU/RSS and total evaluator physical calls need stronger measurement.

## Reproduction and audit

**69/69 local unit tests passed** across the existing 33 PR #15 tests, 25 new integrated tests and 11 freeze/score/replay/audit tests. The new tests were run with Python 3.13.5 in a *partial local reconstruction* of compatible E1.4 dependencies. **The historical full 114-test ACE regression has NOT been rerun on a complete GitHub checkout**, so that gate remains open.

The frozen score and independent fresh-ledger replay each completed **240/240 arms**. Independent-from-worker auditors recomputed **573/573 receipt labels per run**, validated every purchased graph's topology/resource cost, enforced the four-label cap, and verified report arithmetic. Replay matched **17 deterministic fields across all 240 arms**, deliberately excluding elapsed-time counters. The score and replay raw files, SQLite ledgers and audit summary have SHA-256 evidence in `evidence/e14/e14t_result_summary_v1.json`.

Commands from complete ACE checkout:

```bash
PYTHONPATH=code:. python3 -W error::ResourceWarning -m unittest e14.test_e14_integrated_graph e14.test_e14_integrated_policy e14.test_e14_issue13_smoke e14.test_e14t e14.test_e14t_audit -q
PYTHONPATH=code:. python3 -m e14.e14t_run run --repo . --lock design/e1.4/E14T_LOCK_v1.json --bank evidence/e14/e14t_public_bank_v1.json.gz --ledger WORK/e14t-score.sqlite --output WORK/e14t-score.json.gz
# Repeat with fresh WORK/e14t-replay.sqlite and WORK/e14t-replay.json.gz, then call e14t_audit.audit and compare_replay.
```

## Failure analysis and research direction

The evidence identifies **two bottlenecks**. First, the bounded length-extension search is not superior to exhaustive enumeration or a no-inheritance control on reachable cases; the synthetic source prefix confers no independently established benefit. Second, four labels are insufficient for the natural and rare distributions as currently specified; heavy abstention and an exact-motif error in rare cases show that probe-only zero-error metrics conceal ambiguity.

The appropriate next experiment should test *new representation primitives*, not simply another extension of motif length or a different query ranking. Source artifacts must be learned and their acquisition cost counted. Introduce **adversarial distinguishing probes** for exact motif errors, stronger grammar-agnostic controls, and an independent evaluator with its own custody. Do not tune the E1.4t bank after this result or elevate GO/HOLD status without new evidence.

**References:** [Issue #13](https://github.com/dianzherdiana25-hash/ACE/issues/13) · [PR #15](https://github.com/dianzherdiana25-hash/ACE/pull/15) · [Prescore protocol](E14T_PROTOCOL_v1.md).
