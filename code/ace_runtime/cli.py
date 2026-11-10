"""JSON and operational command-line interface for the bounded, local ACE runtime."""
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
        if name == "status":
            command.add_argument("--workspace", default=None, type=Path)
            command.add_argument("--operational", action="store_true", help="show unified Edition 4 operational status")
            command.add_argument("--offline", action="store_true", help="enforce offline mode")
        else:
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
    mission_subs.add_parser("generate", help="generate missions from diagnostics")

    # W3: Core learner repair commands
    train_p = commands.add_parser("train", help="train with admission awareness and max errors tolerance")
    train_p.add_argument("--workspace", required=True, type=Path)
    train_p.add_argument("--task", required=True, type=Path)
    train_p.add_argument("--max-errors", default=0, type=int,
                         help="training errors tolerated; validation must have zero errors")

    doc_p = commands.add_parser("doctor", help="diagnose workspace and system integrity")
    doc_p.add_argument("--workspace", default=Path("./ace-work"), type=Path)
    doc_p.add_argument("--operational", action="store_true", help="include operational store and model checks")

    # Edition 4: Operational commands (`chat`, `do`, `web`, `start`, `stop`, `resume`, `models`, `evidence`, `agenda`, `learn`, `bridge`, `update`, `rollback`)
    chat_p = commands.add_parser("chat", help="ngobrol dengan ACE dalam Bahasa Indonesia")
    chat_p.add_argument("message", nargs="*", help="pesan langsung untuk ACE")
    chat_p.add_argument("--workspace", default=None, type=Path)
    chat_p.add_argument("--once", default="", help="kirim satu pesan lalu keluar")
    chat_p.add_argument("--client-id", default="", help="ID pesan klien untuk idempotensi")
    chat_p.add_argument("--offline", action="store_true", help="jalankan tanpa akses internet")

    do_p = commands.add_parser("do", help="kerjakan tugas rekayasa secara langsung dalam Bahasa Indonesia")
    do_p.add_argument("request", nargs="+", help="deskripsi tugas")
    do_p.add_argument("--workspace", default=None, type=Path)
    do_p.add_argument("--offline", action="store_true", help="jalankan tanpa akses internet")

    web_p = commands.add_parser("web", help="jalankan aplikasi web anime localhost ACE")
    web_p.add_argument("--workspace", default=None, type=Path)
    web_p.add_argument("--host", default="127.0.0.1", help="alamat host (default: 127.0.0.1)")
    web_p.add_argument("--port", default=8080, type=int, help="port HTTP lokal (default: 8080)")
    web_p.add_argument("--allow-lan", action="store_true", help="izinkan pengikatan non-loopback")
    web_p.add_argument("--offline", action="store_true", help="aktifkan mode offline")
    web_p.add_argument("--check-only", action="store_true", help="uji pengikatan port lalu keluar")

    start_p = commands.add_parser("start", help="inisialisasi dan pulihkan sesi operasional ACE")
    start_p.add_argument("--workspace", default=None, type=Path)
    start_p.add_argument("--offline", action="store_true")

    stop_p = commands.add_parser("stop", help="jeda atau hentikan tugas operasional aktif")
    stop_p.add_argument("--workspace", default=None, type=Path)
    stop_p.add_argument("--task", default="", dest="task_id")

    resume_p = commands.add_parser("resume", help="lanjutkan tugas dari checkpoint terakhir")
    resume_p.add_argument("--workspace", default=None, type=Path)
    resume_p.add_argument("--task", default="", dest="task_id")

    models_p = commands.add_parser("models", help="periksa status backend model lokal, offline, dan host")
    models_p.add_argument("models_action", nargs="?", default="status", choices=["status", "verify", "check-ram"])
    models_p.add_argument("--workspace", default=None, type=Path)
    models_p.add_argument("--ram-mb", default=1024, type=int, help="estimasi kebutuhan RAM model dalam MB")

    ev_p = commands.add_parser("evidence", help="tampilkan bukti verifikasi (receipt) dan cerita aktivitas")
    ev_p.add_argument("--workspace", default=None, type=Path)
    ev_p.add_argument("--task", default="", dest="task_id")

    ag_p = commands.add_parser("agenda", help="tampilkan antrean prioritas tugas dan aging score")
    ag_p.add_argument("--workspace", default=None, type=Path)

    learn_p = commands.add_parser("learn", help="periksa frontier kemampuan, gap, dan keterampilan hasil belajar")
    learn_p.add_argument("learn_action", nargs="?", default="status", choices=["status", "run"])
    learn_p.add_argument("--workspace", default=None, type=Path)
    learn_p.add_argument("--gap", default="", dest="gap_id")

    br_p = commands.add_parser("bridge", help="kelola status worker consumer dan work order AI")
    br_p.add_argument("bridge_action", nargs="?", default="status", choices=["status", "enable-consumer", "disable-consumer"])
    br_p.add_argument("--workspace", default=None, type=Path)

    up_p = commands.add_parser("update", help="periksa atau terapkan pembaruan rilis bertahap")
    up_p.add_argument("update_action", nargs="?", default="status", choices=["status", "apply"])
    up_p.add_argument("--workspace", default=None, type=Path)
    up_p.add_argument("--version", default="4.1.0-candidate")
    up_p.add_argument("--fail-smoke", action="store_true", help="simulasikan kegagalan smoke test")

    rb_p = commands.add_parser("rollback", help="kembalikan rilis ke versi stabil sebelumnya")
    rb_p.add_argument("--workspace", default=None, type=Path)

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


