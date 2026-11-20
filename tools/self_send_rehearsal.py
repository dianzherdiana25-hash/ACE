#!/usr/bin/env python3
"""Latih amplop self-send dengan repo bare dan proses gh palsu di fixture."""

import argparse
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


def rehearse(*, fail_mock_gh=False):
    """Kembalikan hasil simulasi, termasuk argv mock dan baris audit."""
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

        # Hanya penanda sintetis. Proses mock mendapat env minimal tanpa token.
        envelope = check_envelope(_BRANCH, merge_authority=False, environ={"GH_TOKEN": None})
        if envelope["mode"] != "dry_run" or not envelope["passed"]:
            raise ValueError("Preflight dry-run fixture menolak amplop.")
        digest = hashlib.sha256(b"fixture payload").hexdigest()
        common = {"branch": _BRANCH, "trigger": "rehearsal", "content_digest": digest}
        events = [{**common, "ts": "2026-11-20T10:00:00Z", "outcome": "prepared"}]
        log = root / "audit.jsonl"
        with log.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(events[0]) + "\n")

        mock, args_file = root / "fixture_gh.py", root / "argv.json"
        mock.write_text(_MOCK_GH, encoding="utf-8")
        args = ["pr", "create", "--draft", "--head", _BRANCH, "--base", "main"]
        result = subprocess.run([sys.executable, "-I", str(mock), str(args_file),
                                 str(int(fail_mock_gh)), *args],
                                cwd=repo, env=env, capture_output=True, timeout=10)
        recorded = json.loads(args_file.read_bytes())
        if recorded != args:
            raise ValueError("Argv mock tidak cocok dengan fixture.")
        if result.returncode == 0:
            events.append({**common, "ts": "2026-11-20T10:01:00Z", "outcome": "sent"})
            with log.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(events[-1]) + "\n")
        report = audit(log)
        # Pointer tetap bisa dibandingkan dengan array log yang disertakan.
        for transition in report["transitions"]:
            for pointer in transition.values():
                pointer["source"] = "audit.jsonl"
        for finding in report["findings"]:
            finding["source"] = "audit.jsonl"
        return {"schema": "ace.self-send-rehearsal.v1", "envelope": envelope,
                "credential_marker": "fixture_only", "remote_is_bare": True,
                "mock_argv": recorded, "mock_exit_code": result.returncode,
                "log": events, "audit": report}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fail-mock-gh", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = rehearse(fail_mock_gh=args.fail_mock_gh)
    except (OSError, ValueError, subprocess.SubprocessError):
        parser.exit(2, "Error: fixture rehearsal gagal disiapkan.\n")
    print(json.dumps(result, indent=2))
    return 1 if result["mock_exit_code"] or result["audit"]["violation_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
