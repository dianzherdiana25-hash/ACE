# ACE E1.5 — bounded source evolution vertical slice (public development)

This increment creates actual candidate Python source artifacts and chooses a staged candidate based on disjoint validation examples. It does **not** execute candidate Python, alter live repository files, invent new architectures, or assert OAIE/self-improvement. The candidate grammar is finite and predeclared. A strict AST interpreter only permits integer addition, subtraction, multiplication, names `x,y`, and bounded integer literals; no `eval`, `exec`, imports, subprocesses, file access or arbitrary functions. The target synthetic task is `3*x + 2*y`, so the successful result is a proof-of-mechanics on a deliberately easy task, **not independent scientific generalization**.

## Execute

```bash
PYTHONPATH=code:. python3 -m unittest ace_loop.test_source_evolution -v
PYTHONPATH=code:. python3 - <<'PY'
from pathlib import Path
from ace_loop.source_evolution import SourceEvolution
engine=SourceEvolution(Path('WORK/e15-source-evolution'))
print(engine.run(stop_after=2))
print(SourceEvolution(Path('WORK/e15-source-evolution')).run())
PY
```

The engine appends SHA256 event receipts using the existing E1.5 `HashLedger`, records all rejected candidates, can pause/resume after an interruption, replays and rejects tampered decisions, evaluates holdout only in the terminal event, stages the selected source atomically without deploying it, and never promotes automatically. The output contains `candidate_promoted=false` and `scientific_decision=NOT_ASSESSED`. A missing staged source can be recovered from the final journal; a changed staged source blocks execution.

## Executed local evidence

Fourteen targeted tests PASS on a compatible local copy of the E1.5 HashLedger interface (not the original full repository engine). Test groups cover AST source safety, disjoint splits, real staged source, resume equivalence, idempotence, tampering, symlink, missing-stage recovery, and type/overflow guards. **Integration against the exact GitHub E1.5 engine and full historical regression remains unverified**. The candidate code is interpreted in-process under a strict AST whitelist, not an OS security sandbox. The actual original engine implementation is unchanged. Frozen E1.4t/E1.4aa, ACE `main`, Tod and the original E1.5 bank remain unchanged.

## Next gates

1. Execute tests with original E1.5 `engine.py` on a clean checkout and add native sandbox validation where arbitrary source code might later be introduced.
2. Replace the hand-authored finite candidate list with a bounded proposal generator; measure proposal compute and failures. Keep a new untouched confirmatory bank outside author control.
3. Add evaluator-owned receipt escrow before connecting any paid remote oracle or allowing any autonomous live source replacement.
