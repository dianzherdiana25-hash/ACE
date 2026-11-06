"""ChatGPT/GitHub task runner for ACE, with strict data-only task envelopes.

GitHub commits one task envelope to chat_tasks/current.json. A fixed
GitHub Actions workflow runs this module, and uploads a canonical evidence
artifact. No server, hosted writable endpoint, paid oracle, or model deployment.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from ace_capability_evolution import compositional, structural
from ace_runtime.engine import Runtime, validate_task

SCHEMA = "ace.chat.request.v1"
REPORT_SCHEMA = "ace.chat.receipt.v1"
MODES = ("research_v03", "runtime_demo", "task_batch")
MAX_BATCH = 4
MAX_TASK_BYTES = 131072


class RequestError(ValueError):
    """Fail-closed on unsupported task envelopes or method requests."""


def canonical(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def sha256(value):
    return hashlib.sha256(value).hexdigest()


def parse_request(raw):
    if type(raw) is not bytes or len(raw) > MAX_TASK_BYTES or len(raw) < 2:
        raise RequestError("invalid request bytes or size")
    try:
        obj = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise RequestError("request is not valid JSON") from exc
    if type(obj) is not dict or set(obj) != {"schema", "mode", "tasks", "request_id"}:
        raise RequestError("invalid request fields")
    if obj["schema"] != SCHEMA or type(obj["mode"]) is not str or obj["mode"] not in MODES:
        raise RequestError("unsupported request schema or mode")
    rid = obj["request_id"]
    if type(rid) is not str or not 1 <= len(rid) <= 60 or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789_-" for c in rid):
        raise RequestError("request_id must be lowercase ascii alphanumeric, _ or -")
    tasks = obj["tasks"]
    if type(tasks) is not list:
        raise RequestError("tasks must be a JSON list")
    if obj["mode"] != "task_batch":
        if tasks:
            raise RequestError("demo/research requests cannot contain custom tasks")
    else:
        if not 1 <= len(tasks) <= MAX_BATCH:
            raise RequestError("task_batch requires 1 to 4 tasks")
        seen = set()
        for task in tasks:
            if type(task) is not dict or set(task) != {"name", "train", "validation", "terminal"}:
                raise RequestError("task requires exactly name/train/validation/terminal")
            key = task["name"]
            if key in seen:
                raise RequestError("duplicate task name")
            seen.add(key)
            # Reuse the exact operational ACE task contract.
            validate_task({k:task[k] for k in ("name", "train", "validation")})
            term = task["terminal"]
            if type(term) is not list or len(term) > 128:
                raise RequestError("terminal must be an array up to 128 observations")
            if term:
                compositional.validate_rows(term, 128)
                dev_words = {w for partition in ("train", "validation") for w,_ in task[partition]}
                if dev_words & {w for w,_ in term}:
                    raise RequestError("terminal overlaps development data")
    return obj


def execute(obj, *, workspace):
    """Return a canonical, provenance-bound receipt from real ACE source APIs."""
    raw_request = canonical(obj)
    result = {
        "schema": REPORT_SCHEMA,
        "request_sha256": sha256(raw_request),
        "request_id": obj["request_id"],
        "mode": obj["mode"],
        "scientific_status": "NOT_ASSESSED",
        "release_decision": "BLOCK_RELEASE",
        "oaie_established": False,
        "candidate_deployed": False,
        "workspace_persistent_across_runs": False,
    }
    mode = obj["mode"]
    if mode == "research_v03":
        report = compositional.run()
        result["research"] = {
            "schema": report["schema"],
            "protocol_commit": report["protocol_commit"],
            "protocol_amendment": report["protocol_amendment"],
            "trial_count": len(report["trials"]),
            "terminal_correct": report["terminal_correct"],
            "terminal_total": report["terminal_total"],
            "beats_fixed_library": report["beats_fixed_library"],
            "compute_matched": report["compute_matched"],
            "open_world_safe": report["open_world_safe"],
            "full_report_sha256": sha256(compositional.s.canonical(report)),
        }
        result["_research_evidence"] = report
    else:
        with Runtime(workspace) as runtime:
            if mode == "runtime_demo":
                from ace_runtime.cli import demo
                receipt = demo(runtime)
                result["demo"] = receipt
            else:
                identities = []
                for task in obj["tasks"]:
                    developer = {k:task[k] for k in ("name", "train", "validation")}
                    identities.append(runtime.enqueue(developer))
                outcomes = runtime.run(max_tasks=len(identities))
                tasks = []
                for task, identity in zip(obj["tasks"], identities):
                    summary = runtime.report(identity)
                    evaluation = None
                    if task["terminal"] and summary["staged"]:
                        evaluation = runtime.evaluate(identity, task["terminal"])
                    tasks.append({
                        "name": task["name"], "task_id": identity,
                        "staged": bool(summary["staged"]),
                        "phase": summary.get("phase"),
                        "model_id": summary.get("model_id"),
                        "terminal": evaluation,
                        "error": summary.get("error"),
                    })
                result["tasks"] = tasks
                result["runtime"] = runtime.status()
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--research-output", type=Path, required=True)
    args = parser.parse_args(argv)
    obj = parse_request(args.request.read_bytes())
    with TemporaryDirectory(prefix="ace-chat-") as tmp:
        receipt = execute(obj, workspace=Path(tmp)/"ace-work")
    research = receipt.pop("_research_evidence", None)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical(receipt))
    if research is not None:
        args.research_output.parent.mkdir(parents=True, exist_ok=True)
        args.research_output.write_bytes(compositional.s.canonical(research))
    print(json.dumps({"request_id":obj["request_id"],
                      "mode":obj["mode"],
                      "receipt_sha256":sha256(canonical(receipt)),
                      "research_sha256":receipt.get("research",{}).get("full_report_sha256"),
                      "scientific_status":"NOT_ASSESSED",
                      "release_decision":"BLOCK_RELEASE"},sort_keys=True))


if __name__ == "__main__":
    main()
