# ACE Research R3 — Adaptive Architecture Evolution (JS pilot v1)

Research-only module. Graph mutations change node count, edges, operator labels, and output routing. They are **actual structural edits**, not merely hyperparameter selection. Nodes are from a finite interpreter of AND, OR, XOR; generated code is never executed. E1.4 and the ACE main runtime are not modified.

**Scope isolation:** PR #35 S4 explores recursively transferred research policy productivity; this study evaluates within-task dataflow topology search. PR #36 synthesizes arithmetic expressions, not module connectivity. This module is independent of both.

## Reproduce

At repo root on Node.js 18+ (no installs):

```sh
node code/ace_research_architecture/experiment.js > /tmp/ace-r3-js.json
```

The JS source embeds deterministic self-tests (including malformed candidate rejection, bounded mutations, split independence, repeatability and test-label inversion not affecting final graph selection). 4 public four-bit Boolean functions with 6 seeded train/validation/test splits: 8 train, 4 validation, 4 final test points. Two functions are used as author-visible development; two as author-visible confirmation. Each architecture-search arm can score up to 120 distinct graphs, with max 12,000 proposals and 4 gates per graph. Graph interpreter is closed, **not** a CPU/memory sandbox for arbitrary untrusted code.

Arms: (1) immutable graph, (2) 27 operator-label settings with fixed wiring, (3) random structural samples, (4) fitness-guided beam mutations including add/delete, rewire, change output route. Training shortlist of 12 is frozen before validation; the holdout is evaluated only after selecting one candidate. Gates executed on all evaluated examples are counted; JS engine and sorting overhead are excluded.

## Actual V8 results

Development:
```json
{
  "fixed": {
    "cases": 12,
    "accuracy": 0.604167,
    "perfect": 3,
    "candidates": 12,
    "gate_ops": 576,
    "mean_gate_count": 3
  },
  "config": {
    "cases": 12,
    "accuracy": 0.75,
    "perfect": 5,
    "candidates": 324,
    "gate_ops": 9648,
    "mean_gate_count": 3
  },
  "random": {
    "cases": 12,
    "accuracy": 0.541667,
    "perfect": 1,
    "candidates": 1440,
    "gate_ops": 28764,
    "mean_gate_count": 0.75
  },
  "evolve": {
    "cases": 12,
    "accuracy": 0.5,
    "perfect": 0,
    "candidates": 1440,
    "gate_ops": 18944,
    "mean_gate_count": 1.0833
  }
}
```

Confirmation:
```json
{
  "fixed": {
    "cases": 12,
    "accuracy": 0.375,
    "perfect": 1,
    "candidates": 12,
    "gate_ops": 576,
    "mean_gate_count": 3
  },
  "config": {
    "cases": 12,
    "accuracy": 0.604167,
    "perfect": 3,
    "candidates": 324,
    "gate_ops": 9648,
    "mean_gate_count": 3
  },
  "random": {
    "cases": 12,
    "accuracy": 0.375,
    "perfect": 0,
    "candidates": 1440,
    "gate_ops": 28472,
    "mean_gate_count": 0.75
  },
  "evolve": {
    "cases": 12,
    "accuracy": 0.395833,
    "perfect": 1,
    "candidates": 1440,
    "gate_ops": 19172,
    "mean_gate_count": 1
  }
}
```

Test checks passed: 6. Per-arm/per-case evidence is in results.json and is deterministic from experiment.js. No evidence that this study has produced a generally superior architecture search algorithm or achieved OAIE. Tasks/holdout are public and author-visible; small samples; no independent adjudicator, CI, full-regression or production self-edit. Future work: sealed new tasks and equal gate-execution budgets, not only equal candidate budgets.

**Parallel local Python experiment (separate research artifact, not a claim about this exact JS code):** 14/14 tests passed; 288 records deterministically replayed; confirmation accuracies fixed 46.03%, fixed wiring/config search 68.65%, random 60.71%, evolved 62.70%. This negative result is not superseded by this JS pilot.

Do not merge without separate review and exact-head CI. No changes outside `code/ace_research_architecture/` are requested.
