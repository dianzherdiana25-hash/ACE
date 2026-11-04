import json
import os
import socket
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from .contract import canonical_json
from .development import run_fixture
from .isolation import WorkerError, _sandbox_python, _stage_solver, fit_isolated
from .public_bank import public_fixtures
from .split_audit import RuleBlock, audit_splits


class IsolationTests(unittest.TestCase):
    def test_host_canaries_are_unavailable_to_worker(self):
        with tempfile.TemporaryDirectory() as temp, socket.socket() as listener:
            private = Path(temp) / "sealed.json"
            private.write_text("EVALUATOR_CANARY")
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            port = listener.getsockname()[1]
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                pass
            script = """
import importlib.util
import os
import resource
import socket
import sys

sys.path.insert(0, "/solver")
assert importlib.util.find_spec("e13.baseline") is not None
assert importlib.util.find_spec("e13.public_bank") is None
assert importlib.util.find_spec("e13.evaluator") is None
assert importlib.util.find_spec("e13.split_audit") is None
assert "ACE_CANARY" not in os.environ
assert resource.getrlimit(resource.RLIMIT_CPU) == (1, 1)
assert resource.getrlimit(resource.RLIMIT_AS) == (134217728, 134217728)
try:
    open(sys.argv[1], "rb")
except FileNotFoundError:
    pass
else:
    raise AssertionError("private evaluator file visible")
with socket.socket() as client:
    client.settimeout(0.5)
    assert client.connect_ex(("127.0.0.1", int(sys.argv[2]))) != 0
print("canaries blocked")
"""
            solver = Path(temp) / "solver"
            solver.mkdir()
            _stage_solver(solver)
            with patch.dict(os.environ, {"ACE_CANARY": "secret"}):
                stdout, _ = _sandbox_python(["-c", script, str(private), str(port)], solver=solver)
            self.assertEqual(stdout, b"canaries blocked\n")

    def test_public_fixtures_in_isolation(self):
        for fixture in public_fixtures():
            with self.subTest(request=fixture.fit_request):
                outcome = run_fixture(fixture)
                self.assertEqual((outcome["correct"], outcome["total"]), (3, 3))
                metrics = outcome["worker"]
                self.assertTrue(0 < metrics["cpu_us"] <= 1_000_000)
                self.assertTrue(0 < metrics["wall_us"] <= 3_000_000)
                self.assertTrue(0 < metrics["rss_kib"] <= 128 * 1024)

    def test_opaque_id_and_private_label_do_not_change_fit(self):
        fixture = public_fixtures()[1]
        before = run_fixture(fixture)
        request = json.loads(fixture.fit_request)
        request["task_id"] = "0123456789abcdef" * 2
        canary = replace(fixture.probes[0], expected=73)
        after = run_fixture(replace(fixture, fit_request=canonical_json(request),
                                    probes=(canary, *fixture.probes[1:])))
        self.assertEqual(before["program_sha256"], after["program_sha256"])
        self.assertEqual(before["fit_steps"], after["fit_steps"])
        self.assertEqual(after["correct"], 2)

    def test_worker_timeout(self):
        with patch("e13.isolation._WALL_SECONDS", 0.5):
            with self.assertRaisesRegex(WorkerError, "wall limit"):
                _sandbox_python(["-c", "import time; time.sleep(5)"])

    def test_invalid_reply_fails_closed(self):
        raw = public_fixtures()[0].fit_request
        with patch("e13.isolation._sandbox_python", return_value=(b'{"extra":"invalid"}', 10)):
            with self.assertRaisesRegex(WorkerError, "invalid isolated fit result"):
                fit_isolated(raw)


class SplitAuditTests(unittest.TestCase):
    def setUp(self):
        self.suite = {"S": ([2, 4], [4, 2])}
        self.first = RuleBlock("S", "development", {"op": "rise"}, ([2, 3],),
                               lambda tokens: (int(tokens[0] < tokens[1]),))
        self.second = RuleBlock("S", "selection", {"op": "fall"}, ([3, 2],),
                                lambda tokens: (int(tokens[0] > tokens[1]),))

    def test_disjoint_blocks_and_same_split_repetitions(self):
        audit_splits([self.first, self.first, self.second], self.suite)

    def test_cross_split_duplicates(self):
        for field, reason in (("shape", "rule shape"), ("reference", "probe behavior"),
                              ("tasks", "task payload")):
            duplicate = replace(self.second, **{field: getattr(self.first, field)})
            with self.subTest(reason=reason), self.assertRaisesRegex(ValueError, reason):
                audit_splits([self.first, duplicate], self.suite)

    def test_missing_common_suite_or_tasks(self):
        with self.assertRaisesRegex(ValueError, "common probes and task payloads"):
            audit_splits([self.first], {})
        with self.assertRaisesRegex(ValueError, "common probes and task payloads"):
            audit_splits([replace(self.first, tasks=())], self.suite)
