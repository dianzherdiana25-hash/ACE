# ACE — Autonomous Capability Evolution

ACE researches intelligence that can develop, test, transfer and inherit
capabilities across generations. The long-term vision is Open-Ended Autonomous
Intelligence Evolution (OAIE); see [the project charter](PROJECT_CHARTER.md).

This `main` branch contains a **runnable public research toolkit**, with selected
R1 finite-state induction and S2 typed arithmetic search sources imported without
changes from their pinned research commits. It is a selected integration, not
the complete historical ACE codebase. Existing research branches and frozen
experiments remain available. The bounded runtime uses Python 3.12+ standard
library on Linux without API keys or paid services. Some research modules and
the complete test suite also require NumPy; CI installs `numpy==2.1.3`.

## Run the operational ACE loop

```sh
python3 ace.py demo --workspace ./ace-work
python3 ace.py status --workspace ./ace-work
```

The demo learns a counter, validates its inheritance on a second task without
refitting, then learns a counter/guard product when the inherited counter fails
validation. It stores the queue, learned library, decisions and evaluation
receipts in SQLite. Repeat the commands or restart the process to resume safely.

To submit your own task:

```sh
python3 ace.py enqueue --workspace ./ace-work --task examples/equal-counts.json
python3 ace.py run --workspace ./ace-work --max-tasks 16
```

Use the returned task ID with `predict --task ID --word aabb`, `report --task ID`,
or `evaluate --task ID --data examples/equal-counts-terminal.json`, always adding
`--workspace ./ace-work`. Tasks supply labeled a/b strings; only the declared
counter/DFA/product grammar is supported. A model must fit every training and
validation label before local prediction is enabled. This does not guarantee
correctness after a hidden change of meaning.

This is an operational bounded ACE generation. Choosing its own research agenda,
inventing new learning/representation classes, robust open-world transfer and
OAIE remain open. [Runtime contract and acceptance](docs/ACE_RUNTIME_V1.md).

## Reproduce the research experiments

```sh
python3 tools/verify_sources.py
PYTHONPATH=code python3 -m unittest ace_research_primitives.test_primitive_discovery ace_candidate_search.test_search ace_candidate_search.test_verify_results ace_capability_evolution.test_pilot ace_capability_evolution.test_structural ace_capability_evolution.test_compositional ace_runtime.test_engine ace_runtime.test_cli -v
PYTHONPATH=code python3 -m ace_capability_evolution.compositional --output /tmp/ace-v03.json
```

The original multi-generation acquisition and structural-switch pilots also run
directly, without separate branch checkouts:

```sh
PYTHONPATH=code python3 -m ace_capability_evolution.pilot --output /tmp/ace-v01.json
PYTHONPATH=code python3 -m ace_capability_evolution.verify /tmp/ace-v01.json
PYTHONPATH=code python3 -m ace_capability_evolution.structural --output /tmp/ace-v02.json
PYTHONPATH=code python3 -m ace_capability_evolution.verify_structural /tmp/ace-v02.json
```

The new v0.3 experiment composes a typed counter with a finite-state guard learned
from counterexamples. Its public run improves over counter-only selection, but
**does not beat the strong fixed-product library**. It does not establish new
primitive-type invention, safe open-world adaptation, recursive improvement or
OAIE. Programs that fail admission remain diagnostic predictions, not acquired
capabilities. No candidate is deployed by these commands or by merging this code.

[Protocol](docs/COMPOSITION_PROTOCOL_V03.md) ·
[Feasibility amendment](docs/COMPOSITION_PROTOCOL_V031.md) ·
[Results and limits](docs/COMPOSITION_RESULTS_V03.md) ·
[Imported source provenance](docs/UPSTREAM_SOURCES.json).

Scientific status: **NOT_ASSESSED**. Earlier v0.1/v0.2 release gates remain
**BLOCK_RELEASE**. Their unchanged package READMEs describe the original separate
checkout layout; the commands above use the integrated local sources.
