"""Tests for remote ACE CLI (`--remote` / `ACE_REMOTE_URL`) for Termux and client devices."""
from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ace_operational.store import OperationalStore
from ace_operational.web_server import ACEWebServer
from ace_runtime.cli import main


class RemoteCLITest(unittest.TestCase):
    def test_remote_status_chat_and_offline_guard(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
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


if __name__ == "__main__":
    unittest.main()
