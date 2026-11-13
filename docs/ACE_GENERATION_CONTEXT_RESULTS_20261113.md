# Generation Context — Equivalence + Speedup Confirmation (2026-11-13)

**Candidate:** the per-round generation context selected by
profiling pilot 2 (PR #183), whose report fixed the two promotion
gates and the preregistered delta before this build.
**Class:** search-set-preserving (raw-set/order). Workload: the
development band (pricing + shipping, levels 1–3, budget 200) —
pilot-regime estimates, not sealed evidence.

## What changed

`variants_by_group` now builds one `_round_context` per round —
the spec-number set plus the Compare and AugAssign nodes collected
in a single tree walk — and passes it to the operator groups.
Previously three groups recomputed `_spec_numbers(spec)` each and
two groups each walked the whole tree for their own node kinds.
Group functions take the context optionally; without it they
compute everything themselves, so the no-context path remains the
frozen equivalence reference (`gen_context_bench.variants_no_context`
/ `solve_no_context`, which keep parse-once tree sharing and the
same `CachingBudget` — the baseline is the immediately preceding
shipped path, so the delta below is this candidate's alone). The
context is read-only; a test pins that groups never mutate it. The
profiling observer's group wrapper forwards the context (one line).

## Gate 1 — equivalence replay (pilot workload, seeds 1–12)

- 6 differential tests (`test_gen_context.py`): context contents
  match an independent computation; every group function's output
  is identical with the context, without it (tree only), and bare;
  the context is unmutated after all groups run;
  `variants_by_group` equals the no-context reference exactly;
  solve outputs identical on sampled tasks at levels 1–4; broken
  source raises in both paths.
- Bench replay on the pilot workload: **0 output mismatches** on
  72/72 tasks (code, shown_score, evals, credits compared per task
  across all timed runs); median ratio 0.894 [0.882, 0.904]
  (reported, not the verdict — this workload selected the
  candidate's parent phase).

## Gate 2 — fresh-workload confirmation (seeds 901–912)

Disjoint from the pilot workload (1–12) and from the parse-once
confirmation (501–512). Preregistered delta 0.05; warm-up plus
5 reps per mode with alternating start, per-mode medians,
task-cluster bootstrap (2,000 iterations).

- **Median per-task ratio 0.9028, 95% CI [0.8984, 0.9087]** —
  entirely below 0.95 → **CONFIRMED**, a ≈9.7% median improvement
  of solve wall attributable to this candidate alone.
- Summed per-task medians: 0.079 s → 0.071 s over 72 tasks
  (≈1.10 ms → ≈0.99 ms per task).
- 0 output mismatches; 1 of 72 tasks slower (worst ratio 1.02,
  `task_db08dccbae18f6fe`, millisecond scale).

Size reconciliation: pilot 2 put transform_serialize at 0.173 s
of the 0.957 s *instrumented* wall, but the instrumented wall
carries the observer's own parse pass; against the 0.510 s
uninstrumented wall the phase is roughly a third of product time,
so a ~10% total improvement from cheaper generation is
consistent, not surprising.

## Honest bounds

Same regime as both pilots: saturated dev band (the pilot
workloads solve fully), one shared development VM, small absolute
times. The confirmation says the generation context is faster on
this band by the preregistered margin with identical outputs;
generalisation beyond the band is unmeasured. Focused suites:
57 tests OK (gen-context, parse-once, pilot, profiling,
reasoning, curriculum).

## Reproduce

```bash
cd code
python3 -m unittest ace_operational.test_gen_context
python3 -m ace_operational.gen_context_bench                 # seeds 901-912
python3 -m ace_operational.gen_context_bench --seeds 1-12    # replay
```

Raw outputs: lane handover store `gen_context_20261113/`
(`confirmation.json` with per-task detail, `replay_pilot_workload.json`);
the confirmation summary is
`docs/ACE_GENERATION_CONTEXT_CONFIRMATION_20261113.json`.
