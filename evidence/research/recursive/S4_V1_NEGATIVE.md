# S4-v1 observed local development run (negative finding)

Executed 2026-11-05, CPython, single deterministic seed 20261105. Run command: `python study.py > results.json` on locally executed equivalent implementation before GitHub commit. GitHub module reproduces same deterministic logic; **the exact GitHub commit has not been separately checked out and rerun**. Wall/CPU timing is machine-dependent.

- Four generations, 24 tasks/generation, six labels/task, six equal-budget policies.
- 3,456 labels per split (development, future, adversarial inverted payoff), **10,368 simulated labels total**, 576 labels per policy per split. Zero external/paid labels.
- Future success counts (out of 576): evolving adaptive 364; static adaptive0 366; static adaptive1 361; fixedA 292; fixedB 273; uniform 278.
- Negative inversion counts: evolving adaptive 353; static adaptive0 351; static adaptive1 349; fixedA 253; fixedB 290; uniform 280.
- Successor priors across generations: 0→1, 1→1, 1→0, 0→1.
- Future gain vs strongest matched control: **−2/576 = −0.347 percentage points**.
- Negative inversion gap vs strongest control: **+2/576 = +0.347 percentage points**.
- Predeclared criterion: future gain ≥ +28.8 successes and negative loss ≥ −28.8 successes. **REJECT / NO EVIDENCE OF RECURSIVE RESEARCH-PRODUCTIVITY IMPROVEMENT**.
- Local CPU time: ~0.0072 process seconds (not independently replicated).

Important: comparing only against fixedA/B would misleadingly show a positive gain, but a static adaptive policy outperformed the successor. The experiment tests policy tie-break inheritance only; there is no self-authored source or architecture. These synthetic results are not an independent scientific confirmation. No E1.4 locks or heldouts accessed.

Next falsifiable hypothesis: in a nonstationary but predictably autocorrelated task-family sequence, a successor trained on prior-family transition statistics can beat a matched adaptive static-prior and equal-budget online change-point baseline on disjoint future family sequences, while failing safely under adversarial reversed transition dynamics. Freeze sequence generators and thresholds before executing.
