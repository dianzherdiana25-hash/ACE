# R1 H4 — evidence-conditioned counter-register construction

**Research status: PUBLIC SYNTHETIC DEVELOPMENT / scientific NOT_ASSESSED. No OAIE claim.**

Branch: `research/chat-r1-primitives`. Scope exclusively `code/ace_research_primitives/`; no changes to main, frozen E1.4, or the other researchers' lanes. Draft PR #38 remains unmerged.

## Prior evidence and design
H1/H2 successfully induced small finite-state transition graphs. H3 **rejected** scaling and noise robustness at 63 labels/task (16/48 clean worlds >=90% with target sizes 6–12; 11/48 after one label flip). H4 asks whether a **different memory representation** can be induced from observations rather than increasing the number of automaton states.

**H4 PRE-SCORE protocol commit:** `85515f6c91c18b898c8e51d1d2ed75b3df755ef0`. Protocol and acceptance thresholds were committed before H4 implementation/execution. This is not a novel primitive type; the *integer-register class*, the count embedding and residual guard classes were designed by the researcher. The learned weights / acceptance threshold / guard instances arise from observed positive/negative training examples.

## Implementation and evaluation methodology
- `h4_counter_induction.py`: construct integer signed normal vectors to differences between observed **positive Parikh count vectors**, normalizing with gcd. Infer acceptance `w_a*#a+w_b*#b=t` from positive evidence. If false positives remain, consider data-supported prefix-min, prefix-max and absent-bigram residual guards; reject counter hypotheses with remaining training error. **No oracle access inside inference, no eval/exec or generated candidate code.**
- Training is all 63 binary strings of length 0..5. Validation is all 192 words of length 6..7 (diagnostic only). For each of 12 worlds, terminal holdout is **48 unique length-disjoint strings** (24 positives and 24 negatives). Most holdout lengths 8..20; block languages use n=4..27, so lengths 8..54. Positive/negative pairs share a symbol-count multiset on the Dyck and ordered-block tasks; equal-count and ratio cases use one-character flips for hard negatives.
- Four controls: baseline RPNI (same 63 training labels), exact-prefix memorizer, suffix-3 majority, and best of original finite single-predicate library by train error. Strongest **hindsight holdout control per task** is used as a deliberately optimistic reference; it is never used to tune the new learner. Counter-only without residual guard is evaluated as ablation.
- 12 × (63 training + 192 diagnostic + 48 holdout) = **3,636** synthetic label evaluations in total. Register proposal/guard budget <=1,000 each/world; RPNI original <=10,000 attempted merges. Counts are not compute-equivalence.
- `audit_h4.py` is a separate reference auditor that does not import `h4_counter_induction.py`: it reconstructs holdout samples, target labels, original baseline predictions (using independently pre-existing H3 reference helpers), serial counter and original DFA predictions, errors and all acceptance gates.
- `test_h4_counter_induction.py`: 16 new tests. Full R1 suite now **41/41 PASS locally**, including prior H1–H3 tests, in unittest discovery mode. No final-HEAD GitHub Actions run yet.

## Predeclared H4a: eight counter-structured tasks

| Task | Learned state / guard | Induced correct / 48 | Optimistic oracle best control / 48 | Counter-only ablation / 48 |
|---|---|---:|---:|---:|
| #a == #b | (1,-1), no guard | 48 | 37 | 48 |
| #a == 2#b | (1,-2), no guard | 48 | 26 | 48 |
| #b == 2#a | (2,-1), no guard | 48 | 28 | 48 |
| #a == 3#b | (1,-3), no guard | 48 | 30 | 48 |
| Dyck-1 a-opening | (1,-1), min prefix >=0 | 48 | 32 | 24 |
| Reverse Dyck-1 b-opening | (1,-1), max prefix <=0 | 48 | 30 | 24 |
| a^n b^n | (1,-1), forbid `ba` | 48 | 24 | 24 |
| b^n a^n | (1,-1), forbid `ab` | 48 | 24 | 24 |

**H4a PASSED on this specifically designed synthetic bank:** 384/384 = **100%** induced holdout correctness, vs best-per-task holdout controls 231/384 = **60.15625%**. Absolute gain **+39.84375 percentage points**; 8/8 primary tasks >=90% correctness. The prespecified H4a acceptance required mean >=85%, gain >=10pp, and >=6/8 tasks >=90%, all met.

