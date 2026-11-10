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

    # W1: Mission Bus subcommands
    mission_parser = commands.add_parser("mission", help="interact with the ACE Mission Bus")
    mission_parser.add_argument("--workspace", required=True, type=Path)
    mission_subs = mission_parser.add_subparsers(dest="mission_action", required=True)

    next_p = mission_subs.add_parser("next", help="claim next pending mission")
    next_p.add_argument("--agent", default="advisor_antigravity", help="agent identifier")

    sub_p = mission_subs.add_parser("submit", help="submit artifact for claimed mission")
    sub_p.add_argument("--id", required=True, dest="mission_id", help="mission ID")
    sub_p.add_argument("--artifact", required=True, type=Path, help="path to artifact")
    sub_p.add_argument("--agent", default="advisor_antigravity", help="agent identifier")
    sub_p.add_argument("--decision", default="PENDING_EVALUATION", help="decision")

    mission_subs.add_parser("status", help="check mission queue status and hash chain")

    gen_p = mission_subs.add_parser("generate", help="generate missions from diagnostics")

    # W3: Core learner repair commands
    train_p = commands.add_parser("train", help="train with admission awareness and max errors tolerance")
    train_p.add_argument("--workspace", required=True, type=Path)
    train_p.add_argument("--task", required=True, type=Path)
    train_p.add_argument("--max-errors", default=0, type=int,
                         help="training errors tolerated; validation must have zero errors")

    doc_p = commands.add_parser("doctor", help="diagnose workspace and system integrity")
    doc_p.add_argument("--workspace", default=Path("./ace-work"), type=Path)

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
        if args.command == "mission":
            from ace_mission.bus import MissionBus
            from ace_mission.generator import MissionGenerator
            bus = MissionBus(args.workspace / "mission_bus.sqlite3")
            if args.mission_action == "next":
                result = bus.next_mission(args.agent) or {"status": "NO_PENDING_MISSIONS"}
            elif args.mission_action == "submit":
                result = bus.submit_mission(
                    mission_id=args.mission_id,
                    artifact_path=str(args.artifact),
                    agent_id=args.agent,
                    decision=args.decision,
                    provenance="ADVISOR_AGENT"
                )
            elif args.mission_action == "status":
                result = bus.status()
            elif args.mission_action == "generate":
                generator = MissionGenerator(bus)
                diags = [
                    {"type": "INFORMATION_SHORTAGE"},
                    {"type": "TOOL_SHORTAGE"},
                    {"type": "METHOD_SHORTAGE"},
                    {"type": "BUDGET_EXHAUSTION"},
                    {"type": "ADMISSION_FAILURE"},
                    {"type": "DRIFT_VULNERABILITY"},
                ]
                missions = generator.generate_from_diagnostics(diags)
                result = {"generated_count": len(missions), "missions": missions}
            print(json.dumps(result, sort_keys=True, allow_nan=False))
            return 0

        if args.command == "doctor":
            from ace_core_repair.doctor import run_doctor_diagnostics
            report = run_doctor_diagnostics(args.workspace)
            print(json.dumps(report, sort_keys=True, indent=2))
            return 0

        if args.command == "train":
            from ace_core_repair.admission import fit_with_admission
            task = read_task(args.task)
            _, eval_res = fit_with_admission(task["train"], task["validation"],
                                            max_errors=args.max_errors)
            eval_res["task_name"] = task["name"]
            print(json.dumps(eval_res, sort_keys=True, indent=2))
            return 0

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
