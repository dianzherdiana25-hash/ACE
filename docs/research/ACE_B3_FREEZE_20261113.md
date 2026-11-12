# Pricing substrate v1 — freeze record (Stage B-3)

Date: 2026-11-13. Author/builder: Muse (Ian), ACE's
registered development-engine brain, under the
coordinator's ratified scope. Design: bench Task 06
(`ANTIGRAVITY_TASK_06_B3_PRICING_SUBSTRATE_DESIGN.md`).
This freeze binds the substrate and the pricing
generator together; a discovery run against any other
digest is an integrity failure of that run.

## 1. The lever decision (B3-R3), taken before the freeze

The original generator enumerates exactly 216 unique
pricing programs, and the stage's first probe measured
BOTH the authored substrate and the generic token-search
comparator at 216/216 — freezing over that ceiling
would repeat the v1/v2 saturation deliberately. Per the
coordinator's ratification (2026-11-13), the case-grid
lever was applied ONCE, as a single principled
expansion: `_pricing_family` ranges now span their
realistic commercial ranges in one step (thresholds
{50k…1M}, bulk/member percentages {5,10,15,20}, tax
{10,11,12} bracketing the 11% PPN rate) — 480 parameter
combinations. No new defect classes; no structural
template change; the substrate's operators are
parameter-free and unchanged. This is not a serial
widening: any further expansion is a new decision.

## 2. Census (B3-R5) against the frozen generator

Seeds 20000–25999, levels 1–3, deduplicated by
`normalized_form`: **2,857 unique programs** (of the
2,880 theoretical ceiling): singles 479–480 per class,
pairs 471–474 per pair class. Allocation headroom
against the dossier's demand (~170) is now ample; the
CAP-1/2/3 caps, computed against the old 216 universe,
are to be re-derived against this census at
preregistration lock-in (coordinator's instruction),
not inherited silently.

## 3. Probe (one-shot for the frozen configuration)

Probe set fixed BEFORE the re-probe from a fresh seed
band (20000–20999, levels 1–3, dedupe by program):
1,768 unique programs. The substrate's operators were
authored against the defect catalog before the FIRST
probe and never iterated against any probe set; the
generator lever changed the population, not the
operators, and this re-probe is the freeze's own
(bench Task 06 §5: a moved template requires a
re-probe). Judgement on holdout by the lab verifier,
both arms at evaluation-budget 400:

- Substrate: **1.000 overall** (singles 1.000, pairs
  1.000, every pair class 1.000) — the declared bar
  (≥95% incl. all singles) is met.
- Comparator (token search): **1.000 overall**, as
  measured. The expansion multiplies distinct programs;
  it does not change per-program reachability for token
  swaps, and the comparator's saturation is therefore
  reported as a persisting measured state. Per the
  coordinator's fence it returns to the hub as the
  input for the next lever decision (defect classes);
  it does not block this freeze, whose baseline arm is
  the substrate, and whose calibration checkpoint (P4)
  exists to measure ceiling risk before the
  preregistration locks.

Evidence: `evidence/b3_probe_set.json` (original set),
`evidence/b3_probe_report.json` (original probe),
`evidence/b3_census_expanded.json`,
`evidence/b3_probe_set_v2.json`,
`evidence/b3_probe_report_v2.json` (frozen-config
probe; wall 14.6 s).

## 4. The frozen artifact

- Module: `code/ace_operational/pricing_substrate.py`
  (sha256 `791fd77f6e33c53a9c0e7520d2c43f0fe00434d40ce44ed9ca17411b692e7292`):
  two structural operator generators in fixed order —
  `_variants_threshold`, `_variants_rebase_basis` —
  plus `pricing_variants` and `solve_pricing`
  (max_rounds 6, frontier width 4).
- Generator: `curriculum_lab.py` at sha256
  `22304a45705bfef6eff675a38ca2d35836e5e96c871dfbd84aaf61eaeb16775c`.
- Probe report (frozen config) sha256:
  `2ce79d88dc32e2d4cf19d2f6fffc388a1cd8241a5406a005c7ad718c610f50a6`.
- **Freeze digest** (SHA-256 over substrate bytes ·
  ordered operator names · solver parameters · probe
  report digest · generator digest):
  **`658b9022681bcb9e658b7b3f1c85fd3bc8e106718dca8b5ff1fd6b8cffd6bd21`**
- The P2 adapter is rebound in this same stage:
  `PricingAdapter.baseline_variants` = the substrate's
  `pricing_variants`; `baseline_catalog_id` =
  `pricing-substrate-v1:658b9022…d21`.

## 5. Versioning

Frozen as **pricing substrate v1**. Any post-freeze
change to an operator, a signature, or a solver
parameter is v2: new probe on a fresh set, new digest,
new freeze record. The substrate's author does not
select probe sets (fixed by seed range before
authoring) and, per two-hats, is not the brain that
later runs the measured discovery dossier against this
baseline.
