"""Tes fixture failover 3 kunci Gemini tanpa jaringan untuk brain_bridge (AG3).

Memverifikasi di modul logika jembatan (``code/ace_operational/brain_bridge.py``):
- galat kuota (429 / RESOURCE_EXHAUSTED) pada kunci 1 menyajikan dari kunci 2, lalu 3;
- galat non-kuota TIDAK memicu failover;
- setiap panggilan berhasil mencatat kunci penyaji (``key``) pada log JSONL fixture.
"""

from __future__ import annotations

from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import threading
import unittest
from unittest import mock
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from ace_operational import brain_bridge as bridge


def _key_from_cmd(cmd: list[str]) -> str:
    # .../custom.<key>/bin/<key>_call.py -> ekstrak <key>
    return Path(cmd[1]).stem.removesuffix("_call")


class GeminiKeyFailoverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.state = self.root / "state.json"
        self.log = self.root / "calls.jsonl"
        self.helpers = self.root / "helpers"
        self.budgets = dict.fromkeys(bridge.ROLE_MAP, 10)
        self.role_map = {**bridge.ROLE_MAP, "front": ("gemini", "gemini-3-flash-preview")}

        for p in (
            mock.patch.object(bridge, "STATE", self.state),
            mock.patch.object(bridge, "LOG", self.log),
            mock.patch.object(bridge, "HELPERS", self.helpers),
            mock.patch.object(bridge, "BUDGETS", self.budgets),
            mock.patch.object(bridge, "ROLE_MAP", self.role_map),
            mock.patch.object(bridge, "FALLBACKS", {}),
        ):
            p.start()
            self.addCleanup(p.stop)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), bridge.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.shutdown)
        self.addCleanup(self.server.server_close)
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

    def _post(self, path: str, payload: dict) -> tuple[int, dict]:
        req = Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            resp = urlopen(req, timeout=5)
        except HTTPError as exc:
            resp = exc
        with resp:
            return resp.code, json.load(resp)

    def test_quota_429_and_resource_exhausted_failover_key1_to_key2_then_key3_and_logs(self) -> None:
        attempted_chat: list[str] = []

        def fake_subprocess_chat(cmd, **_kwargs):
            key = _key_from_cmd(cmd)
            attempted_chat.append(key)
            if key == "gemini":
                return subprocess.CompletedProcess(
                    cmd, 1, "", "HTTP 429 Too Many Requests\n429 rate limited"
                )
            if key == "gemini2":
                return subprocess.CompletedProcess(
                    cmd, 0, json.dumps({"content": "dari-kunci-2", "finish_reason": "stop"}), ""
                )
            raise AssertionError(f"Kunci tak diharapkan: {key}")

        with mock.patch.object(bridge.subprocess, "run", side_effect=fake_subprocess_chat):
            code1, body1 = self._post(
                "/v1/chat/completions",
                {"role": "front", "messages": [{"role": "user", "content": "uji-1"}]},
            )
        self.assertEqual(code1, 200)
        self.assertEqual(body1["choices"][0]["message"]["content"], "dari-kunci-2")
        self.assertEqual(attempted_chat, ["gemini", "gemini2"])
        self.assertEqual(bridge.LAST_KEY, "gemini2")

        # Sekarang kunci 1 & 2 sama-sama RESOURCE_EXHAUSTED -> jatuh ke kunci 3.
        attempted_k3: list[str] = []

        def fake_subprocess_key3(cmd, **_kwargs):
            key = _key_from_cmd(cmd)
            attempted_k3.append(key)
            if key in {"gemini", "gemini2"}:
                return subprocess.CompletedProcess(
                    cmd, 1, "", "google.genai.errors.APIError: RESOURCE_EXHAUSTED"
                )
            return subprocess.CompletedProcess(
                cmd, 0, json.dumps({"content": "dari-kunci-3", "finish_reason": "stop"}), ""
            )

        with mock.patch.object(bridge.subprocess, "run", side_effect=fake_subprocess_key3):
            code2, body2 = self._post(
                "/v1/chat/completions",
                {"role": "front", "messages": [{"role": "user", "content": "uji-2"}]},
            )
        self.assertEqual(code2, 200)
        self.assertEqual(body2["choices"][0]["message"]["content"], "dari-kunci-3")
        self.assertEqual(attempted_k3, ["gemini", "gemini2", "gemini3"])

        # Jalur /v1/embeddings juga memfailover kunci 1 -> kunci 2 dan mencatat 'key' di log.
        attempted_emb: list[str] = []

        def fake_subprocess_emb(cmd, **_kwargs):
            key = _key_from_cmd(cmd)
            attempted_emb.append(key)
            if key == "gemini":
                return subprocess.CompletedProcess(cmd, 1, "", "RESOURCE_EXHAUSTED")
            return subprocess.CompletedProcess(
                cmd, 0, json.dumps({"values": [0.25, 0.75]}), ""
            )

        with mock.patch.object(bridge.subprocess, "run", side_effect=fake_subprocess_emb):
            code3, body3 = self._post(
                "/v1/embeddings", {"role": "embedding", "input": "vektor-uji"}
            )
        self.assertEqual(code3, 200)
        self.assertEqual(body3["data"][0]["embedding"], [0.25, 0.75])
        self.assertEqual(attempted_emb, ["gemini", "gemini2"])

        entries = [json.loads(ln) for ln in self.log.read_text(encoding="utf-8").splitlines()]
        self.assertEqual([e.get("key") for e in entries], ["gemini2", "gemini3", "gemini2"])

    def test_non_quota_error_does_not_fail_over_to_other_keys(self) -> None:
        attempted: list[str] = []

        def fake_subprocess_non_quota(cmd, **_kwargs):
            key = _key_from_cmd(cmd)
            attempted.append(key)
            return subprocess.CompletedProcess(
                cmd, 1, "", "HTTP 400 InvalidArgument: malformed schema payload"
            )

        with mock.patch.object(bridge.subprocess, "run", side_effect=fake_subprocess_non_quota):
            code_chat, err_chat = self._post(
                "/v1/chat/completions",
                {"role": "front", "messages": [{"role": "user", "content": "bad"}]},
            )
            self.assertEqual(code_chat, 502)
            self.assertEqual(err_chat["error"]["type"], "organ_unavailable")
            self.assertEqual(attempted, ["gemini"])

            attempted.clear()
            code_emb, err_emb = self._post(
                "/v1/embeddings", {"role": "embedding", "input": "bad"}
            )
            self.assertEqual(code_emb, 502)
            self.assertEqual(err_emb["error"]["type"], "organ_unavailable")
            self.assertEqual(attempted, ["gemini"])


if __name__ == "__main__":
    unittest.main()
