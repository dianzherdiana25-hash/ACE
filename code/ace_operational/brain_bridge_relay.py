#!/usr/bin/env python3
"""EVO 0009 bridge, sandbox side: a loopback HTTP surface with
the same OpenAI-compatible shape as the VM bridge. Brain
requests are spooled to files; the VM-side relay pump (which
initiates all connections - this host's sshd refuses remote
port forwarding and the VM accepts no inbound) executes them
through the vault connector helpers and spools the answers
back. Credentials never leave ila's VM.
"""
import json
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SPOOL = Path.home() / "bridge-spool"
REQ = SPOOL / "req"
RESP = SPOOL / "resp"
PORT = 18931
TIMEOUT_S = 240

# The engine's models_backend contract (measured against the live
# engine, EVO 0009 milestone 4): discovery reads /health expecting
# {"status": "ok"} and /v1/models under a 0.6 s timeout, so the
# model list is served locally from a cache - never spooled - and
# the health body carries the llama.cpp-style status field. The
# cache starts as the bridge's role-model list and refreshes in
# the background through the spool.
_STATIC_MODELS = {"object": "list", "data": [
    {"id": "front:gemini-3-flash-preview", "object": "model",
     "owned_by": "gemini"},
    {"id": "coder:qwen/qwen3.8-27b", "object": "model",
     "owned_by": "groq"},
    {"id": "validator:openai/gpt-oss-120b", "object": "model",
     "owned_by": "groq"},
    {"id": "judge:deepseek-ai/DeepSeek-V4-Flash", "object": "model",
     "owned_by": "gonka"},
    {"id": "ace-front", "object": "model", "owned_by": "ace-bridge"},
]}
_models_cache: dict = json.loads(json.dumps(_STATIC_MODELS))
_models_lock = threading.Lock()


def spool_fetch(payload):
    """One spool round trip; returns the {status, body} doc or
    None on timeout. Shared by the HTTP handler and the models
    cache refresher."""
    REQ.mkdir(parents=True, exist_ok=True)
    RESP.mkdir(parents=True, exist_ok=True)
    call_id = uuid.uuid4().hex
    (REQ / f"{call_id}.json").write_text(json.dumps(
        {**payload, "ts": time.time()}), encoding="utf-8")
    deadline = time.time() + TIMEOUT_S
    target = RESP / f"{call_id}.json"
    while time.time() < deadline:
        if target.exists():
            doc = json.loads(target.read_text(encoding="utf-8"))
            target.unlink(missing_ok=True)
            (REQ / f"{call_id}.json").unlink(missing_ok=True)
            return doc
        time.sleep(0.1)
    (REQ / f"{call_id}.json").unlink(missing_ok=True)
    return None


def _models_refresher() -> None:
    while True:
        doc = spool_fetch({"path": "/v1/models", "request": {}})
        if doc and doc.get("status") == 200 \
                and isinstance(doc.get("body"), dict) \
                and isinstance(doc["body"].get("data"), list):
            with _models_lock:
                _models_cache.update(doc["body"])
        time.sleep(300)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self._send(200, {"status": "ok", "ok": True,
                             "side": "sandbox-relay"})
        elif self.path == "/v1/models":
            with _models_lock:
                snapshot = json.loads(json.dumps(_models_cache))
            self._send(200, snapshot)
        else:
            self._send(404, {"error": "not found"})

    def _spool(self, payload):
        doc = spool_fetch(payload)
        if doc is None:
            return self._send(504, {
                "error": {"message": "brain bridge relay timeout",
                          "type": "organ_unavailable"}})
        return self._send(doc["status"], doc["body"])

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        try:
            req = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            return self._send(400, {"error": "bad json"})
        self._spool({"path": self.path, "request": req})


if __name__ == "__main__":
    threading.Thread(target=_models_refresher, daemon=True).start()
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"sandbox relay on 127.0.0.1:{PORT}", flush=True)
    server.serve_forever()
