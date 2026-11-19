"""E5 — tes kontrak transport bridge (relay spool <-> pump), offline penuh.

Mengunci bentuk pesan dan siklus hidup spool yang menjadi kontrak antara
`brain_bridge_relay` (sisi sandbox) dan `brain_bridge_pump` (sisi VM):
- berkas req = payload + "ts", bernama <uuid>.json di req/;
- berkas resp = {"status", "body"} diterbitkan atomik lewat .tmp -> rename;
- relay membersihkan req+resp sesudah membaca, dan membersihkan req saat
  timeout (mengembalikan None);
- execute() pump: routing /v1/budget & /v1/models, resolusi role
  (role -> model -> fallback "front"), 429 saat over-budget, bentuk
  chat/embeddings, dan 502 saat organ meledak.

Tidak ada proses live yang disentuh: spool diarahkan ke direktori
sementara, modul pump dimuat dari salinan di direktori sementara, dan
bridge pump dimock pada fungsi organ.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from ace_operational import brain_bridge_relay as relay

REPO_MODULES = Path(__file__).resolve().parent


def _load_pump(tmpdir: Path):
    """Muat brain_bridge_pump dari salinan sementara (HERE-nya ikut pindah,
    sehingga STATE/TMP bridge tidak menyentuh pohon repo)."""
    for name in ("brain_bridge.py", "brain_bridge_pump.py"):
        shutil.copy(REPO_MODULES / name, tmpdir / name)
    spec = importlib.util.spec_from_file_location(
        "brain_bridge_pump_e5", tmpdir / "brain_bridge_pump.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SpoolFetchContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        spool = Path(self.tmp.name) / "bridge-spool"
        self.req_dir = spool / "req"
        self.resp_dir = spool / "resp"
        patcher = mock.patch.multiple(
            relay, REQ=self.req_dir, RESP=self.resp_dir, TIMEOUT_S=5)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _fake_pump(self, responder):
        def run():
            deadline = time.time() + 5
            while time.time() < deadline:
                reqs = list(self.req_dir.glob("*.json")) if self.req_dir.exists() else []
                if reqs:
                    responder(reqs[0])
                    return
                time.sleep(0.05)
        t = threading.Thread(target=run, daemon=True)
        t.start()
        return t

    def test_round_trip_message_shape_and_cleanup(self):
        seen = {}

        def responder(req_path: Path):
            seen["payload"] = json.loads(req_path.read_text(encoding="utf-8"))
            call_id = req_path.stem
            tmp = self.resp_dir / f"{call_id}.json.tmp"
            tmp.write_text(json.dumps({"status": 200, "body": {"ok": True}}),
                           encoding="utf-8")
            tmp.rename(self.resp_dir / f"{call_id}.json")

        self._fake_pump(responder)
        doc = relay.spool_fetch({"path": "/v1/chat/completions",
                                 "request": {"role": "coder", "messages": []}})
        self.assertEqual(doc, {"status": 200, "body": {"ok": True}})
        self.assertEqual(seen["payload"]["path"], "/v1/chat/completions")
        self.assertEqual(seen["payload"]["request"]["role"], "coder")
        self.assertIsInstance(seen["payload"]["ts"], float)
        # Siklus hidup: req dan resp dibersihkan sesudah dibaca.
        self.assertEqual(list(self.req_dir.glob("*.json")), [])
        self.assertEqual(list(self.resp_dir.glob("*.json")), [])

    def test_tmp_response_is_not_consumed_before_atomic_rename(self):
        result = {}

        def responder(req_path: Path):
            call_id = req_path.stem
            (self.resp_dir / f"{call_id}.json.tmp").write_text(
                json.dumps({"status": 200, "body": {"late": True}}),
                encoding="utf-8")
            time.sleep(0.4)
            result["before_rename_returned"] = "doc" in result
            (self.resp_dir / f"{call_id}.json.tmp").rename(
                self.resp_dir / f"{call_id}.json")

        self._fake_pump(responder)
        doc = relay.spool_fetch({"path": "/v1/models", "request": {}})
        result["doc"] = doc
        self.assertEqual(doc["body"], {"late": True})

    def test_timeout_returns_none_and_removes_request(self):
        with mock.patch.object(relay, "TIMEOUT_S", 0.4):
            doc = relay.spool_fetch({"path": "/v1/chat/completions",
                                     "request": {}})
        self.assertIsNone(doc)
        self.assertEqual(list(self.req_dir.glob("*.json")), [])

    def test_spool_directories_created_on_demand(self):
        self.assertFalse(self.req_dir.exists())
        with mock.patch.object(relay, "TIMEOUT_S", 0.3):
            relay.spool_fetch({"path": "/v1/models", "request": {}})
        self.assertTrue(self.req_dir.is_dir())
        self.assertTrue(self.resp_dir.is_dir())


class RelayHandlerContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), relay.Handler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever,
                                      daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def _call(self, method, path, body=None):
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}",
            method=method,
            data=None if body is None else body.encode("utf-8"),
            headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            return err.code, json.loads(err.read().decode("utf-8"))

    def test_health_shape_is_local(self):
        status, body = self._call("GET", "/health")
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["side"], "sandbox-relay")

    def test_models_served_from_local_cache_without_spooling(self):
        with tempfile.TemporaryDirectory() as tmp:
            req_dir = Path(tmp) / "req"
            with mock.patch.multiple(relay, REQ=req_dir, RESP=Path(tmp) / "resp"):
                status, body = self._call("GET", "/v1/models")
            self.assertEqual(status, 200)
            ids = [m["id"] for m in body["data"]]
            self.assertIn("ace-front", ids)
            self.assertFalse(req_dir.exists() and list(req_dir.glob("*.json")))

    def test_post_budget_is_method_not_allowed(self):
        status, _ = self._call("POST", "/v1/budget", body="{}")
        self.assertEqual(status, 405)

    def test_post_bad_json_is_400(self):
        status, body = self._call("POST", "/v1/chat/completions",
                                  body="{bukan json")
        self.assertEqual(status, 400)
        self.assertEqual(body["error"], "bad json")

    def test_unknown_get_path_is_404(self):
        status, _ = self._call("GET", "/tidak-ada")
        self.assertEqual(status, 404)


class PumpExecuteContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pump = _load_pump(Path(self.tmp.name))
        self.bridge = self.pump.bridge
        self.bridge._log = lambda rec: None

    def test_budget_path_delegates_to_bridge_budget_response(self):
        with mock.patch.object(self.bridge, "budget_response",
                               return_value=(200, {"roles": {}})) as br:
            status, body = self.pump.execute("/v1/budget", {})
        br.assert_called_once_with()
        self.assertEqual((status, body), (200, {"roles": {}}))

    def test_models_path_lists_role_model_pairs(self):
        status, body = self.pump.execute("/v1/models", {})
        self.assertEqual(status, 200)
        ids = {m["id"] for m in body["data"]}
        for role, (provider, model) in self.bridge.ROLE_MAP.items():
            self.assertIn(f"{role}:{model}", ids)

    def test_unknown_role_falls_back_to_front_and_model_field_is_a_role(self):
        seen = {}

        def fake_check(role):
            seen["role"] = role
            return True, 1

        env = {"content": "halo", "finish_reason": "stop", "usage": {}}
        with mock.patch.object(self.bridge, "_budget_check", fake_check), \
                mock.patch.object(self.bridge, "serve_chat",
                                  return_value=(env, "groq", "m-x", False)):
            self.pump.execute("/v1/chat/completions", {"role": "tidak-ada"})
            self.assertEqual(seen["role"], "front")
            self.pump.execute("/v1/chat/completions", {"model": "judge"})
            self.assertEqual(seen["role"], "judge")

    def test_over_budget_returns_429_without_calling_organ(self):
        with mock.patch.object(self.bridge, "_budget_check",
                               return_value=(False, 200)), \
                mock.patch.object(self.bridge, "serve_chat",
                                  side_effect=AssertionError("tidak boleh dipanggil")):
            status, body = self.pump.execute(
                "/v1/chat/completions", {"role": "coder", "messages": []})
        self.assertEqual(status, 429)
        self.assertEqual(body["error"]["type"], "budget_exhausted")

    def test_chat_success_shape_and_brain_of_origin(self):
        env = {"content": "jawaban", "finish_reason": "stop",
               "usage": {"total_tokens": 3}}
        with mock.patch.object(self.bridge, "_budget_check",
                               return_value=(True, 7)), \
                mock.patch.object(self.bridge, "serve_chat",
                                  return_value=(env, "groq", "model-x", True)) as sc:
            status, body = self.pump.execute(
                "/v1/chat/completions",
                {"role": "coder",
                 "messages": [{"role": "user", "content": "halo"}],
                 "max_tokens": 42})
        self.assertEqual(status, 200)
        self.assertEqual(body["object"], "chat.completion")
        self.assertEqual(body["brain_of_origin"], "groq/model-x")
        self.assertEqual(body["choices"][0]["message"]["content"], "jawaban")
        self.assertEqual(sc.call_args.args[1], "halo")
        self.assertEqual(sc.call_args.args[2], 42)

    def test_organ_exception_becomes_502(self):
        with mock.patch.object(self.bridge, "_budget_check",
                               return_value=(True, 1)), \
                mock.patch.object(self.bridge, "serve_chat",
                                  side_effect=RuntimeError("organ jatuh")):
            status, body = self.pump.execute(
                "/v1/chat/completions", {"role": "front", "messages": []})
        self.assertEqual(status, 502)
        self.assertEqual(body["error"]["type"], "organ_unavailable")
        self.assertIn("organ jatuh", body["error"]["message"])

    def test_embeddings_uses_first_list_item_and_shapes_values(self):
        seen = {}

        def fake_embed(model, text):
            seen["text"] = text
            return {"values": [0.1, 0.2]}

        with mock.patch.object(self.bridge, "_budget_check",
                               return_value=(True, 2)), \
                mock.patch.object(self.bridge, "embed_helper", fake_embed):
            status, body = self.pump.execute(
                "/v1/embeddings",
                {"role": "embedding", "input": ["pertama", "kedua"]})
        self.assertEqual(status, 200)
        self.assertEqual(seen["text"], "pertama")
        self.assertEqual(body["data"][0]["embedding"], [0.1, 0.2])
        self.assertIn("brain_of_origin", body)


class CrossSideRoundTripTests(unittest.TestCase):
    """Relay spool_fetch -> pump.execute (bridge dimock) -> resp atomik."""

    def test_full_round_trip_through_spool_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            pump_side = tmp_path / "pumpside"
            pump_side.mkdir()
            pump = _load_pump(pump_side)
            spool = tmp_path / "bridge-spool"
            req_dir, resp_dir = spool / "req", spool / "resp"
            env = {"content": "dari pump", "finish_reason": "stop",
                   "usage": {}}
            with mock.patch.object(pump.bridge, "_budget_check",
                                   return_value=(True, 3)), \
                    mock.patch.object(pump.bridge, "_log", lambda rec: None), \
                    mock.patch.object(pump.bridge, "serve_chat",
                                      return_value=(env, "groq", "m-y", False)), \
                    mock.patch.multiple(relay, REQ=req_dir, RESP=resp_dir,
                                        TIMEOUT_S=5):
                def pump_loop():
                    deadline = time.time() + 5
                    while time.time() < deadline:
                        reqs = list(req_dir.glob("*.json")) if req_dir.exists() else []
                        if reqs:
                            payload = json.loads(
                                reqs[0].read_text(encoding="utf-8"))
                            status, body = pump.execute(payload["path"],
                                                         payload["request"])
                            tmp_file = resp_dir / f"{reqs[0].stem}.json.tmp"
                            tmp_file.write_text(json.dumps(
                                {"status": status, "body": body}),
                                encoding="utf-8")
                            tmp_file.rename(resp_dir / f"{reqs[0].stem}.json")
                            return
                        time.sleep(0.05)

                t = threading.Thread(target=pump_loop, daemon=True)
                t.start()
                doc = relay.spool_fetch(
                    {"path": "/v1/chat/completions",
                     "request": {"role": "coder",
                                 "messages": [{"role": "user",
                                               "content": "tes"}]}})
                t.join(timeout=5)
            self.assertEqual(doc["status"], 200)
            self.assertEqual(doc["body"]["choices"][0]["message"]["content"],
                             "dari pump")


if __name__ == "__main__":
    unittest.main()
