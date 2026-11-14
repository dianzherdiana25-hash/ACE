# ANTIGRAVITY TASK 07 — INITIAL CENSUS: unique pricing programs

Status: **ANALYSIS — an initial census, measured now.** This is
*not* the official census of the future B-3 stage (Task 06,
B3-R5): that census is a deliverable of the stage itself,
re-run against whatever generator is then frozen. This one
exists to answer, early, a single question: **can the Task 02
dossier's set allocations be funded from the pricing universe
as it exists today?** Author: Antigravity bench room,
2026-11-13 (no Gemini). No repo code was modified.

## Method (reproducible)

- Script: `census_pricing_task07.py` in this handover folder
  (kept with this report; raw output in
  `census_task07_result.json`).
- Generator used **as-is**: `curriculum_lab.generate_task(
  "pricing", level, seed=…)` from the `wt-g3inst` lineage,
  levels 1–4, seeds 0–3999 per level (16,000 generations).
- Deduplication key: `curriculum_lab.normalized_form` of the
  buggy code (renaming-invariant canonical form), exactly the
  dedup rule designed in Task 05.
- Exhaustiveness check: cumulative unique programs per level
  recorded every 500 seeds (saturation curve, §2).

## 1. Headline: the universe is exactly its theoretical ceiling

| Measure | Count |
|---|---|
| **Total unique pricing programs** | **216** |
| Theoretical ceiling (36 parameter combos × 6 defect sets) | 216 |
| Parameter combinations realised | 36 / 36 |
| Generation failures (`InvalidTaskError`) in 16,000 draws | 0 |

The generator realises its entire combinatorial space: every
parameter combination × every defect set produces a valid,
identifiable, climbable task. Nothing is lost to the
identifiability or gradient-path requirements in this family.

## 2. Breakdown

**By defect set** — perfectly uniform, 36 each (= all parameter
combinations):

| Defect set | Unique programs |
|---|---|
| `threshold_boundary` | 36 |
| `tax_basis` | 36 |
| `member_basis` | 36 |
| `threshold_boundary`+`tax_basis` | 36 |
| `threshold_boundary`+`member_basis` | 36 |
| `tax_basis`+`member_basis` | 36 |
| **Singles subtotal** | **108** |
| **Pairs subtotal** | **108** |

**By level** (unique programs *seen at* that level; levels
overlap — see the note):

| Level | Unique programs | Composition |
|---|---|---|
| L1 | 72 | singles of `tax_basis`, `member_basis` |
| L2 | 36 | singles of `threshold_boundary` |
| L3 | 108 | all pairs |
| L4 | 72 | the subtlety-≥3 pairs, **identical code to L3** |

Saturation: every level reached its final count **within the
first 500 seeds** and never moved across the remaining 3,500 —
this census is exhaustive, not a sample estimate.

> **L4 adds zero programs.** 72 programs appear at both L3 and
> L4; the L4 dressing (poisoned spec text) changes the *spec*,
> not the code, and `normalized_form` counts programs. Any
> allocation arithmetic that sums the level column (288) is
> double-counting. This also restates Task 05's warning in
> measured form: adversarial dressing is not a hardness lever
> for a solver that never reads the spec.

## 3. Feasibility verdict vs the Task 02 allocation

Demand (all sets unique programs, pairwise disjoint):

| Set | Design size | Draws from |
|---|---|---|
| B-3 probe set (Task 06) | ≥50 (each single & pair class ≥5) | singles + pairs |
| Control (Task 02) | ≥30 | substrate-solved, L1–L3 |
| Discovery pool (Task 02) | 12 (4/class) | singles |
| Evaluation (Task 02) | ≥45 singles (15/class) + 18 pairs | singles + pairs |
| Calibration (Task 05 P4) | ≥15 assumed (≥5/class) | singles (+pairs) |

**Totals are comfortable; the singles segment is the binding
constraint.** Against all 216: minimum total demand ≈ 170,
leaving ≈46 spare. Against the **108 singles** specifically:

- Fixed singles demand: pool 12 + evaluation 45 = **57**.
- Remaining singles for probe + control + calibration: **51**.
- If probe, control and calibration each drew singles freely
  (e.g. control 30 all-singles, probe ~30 singles), demand
  reaches ≈132 singles → **infeasible by ~24**.
- With the allocation caps below, worst-case singles demand
  is **99 of 108** (9 spare), pairs **76 of 108** (32 spare),
  and every set meets its designed size. Per-class check:
  each single class holds 36; capped per-class demand
  ≈ 33. Each pair class holds 36; demand ≈ 26.

**VERDICT: FEASIBLE WITH ALLOCATION AMENDMENTS — sizes stand,
composition is capped.** No Task 02 size needs to shrink,
provided the preregistration adopts these composition caps
(allocation amendments, decided before preregistration —
exactly the amendment channel Task 05 P2-R1 foresaw):

- **CAP-1 (control):** at most 10 of the ≥30 control programs
  are singles; the rest are pairs (the substrate composes
  pairs; control's regression function is level-agnostic).
- **CAP-2 (probe):** at most 20 of the ≥50 probe programs are
  singles.
- **CAP-3 (calibration):** at most 12 singles (4/class).
- The ≈41 unallocated programs (9 singles, 32 pairs) remain a
  **reserve**: replacements for any drawn task later rejected
  (e.g. by P4 calibration outcomes), never a silent top-up of
  a set after results.

Fallback if the caps are ever rejected: reduce evaluation
singles 45 → 36 (12/class) by pre-preregistration amendment;
the census shows no other size is under pressure.

## 4. Caveats

- This census describes the generator **as it stands**. P4
  hardening levers 3–4 (case-grid or defect-catalog changes)
  would change the universe; the official B-3 census
  (Task 06 B3-R5) re-runs against the then-frozen generator
  and supersedes these numbers for the stage's own
  allocations.
- "Unique program" ≠ "unique task instance": shown-case
  selection is deterministic given the program's parameters
  and defect set, so one program yields one task shape here;
  if shown selection ever becomes seed-dependent, task-level
  custody gets *more* room, never less — the program-level
  count in this census is the conservative bound.
- Control feasibility is counted against *potential*
  population (all programs sit in the substrate's three
  classes by construction). The realised control set can only
  be drawn after the substrate exists and its solved
  population is measured (Task 06 §4); if the frozen
  substrate solves materially fewer pairs than designed,
  CAP-1 must be revisited with real numbers.

— End of census. Raw data: `census_task07_result.json`;
method: `census_pricing_task07.py` (both in this folder).
