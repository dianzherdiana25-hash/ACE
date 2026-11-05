# Bounded typed candidate search

This independent module synthesizes integer arithmetic programs from a declared
recursive grammar and training observations. It does not import or modify
`ace_loop`, `ace_evolution`, or `ace_receipts`. Programs are immutable typed AST
data interpreted by a closed dispatcher; no candidate Python is compiled or
executed. The original five programs exist only in the comparison arm.

Before implementation, GitHub was inspected on 2026-11-05:

- Repository default HEAD: `5b0059b85055404a46adcdef305de81f5257486c`.
- Base `research/e15-source-evolution`: `965640786cbf2f8adcd89eb1d980945f78c2da77`.
- PR #27: open draft, same base-branch head, finite five-program implementation;
  its reported 46-test Actions result is historical, separate from these results.
- Working branch: `codex/ace-candidate-search`. All new files are under this module.

## Run

Python 3.10+ and POSIX (`flock`, directory fsync); stdlib only, no service or API.
From the repository root:

```sh
PYTHONPATH=code:. python -m unittest ace_candidate_search.test_search ace_loop.test_source_evolution ace_loop.test_engine ace_loop.test_portfolio -v
PYTHONPATH=code python -m ace_candidate_search.benchmark --output /tmp/ace-search-new-run
PYTHONPATH=code python -m ace_candidate_search.verify_results
```

The benchmark requires a new output directory, writes all 64 journals and a
summary, and prints aggregate results. The verifier checks the committed gzip
archives against their SHA-256 manifest, every journal hash chain, every trial
and decision regenerated from the grammar, and each summary's final receipt.
Timings vary; ASTs, costs, choices and journal bytes are deterministic.

```python
from pathlib import Path
from ace_candidate_search import Grammar, Limits, Observation, run

train = (Observation(-1, 2, 8), Observation(2, 1, -1))
validation = (Observation(3, 4, 6),)
holdout = (Observation(-2, 3, 13),)
path = Path('/tmp/search-checkpoint.jsonl')
run(path, Grammar(), Limits(), train, validation, holdout, pause_after=8)
result = run(path, Grammar(), Limits(), train, validation, holdout)
```

These observations describe `3*y - 2*x`. Use a new path for changed inputs,
grammar, limits, or mode; changed commitments fail replay.

## Grammar, bounds and selection

The grammar is `Int := x | y | constant | add(Int,Int) | sub(Int,Int) |
mul(Int,Int)`. Default constants are `(0,1,2,3)`; constants and allowed operation
names are explicit configuration. Boolean/float aliases, unknown variables,
malformed arity and executable constructs are rejected. Intermediate integers
are bounded to magnitude `10**9`, inputs to `100`, and observations to 128 per
split. Overflow is a recorded candidate failure, never a successful partial score.
ASTs have absolute ceilings of depth 6 and 15 operations (31 nodes).

`beam` composes expressions in depth order, canonicalizes commutative operands,
and retains terminals plus a training-ranked beam at completed depths. Training
rank is absolute error, operation count, depth, then canonical AST bytes. The
algorithm generates structures and constants from the declared grammar; it does
not infer new arithmetic primitives. The frontier receipt records retained
parents and the number pruned. `frontier_exhausted` means this bounded frontier
finished, without claiming exhaustive coverage of the grammar.

`enumerate` retains all preceding successful expressions without training
feedback pruning; candidate and compute bounds prevent exhaustive explosion.
`fixed-list` searches the five PR #27 programs; `fixed` uses `x+y`. Every arm
obeys the same grammar, structural, candidate and total work ceilings. The
fixed arms legitimately spend less than the ceiling, and their existing ASTs
are not charged as synthesis attempts.

Explicit configurable ceilings cover depth, operation count, number of scored
candidates, beam size, shortlist size, and deterministic compute work. One work
unit is a composition attempt or an interpreted AST node. Structural and
commutativity rejection attempts are charged. Full training-evaluation work is
reserved before admitting a candidate. A worst-case reserve for validation and
one final holdout evaluation is withheld from search; total reported work never
exceeds `max_work`. Actual process CPU and wall time, including journal writes,
are also reported. Work units exclude hashing, sorting, AST allocation and I/O;
this is a bounded logical compute budget, not an OS-enforced CPU/memory sandbox.
All these overheads have finite structural/count ceilings.

Only training observations enter `Search`. After search stops, a training-ranked
shortlist is frozen; validation ranks that shortlist once. Other candidates are
explicitly excluded by training rank or overflow. Validation decisions and a
final selected AST are committed in a freeze receipt before holdout scoring.
Holdout is never used in proposals or selection. Input coordinates must be
unique and disjoint across splits. Split hashes commit the supplied public data.
No source code, predictor callback, filesystem access, or oracle is available to
candidate programs. This is an API/data separation within one trusted process,
not a private evaluator or sealed confirmatory bank.

## Recovery and integrity

