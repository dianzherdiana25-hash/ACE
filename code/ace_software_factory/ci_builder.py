"""Hasilkan workflow pengujian produk yang dapat ditelaah sebelum diaktifkan.

Sumber pin checkout dan direktori suite wajib ada dalam kontrak. Workflow
memakai akses contents baca saja dan mematikan persistence kredensial.
Template hanya menguji Python lokal yang tersedia pada runner.
"""
import argparse
import json
from hashlib import sha256
from pathlib import Path
import re
import sys

from ._artifact_io import read_relative
from ._contracts import ContractError, canonical, checked, decode, digest, entries, identifier, integer, obj, read, schema, text
from .repo_scaffolder import _relative, materialize


BRANCH = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_-]*(?:/[a-zA-Z0-9][a-zA-Z0-9_-]*)*")
TEST_PATH = re.compile(r"[a-zA-Z0-9_-]+(?:/[a-zA-Z0-9_-]+)*/test_[a-zA-Z0-9_]+\.py")
ACTION_COMMIT = re.compile(r"[0-9a-f]{40}")
RUNNERS = {"ubuntu-24.04", "ubuntu-22.04"}
FILE_MAX = 200_000


def _suite_config(root, raw):
    obj(raw, ("id", "tests", "files", "timeout_minutes"))
    key = identifier(raw["id"], "ID suite")
    timeout = integer(raw["timeout_minutes"], "Menit maksimum", 1, 30)
    collection = text(raw["tests"], "Direktori tes", 160)
    _relative(collection)
    paths = set()
    observed = []
    for entry in entries(raw["files"], 120, minimum=1):
        obj(entry, ("path", "sha256"))
        path = text(entry["path"], "Berkas tes", 200)
        if path in paths or not TEST_PATH.fullmatch(path) or path.rpartition("/")[0] != collection:
            raise ContractError("Berkas tes ganda atau berada di luar direktori suite.")
        paths.add(path)
        anchor = digest(entry["sha256"])
        size = len(read_relative(root, path, FILE_MAX, anchor))
        observed.append({"path": path, "sha256": anchor, "bytes": size})
    return key, timeout, collection, sorted(observed, key=lambda row: row["path"])


def build(root, plan, expected):
    checked(plan, expected)
    schema(plan, "ace.factory-ci-plan.v1", ("id", "checkout_commit", "checkout_ref", "runner", "branches", "suites"))
    workflow = identifier(plan["id"], "ID workflow")
    checkout = plan["checkout_commit"]
    if not isinstance(checkout, str) or not ACTION_COMMIT.fullmatch(checkout) or set(checkout) == {"0"}:
        raise ContractError("Checkout action harus di-pin ke commit penuh.")
    ref = text(plan["checkout_ref"], "Rujukan pin checkout")
    runner = plan["runner"]
    if not isinstance(runner, str) or runner not in RUNNERS:
        raise ContractError("Runner belum terdaftar.")
    branches = []
    for name in entries(plan["branches"], 30, minimum=1):
        if not isinstance(name, str) or len(name) > 100 or not BRANCH.fullmatch(name) or name in branches:
            raise ContractError("Branch CI tidak sah atau ganda.")
        branches.append(name)
    lines = [f"name: {workflow}", "on:", "  pull_request:", f"    branches: {json.dumps(sorted(branches))}",
             "permissions:", "  contents: read", "jobs:"]
    suites = {}
    covered = set()
    for raw in entries(plan["suites"], 20, minimum=1):
        key, timeout, collection, observed = _suite_config(root, raw)
        if key in suites or collection in covered:
            raise ContractError("Suite CI ganda.")
        covered.add(collection)
        suites[key] = timeout, collection, observed
    report_suites = []
    for key, (timeout, collection, observed) in sorted(suites.items()):
        lines.extend([f"  {key}:", f"    runs-on: {runner}", f"    timeout-minutes: {timeout}",
                      "    steps:", f"      - uses: actions/checkout@{checkout}",
                      "        with:", "          persist-credentials: false",
                      "      - name: Run unit tests",
                      f"        run: python3 -m unittest discover -s {collection} -v"])
        report_suites.append({"id": key, "directory": collection, "timeout_minutes": timeout, "files": observed})
    payload = ("\n".join(lines) + "\n").encode()
    path = f".github/workflows/{workflow}.yml"
    report = {"schema": "ace.factory-ci-report.v1", "plan_sha256": expected, "checkout_ref": ref,
              "workflow": path, "workflow_sha256": sha256(payload).hexdigest(),
              "suites": report_suites, "status": "generated"}
    return {path: payload, "ci_report.json": canonical(report) + b"\n"}, report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        files, report = build(args.root, decode(read(args.plan)), args.expect_sha256)
        materialize(args.output, files)
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
