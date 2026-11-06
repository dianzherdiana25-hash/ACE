# ACE operational generation v1

The runtime connects task intake, bounded candidate creation, validation,
inheritance, retained capabilities, local prediction, terminal evaluation and
restart recovery. It uses the existing R1 learner and S2 typed counter programs
without changing their imported source bytes. No API, cloud worker or paid
evaluator is required. Run `python3 ace.py --help` for the interface.

## Task and completion contract

A task is exactly `{"name": ..., "train": [...], "validation": [...]}`. Each row
is `["an a/b string", true-or-false]`. Training has 1..63 observations with at
most 63 distinct prefix-tree nodes; validation has 1..128 observations. Inputs
are at most 100 characters. Duplicate inputs, contradictory labels, overlap,
integer/Boolean aliases and unsupported fields are rejected. See `examples/`.

Each `run` processes at most the requested number of pending tasks, in persisted
enqueue order. It first tests existing capabilities on all supplied train and
validation labels. An exact match is inherited without calling the learner.
Otherwise, it invokes the counterexample-guided composition learner and compares
the new selected candidate with the retained library. Exact train+validation fit
is required to stage a model. Failed admission records `NO_VALIDATED_MODEL` and
does not enable predictions. Up to 256 tasks and 128 distinct capabilities can
be stored per workspace. No model is deployed as a service.

The supported representation grammar is seven typed counter slopes, learned
binary DFAs, and their conjunction. There is no arbitrary source generation,
code execution, learned extension of the grammar or independent research-agenda
selection. The queue is FIFO. A completed task is a recorded bounded trial,
not evidence that its behavior is correct in every future world.

## Persistence, custody and recovery

`WORKSPACE/ace.sqlite3` stores the task queue, immutable program data, full trial
reports and a hash-linked event chain. SQLite WAL with FULL synchronization and
`BEGIN IMMEDIATE` serializes writers. Each pure learning trial, model insertion,
task result and receipt commit atomically. A failure inside a trial rolls back
its model writes. A process interruption rolls back its active transaction;
the next process can recompute that pure trial. Concurrent processes cannot
complete the same queued task twice. No external effect or paid oracle is
performed, and these properties do not certify external exactly-once behavior.

Replay checks source/schema identity, event/state agreement, enqueue order,
program fingerprints and closed typed structure. It also checks stored terminal
scores against frozen programs. The database belongs to the local trusted
workspace: hashes detect inconsistent edits and corruption; they are not an
external signature against a party able to rewrite the entire database.

The workspace pins the engine and relevant learner source bytes. Opening it
after a source change fails explicitly; use a new workspace or a separately
reviewed migration. Upgrading code never silently rewrites an old experiment.

## Terminal evaluation

`evaluate` takes a separate JSON array of at most 128 labeled inputs, disjoint
from that task's development inputs. Evaluation never fits a model and cannot
change a staging decision or library entry. The first dataset is bound to the
task; repeating it returns its cached receipt, while a different dataset is
rejected. This prevents accidental repeated terminal selection within one task.
Custody is local and user-supplied, not independently sealed evaluation.

## Acceptance evidence

Tests exercise real learned reuse without refitting, rejection of negative
transfer, retention of previous capabilities, blocked unvalidated predictions,
bounded/idempotent intake, terminal separation, durable reports, process restart,
two simultaneous workers, and source/event/model/evaluation integrity checks.
An actual subprocess calls `os._exit` after model insertion but before commit;
reopening proves the trial and partial capability rolled back, then resumes it.

The public demo runs three author-selected synthetic tasks: equal-count learning,
equal-count inheritance on a different validation sample, and changed ends-b
semantics requiring a learned guard. All three score 128/128 on the known public
terminal data. It reuses the existing v0.3 bank and establishes operational
integration only. It is not a new independent scientific experiment, generalized
method transfer or a compute-matched performance result. Skipping a refit does
not mean fewer labels: every target's development labels are still checked.

Scientific `NOT_ASSESSED`; open-world safety and OAIE remain unestablished.
The next scientific gate remains the v0.3 fixed-product comparison and richer,
independently frozen counterexamples, rather than relabeling this demo as OAIE.
