"""Tes fixture governor anggaran harian jembatan per peran & pergantian hari UTC (AG2)."""

from __future__ import annotations

import json
from http.server import ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import time
import unittest
from unittest import mock
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from ace_operational import brain_bridge as bridge


class BridgeGovernorFixtureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.state = self.root / "state.json"
        self.log = self.root / "calls.jsonl"
        self.helpers = self.root / "helpers"
        self.fixture_budgets = dict.fromkeys(bridge.ROLE_MAP, 3)

        self.patchers = [
            mock.patch.object(bridge, "STATE", self.state),
            mock.patch.object(bridge, "LOG", self.log),
            mock.patch.object(bridge, "HELPERS", self.helpers),
            mock.patch.object(bridge, "BUDGETS", self.fixture_budgets),
            mock.patch.object(
                bridge,
                "call_helper",
                side_effect=lambda provider, model, prompt, max_tokens: {
                    "content": f"ok:{prompt}",
                    "finish_reason": "stop",
                },
            ),
        ]
        for p in self.patchers:
            p.start()
            self.addCleanup(p.stop)

    def _post_chat(self, url: str, role: str, prompt: str) -> tuple[int, dict]:
        data = json.dumps(
            {"role": role, "messages": [{"role": "user", "content": prompt}]}
        ).encode("utf-8")
        req = Request(
            f"{url}/v1/chat/completions",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        try:
            resp = urlopen(req, timeout=5)
        except HTTPError as exc:
            resp = exc
        with resp:
            return resp.code, json.load(resp)

    def test_daily_cap_3_enforced_and_rolls_over_at_utc_midnight(self) -> None:
        self.assertEqual(bridge.BUDGETS["front"], 3)
        utc_day1 = time.struct_time((2026, 11, 20, 23, 59, 59, 4, 324, 0))
        utc_day2 = time.struct_time((2026, 11, 21, 0, 0, 1, 5, 325, 0))

        current_gmtime = {"val": utc_day1}
        server = ThreadingHTTPServer(("127.0.0.1", 0), bridge.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.shutdown)
        self.addCleanup(server.server_close)
        url = f"http://127.0.0.1:{server.server_port}"

        real_gmtime = time.gmtime
        with mock.patch.object(
            bridge.time,
            "gmtime",
            side_effect=lambda *args: current_gmtime["val"] if not args else real_gmtime(*args),
        ), mock.patch.object(
            bridge.time, "localtime", return_value=utc_day1
        ):
            self.assertEqual(bridge._today(), "2026-11-20")

            # 3 panggilan dalam batas harian berhasil.
            for idx in range(1, 4):
                code, body = self._post_chat(url, "front", f"p{idx}")
                self.assertEqual(code, 200)
                self.assertEqual(body["choices"][0]["message"]["content"], f"ok:p{idx}")

            # Panggilan ke-4 melewati batas 3 -> 429 budget_exhausted.
            code4, err4 = self._post_chat(url, "front", "p4")
            self.assertEqual(code4, 429)
            self.assertEqual(err4["error"]["type"], "budget_exhausted")

            # Peran lain ("coder") masih memiliki kuota terpisah.
            code_coder, _ = self._post_chat(url, "coder", "c1")
            self.assertEqual(code_coder, 200)

            # Pergantian hari UTC -> walaupun localtime masih hari lama, _today() berganti & kuota pulih.
            current_gmtime["val"] = utc_day2
            self.assertEqual(bridge._today(), "2026-11-21")
            code_rollover, body_rollover = self._post_chat(url, "front", "after-utc")
            self.assertEqual(code_rollover, 200)
            self.assertEqual(body_rollover["choices"][0]["message"]["content"], "ok:after-utc")

        log_rows = [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()]
        over_entries = [r for r in log_rows if r.get("result") == "over_budget"]
        self.assertEqual(len(over_entries), 1)
        self.assertEqual(over_entries[0]["role"], "front")


if __name__ == "__main__":
    unittest.main()
