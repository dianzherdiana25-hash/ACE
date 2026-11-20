#!/usr/bin/env python3
"""Latih amplop self-send dengan repo bare dan proses gh palsu di fixture.

Batch menyisipkan satu target main untuk menguji penolakan sebelum prepared.
Waktu fixture memakai UTC dan maju satu menit per peristiwa yang tercatat.
"""

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

if __package__:
    from .self_send import check_envelope
    from .self_send_audit import audit
else:
    from self_send import check_envelope
    from self_send_audit import audit


_BRANCH = "ace-auto/20261120-rehearsal"
_MOCK_GH = """import json
from pathlib import Path
import sys

Path(sys.argv[1]).write_text(json.dumps(sys.argv[3:]), encoding='utf-8')
raise SystemExit(int(sys.argv[2]))
"""


def _deliver_fixture(repo, mock, branch, env, fail_mock_gh):
    args_file = mock.with_name("argv.json")
    args_file.unlink(missing_ok=True)
    args = ["pr", "create", "--draft", "--head", branch, "--base", "main"]
    result = subprocess.run([sys.executable, "-I", str(mock), str(args_file),
                             str(int(fail_mock_gh)), *args],
                            cwd=repo, env=env, capture_output=True, timeout=10)
    recorded = json.loads(args_file.read_bytes())
    if recorded != args:
        raise ValueError("Argv mock tidak cocok dengan fixture.")
    return recorded, result.returncode


def _rehearse(branches, *, fail_mock_gh=False):
    env = {"PATH": os.defpath, "GIT_CONFIG_GLOBAL": os.devnull,
           "GIT_CONFIG_SYSTEM": os.devnull, "GIT_TERMINAL_PROMPT": "0"}
    with TemporaryDirectory(prefix="ace-send-rehearsal-") as directory:
        root = Path(directory)
        remote, repo = root / "fixture.git", root / "checkout"
        def git(*argv):
            return subprocess.run(["git", *map(str, argv)], cwd=root, env=env, check=True,
                                  capture_output=True, text=True, timeout=10).stdout.strip()

        git("init", "--bare", "-q", remote)
        git("init", "-q", repo)
        git("-C", repo, "remote", "add", "origin", remote)
        configured = git("-C", repo, "remote", "get-url", "origin")
        if Path(configured) != remote or git("--git-dir", remote, "rev-parse", "--is-bare-repository") != "true":
            raise ValueError("Remote rehearsal bukan repo bare fixture.")

        events, outcomes = [], []
        log = root / "audit.jsonl"
        mock = root / "fixture_gh.py"
        mock.write_text(_MOCK_GH, encoding="utf-8")
        start = datetime(2026, 11, 20, 10, tzinfo=timezone.utc)
        with log.open("x", encoding="utf-8") as stream:
            def append(common, outcome):
                stamp = (start + timedelta(minutes=len(events))).isoformat().replace("+00:00", "Z")
                event = {**common, "ts": stamp, "outcome": outcome}
                events.append(event)
                stream.write(json.dumps(event) + "\n")
                stream.flush()

            for branch in branches:
                envelope = check_envelope(branch, merge_authority=False, environ={"GH_TOKEN": None})
                outcome = {"branch": branch, "envelope": envelope}
                outcomes.append(outcome)
                if envelope["mode"] != "dry_run" or not envelope["passed"]:
                    outcome["status"] = "rejected"
                    continue
                payload = b"fixture payload" if branch == _BRANCH else branch.encode("utf-8")
                common = {"branch": branch, "trigger": "rehearsal",
                          "content_digest": hashlib.sha256(payload).hexdigest()}
                append(common, "prepared")
                recorded, exit_code = _deliver_fixture(repo, mock, branch, env, fail_mock_gh)
                outcome.update(mock_argv=recorded, mock_exit_code=exit_code,
                               status="mock_failed" if exit_code else "sent")
                if not exit_code:
                    append(common, "sent")
        report = audit(log)
        # Pointer tetap bisa dibandingkan dengan array log yang disertakan.
        for transition in report["transitions"]:
            for pointer in transition.values():
                pointer["source"] = "audit.jsonl"
        for finding in report["findings"]:
            finding["source"] = "audit.jsonl"
        return outcomes, events, report


def rehearse(*, fail_mock_gh=False):
    """Kembalikan hasil simulasi, termasuk argv mock dan baris audit."""
    (result,), events, report = _rehearse([_BRANCH], fail_mock_gh=fail_mock_gh)
    if result["status"] == "rejected":
        raise ValueError("Preflight dry-run fixture menolak amplop.")
    return {"schema": "ace.self-send-rehearsal.v1", "envelope": result["envelope"],
            "credential_marker": "fixture_only", "remote_is_bare": True,
            "mock_argv": result["mock_argv"], "mock_exit_code": result["mock_exit_code"],
            "log": events, "audit": report}


def rehearse_batch(count):
    if type(count) is not int or count < 2:
        raise ValueError("Batch memerlukan setidaknya dua amplop.")
    branches = ["main" if number == 2 else f"{_BRANCH}-{number}" for number in range(1, count + 1)]
    outcomes, events, report = _rehearse(branches)
    return {"schema": "ace.self-send-rehearsal-batch.v1", "envelopes": outcomes,
            "credential_marker": "fixture_only", "remote_is_bare": True,
            "log": events, "audit": report}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--fail-mock-gh", action="store_true")
    modes.add_argument("--batch", type=int, metavar="N")
    args = parser.parse_args(argv)
    try:
        result = (rehearse(fail_mock_gh=args.fail_mock_gh) if args.batch is None
                  else rehearse_batch(args.batch))
    except (OSError, ValueError, subprocess.SubprocessError):
        parser.exit(2, "Error: fixture rehearsal gagal disiapkan.\n")
    print(json.dumps(result, indent=2))
    if args.batch is not None:
        expected = ["sent", "rejected", *(["sent"] * (args.batch - 2))]
        return int([row["status"] for row in result["envelopes"]] != expected
                   or bool(result["audit"]["findings"] or result["audit"]["violation_count"]))
    return 1 if result["mock_exit_code"] or result["audit"]["violation_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
