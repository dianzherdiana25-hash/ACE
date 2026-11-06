# ACE capability evolution pilot (coordinator-owned)

A bounded, **executed** multi-generation public synthetic prototype which composes the actual pinned R1 DFA induction and S2 closed typed arithmetic search from separate GitHub research PRs. It stages task-specific candidates, tests frozen retention and reports terminal generalization without using it to select candidates. All candidates remain local data and are **never deployed**.

Run with **both** exact pinned research checkouts on `PYTHONPATH`:
```sh
PYTHONPATH="_lane/r1/code:_lane/s2/code:code:." python -m unittest ace_capability_evolution.test_pilot -v
PYTHONPATH="_lane/r1/code:_lane/s2/code:." python -m ace_capability_evolution.pilot --output /tmp/ace-evolution.json
PYTHONPATH="_lane/r1/code:_lane/s2/code:." python -m ace_capability_evolution.verify /tmp/ace-evolution.json
```

See [prescore](../../docs/ACE_CAPABILITY_EVOLUTION_PILOT_PRESCORE_V1.md) and [results](../../docs/ACE_CAPABILITY_EVOLUTION_PILOT_RESULTS_20261106.md) for exact source SHAs, evidence, negative results and accepted limits.

**Research status: NOT_ASSESSED. Release status: BLOCK_RELEASE. OAIE: NOT_ESTABLISHED.** Passing CI means the source adapters and public evidence replay function, not that the model has become generally smarter.
