"""Tes fixture untuk tools/relay_spool_tools.py (D8 — mandiri, tanpa relai hidup)."""
from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest

from tools import relay_spool_tools as rst


class RelaySpoolToolsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.spool = Path(self.tmp.name) / "spool"
        (self.spool / "req").mkdir(parents=True)
        (self.spool / "resp").mkdir(parents=True)

    def _write_req(self, name: str, data: object, *, raw: bytes | None = None) -> Path:
        p = self.spool / "req" / name
        if raw is not None:
            p.write_bytes(raw)
        else:
            p.write_text(json.dumps(data), encoding="utf-8")
        return p

    def _write_resp(self, name: str, data: object, *, raw: bytes | None = None) -> Path:
        p = self.spool / "resp" / name
        if raw is not None:
            p.write_bytes(raw)
        else:
            p.write_text(json.dumps(data), encoding="utf-8")
        return p

    def test_01_valid_req_resp_and_dir_pass(self) -> None:
        req = self._write_req("call_001.json", {"path": "/v1/chat/completions", "request": {"role": "front"}, "ts": 1700000000.5})
        resp = self._write_resp("call_001.json", {"status": 200, "body": {"choices": []}})

        r_req = rst.validate_spool_file(req)
        r_resp = rst.validate_spool_file(resp)
        r_dir = rst.validate_spool_dir(self.spool)
        self.assertTrue(r_req["valid"], r_req)
        self.assertTrue(r_resp["valid"], r_resp)
        self.assertTrue(r_dir["valid"], r_dir)
        self.assertEqual(r_dir["total_files"], 2)
        self.assertEqual(r_dir["valid_count"], 2)

    def test_02_truncated_corrupt_nonfinite_and_invalid_utf8_caught_with_reasons(self) -> None:
        cases = [
            ("empty.json", "req", b"", "empty_file"),
            ("trunc.json", "req", b'{"path": "/v1/budget", "req', "corrupt_or_truncated_json"),
            ("badutf8.json", "resp", b"\xff\xfe\xfd", "invalid_utf8"),
            ("nan.json", "req", b'{"path": "/v1/chat/completions", "request": {}, "ts": NaN}', "non_finite_json_number"),
            ("list.json", "resp", b"[1, 2, 3]", "non_object_root"),
        ]
        for fname, kind, payload, prefix in cases:
            with self.subTest(fname=fname):
                p = self.spool / kind / fname
                p.write_bytes(payload)
                res = rst.validate_spool_file(p)
                self.assertFalse(res["valid"])
                self.assertTrue(any(r.startswith(prefix) for r in res["reasons"]), res["reasons"])

    def test_03_missing_wrong_types_and_bad_ranges_rejected(self) -> None:
        bad_req = self._write_req("bad_req.json", {"path": "no-slash", "request": [], "ts": True})
        res_req = rst.validate_spool_file(bad_req)
        self.assertFalse(res_req["valid"])
        self.assertIn("invalid_field:path", res_req["reasons"])
        self.assertIn("invalid_type:request", res_req["reasons"])
        self.assertIn("invalid_field:ts", res_req["reasons"])

        bad_resp = self._write_resp("bad_resp.json", {"status": 999, "body": "text"})
        res_resp = rst.validate_spool_file(bad_resp)
        self.assertFalse(res_resp["valid"])
        self.assertIn("invalid_field:status", res_resp["reasons"])
        self.assertIn("invalid_type:body", res_resp["reasons"])

    def test_04_temp_artifact_and_symlink_caught_safely(self) -> None:
        (self.spool / "resp" / "partial.json.tmp").write_text('{"status": 200', encoding="utf-8")
        secret_outside = Path(self.tmp.name) / "outside.json"
        secret_outside.write_text('{"path": "/v1/budget", "request": {}, "ts": 1}', encoding="utf-8")
        sym = self.spool / "req" / "link.json"
        sym.symlink_to(secret_outside)

        res_dir = rst.validate_spool_dir(self.spool)
        self.assertFalse(res_dir["valid"])
        self.assertEqual(res_dir["invalid_count"], 2)
        all_reasons = [r for f in res_dir["files"] for r in f["reasons"]]
        self.assertIn("non_json_or_temp_artifact", all_reasons)
        self.assertIn("symlink_disallowed", all_reasons)

    def test_05_clean_defaults_to_dry_run_and_keeps_all_files(self) -> None:
        now = 2_000_000.0
        req_active = self._write_req("active.json", {"path": "/v1/chat/completions", "request": {}, "ts": now - 5})
        resp_active = self._write_resp("active.json", {"status": 200, "body": {}})
        os.utime(req_active, (now - 5, now - 5))
        os.utime(resp_active, (now - 5, now - 5))

        resp_orphan = self._write_resp("orphan_resp.json", {"status": 200, "body": {}})
        os.utime(resp_orphan, (now - 5, now - 5))

        req_old = self._write_req("stale_req.json", {"path": "/v1/budget", "request": {}, "ts": now - 500})
        os.utime(req_old, (now - 500, now - 500))

        tmp_file = self.spool / "resp" / "leftover.json.tmp"
        tmp_file.write_text("partial", encoding="utf-8")
        os.utime(tmp_file, (now - 5, now - 5))

        dry_report = rst.clean_orphan_spool(self.spool, max_age_seconds=120.0, now=now)
        self.assertTrue(dry_report["dry_run"])
        self.assertEqual(dry_report["active_count"], 2)
        self.assertEqual(dry_report["orphan_count"], 3)
        self.assertEqual(dry_report["deleted_count"], 0)
        self.assertCountEqual(
            dry_report["would_delete"],
            ["req/stale_req.json", "resp/orphan_resp.json", "resp/leftover.json.tmp"],
        )
        # Dry-run MUST NOT delete anything on disk.
        self.assertTrue(req_active.exists())
        self.assertTrue(resp_active.exists())
        self.assertTrue(resp_orphan.exists())
        self.assertTrue(req_old.exists())
        self.assertTrue(tmp_file.exists())

    def test_06_clean_with_execute_removes_only_orphans_preserving_active_pair(self) -> None:
        now = 2_000_000.0
        req_active = self._write_req("active.json", {"path": "/v1/chat/completions", "request": {}, "ts": now - 5})
        resp_active = self._write_resp("active.json", {"status": 200, "body": {}})
        os.utime(req_active, (now - 5, now - 5))
        os.utime(resp_active, (now - 5, now - 5))

        resp_orphan = self._write_resp("orphan_resp.json", {"status": 200, "body": {}})
        req_old = self._write_req("stale_req.json", {"path": "/v1/budget", "request": {}, "ts": now - 500})
        os.utime(resp_orphan, (now - 5, now - 5))
        os.utime(req_old, (now - 500, now - 500))

        exec_report = rst.clean_orphan_spool(self.spool, max_age_seconds=120.0, execute=True, now=now)
        self.assertFalse(exec_report["dry_run"])
        self.assertEqual(exec_report["deleted_count"], 2)
        self.assertCountEqual(exec_report["deleted"], ["req/stale_req.json", "resp/orphan_resp.json"])
        self.assertTrue(req_active.exists())
        self.assertTrue(resp_active.exists())
        self.assertFalse(resp_orphan.exists())
        self.assertFalse(req_old.exists())

    def test_07_cli_validate_clean_and_error_exit_codes(self) -> None:
        self._write_req("ok.json", {"path": "/v1/budget", "request": {}, "ts": 100})
        self._write_resp("orphan.json", {"status": 200, "body": {}})

        out_val = io.StringIO()
        with contextlib.redirect_stdout(out_val):
            rc_val = rst.main(["validate", "--spool-dir", str(self.spool)])
        self.assertEqual(rc_val, 0)
        self.assertTrue(json.loads(out_val.getvalue())["valid"])

        out_md = io.StringIO()
        with contextlib.redirect_stdout(out_md):
            rc_md = rst.main(["clean", "--spool-dir", str(self.spool), "--format", "md"])
        self.assertEqual(rc_md, 0)
        md_text = out_md.getvalue()
        self.assertIn("DRY-RUN", md_text)
        self.assertIn("resp/orphan.json", md_text)
        # Orphan resp still exists after CLI default dry-run.
        self.assertTrue((self.spool / "resp" / "orphan.json").exists())

        out_exec = io.StringIO()
        with contextlib.redirect_stdout(out_exec):
            rc_exec = rst.main(["clean", "--spool-dir", str(self.spool), "--execute"])
        self.assertEqual(rc_exec, 0)
        self.assertFalse((self.spool / "resp" / "orphan.json").exists())

        err_buf = io.StringIO()
        with contextlib.redirect_stderr(err_buf):
            rc_bad = rst.main(["clean", "--spool-dir", str(self.spool), "--max-age-seconds", "-5"])
        self.assertEqual(rc_bad, 2)


if __name__ == "__main__":
    unittest.main()
