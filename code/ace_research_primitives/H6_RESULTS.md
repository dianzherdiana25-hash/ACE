# ACE R1 H6 results — bounded distinguishing queries

Status: **PUBLIC SYNTHETIC DEVELOPMENT, NOT_ASSESSED, overall H6 REJECTED**. Pre-score hypothesis and task bank specification committed in `H6_PROTOCOL.md` at `b54c02a24c79021e852b01f9c8c7a1473e746981`, prior to implementation and scoring. Experiment run locally on Python 3.13.5 stdlib-only source, no external or paid evaluator; no source-code candidates executed. Frozen E1.4 and other team paths not modified.

## Reproduce
From repository root:
```bash
cd code
PYTHONPATH=. python -m unittest ace_research_primitives.test_h6_distinguish -v
PYTHONPATH=. python -m unittest discover -s ace_research_primitives -p 'test_h6_*.py' -v
PYTHONPATH=. python -m ace_research_primitives.h6_distinguish --output /tmp/r1-h6.json
PYTHONPATH=. python -m ace_research_primitives.audit_h6 /tmp/r1-h6.json
sha256sum /tmp/r1-h6.json
```

**Exact local evidence:** 117,912 bytes; SHA256 `9b94a2e037f150863aee1f5ea8cb2a189844a9059d7c8611728dbf0a278b7315`. Raw JSON is a reproducibility attachment in the ChatGPT conversation, *not* checked into repository. `12/12` local tests pass. Separate within-team audit independently reconstructs 80 worlds, 240 (world × method) score records, 256 query-oracle labels including controls, and rechecks the selected candidate against 256 terminal strings for every decided world. It detects tampered oracle labels, decisions, terminal scores and altered aggregate gates.

The three executed H6 source files have local Git blob SHA values matching the uploaded GitHub bytes exactly:
- `h6_distinguish.py` = `62bc1212ec21ea3680f75ef4e468a3b0082f5077`
- `audit_h6.py` = `e0809f83bf3a0b7db267a706a0686e05212b1ba3`
- `test_h6_distinguish.py` = `51d3ebc50e80bcd88ea0eb3c7bcb9dc6a356eed0`

## H6a: mechanically identify supplied hypotheses using one new label

Each of 80 tasks starts with two *researcher-authored* Boolean hypotheses that agree on all 63 training words. One model flips the source predicate on selected 5-character trigger substrings for lengths >=6. The selector can inspect the pair's predictions on 1,984 candidate words (lengths 6–10), then purchase one oracle label.

| Strategy | Correct mechanism identified | Abstained | Query labels | Correct terminal predictions when decided |
|---|---:|---:|---:|---:|
| Choose first disagreement | **80/80** | 0 | 80 | 20,480 / 20,480 |
| Uniform random full pool | **10/80** | 70 | 80 | 2,560 / 2,560 |
| Random *among disagreements* | **80/80** | 0 | 80 | 20,480 / 20,480 |

**H6a PASS (development bank only).** Advantage over uniform-pool random is +87.5 percentage points in identification, above the preregistered +40pp gate. However the **stronger compute-cost-aware conceptual comparator** random-among-disagreements performs identically; the benefit is knowing which queries distinguish models, not special selection intelligence. The protocol did not demand computational-cost parity, and active scanning of 1,984 candidate inputs costs more than one random sample.

**Important denominator:** terminal correctness is conditional on selecting a hypothesis. The 70 abstained uniform-random worlds must not be silently counted as successful generalization.

## H6b: non-identifiable late mechanism shift

Eight worlds with paired hypothesis models that differ only for length >=14, outside the entire allowed query pool (length <=10). All **8/8 abstain**, so the preregistered nonidentifiability gate **PASS**. This does not mean the system can predict the unseen shift; it correctly lacks discriminating evidence.

## H6c: out-of-class unknown mechanism

Eight worlds provide only candidates H0 (base) and H1 (flip when `aaaaa` occurs). But actual oracle flips when `bbbbb` occurs, an unlisted third mechanism. The first chosen disagreement query contains `aaaaa` but not `bbbbb`; oracle matches H0. The selector accepts **H0 in 8/8 cases**, **abstains 0/8**, creating 8 false-confidence acceptances. Preregistered requirement was at least 6/8 abstentions. Therefore **H6c FAIL**; **overall H6 GO REJECTED**.

With Boolean outputs, if the only two proposed hypotheses disagree on a particular query, any Boolean oracle label must match exactly one of them. **One disagreement label can never, by itself, certify that the true mechanism belongs to the candidate set**. This is a structural closed-world limitation of this protocol, not a software bug.

## Bounded evidence, limitations and next falsifiers

- Query-oracle budget: 256 total calls = 80 worlds × 3 methods + 8 late controls + 8 open-world controls. Each method consumes one synthetic label per world; terminal labels scored separately, without reuse for selection.
- The paired hypotheses and base predicates are **researcher-provided**, not inferred or invented. This is not open-ended primitive discovery. Strong random-disagreement control ties exactly.
- No independent third-party run, no final-HEAD GitHub Actions CI. 12 H6 tests were run locally; full historical H1–H5 GitHub exact-HEAD regression was **not** rerun during this extension. Scientific status remains **NOT_ASSESSED**.
- Follow-on scientific challenge: use multi-hypothesis open-world models or counterexample-driven class construction, combined with an explicit *model-class adequacy* test; compare to equally resourced alternate class proposal baselines and unavoidable semantic-indistinguishability witnesses. Do not equate more queries or bigger hand-authored class list with self-invented primitives.