The zero-counter ablation falls to 24/48 on Dyck / ordered-block tasks because balanced symbol totals alone cannot identify order and prefix constraints. Guard selection is a fixed engineer-supplied class, not an autonomously discovered kind of state or operator.

## Predeclared H4b: negative specificity controls

| Out-of-class control | Counter proposed? | Fallback model holdout correct |
|---|---|---:|
| odd count(a) (regular) | No | 48/48 |
| avoids `aba` (regular) | No | 48/48 |
| palindrome (non-counter structure) | No | **31/48** |

**H4b specificity gate PASSED:** 0/3 unsupported counter proposals (required <=1). This does **not** imply reliable fallback accuracy: palindrome remains 31/48 (64.58%) even though the learner abstains. Counterexample: `aabaaaaa` truth=0, fallback=1.

## Adversarial indistinguishability: decisive negative result

The special target `late_flip_equal` has **identical labels to `#a==#b` across all 63 training examples**, and the opposite predicate on holdout lengths >=8. The algorithm therefore constructs the **same signed register**, but obtains **0/48 holdout correctness**. Witness: `abbbaaab` truth=0, constructed prediction=1. Its original RPNI fallback achieves only 11/48, and the best hindsight baseline 24/48.

The model cannot distinguish these worlds from training data. This falsifies strong claims that training-consistent representation synthesis ensures true semantic identification or safe OOD acceptance.

## Integrity, reproducibility and evidence

Commands from repository root:

```sh
cd code
PYTHONPATH=. python -m unittest discover -s ace_research_primitives -p 'test_*.py' -v
PYTHONPATH=. python -m ace_research_primitives.h4_counter_induction --output /tmp/r1-h4.json
PYTHONPATH=. python -m ace_research_primitives.audit_h4 /tmp/r1-h4.json
sha256sum /tmp/r1-h4.json
```

Full local result **58,095 bytes**, SHA256 `afaf6d4465c141d10e58a454ae46f3a21e5f2647fb94f8087786b674498e2dcb`. The raw JSON contains all 12 outcomes, original and constructed model representations, 7 model scores ×3 splits, hashes of word banks, feature construction attempts and 4 holdout counterexamples per model. It is provided as a downloadable conversation artifact, not committed as a GitHub JSON blob; it can be deterministically regenerated.

Independent within-team audit: **12 tasks, 3,636 label recomputations, 252 model×task×split score cells reconciled**; tampering with scores, learned guard, RPNI state, holdout digest or acceptance aggregate is detected by unit tests. All 41/41 local tests PASS.

Local `git hash-object` matches on-branch GitHub blobs exactly:
- `h4_counter_induction.py` `5ef43eebe04f354c75fc95d8d288d1a0cb238052`
- `audit_h4.py` `1a8dc3acb2d966a7f2d4aa4f949625d1447a472b`
- `test_h4_counter_induction.py` `d286c69494fd8d7065efa751e8c8338fa61b4ce4`

**Transparent post-initial-execution technical amendment:** The very first H4 run terminated *without emitting a complete report* because the matched-length adversarial `late_flip_equal` generator sampled odd-length positives; an equal-count negative cannot exist at the same odd length. The code now restricts this **one adversarial holdout family** to even lengths before sampling positives. This correction happened after implementation/attempted execution and before the first complete H4 score report. Primary eight targets, three specificity controls, original observation cap and acceptance gates were unchanged. Therefore treat H4 as within-team synthetic exploratory evidence, not fully independent prescore-confirmatory science. A later postscore evidence-extension also records `rpni_automaton` serializations, allowing a separate auditor to replay previous numerical scores without changing learner decisions.

## Interpretation and unresolved limitations
This is a bounded **representation synthesis** demonstration, not open-ended creation of computational primitives. The register algebra and guard templates were researcher-supplied; weights and instantiated residual predicates were inferred from labels. All primary tasks were hand-designed to fit this representation family, with deliberately balanced holdout sets; the 39.8pp improvement **must not** be extrapolated to unknown task distributions. Even a perfect 100% result here coexists with the 0% indistinguishability counterexample and the negative H3 scaling result.

No external independent assessor, final-head GitHub CI, third-party task family, non-symbolic environment, stochastic/noisy label robustness, multi-register or actual stack discovery, or compute-matched SAT/EDSM baselines verified. No OAIE or autonomous primitive-class invention claim. Keep PR #38 draft and do not merge.
