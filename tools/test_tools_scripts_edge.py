"""Uji kasus tepi untuk skrip utilitas non-verdict di tools/ (>=25 kasus):
verify_sources, ace_ai_diagnostic, dan ace_reasoning_audit.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools import ace_ai_diagnostic as aid
from tools import ace_reasoning_audit as ara
from tools import verify_sources as vs

REPO_ROOT = Path(__file__).resolve().parents[1]


def _git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def _write_upstream_manifest(root: Path, files: dict, schema: str = "ace.source-integration.v1") -> None:
    docs = root / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "UPSTREAM_SOURCES.json").write_text(
        json.dumps({"schema": schema, "files": files}),
        encoding="utf-8",
    )


def _valid_reasoning_artifact() -> dict:
    cells = []
    families = [
        "add",
        "subtract",
        "multiply",
        "double_sum",
        "square_shift",
        "equality",
        "less",
        "sum_equals_two",
    ]
    for i in range(24):
        fam = families[i % len(families)]
        rows = []
        for idx in range(48):
            env = {"x": idx - 10, "y": (idx * 3) - 20}
            rows.append({"inputs": env, "output": ara.truth(fam, env)})
        cells.append(
            {
                "family": fam,
                "train": rows[:12],
                "validation": rows[12:24],
                "terminal": rows[24:48],
                "A_internal": {"decision": {"status": "ABSTAIN", "program": None}, "terminal": {"predictions": [], "correct": 0, "abstained": 24}},
                "F_same_fresh_solver": {"decision": {"status": "ABSTAIN", "program": None}, "terminal": {"predictions": [], "correct": 0, "abstained": 24}},
                "B_SYNTHETIC_FIXTURE": {"decision": {"status": "ABSTAIN", "program": None}, "terminal": {"predictions": [], "correct": 0, "abstained": 24}},
            }
        )
    return {
        "cells": cells,
        "summary": {
            "A_correct": 0,
            "F_correct": 0,
            "B_fixture_correct": 0,
            "external_model_calls": 0,
            "scientific_status": "NOT_ASSESSED",
            "release_gate": "BLOCK_RELEASE",
        },
        "hidden_shift": {"false_admission": True, "terminal": {"correct": 0}},
    }


class VerifySourcesEdgeTests(unittest.TestCase):
    """Kasus tepi untuk tools/verify_sources.py."""

    def test_verify_real_repository_passes(self) -> None:
        self.assertGreater(vs.verify(REPO_ROOT), 0)

    def test_verify_valid_fixture_matches_git_blob_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = b"halo dunia\n"
            (root / "src").mkdir()
            (root / "src" / "a.txt").write_bytes(payload)
            _write_upstream_manifest(root, {"src/a.txt": {"git_blob": _git_blob_sha1(payload)}})
            self.assertEqual(vs.verify(root), 1)

    def test_verify_rejects_wrong_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.txt").write_bytes(b"x")
            _write_upstream_manifest(root, {"a.txt": {"git_blob": _git_blob_sha1(b"x")}}, schema="wrong.v0")
            with self.assertRaisesRegex(ValueError, "schema"):
                vs.verify(root)

    def test_verify_rejects_empty_or_list_files_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_upstream_manifest(root, {})
            with self.assertRaisesRegex(ValueError, "nonempty"):
                vs.verify(root)
            _write_upstream_manifest(root, ["a.txt"])  # type: ignore[arg-type]
            with self.assertRaisesRegex(ValueError, "nonempty"):
                vs.verify(root)

    def test_verify_rejects_path_traversal_absolute_and_empty_name(self) -> None:
        for bad_name in ("../escape.txt", "/etc/passwd", ""):
            with tempfile.TemporaryDirectory() as tmp, self.subTest(name=bad_name):
                root = Path(tmp)
                _write_upstream_manifest(root, {bad_name: {"git_blob": "a" * 40}})
                with self.assertRaisesRegex(ValueError, "invalid source path"):
                    vs.verify(root)

    def test_verify_rejects_symlink_escaping_repo_root(self) -> None:
        with tempfile.TemporaryDirectory() as outer, tempfile.TemporaryDirectory() as repo:
            outside_file = Path(outer) / "secret.txt"
            outside_file.write_bytes(b"rahasia")
            root = Path(repo)
            os.symlink(outside_file, root / "leak.txt")
            _write_upstream_manifest(root, {"leak.txt": {"git_blob": _git_blob_sha1(b"rahasia")}})
            with self.assertRaisesRegex(ValueError, "escapes repository"):
                vs.verify(root)

    def test_verify_rejects_bad_blob_id_format(self) -> None:
        for bad_blob in ("A" * 40, "1234", 123, None):
            with tempfile.TemporaryDirectory() as tmp, self.subTest(blob=bad_blob):
                root = Path(tmp)
                (root / "a.txt").write_bytes(b"ok")
                meta = {"git_blob": bad_blob} if bad_blob is not None else "raw"
                _write_upstream_manifest(root, {"a.txt": meta})
                with self.assertRaisesRegex(ValueError, "Git blob ID"):
                    vs.verify(root)

    def test_verify_detects_single_byte_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.txt").write_bytes(b"abcd")
            _write_upstream_manifest(root, {"a.txt": {"git_blob": _git_blob_sha1(b"abcX")}})
            with self.assertRaisesRegex(ValueError, "source mismatch"):
                vs.verify(root)

    def test_verify_raises_file_not_found_for_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_upstream_manifest(root, {"missing.txt": {"git_blob": "0" * 40}})
            with self.assertRaises(FileNotFoundError):
                vs.verify(root)


class AceAiDiagnosticEdgeTests(unittest.TestCase):
    """Kasus tepi untuk tools/ace_ai_diagnostic.py."""

    def test_limit_bounds_rejects_0_and_31(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "c.json"
            p.write_text("[]", encoding="utf-8")
            for bad_limit in (0, -1, 31):
                with self.subTest(limit=bad_limit), self.assertRaises(ValueError):
                    aid.audit_consultations(p, limit=bad_limit)

    def test_limit_bounds_accepts_1_and_30_and_slices_tail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "c.json"
            items = [{"hypothesis_id": f"h-{i}", "ai_answered": None} for i in range(35)]
            p.write_text(json.dumps(items), encoding="utf-8")
            res1 = aid.audit_consultations(p, limit=1)
            self.assertEqual(res1["records_scored"], 1)
            self.assertEqual(res1["records"][0]["hypothesis_id"], "h-34")
            res30 = aid.audit_consultations(p, limit=30)
            self.assertEqual(res30["records_scored"], 30)
            self.assertEqual(res30["records"][0]["hypothesis_id"], "h-5")

    def test_rejects_non_list_json_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "c.json"
            p.write_text('{"not": "a list"}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "JSON list"):
                aid.audit_consultations(p)

    def test_empty_consultation_list_keeps_block_release_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "c.json"
            p.write_text("[]", encoding="utf-8")
            res = aid.audit_consultations(p)
        self.assertEqual(res["records_scored"], 0)
        self.assertEqual(res["release_gate"], "BLOCK_RELEASE")
        self.assertFalse(res["candidate_deployed"])

    def test_malformed_non_dict_and_missing_source_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "c.json"
            p.write_text(json.dumps(["bad", 123, {"hypothesis_id": "h1"}]), encoding="utf-8")
            res = aid.audit_consultations(p)
        self.assertEqual(res["records"][0]["status"], "REJECTED_MALFORMED_RECORD")
        self.assertEqual(res["records"][1]["status"], "REJECTED_MALFORMED_RECORD")
        self.assertEqual(res["records"][2]["status"], "NO_CANDIDATE_SOURCE")
        self.assertIsNone(res["records"][2]["candidate_source_sha256"])

    def test_unsafe_python_rejected_without_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "c.json"
            marker = Path(tmp) / "pwned.txt"
            code = f"import os\nopen({str(marker)!r}, 'w').write('x')\n"
            p.write_text(json.dumps([{"hypothesis_id": "evil", "ai_answered": code}]), encoding="utf-8")
            res = aid.audit_consultations(p)
        self.assertEqual(res["records"][0]["status"], "UNSUPPORTED_STATIC_GRAMMAR")
        self.assertFalse(res["records"][0]["candidate_python_executed"])
        self.assertFalse(marker.exists())

    def test_public_diagnostic_and_duplicate_behavior_detection(self) -> None:
        src1 = "def ace_v04_cand_a(length, density, stride_val):\n    return int(density % 2 == 0)\n"
        src2 = "def ace_v04_cand_b(length, density, stride_val):\n    return 1 if (density % 2) == 0 else 0\n"
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "c.json"
            p.write_text(
                json.dumps(
                    [
                        {"hypothesis_id": "h-a", "ai_answered": src1},
                        {"hypothesis_id": "h-b", "ai_answered": src2},
                    ]
                ),
                encoding="utf-8",
            )
            res = aid.audit_consultations(p)
        self.assertEqual(res["records"][0]["status"], "PUBLIC_DIAGNOSTIC_ONLY")
        self.assertEqual(res["records"][1]["status"], "PUBLIC_DIAGNOSTIC_ONLY")
        self.assertEqual(res["records"][1].get("public_behavior_duplicate_of"), "h-a")

    def test_cli_missing_input_exits_2_and_valid_input_exits_0(self) -> None:
        script = REPO_ROOT / "tools" / "ace_ai_diagnostic.py"
        p_err = subprocess.run(
            [sys.executable, str(script), "--input", "/tmp/does_not_exist_ai.json"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(p_err.returncode, 2)
        self.assertEqual(json.loads(p_err.stderr)["status"], "ERROR")

        with tempfile.TemporaryDirectory() as tmp:
            inp = Path(tmp) / "c.json"
            inp.write_text("[]", encoding="utf-8")
            p_ok = subprocess.run(
                [sys.executable, str(script), "--input", str(inp)],
                capture_output=True,
                text=True,
            )
        self.assertEqual(p_ok.returncode, 0)
        self.assertEqual(json.loads(p_ok.stdout)["schema"], "ace.ask_ai.public_diagnostic.v1")


class AceReasoningAuditEdgeTests(unittest.TestCase):
    """Kasus tepi untuk tools/ace_reasoning_audit.py."""

    def test_same_distinguishes_bool_from_int(self) -> None:
        self.assertFalse(ara.same(True, 1))
        self.assertFalse(ara.same(False, 0))
        self.assertTrue(ara.same(True, True))
        self.assertTrue(ara.same(0, 0))

    def test_interpret_nested_ops_and_comparisons(self) -> None:
        tree = {
            "op": "lt",
            "args": [
                {"op": "add", "args": [{"var": "x"}, {"const": 2}]},
                {"op": "mul", "args": [{"var": "y"}, {"op": "sub", "args": [{"const": 5}, {"const": 2}]}]},
            ],
        }
        self.assertIs(ara.interpret(tree, {"x": 4, "y": 3}), True)
        self.assertIs(ara.interpret({"op": "eq", "args": [{"var": "x"}, {"var": "y"}]}, {"x": -2, "y": -2}), True)

    def test_interpret_rejects_unknown_op_or_missing_var(self) -> None:
        with self.assertRaises(KeyError):
            ara.interpret({"op": "div", "args": [{"const": 1}, {"const": 1}]}, {})
        with self.assertRaises(KeyError):
            ara.interpret({"var": "z"}, {"x": 1, "y": 2})

    def test_truth_covers_all_eight_families_with_negatives(self) -> None:
        env = {"x": -3, "y": 5}
        self.assertEqual(ara.truth("add", env), 2)
        self.assertEqual(ara.truth("subtract", env), -8)
        self.assertEqual(ara.truth("multiply", env), -15)
        self.assertEqual(ara.truth("double_sum", env), 4)
        self.assertEqual(ara.truth("square_shift", env), 14)
        self.assertIs(ara.truth("equality", {"x": 4, "y": 4}), True)
        self.assertIs(ara.truth("less", env), True)
        self.assertIs(ara.truth("sum_equals_two", env), True)

    def test_truth_unknown_family_raises_key_error(self) -> None:
        with self.assertRaises(KeyError):
            ara.truth("modulo", {"x": 1, "y": 2})

    def test_audit_passes_on_valid_24_cell_synthetic_artifact(self) -> None:
        artifact = _valid_reasoning_artifact()
        out = ara.audit(artifact)
        self.assertEqual(out["status"], "REFERENCE_REPLAY_PASS_PUBLIC_ONLY")
        self.assertEqual(out["score_cells"], 72)
        self.assertFalse(out["independent_scientific_validation"])

    def test_audit_rejects_duplicate_input_keys_across_splits(self) -> None:
        artifact = _valid_reasoning_artifact()
        artifact["cells"][0]["validation"][0]["inputs"] = dict(artifact["cells"][0]["train"][0]["inputs"])
        with self.assertRaises(AssertionError):
            ara.audit(artifact)

    def test_audit_rejects_nonzero_external_calls_or_missing_false_admission(self) -> None:
        artifact = _valid_reasoning_artifact()
        artifact["summary"]["external_model_calls"] = 1
        with self.assertRaises(AssertionError):
            ara.audit(artifact)

        artifact2 = _valid_reasoning_artifact()
        artifact2["hidden_shift"]["false_admission"] = False
        with self.assertRaises(AssertionError):
            ara.audit(artifact2)

    def test_audit_rejects_incorrect_cell_count(self) -> None:
        artifact = _valid_reasoning_artifact()
        artifact["cells"].pop()
        with self.assertRaises(AssertionError):
            ara.audit(artifact)

    def test_audit_executes_non_null_program_and_verifies_terminal_score(self) -> None:
        artifact = _valid_reasoning_artifact()
        # Sel indeks 0 adalah family "add".
        cell0 = artifact["cells"][0]
        prog = {"op": "add", "args": [{"var": "x"}, {"var": "y"}]}
        preds = [ara.interpret(prog, r["inputs"]) for r in cell0["terminal"]]
        cell0["A_internal"] = {
            "decision": {"status": "STAGED_EMPIRICAL", "program": prog},
            "terminal": {"predictions": preds, "correct": 24, "abstained": 0},
        }
        artifact["summary"]["A_correct"] = 24
        out = ara.audit(artifact)
        self.assertEqual(out["correct_by_arm"]["A_internal"], 24)


if __name__ == "__main__":
    unittest.main()