def _handle_operational_command(args) -> int:
    from ace_operational.autonomy_loop import AutonomyOrchestrator
    from ace_operational.language import ConversationalEngine
    from ace_operational.models_backend import ModelRouter
    from ace_operational.store import OperationalStore
    from ace_operational.web_server import ACEWebCore, ACEWebServer

    with OperationalStore(args.workspace) as store:
        if getattr(args, "offline", False):
            store.set_offline(True)

        if args.command == "start":
            recovered = store.recover_interrupted_tasks()
            core = ACEWebCore(store)
            payload = core.get_status_payload()
            payload["recovered_tasks"] = [t["task_id"] for t in recovered]
            print(json.dumps(payload, sort_keys=True, ensure_ascii=False))
            return 0

        if args.command == "status":
            core = ACEWebCore(store)
            print(json.dumps(core.get_status_payload(), sort_keys=True, ensure_ascii=False))
            return 0

        if args.command in ("chat", "do"):
            engine = ConversationalEngine(store)
            if args.command == "do":
                text = " ".join(args.request).strip()
            else:
                text = (args.once or " ".join(args.message)).strip()

            if text:
                res = engine.handle_user_message(
                    text,
                    client_message_id=getattr(args, "client_id", "") or None,
                )
                print(json.dumps({
                    "reply": res["reply"],
                    "duplicate": res["duplicate"],
                    "task_id": res["task"]["task_id"] if res["task"] else None,
                    "task_status": res["task"]["status"] if res["task"] else None,
                    "intent": res["intent_frame"].get("intent"),
                }, sort_keys=True, ensure_ascii=False))
                return 0

            # Interactive REPL loop when no one-shot message given
            print("ACE Studio Chat (ketik 'keluar' untuk berhenti)")
            while True:
                try:
                    line = input("Kamu > ").strip()
                except EOFError:
                    break
                if not line or line.lower() in ("keluar", "exit", "quit"):
                    break
                res = engine.handle_user_message(line)
                print(f"ACE  > {res['reply']}\n")
            return 0

        if args.command == "stop":
            core = ACEWebCore(store)
            tid = args.task_id
            if not tid:
                latest = store.get_latest_task()
                tid = latest["task_id"] if latest else ""
            if not tid:
                print(json.dumps({"status": "NO_ACTIVE_TASK"}))
                return 0
            res = core.control_task(tid, "pause")
            print(json.dumps({"task_id": tid, "status": res["task"]["status"]}, sort_keys=True))
            return 0

        if args.command == "resume":
            core = ACEWebCore(store)
            tid = args.task_id
            if not tid:
                latest = store.get_latest_task()
                tid = latest["task_id"] if latest else ""
            if not tid:
                print(json.dumps({"status": "NO_TASK_TO_RESUME"}))
                return 0
            res = core.control_task(tid, "resume")
            print(json.dumps({"task_id": tid, "status": res["task"]["status"]}, sort_keys=True))
            return 0

        if args.command == "models":
            router = ModelRouter(store)
            if args.models_action == "check-ram":
                out = router.check_ram_budget_for_model(args.ram_mb)
            else:
                out = router.health_check()
            print(json.dumps(out, sort_keys=True, ensure_ascii=False))
            return 0

        if args.command == "evidence":
            receipts = store.list_receipts(args.task_id or None)
            events = store.list_events(include_heartbeats=False, limit=30)
            print(json.dumps({"receipts": receipts, "events": events}, sort_keys=True, ensure_ascii=False))
            return 0

        if args.command == "agenda":
            orch = AutonomyOrchestrator(store)
            print(json.dumps({"agenda": orch.get_prioritized_agenda()}, sort_keys=True, ensure_ascii=False))
            return 0

        if args.command == "learn":
            orch = AutonomyOrchestrator(store)
            if args.learn_action == "run" and args.gap_id:
                res = orch.learn_skill_and_resume_parent(gap_id=args.gap_id)
                print(json.dumps({"skill": res["skill"], "gap": res["gap"]}, sort_keys=True, ensure_ascii=False))
                return 0
            print(json.dumps({
                "frontier": store.list_frontier(),
                "gaps": store.list_gaps(),
                "skills": store.list_skills(),
            }, sort_keys=True, ensure_ascii=False))
            return 0

        if args.command == "bridge":
            orch = AutonomyOrchestrator(store)
            if args.bridge_action == "enable-consumer":
                orch.set_worker_consumer_active(True)
            elif args.bridge_action == "disable-consumer":
                orch.set_worker_consumer_active(False)
            print(json.dumps({
                "worker_consumer_active": orch.is_worker_consumer_active(),
                "work_orders": store.list_work_orders(),
                "mission_bus": orch.mission_bus.status(),
            }, sort_keys=True, ensure_ascii=False))
            return 0

        if args.command == "update":
            orch = AutonomyOrchestrator(store)
            if args.update_action == "apply":
                res = orch.stage_and_apply_update(args.version, smoke_test_passes=not args.fail_smoke)
                print(json.dumps(res, sort_keys=True, ensure_ascii=False))
                return 0
            print(json.dumps({
                "active_version": store.get_meta("release_version"),
                "previous_version": store.get_meta("previous_release_version"),
            }, sort_keys=True, ensure_ascii=False))
            return 0

        if args.command == "rollback":
            orch = AutonomyOrchestrator(store)
            print(json.dumps(orch.rollback_release(), sort_keys=True, ensure_ascii=False))
            return 0

        if args.command == "web":
            server = ACEWebServer(
                store,
                host=args.host,
                port=args.port,
                allow_lan=args.allow_lan,
            )
            info = {
                "url": server.url,
                "host": server.host,
                "requested_port": server.requested_port,
                "actual_port": server.actual_port,
                "port_fallback_used": server.port_fallback_used,
                "workspace": str(store.workspace),
            }
            if args.check_only:
                server.stop()
                print(json.dumps(info, sort_keys=True, ensure_ascii=False))
                return 0
            print(f"ACE Studio Web aktif di: {server.url}", flush=True)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                server.stop()
            return 0

    return 0


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        # Operational commands handled by ace_operational
        operational_cmds = {
            "chat", "do", "web", "start", "stop", "resume",
            "models", "evidence", "agenda", "learn", "bridge", "update", "rollback",
        }
        if args.command in operational_cmds:
            return _handle_operational_command(args)

        if args.command == "status" and (
            getattr(args, "operational", False) or args.workspace is None
        ):
            return _handle_operational_command(args)

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
            if getattr(args, "operational", False):
                from ace_operational.models_backend import ModelRouter
                from ace_operational.store import OperationalStore
                with OperationalStore(args.workspace) as store:
                    report["operational_models"] = ModelRouter(store).health_check()
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