Journals contain configuration commitments, candidate ASTs and IDs, grammar rules
and parent IDs, per-candidate training results/costs, overflow failures, frontier
pruning, stop reasons, shortlist exclusions, validation decisions, the frozen
selection and final results. Candidate identity is SHA-256 of its canonical AST.
Parent IDs describe expression composition; the fixed-list arm can reference
subexpressions that were not separately scored.

Every event has a sequence, previous hash and checksum. Resume verifies canonical
bytes and recomputes the entire semantic prefix, rejecting even rehashed forged
scores, decisions, boolean aliases and extra terminal events. Empty, truncated,
noncanonical or corrupted existing evidence fails visibly without repair.
Changed inputs/configuration also fail. Roots, ancestors, journal and lock
symlinks are rejected. Local trusted writers are serialized with `flock`.

An atomic replacement checkpoint is fsynced every 64 events, on requested pause,
at freeze and at completion; directory fsync follows replacement. Uncommitted
pure work may repeat after a crash. No remote calls or side effects are replayed.
Pure holdout scoring is recomputed when verifying a completed journal; this does
not reopen search or selection. Replay cost is additional real CPU, outside the
original logical cost receipt. Pause at freeze does not score holdout.

The tests kill a live worker with SIGKILL immediately after its first durable
64-event checkpoint, then compare resumed and clean journal bytes. They also
inject failure before atomic replacement and resume at phase boundaries.
Durability relies on local POSIX filesystem guarantees. The checkpoint file is
replaced as a whole; old rows remain byte-identical. Hashes are not signatures:
whole-history rollback/deletion or coordinated replacement of the trusted code,
inputs and journal cannot be detected without an external trusted chain head.
Symlink checks do not defend against a hostile filesystem owner racing the host.

## Executed development evidence

Python 3.12.14, CPU only, no paid calls. `results/tests.log`: **68 tests PASS**
(22 new + 46 existing), exit 0. Existing dependencies were fetched from the exact
base; 16 existing source/test files matched their GitHub blob SHAs byte for byte.
Initial harness failures (an omitted test-helper mode argument and unavailable
sparse-checkout dependencies) were resolved before this acceptance run. No
existing implementation or workflow was changed. Full historical archive
regression and native sandbox validation were not run.

The eight public synthetic tasks are original linear, negative linear,
difference, product with offset, quadratic, constant, floor division, and a
fourth-degree polynomial. Each has 4 training, 3 validation and 3 final holdout
observations. A solved task means all 3 holdout observations match exactly.
Every result is retained, including unsupported targets and budget failures.

| Budget | Arm | Solved / 8 | Scored candidates | Total logical work | CPU seconds |
| --- | --- | ---: | ---: | ---: | ---: |
| Standard | Fixed | 0 | 8 | 240 | 0.015 |
| Standard | Fixed list | 1 | 40 | 1,632 | 0.016 |
| Standard | Enumerate | 5 | 16,000 | 440,866 | 4.831 |
| Standard | Beam | 6 | 10,491 | 286,707 | 2.711 |
| Tight | Fixed | 0 | 8 | 240 | 0.012 |
| Tight | Fixed list | 1 | 40 | 1,632 | 0.016 |
| Tight | Enumerate | 0 | 40 | 304 | 0.015 |
| Tight | Beam | 0 | 40 | 304 | 0.014 |

Per-run standard ceilings: depth 3, 3 operations, 2,000 candidates, 200,000 work,
beam 20, shortlist 5. Tight ceilings: same structure/selection, 5 candidates and
300 work. Comparisons share ceilings, not equal actual CPU or equal actual work.
These two predeclared harness regimes expose both useful synthesis and the
advantage of the hand-selected list when search is severely constrained.

Standard beam solves the six representable tasks; enumeration misses negative
linear under its candidate cap. Both fail the floor-division and fourth-degree
tasks on final holdout. Tight generated search stops after terminals and fails
all eight; fixed-list search retains the original linear solution. The fixed
list is much cheaper and does not cover the other task structures.

`results/summary.json` contains all 64 per-run scores, actual timing, limits,
search costs, stop reasons, selected ASTs, decisions, and journal hashes.
`results/*.json.gz` contain **all 64 complete journals**, bundled by task as JSON
maps from relative journal names to canonical JSONL text. Their manifest binds
the compressed bytes. `verify_results` regenerates and checks every event.

These are small author-visible, deterministic development fixtures with known
human-designed grammar and targets. There are no independent tasks, random-seed
replicates, confidence intervals, hidden target grammar, or scientific superiority
claim. The existing fixed-list task is intentionally favorable to that baseline;
the broader tasks are intentionally favorable to synthesis. Beam can prune a
needed subexpression, and bounded enumeration is order-sensitive. Three holdout
points cannot establish semantic equivalence. No target or budget was tuned after
the reported final benchmark. No architecture invention, live promotion,
deployment, merge, or OAIE claim is made.

`ENGINEERING_GATE = PASS` for this tested bounded module.
`RESEARCH_HYPOTHESIS = NOT_ASSESSED`.
