# ACE Meta-Controller — public synthetic vertical slice

This module is **operational but deliberately bounded**. It selects research
problems, emits finite predeclared hypotheses, allocates integer experiment
budget, compares deterministic train/validation errors, adopts only safe
validation improvements, stops after two nonproductive trials on a track,
and recovers interrupted state from an append-only SHA-256 event chain and
atomic checkpoint. It uses no third-party packages and has no external actions.

Baseline: PR #27 `research/e15-source-evolution`, commit
`965640786cbf2f8adcd89eb1d980945f78c2da77`. The module is independent;
no changes to `ace_loop`, E1.4, or CI are required.

## Reproduce (Python 3.10+ on POSIX with `fcntl`)

From the repository root:

```sh
PYTHONPATH=code python3 -m unittest ace_meta_controller.test_controller -v
ROOT=$(mktemp -d)
PYTHONPATH=code python3 -m ace_meta_controller.cli --root "$ROOT/run" --stop-after-trials 3
PYTHONPATH=code python3 -m ace_meta_controller.cli --root "$ROOT/run"
PYTHONPATH=code python3 -m ace_meta_controller.cli --root "$ROOT/run"
sha256sum "$ROOT/run/events.jsonl"
```

The first command runs the module's unit/adversarial suite; the next three
perform a paused run, resumed completion, and idempotent readback. Run data
are intentionally written outside the repository. Pass `--budget 2` or
`--budget 16` on a fresh root to change the cap; do not change a live run's
budget, as replay then fails closed. Costs are simulated **experiment units**,
not monetary spending.

## Decision contract

- Problems are public fixed synthetic targets, prioritized for pilot coverage.
  Each has an ordered finite coefficient-pair hypothesis list and a cost of
  two units. After a pilot on each eligible track, the next track maximizes
  `floor(100 * current_validation_gain / spent_units)` with priority tie-break.
- Each hypothesis gets a deterministic train and disjoint validation score:
  `absolute_error = sum(abs(predicted - target))`. Adopt only when validation
  absolute error strictly decreases without increasing training error.
- Two consecutive failed hypotheses stop that track. The controller stops
  when no eligible funded trial remains. Only after all decisions does it
  record a separate, disjoint public holdout comparison; **never** select
  using holdout. Both train/validation reuse public data and are not a
  statistically independent confirmatory experiment.
- Writes `config`, paired `trial` and `decision`, and one `complete` record.
  Each event has sequence, previous hash, and SHA-256 canonical JSON digest;
  `fsync` is used on append. A single nonblocking POSIX file lock prevents
  concurrent writers, while an atomic checkpoint stores the replayed state
  digest. Torn/altered journals and forged rehashed decisions fail closed.
- If interruption occurs after trial receipt but before decision, replay
  recomputes the pure score and commits exactly one decision. Old or missing
  checkpoints can be reconstructed from verified events; contradictory
  checkpoints halt. No automatic repair of a corrupted journal is attempted.

## Limitations

This is a **finite local research scheduler** and not general hypothesis
invention, independent scientific discovery, self-modifying architecture,
or open-ended evolution. The objectives, targets, hypotheses, budgets and
holdout are all author-visible. In particular the synthetic task was chosen
to demonstrate expected gains, so a zero holdout error is only a mechanics
check. `scientific_decision=NOT_ASSESSED`, `candidate_promoted=false`.

It does not integrate with GitHub CI, `ace_loop`, remote oracles, external
receipts, Work tasks, or real spending. Do not substitute effectful adapters:
replaying results would re-execute the effect and violate at-most-once safety.
The filesystem threat model assumes a trusted local OS; the SHA chain is not
cryptographically signed and cannot protect against a privileged attacker
who changes the source, all receipts, and the evaluator itself. Future live
integrations need isolated evaluator-owned receipts, an independent bank,
a documented action approval boundary, and precise recovery semantics.
