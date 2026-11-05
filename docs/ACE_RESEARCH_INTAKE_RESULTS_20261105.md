# ACE Main Coordinator: independent R1/R8 public research intake — 2026-11-05

**Scientific disposition: HOLD / NO PROMOTION / NOT_ASSESSED.** This is a coordinator-owned external task-generator and exact-head replication on public synthetic worlds, **not** blinded independent evaluator custody or OAIE. Nothing here authorizes changing ACE `main`, frozen E1.4, either research branch, or Tod.

## Prescore and provenance

- Frozen coordinator [pre-score protocol](ACE_RESEARCH_INTAKE_PRESCORE_V1.md) was added in **earlier commit** `b8d9c1123933f7cb21ea832cc2a58c24505eca65`, before experiment code, tests or new scoring. Actions compares current protocol bytes to the committed protocol at that SHA and fails if changed.
- R1 code pinned to PR #38 exact HEAD `cf8948144919d41a70d1da6f3fb289d1dc818e36`; R8 pinned to PR #40 exact HEAD `9fa4cb8ec3896ea157ad135d75d241da3a4cb6c1`. Distinct source checkout paths; GitHub Actions verifies both HEADs.
- [Green GitHub Actions run #42063759593](https://github.com/dianzherdiana25-hash/ACE/actions/runs/42063759593), coordinator SHA `6bc19bf5dd2e1c41214c7f66b50b03899c6d6db8`: **r1-independent-public-transfer PASS; r8-public-null-canary PASS**.
- R1 test suite: 6/6 PASS; source/controls/metrics computed on independent coordinator bank. **Two consecutive full runs** produced byte-identical canonical JSON; SHA256 `3a63234ab34d977b98ddfa9393e0419e854d876d5b91b9d86db6624df15d4e0a` (49,812 bytes). GitHub Actions artifact `ace-r1-independent-public-intake`, ID `13433295233`, containing `r1_new_tasks.json`, `r1_summary.json`.
- R8 previously published 512-run public null replay: 62/62 tests PASS; regenerated JSON byte-identical to pinned `results_growth_null.json`; SHA256 `ab137f587eaf134482ce745778a48cc2b81a537be525c8627d4b15e591643d7f`. Artifact `ace-r8-public-null-intake`, ID `13433000530`.

## R1 independent new-task results

24 independently generated binary DFAs, nominal 6/8/10/12 source states (6 per group), graph-reachable, source-state count **not shown minimal**; 63 training labels and 256 length-12..20 terminal labels each, own seed and target generator independent of R1 H1–H5 target generators. No validation/terminal label conditions used in sampling or model selection. Three matched training-only fitted controls (fixed-predicate library, suffix3, prefix memorizer). Hindsight per-task best control **is not selectable**; only a conservative reference.

| Nominal states | Clean induced correct / 1536 | Clean tasks >=90% / 6 | One-label-noise correct / 1536 | Noisy tasks >=90% / 6 |
|---|---:|---:|---:|---:|
| 6 | 1416 | 4 | 1286 | 3 |
| 8 | 1161 | 1 | 1089 | 0 |
| 10 | 1041 | 0 | 996 | 0 |
| 12 | 1048 | 0 | 1023 | 0 |
| **Total** | **4666/6144 = 75.9440%** | **5/24** | **4394/6144 = 71.5169%** | **3/24** |

- Clean per-task hindsight oracle control: 68.9290%; induced gain **+7.0150 pp** (mean threshold +5 pp passes, required task count **18/24 FAILS**). Overall clean composite gate **FAIL**.
- One corrupt train label per task: 71.5169% accuracy, degradation 4.4271 pp vs clean; noisy best control 69.1081%, induced gain **+2.4089 pp**. Mean/noise degradation threshold passes, but required >=16/24 tasks with >=90% accuracy **FAILS**. Overall noise composite gate **FAIL**.
- Inverted-rule long-input counterfactual: same observed training labels are compatible with a different terminal rule. Current R1 interface emits a binary prediction on all 24x256 terminal items, with no abstention. **24/24 drift tasks unprotected by the API**; semantic safety promotion HALTS. This is an information-theoretic indistinguishability demonstration, not a calibrated OOD detector score.
- 3,293 R1 merge attempts across paired clean/noisy fitting. 7,656 distinct ground-truth train+terminal synthetic labels; repeated fitting does not create fresh unique oracle ground truth. CPU timings in separate run diagnostics are nondeterministic and excluded from receipt hash.
- All original H1–H5 R1 outcomes remain unchanged. R1 H2 positive within 2–5-state public generated class; R1 H3/H5 already reported negative complexity/selection/OOD outcomes. The coordinator's new sample adds **new public independent-generator support for complexity failure**, not cross-family or sealed scientific confirmation.

## R8 measurement canary

Under **known zero true effect** on its own author-visible synthetic null distribution, R8's micro-score >=+10 pp naive gate fires **42/512 = 8.203125%**, while its stronger family/lineage diagnostic fires **9/512 = 1.7578125%**. This is a relative improvement in this particular null setup, but **9 false passes remain**. These are not valid real-world calibrated p-values or evidence of intelligence growth; no new ACE policy is accepted.

## Coordinator integration disposition

**DO NOT PROMOTE R1 or R8 research to a generalized ACE intelligence-growth claim.** Keep draft PR #38 and #40 in research/evidence custody; no merging or source mutation. Technical study replay is a reproducibility gate; scientific acceptance additionally requires a genuinely separate sealed generator/family, independence against selection and multiple testing, matched cost/capacity baselines, robust noise/shift/abstention and signed evaluator custody.

**Next falsifiable research handoff:**
1. **R1**: independently design active-label acquisition or abstraction that yields >=18/24 >=90% on *new* high-complexity tasks at a fixed label budget, while distinguishing non-identifiable drift via correctly calibrated abstention. Do not retune against these now-visible 24 worlds and then claim blind OOD generalization.
2. **R8**: improve false discovery screening under sequential selection, correlated tasks and reusable test families; publish a family-cluster error bound with external evaluator custody. Repeat the known-zero-effect diagnostic on *new precommitted* seeds/families, not by selecting this one favorable outcome.
3. **R7**: evaluate safety/coverage trade-off for uncertainty and abstention under shift as a **separate** decision problem; R7's reported shift failures prevent reuse as an accepted safety certificate.
4. **Red Team**: review agent-engine journal and report false-pass/race findings before any core integration; positive source unit tests do not resolve current adversarial expected failures.
5. **Codex**: preserve the inherited E1.6 missing historical-test and native sandbox blockers, as tracked in #17/#49. Do not merge unsafe source variants while existing E1.4 controls remain unverified.

All scores are public synthetic engineering/research evidence. **Capability-growth scientific gate = NOT_ASSESSED**, and **OAIE = NOT_ESTABLISHED**.
