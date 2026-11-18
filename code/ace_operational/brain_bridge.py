#!/usr/bin/env python3
"""EVO 0009 brain bridge (ila VM side).

Serves an OpenAI-compatible surface to ACE's engine, routing by
ROLE to the ratified API organ map (EVO 0009 design S2.2, hub
ratification 2026-11-18) and executing through the Secure Vault
connector helpers - credentials never leave this VM.

Transport shape: this VM accepts no inbound tailnet connections
(client-only enrolment), so the engine reaches this service
through a reverse tunnel that THIS side initiates and maintains
to the sandbox (ssh -R). The engine calls a loopback port on its
own host; requests travel the VM-initiated tunnel to here.

Governor (ratified initial budgets, calls/day): front 200,
coder 200, cross-validator 100, embedding 200, judge 20 - the
judge cap carries the measurement line's priority claim on the
Gonka balance. Over-budget returns a 429 error body; the
engine's fail-closed BrainUnavailable semantics take it from
there. Every call is logged with its brain-of-origin.
"""
import json
import subprocess
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).parent
STATE = HERE / "bridge_state.json"
LOG = HERE / "bridge_calls.jsonl"
HELPERS = Path.home() / "workspace" / "custom-connectors"
PORT = 8931

ROLE_MAP = {
    "front": ("gemini", "gemini-3-flash-preview"),
    "coder": ("groq", "qwen/qwen3.8-27b"),
    "validator": ("groq", "openai/gpt-oss-120b"),
    "judge": ("gonka", "deepseek-ai/DeepSeek-V4-Flash-0731"),
    "embedding": ("gemini", "gemini-embedding-001"),
}
BUDGETS = {"front": 200, "coder": 200, "validator": 100,
           "embedding": 200, "judge": 20}

_lock = threading.Lock()


def _today():
    return time.strftime("%Y-%m-%d", time.localtime())


def _budget_check(role):
    with _lock:
        state = {}
        if STATE.exists():
            state = json.loads(STATE.read_text())
        if state.get("day") != _today():
            state = {"day": _today(), "counts": {}}
        used = state["counts"].get(role, 0)
        if used >= BUDGETS[role]:
            return False, used
        state["counts"][role] = used + 1
        STATE.write_text(json.dumps(state))
        return True, used + 1


def _log(record):
    with _lock:
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def call_helper(provider, model, prompt, max_tokens):
    helper = (HELPERS / f"custom.{provider}" / "bin"
              / f"{provider}_call.py")
    if provider == "gemini":
        out = subprocess.run(
            ["python3", str(helper), "generate", model, prompt,
             str(max_tokens)], capture_output=True, text=True,
            timeout=600)
    else:
        with tempfile.NamedTemporaryFile(
                "w", suffix=".txt", delete=False,
                encoding="utf-8") as fh:
            fh.write(prompt)
            prompt_file = fh.name
        try:
            out = subprocess.run(
                ["python3", str(helper), "chatfile", model,
                 prompt_file, str(max_tokens)],
                capture_output=True, text=True, timeout=600)
        finally:
            Path(prompt_file).unlink(missing_ok=True)
    if out.returncode != 0:
        tail = (out.stderr.strip().splitlines() or ["?"])[-1]
        raise RuntimeError(f"{provider} helper failed: {tail}"[:300])
    return json.loads(out.stdout)


def embed_helper(model, text):
    helper = HELPERS / "custom.gemini" / "bin" / "gemini_call.py"
    out = subprocess.run(
        ["python3", str(helper), "embed", model, text],
        capture_output=True, text=True, timeout=300)
    if out.returncode != 0:
        tail = (out.stderr.strip().splitlines() or ["?"])[-1]
        raise RuntimeError(f"gemini embed failed: {tail}"[:300])
    return json.loads(out.stdout)


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
            self._send(200, {"ok": True,
                             "roles": sorted(ROLE_MAP),
                             "budgets": BUDGETS})
        elif self.path == "/v1/models":
            self._send(200, {"object": "list", "data": [
                {"id": f"{role}:{model}", "object": "model",
                 "owned_by": provider}
                for role, (provider, model) in ROLE_MAP.items()]})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        try:
            req = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            return self._send(400, {"error": "bad json"})
        role = req.get("role") or req.get("model")
        if role not in ROLE_MAP:
            # Role-less callers (the engine's models_backend names a
            # local model, not a bridge role) land on the front role.
            role = "front"
        ok, used = _budget_check(role)
        if not ok:
            _log({"ts": time.time(), "role": role,
                  "result": "over_budget"})
            return self._send(429, {
                "error": {"message":
                          f"daily budget exhausted for role {role}",
                          "type": "budget_exhausted"}})
        provider, model = ROLE_MAP[role]
        t0 = time.time()
        try:
            if self.path == "/v1/embeddings":
                text = req.get("input", "")
                if isinstance(text, list):
                    text = text[0] if text else ""
                env = embed_helper(model, text)
                _log({"ts": t0, "role": role,
                      "brain": f"{provider}/{model}",
                      "result": "ok", "used_today": used})
                return self._send(200, {
                    "object": "list",
                    "data": [{"object": "embedding", "index": 0,
                              "embedding": env["values"]}],
                    "model": model,
                    "brain_of_origin": f"{provider}/{model}"})
            messages = req.get("messages") or []
            prompt = "\n".join(
                m.get("content", "") for m in messages) \
                or req.get("prompt", "")
            max_tokens = int(req.get("max_tokens", 1024))
            env = call_helper(provider, model, prompt, max_tokens)
            _log({"ts": t0, "role": role,
                  "brain": f"{provider}/{model}", "result": "ok",
                  "used_today": used,
                  "wall_s": round(time.time() - t0, 2)})
            return self._send(200, {
                "id": f"bridge-{int(t0 * 1000)}",
                "object": "chat.completion",
                "model": model,
                "brain_of_origin": f"{provider}/{model}",
                "choices": [{
                    "index": 0,
                    "message": {"role": "assistant",
                                "content": env["content"]},
                    "finish_reason": env.get("finish_reason")}],
                "usage": env.get("usage", {})})
        except Exception as err:  # fail closed, logged
            _log({"ts": t0, "role": role,
                  "brain": f"{provider}/{model}",
                  "result": f"error: {err}"[:200]})
            return self._send(502, {
                "error": {"message": str(err)[:300],
                          "type": "organ_unavailable"}})


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"brain bridge on 127.0.0.1:{PORT}", flush=True)
    server.serve_forever()
