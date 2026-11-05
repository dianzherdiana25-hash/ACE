# ACE E1.4z — Postscore semantic-drift audit, 2026-11-05

**Status: public exploratory/postscore, NOT_ASSESSED.** Prescore bank remains frozen in `research/e14z-semantic-drift`. This change is a child branch, not an amendment to the prescore bank.

## Execution

The prescore bank defines 20 source operators, two drift classes (near/far), two target motif pairs, and five controls, for **400 target arms**. Four independent score batches (5 source operators each) were executed and retained in `evidence/e14/z/`. The postscore independent historical DFS audit was rerun from those exact batch reports, and 63 E1.4y/E1.4z tests passed in the current compatible local workspace.

- Recomputed 138 source label observations (source raw original SQLite journals were not archived).
- Replayed 828 target purchases and checked 1,092 accepted held-out predictions.
- Constructed 176 explicit counterexample graphs for accepted false hypotheses, 176/176 using previously unpurchased query points; these postscore auditor calls do not count as purchased learner interventions.
- Analytical 66-point query-domain random two-query miss probabilities: near drift has 2–9 disagreement points, far drift 45–55. The expected number of false accepts under *uniform random sampling without replacement* is 34.22 near and 3.67 far across 40 worlds per drift. These are mathematical expectations, not observed random policy experiments.

## Main outcomes, per drift (40 arms per strategy)

| Mode | Near correct / wrong / abstain | Far correct / wrong / abstain | Near target labels | Far target labels |
|---|---:|---:|---:|---:|
| transfer-direct | 0 / 40 / 0 | 0 / 40 / 0 | 0 | 0 |
| transfer-verify2 | 0 / 36 / 4 | 0 / 3 / 37 | 80 | 80 |
| cold-new | 0 / 0 / 40 | 4 / 0 / 36 | 160 | 160 |
| cold-old | 2 / 34 / 4 | 0 / 0 / 40 | 118 | 70 |
| sham-transfer | 0 / 19 / 21 | 0 / 4 / 36 | 80 | 80 |

All numbers are from deterministic authored synthetic worlds. Correctness is **exact program identity**, not merely agreement on a few probes. `cold-new` avoids false acceptance here by abstaining in 76/80 arms; it is not an overall success. Source acquisition and target purchases are accounted separately.

## Findings and limits

1. Source-to-target inheritance is brittle under near-semantic drift: even two purchased checks do not reliably identify a change.
2. A larger representation grammar alone is insufficient when the label budget prevents identification.
3. A postscore witness proves a particular accepted program is wrong, but cannot be retroactively treated as an online detection by the learner.
4. Historical source raw SQLite journals were not preserved, so the independent source replay verifies aggregates and operator lineage, not byte-level source receipts.
5. No native Bubblewrap security certification, clean full-checkout regression, independent sealed confirmatory benchmark, AGI or OAIE claim.

**Research decision:** HOLD on unconditional cross-task operator inheritance. Future work should test budget-matched active drift detection, allow explicit representation revision, and lock fresh world banks before scoring.

## Replay

```bash
PYTHONPATH=code:. python -m e14.e14z_audit WORK/e14z-score-*.json --output WORK/e14z-audit-fresh.json
PYTHONPATH=code:. python -m e14.e14z_detection_limits WORK/e14z-score-*.json --output WORK/e14z-limits-fresh.json
PYTHONPATH=code:. python -m unittest discover -s code/e14 -p 'test_e14[yz]*.py' -q
```
