# R3-v4/v4b reproducibility at PR #44 head

Scope: `code/ace_research_architecture/` only. Python 3.10+ standard library; no package installation, no paid evaluator. Candidate circuits are bounded data graphs; source-code execution is not part of the search.

From a clean checkout of the R3 branch:

```bash
PYTHONPATH=code python -m unittest ace_research_architecture.test_credit_v4 ace_research_architecture.test_credit_v4b -v
PYTHONPATH=code python -m ace_research_architecture.verify_credit_v4
PYTHONPATH=code python -m ace_research_architecture.credit_v4 --bank development --seeds 2 --output /tmp/r3-v4-development.json
PYTHONPATH=code python -m ace_research_architecture.credit_v4 --bank fresh --seeds 2 --output /tmp/r3-v4-fork.json
PYTHONPATH=code python -m ace_research_architecture.credit_v4 --bank chain --seeds 2 --output /tmp/r3-v4-chain.json
```

The repository includes `study.py`, `proposal_v3.py`, `credit_v4.py`, both v4 tests, `verify_credit_v4.py`, two original v4 record fixtures, and three v4b record fixtures. No private API or plugin is required. The old v1–v3 **full 32-test** fixtures/modules remain in the conversation ZIP, rather than this PR; therefore only the **12 new v4/v4b tests** are directly runnable from this source tree. The full **44/44 local test** assertion refers to the conversation bundle, not exact PR-head CI.

Repository JSON fixtures were committed as semantically identical **minified** JSON, so byte-level SHA-256 may differ from the originally archived pretty-printed local JSON documented in `R3_V4_NEGATIVE.md`. The replay checker compares full parsed records and summaries, not raw JSON formatting.

Published observations: v4b novelty credit 72.62%, 58.33%, 88.10% across development, fork and chain versus uniform 71.43%, 69.05%, 86.90%. Aggregate novelty 73.02% < uniform 75.79%, with ~2.6% *more* measured gate-work. Small, public synthetic samples; no blind independent evaluator.

**Acceptance:** do not merge, deploy or infer OAIE. Independent reviewer sign-off, exact-head fresh-checkout CI, unseen-task generalization, and equal realized work remain OPEN.
