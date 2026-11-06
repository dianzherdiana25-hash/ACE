"""JSON command-line interface for the bounded, local ACE runtime."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def labeled_rows(value):
    if not isinstance(value, list) or not value:
        raise ValueError("data must be a nonempty JSON array of [binary string, Boolean] rows")
    for row in value:
        if (not isinstance(row, list) or len(row) != 2 or
                type(row[0]) is not str or set(row[0]) - {"a", "b"} or
                type(row[1]) is not bool):
            raise ValueError("each data row must contain a binary a/b string and a JSON Boolean")
    return value


def read_task(path: Path):
    task = read_json(path)
    if not isinstance(task, dict) or set(task) != {"name", "train", "validation"}:
        raise ValueError("task must contain exactly name, train and validation")
    if type(task["name"]) is not str or not task["name"].strip():
        raise ValueError("task name must be a nonempty string")
    labeled_rows(task["train"])
    labeled_rows(task["validation"])
    return task


def positive_integer(value):
    try:
        number = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be a positive integer") from error
    if number < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    for name, help_text in (
        ("init", "initialize a local runtime workspace"),
        ("enqueue", "enqueue labeled development observations from JSON"),
        ("run", "process queued tasks within a task budget"),
        ("status", "inspect durable runtime state"),
        ("report", "inspect the full stored evidence for a completed task"),
        ("predict", "apply a stored program to one a/b string"),
        ("evaluate", "score a stored program on a separate labeled JSON array"),
        ("demo", "run three public synthetic tasks and report terminal evaluation"),
    ):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("--workspace", required=True, type=Path)
        if name == "enqueue":
            command.add_argument("--task", required=True, type=Path,
                                 help="JSON object with name, train and validation")
        elif name == "run":
            command.add_argument("--max-tasks", default=16, type=positive_integer)
        elif name in ("predict", "evaluate", "report"):
            command.add_argument("--task", required=True, dest="task_id")
            if name == "predict":
                command.add_argument("--word", required=True)
            elif name == "evaluate":
                command.add_argument("--data", required=True, type=Path,
                                     help="JSON array of [binary string, Boolean] rows")
    return result


def outcome_summary(outcome):
    """Keep the normal progress output compact; full evidence lives in report."""
    summary = {key: outcome[key] for key in (
        "task_id", "name", "status", "phase", "model_id", "learning_called",
        "staged", "train_labels", "validation_labels", "error",
    ) if key in outcome}
    selection = outcome.get("selection") or {}
    for key in ("train_correct", "validation_correct"):
        if key in selection:
            summary[key] = selection[key]
    return summary


def demo(runtime):
    from ace_capability_evolution.compositional import bank

    task_ids = {}
    terminal_rows = {}
    for name, task, seed in (
        ("source_equal", "equal", 20261106),
        ("inherited_equal", "equal", 20261107),
        ("changed_ends", "ends", 20261106),
    ):
        train, validation, terminal = bank(task, seed)
        task_ids[name] = runtime.enqueue({"name": name, "train": train,
                                          "validation": validation})
        terminal_rows[name] = terminal
    outcomes = [outcome_summary(result) for result in runtime.run(max_tasks=16)]
    evaluation = {name: runtime.evaluate(task_ids[name], terminal_rows[name])
                  for name in task_ids}
    return {"task_ids": task_ids, "outcomes": outcomes,
            "evaluation": evaluation, "status": runtime.status()}


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        # File input is checked before initializing or opening runtime state.
        task = read_task(args.task) if args.command == "enqueue" else None
        rows = labeled_rows(read_json(args.data)) if args.command == "evaluate" else None
        from .engine import Runtime

        with Runtime(args.workspace) as runtime:
            if args.command in ("init", "status"):
                result = runtime.status()
            elif args.command == "enqueue":
                result = {"task_id": runtime.enqueue(task)}
            elif args.command == "run":
                result = {"outcomes": [outcome_summary(outcome)
                                       for outcome in runtime.run(max_tasks=args.max_tasks)]}
            elif args.command == "report":
                result = runtime.report(args.task_id)
            elif args.command == "predict":
                result = {"task_id": args.task_id, "word": args.word,
                          "prediction": runtime.predict(args.task_id, args.word)}
            elif args.command == "evaluate":
                result = {"task_id": args.task_id,
                          "evaluation": runtime.evaluate(args.task_id, rows)}
            else:
                result = demo(runtime)
        print(json.dumps(result, sort_keys=True, allow_nan=False))
        return 0
    except Exception as error:
        print(f"ace: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
