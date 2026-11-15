"""WEB25 — loopback token gate tests for the Web Studio REST API.

Every `/api/*` route (memory list/recall/forget/audit, chat, status, speech,
…) must reject requests without the local token and serve requests carrying
it, while the static UI shell (`/`) stays open. The token follows the
local-credential-file pattern: env `ACE_WEB_TOKEN` first, else
`<workspace>/.ace-web-auth.json` (auto-generated with mode 0600 and reused
across restarts).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest import mock
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from ace_operational.store import OperationalStore
from ace_operational.web_server import ACEWebServer, WEB_AUTH_FILENAME


def _http_json(url: str, *, method: str = "GET", payload: dict | None = None, token: str | None = None) -> tuple[int, dict]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"} if payload is not None else {}
    if token:
        headers["X-ACE-Token"] = token
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=10) as resp:
            return int(resp.status), json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        raw = exc.read().decode("utf-8")
        try:
            return int(exc.code), json.loads(raw)
        except ValueError:
            return int(exc.code), {"raw": raw}


class WebServerAuthTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ace-web-auth-")
        self.addCleanup(self.tmp.cleanup)
        self.ws = Path(self.tmp.name) / "workspace"
        self.store = OperationalStore(self.ws)
        self.server = ACEWebServer(self.store, host="127.0.0.1", port=0)
        self.url = self.server.start_background()
        self.addCleanup(self.server.stop)
        self.tok = self.server.auth_token

    def tearDown(self):
        self.store.close()

    def test_memory_endpoints_reject_without_token(self):
        st, _ = _http_json(f"{self.url}/api/memory")
        self.assertEqual(st, 401)
        st, _ = _http_json(f"{self.url}/api/memory?include_private=1")
        self.assertEqual(st, 401)
        st, _ = _http_json(f"{self.url}/api/memory/audit")
        self.assertEqual(st, 401)
        st, _ = _http_json(f"{self.url}/api/memory", method="POST", payload={"text": "fakta"})
        self.assertEqual(st, 401)
        st, _ = _http_json(f"{self.url}/api/memory/recall", method="POST", payload={"query": "fakta"})
        self.assertEqual(st, 401)
        st, _ = _http_json(f"{self.url}/api/memory/forget", method="POST", payload={"record_id": "mem_x"})
        self.assertEqual(st, 401)

    def test_memory_endpoints_reject_wrong_token(self):
        st, _ = _http_json(f"{self.url}/api/memory", token="token-salah")
        self.assertEqual(st, 401)
        st, _ = _http_json(f"{self.url}/api/memory/forget", method="POST", payload={"record_id": "mem_x"}, token="token-salah")
        self.assertEqual(st, 401)

    def test_memory_endpoints_accept_with_token(self):
        st, d = _http_json(f"{self.url}/api/memory", method="POST", payload={"text": "Kota favoritku adalah Yogyakarta"}, token=self.tok)
        self.assertEqual(st, 200)
        self.assertTrue(d["stored"])
        rec_id = d["record_id"]

        st, snap = _http_json(f"{self.url}/api/memory", token=self.tok)
        self.assertEqual(st, 200)
        self.assertEqual(len(snap["active_records"]), 1)

        st, rec = _http_json(f"{self.url}/api/memory/recall", method="POST", payload={"query": "Yogyakarta"}, token=self.tok)
        self.assertEqual(st, 200)
        self.assertEqual(rec["returned"], 1)

        st, aud = _http_json(f"{self.url}/api/memory/audit", token=self.tok)
        self.assertEqual(st, 200)
        self.assertTrue(aud["chain_ok"])

        st, d_f = _http_json(f"{self.url}/api/memory/forget", method="POST", payload={"record_id": rec_id}, token=self.tok)
        self.assertEqual(st, 200)
        self.assertEqual(d_f["tombstone"]["record_id"], rec_id)

    def test_private_record_not_leaked_without_token(self):
        st, d = _http_json(
            f"{self.url}/api/memory",
            method="POST",
            payload={"text": "Kode pintu rahasia 7788", "sensitivity": "private"},
            token=self.tok,
        )
        self.assertEqual(st, 200)
        st, body = _http_json(f"{self.url}/api/memory?include_private=1")
        self.assertEqual(st, 401)
        self.assertNotIn("7788", json.dumps(body))

    def test_ui_shell_open_but_api_gated(self):
        with urlopen(f"{self.url}/", timeout=10) as resp:
            self.assertEqual(resp.status, 200)
        st, _ = _http_json(f"{self.url}/api/status")
        self.assertEqual(st, 401)
        st, _ = _http_json(f"{self.url}/api/speech")
        self.assertEqual(st, 401)
        st, _ = _http_json(f"{self.url}/api/chat", method="POST", payload={"text": "halo"}, token="token-salah")
        self.assertEqual(st, 401)
        st, d = _http_json(f"{self.url}/api/status", token=self.tok)
        self.assertEqual(st, 200)
        self.assertEqual(d["status"], "ok")

    def test_token_file_created_0600_and_reused(self):
        auth_file = self.ws / WEB_AUTH_FILENAME
        self.assertTrue(auth_file.is_file())
        data = json.loads(auth_file.read_text(encoding="utf-8"))
        self.assertEqual(data["token"], self.tok)
        if os.name == "posix":
            self.assertEqual(stat.S_IMODE(auth_file.stat().st_mode), 0o600)
        # A second server over the same workspace reuses the persisted token.
        server2 = ACEWebServer(self.store, host="127.0.0.1", port=0)
        self.addCleanup(server2.stop)
        self.assertEqual(server2.auth_token, self.tok)

    def test_env_token_takes_precedence_and_skips_file(self):
        ws2 = Path(self.tmp.name) / "workspace-env"
        store2 = OperationalStore(ws2)
        self.addCleanup(store2.close)
        with mock.patch.dict(os.environ, {"ACE_WEB_TOKEN": "token-uji-env"}):
            server3 = ACEWebServer(store2, host="127.0.0.1", port=0)
        self.addCleanup(server3.stop)
        self.assertEqual(server3.auth_token, "token-uji-env")
        self.assertFalse((ws2 / WEB_AUTH_FILENAME).exists())
        url3 = server3.start_background()
        st, _ = _http_json(f"{url3}/api/memory", token="token-uji-env")
        self.assertEqual(st, 200)
        st, _ = _http_json(f"{url3}/api/memory", token="token-lain")
        self.assertEqual(st, 401)


if __name__ == "__main__":
    unittest.main()
