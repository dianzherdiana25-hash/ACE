"""Tests for remote ACE CLI (`--remote` / `ACE_REMOTE_URL`) for Termux and client devices."""
from __future__ import annotations

import contextlib
import io
import json
import os
import socket
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from urllib.error import URLError

from ace_operational.store import OperationalStore
from ace_operational.web_server import ACEWebServer
from ace_runtime.cli import _remote_json, main


class _FakeHTTPResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "_FakeHTTPResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class RemoteCLITest(unittest.TestCase):
    def test_remote_status_chat_and_offline_guard(self) -> None:
        # WEB25: the server gates /api/* behind X-ACE-Token. The fixture
        # provides the credential explicitly via ACE_WEB_TOKEN, which both
        # the server (resolve_web_auth_token) and the remote CLI honor.
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(
            os.environ, {"ACE_WEB_TOKEN": "test-token-remote-cli"}
        ):
            ws = Path(tmp) / "ws"
            with OperationalStore(ws) as store:
                server = ACEWebServer(store, host="127.0.0.1", port=0)
                url = server.start_background()
                try:
                    # 1. Remote status
                    buf = io.StringIO()
                    with contextlib.redirect_stdout(buf):
                        rc = main(["status", "--remote", url])
                    self.assertEqual(rc, 0)
                    status_data = json.loads(buf.getvalue())
                    self.assertIn("avatar_state", status_data)

                    # 2. Remote chat via ACE_REMOTE_URL env var
                    buf2 = io.StringIO()
                    with mock.patch.dict(os.environ, {"ACE_REMOTE_URL": url}):
                        with contextlib.redirect_stdout(buf2):
                            rc2 = main(["chat", "--once", "halo ace"])
                    self.assertEqual(rc2, 0)
                    chat_data = json.loads(buf2.getvalue())
                    self.assertTrue(chat_data["reply"])
                    self.assertEqual(chat_data["remote"], url)

                    # 3. Offline flag must block remote egress
                    err = io.StringIO()
                    with contextlib.redirect_stderr(err):
                        rc3 = main(["chat", "--once", "halo", "--remote", url, "--offline"])
                    self.assertEqual(rc3, 2)
                    self.assertIn("offline", err.getvalue().lower())
                finally:
                    server.stop()

    def test_mocked_status_chat_with_client_id_and_do(self) -> None:
        captured: list[tuple[str, dict | None, float]] = []

        def fake_urlopen(req, timeout=0.0):
            body = json.loads(req.data.decode("utf-8")) if req.data else None
            captured.append((req.full_url, body, timeout))
            if req.full_url.endswith("/api/status"):
                return _FakeHTTPResponse(json.dumps({"avatar_state": "idle", "ok": True}).encode("utf-8"))
            return _FakeHTTPResponse(
                json.dumps(
                    {
                        "reply": "siap dikerjakan",
                        "duplicate": False,
                        "task": {"task_id": "t-42", "status": "queued"},
                        "intent_frame": {"intent": "engineering_task"},
                    }
                ).encode("utf-8")
            )

        with mock.patch("ace_runtime.cli.urlopen", side_effect=fake_urlopen):
            buf_status = io.StringIO()
            with contextlib.redirect_stdout(buf_status):
                rc_s = main(["status", "--remote", "http://127.0.0.1:8080"])
            self.assertEqual(rc_s, 0)
            self.assertEqual(json.loads(buf_status.getvalue())["avatar_state"], "idle")

            buf_chat = io.StringIO()
            with contextlib.redirect_stdout(buf_chat):
                rc_c = main(["chat", "--once", "cek status", "--client-id", "cid-1", "--remote", "http://127.0.0.1:8080"])
            self.assertEqual(rc_c, 0)
            chat_out = json.loads(buf_chat.getvalue())
            self.assertEqual(chat_out["reply"], "siap dikerjakan")
            self.assertEqual(chat_out["task_id"], "t-42")
            self.assertEqual(chat_out["intent"], "engineering_task")

            buf_do = io.StringIO()
            with contextlib.redirect_stdout(buf_do):
                rc_d = main(["do", "periksa", "modul", "--remote", "https://ace.example:8443/prefix"])
            self.assertEqual(rc_d, 0)
            do_out = json.loads(buf_do.getvalue())
            self.assertEqual(do_out["task_status"], "queued")
            self.assertEqual(do_out["remote"], "https://ace.example:8443/prefix")

        self.assertEqual(captured[0][0], "http://127.0.0.1:8080/api/status")
        self.assertEqual(captured[0][2], 15.0)
        self.assertEqual(captured[1][1], {"text": "cek status", "client_message_id": "cid-1"})
        self.assertEqual(captured[2][0], "https://ace.example:8443/api/chat")
        self.assertEqual(captured[2][1], {"text": "periksa modul"})

    def test_remote_error_paths_unreachable_malformed_timeout_and_bad_url(self) -> None:
        # 1. Invalid URL scheme / netloc
        for bad_url in ("ftp://127.0.0.1:8080", "not-a-url"):
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                rc = main(["status", "--remote", bad_url])
            self.assertEqual(rc, 2)
            self.assertIn("URL remote tidak valid", err.getvalue())

        # 2. Server unreachable (URLError)
        with mock.patch("ace_runtime.cli.urlopen", side_effect=URLError("connection refused")):
            err_unreach = io.StringIO()
            with contextlib.redirect_stderr(err_unreach):
                rc_unreach = main(["status", "--remote", "http://127.0.0.1:59999"])
            self.assertEqual(rc_unreach, 2)
            self.assertIn("connection refused", err_unreach.getvalue())

        # 3. Malformed / non-JSON response
        with mock.patch("ace_runtime.cli.urlopen", return_value=_FakeHTTPResponse(b"<html>502 Bad Gateway</html>")):
            err_bad_json = io.StringIO()
            with contextlib.redirect_stderr(err_bad_json):
                rc_bad_json = main(["chat", "--once", "halo", "--remote", "http://127.0.0.1:8080"])
            self.assertEqual(rc_bad_json, 2)
            self.assertTrue(err_bad_json.getvalue().strip())

        # 4. Timeout
        with mock.patch("ace_runtime.cli.urlopen", side_effect=socket.timeout("timed out")):
            err_to = io.StringIO()
            with contextlib.redirect_stderr(err_to):
                rc_to = main(["do", "jalankan", "uji", "--remote", "http://127.0.0.1:8080"])
            self.assertEqual(rc_to, 2)
            self.assertIn("timed out", err_to.getvalue().lower())

        # 5. _remote_json rejects unsupported scheme directly
        with self.assertRaises(ValueError):
            _remote_json("file:///etc/passwd", "/api/status")


if __name__ == "__main__":
    unittest.main()
