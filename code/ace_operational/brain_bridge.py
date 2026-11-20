#!/usr/bin/env python3
"""EVO 0009 brain bridge (ila VM side).

Serves an OpenAI-compatible surface to ACE's engine, routing by
ROLE to the ratified API organ map (EVO 0009 design S2.2, hub
ratification 2026-11-18) and executing through the Secure Vault
connector helpers - credentials never leave this VM.

Transport shape (as built; hub-ratified deviation from the
design's reverse tunnel, which proved infeasible: this VM is
Tailscale client-only and sandbox sshd refuses remote port
forwarding): a store-and-forward relay. A loopback relay on
the sandbox (brain_bridge_relay.py) serves the engine and
spools requests to files; a pump on this VM
(brain_bridge_pump.py) initiates ALL connections over the
ordinary ssh door, executes spooled requests through this
service, and spools the answers back. Credentials never
leave this VM.

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
    "front": ("groq", "openai/gpt-oss-120b"),
    "coder": ("groq", "qwen/qwen3.8-27b"),
    "validator": ("groq", "openai/gpt-oss-120b"),
    "judge": ("gonka", "deepseek-ai/DeepSeek-V4-Flash-0731"),
    "embedding": ("gemini", "gemini-embedding-001"),
}
# Rotation fallbacks (design S2.4; hub decision 2026-11-18 on
# the owner's "use another API" direction): front's primary
# moved to Groq gpt-oss-120b because the Gemini daily bucket
# starves the engine; the Gemini organ remains front's
# rotation fallback when its bucket breathes. A fallback is
# tried once, only on a primary organ failure, and the log
# records the organ that actually served.
FALLBACKS = {
    "front": ("gemini", "gemini-3-flash-preview"),
}
BUDGETS = {"front": 200, "coder": 200, "validator": 100,
           "embedding": 200, "judge": 20}

_lock = threading.Lock()
LAST_KEY = None
"""Which gemini bucket served the most recent gemini call
(custom.gemini / custom.gemini2 / custom.gemini3); quota accounting only."""


def _today():
    return time.strftime("%Y-%m-%d", time.gmtime())


def _write_log_unlocked(record):
    try:
        Path(LOG).parent.mkdir(parents=True, exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _is_valid_budget_state(state):
    if not isinstance(state, dict):
        return False
    day = state.get("day")
    counts = state.get("counts")
    if not isinstance(day, str) or not day.strip() or not isinstance(counts, dict):
        return False
    return all(isinstance(k, str) and type(v) is int and v >= 0 for k, v in counts.items())


def _budget_check(role):
    with _lock:
        today = _today()
        state = {"day": today, "counts": {}}
        if STATE.exists():
            corrupt_reason = None
            try:
                loaded = json.loads(STATE.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                corrupt_reason = "invalid_or_truncated_json"
                loaded = None
            else:
                if not _is_valid_budget_state(loaded):
                    corrupt_reason = "invalid_schema_or_negative_count"
            if corrupt_reason is not None:
                # Fail-closed (keputusan saringan Ian atas AG15, 2026-11-20):
                # state rusak TIDAK mereset jatah — perilaku reset AG15
                # membatalkan keputusan fail-closed 96f1fa8 dan membuka
                # pelipatgandaan anggaran lewat korupsi berulang. Yang
                # dipertahankan dari AG15: validator skema + catatan
                # peringatan di log. Berkas state dibiarkan apa adanya
                # untuk diperiksa operator.
                _write_log_unlocked({
                    "ts": time.time(),
                    "role": role,
                    "level": "warning",
                    "warning": "corrupt_budget_state_blocked",
                    "reason": corrupt_reason,
                    "result": "fail_closed_state_untouched",
                })
                return False, BUDGETS[role]
            elif loaded.get("day") == today:
                state = loaded
        used = state["counts"].get(role, 0)
        if used >= BUDGETS[role]:
            return False, used
        state["counts"][role] = used + 1
        STATE.write_text(json.dumps(state), encoding="utf-8")
        return True, used + 1


def budget_response():
    """Tampilkan saldo governor tanpa memakai jatah panggilan."""
    with _lock:
        try:
            state = json.loads(STATE.read_text(encoding="utf-8"))
        except FileNotFoundError:
            state = None
        except (OSError, ValueError):
            return _budget_unavailable()
        else:
            if (not isinstance(state, dict)
                    or not isinstance(state.get("day"), str)):
                return _budget_unavailable()
        initialized = state is not None and state["day"] == _today()
        counts = state.get("counts") if initialized else {}
        if not isinstance(counts, dict):
            return _budget_unavailable()
        roles = {}
        for role, limit in BUDGETS.items():
            used = counts.get(role, 0)
            if type(used) is not int or used < 0:
                return _budget_unavailable()
            roles[role] = {"daily_budget": limit, "used_today": used,
                           "remaining": max(0, limit - used)}
    return 200, {"initialized": initialized, "roles": roles}


def _budget_unavailable():
    return 503, {"error": {"message": "bridge budget state unavailable",
                           "type": "budget_state_unavailable"}}


def _log(record):
    with _lock:
        _write_log_unlocked(record)


def _is_quota(text):
    low = text.lower()
    return "429" in text or "resource_exhausted" in low \
        or "quota" in low


def call_helper(provider, model, prompt, max_tokens):
    helper = (HELPERS / f"custom.{provider}" / "bin"
              / f"{provider}_call.py")
    if provider == "gemini":
        # Two quota buckets, one organ (hub, 2026-11-18):
        # custom.gemini, custom.gemini2, custom.gemini3, failing over on
        # quota-class errors only. The module-level
        # LAST_KEY records which bucket served.
        global LAST_KEY
        last_err = None
        for key in ("gemini", "gemini2", "gemini3"):
            khelper = (HELPERS / f"custom.{key}" / "bin"
                       / f"{key}_call.py")
            out = subprocess.run(
                ["python3", str(khelper), "generate", model,
                 prompt, str(max_tokens)], capture_output=True,
                text=True, timeout=600)
            if out.returncode == 0:
                LAST_KEY = key
                return json.loads(out.stdout)
            tail = (out.stderr.strip().splitlines() or ["?"])[-1]
            last_err = RuntimeError(
                f"gemini helper ({key}) failed: {tail}"[:300])
            if not _is_quota(out.stderr):
                raise last_err
        raise last_err
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
    # Same two-bucket route as generate (embeddings draw on
    # their own metric, but the second key is headroom all
    # the same when the first is refused).
    global LAST_KEY
    last_err = None
    for key in ("gemini", "gemini2", "gemini3"):
        helper = (HELPERS / f"custom.{key}" / "bin"
                  / f"{key}_call.py")
        out = subprocess.run(
            ["python3", str(helper), "embed", model, text],
            capture_output=True, text=True, timeout=300)
        if out.returncode == 0:
            LAST_KEY = key
            return json.loads(out.stdout)
        tail = (out.stderr.strip().splitlines() or ["?"])[-1]
        last_err = RuntimeError(
            f"gemini embed ({key}) failed: {tail}"[:300])
        if not _is_quota(out.stderr):
            raise last_err
    raise last_err


def serve_chat(role, prompt, max_tokens):
    """Execute one chat call for a role, with the rotation
    fallback tried once on a primary organ failure. Returns
    (envelope, served_provider, served_model, fell_back).
    Raises RuntimeError naming both organs when all fail.
    Shared by the HTTP handler and the relay pump so every
    door serves the same rotation."""
    global LAST_KEY
    LAST_KEY = None
    provider, model = ROLE_MAP[role]
    try:
        env = call_helper(provider, model, prompt, max_tokens)
        return env, provider, model, False
    except Exception as primary_err:
        if role not in FALLBACKS:
            raise
        fb_provider, fb_model = FALLBACKS[role]
        try:
            env = call_helper(fb_provider, fb_model, prompt,
                              max_tokens)
        except Exception as fb_err:
            raise RuntimeError(
                f"primary {provider}/{model} failed "
                f"({primary_err}); fallback "
                f"{fb_provider}/{fb_model} failed "
                f"({fb_err})") from fb_err
        return env, fb_provider, fb_model, True


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
        elif self.path == "/v1/budget":
            self._send(*budget_response())
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path == "/v1/budget":
            return self._send(405, {"error": "method not allowed"})
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
            env, sp, sm, fell_back = serve_chat(
                role, prompt, max_tokens)
            served = (sp, sm)
            _log({"ts": t0, "role": role,
                  "brain": f"{served[0]}/{served[1]}",
                  "result": "ok", "used_today": used,
                  "key": LAST_KEY, "fallback": fell_back,
                  "wall_s": round(time.time() - t0, 2)})
            return self._send(200, {
                "id": f"bridge-{int(t0 * 1000)}",
                "object": "chat.completion",
                "model": served[1],
                "brain_of_origin": f"{served[0]}/{served[1]}",
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
