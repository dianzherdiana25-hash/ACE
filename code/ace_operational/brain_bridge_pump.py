#!/usr/bin/env python3
"""EVO 0009 relay pump (ila VM side): polls the sandbox spool
over the ordinary ssh/scp door, executes pending brain
requests through bridge.py's routing + governor, and returns
answers by scp. All connections are initiated from this VM:
the sandbox sshd refuses remote port forwarding and this VM
accepts no inbound connections, so the organ path is a
store-and-forward relay. Credentials never leave this VM.
"""
import base64
import importlib.util
import json
import os
import subprocess
import time

HERE = os.path.dirname(os.path.abspath(__file__))
_bridge_file = os.path.join(HERE, "brain_bridge.py")
if not os.path.exists(_bridge_file):
    _bridge_file = os.path.join(HERE, "bridge.py")
spec = importlib.util.spec_from_file_location("bridge", _bridge_file)
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)

REMOTE = "sshremote@ace-sandbox.taild2ddcb.ts.net"
SPOOL = "bridge-spool"
POLL_S = 3
TMP = os.path.join(HERE, "pump-tmp")
os.makedirs(TMP, exist_ok=True)

PROXY = ("ProxyCommand=openssl s_client -quiet -connect %h:%p "
         "-servername %h -verify_return_error -verify_hostname %h")


def drive(argv, deadline=90):
    env = dict(os.environ)
    env["DRIVER_CMD"] = json.dumps(argv)
    env["DRIVER_DEADLINE"] = str(deadline)
    out = subprocess.run(
        ["python3", os.path.expanduser("~/workspace/sshdrive.py")],
        capture_output=True, text=True, env=env,
        timeout=deadline + 30)
    return out.stdout


def ssh_run(remote_cmd, deadline=90):
    return drive(["ssh", "-p", "443", "-o", PROXY, "-o",
                  "StrictHostKeyChecking=no", REMOTE, remote_cmd],
                 deadline)


def scp_from(remote_path, local_path, deadline=90):
    return drive(["scp", "-O", "-P", "443", "-o", PROXY, "-o",
                  "StrictHostKeyChecking=no",
                  f"{REMOTE}:{remote_path}", local_path], deadline)


def scp_to(local_path, remote_path, deadline=90):
    return drive(["scp", "-O", "-P", "443", "-o", PROXY, "-o",
                  "StrictHostKeyChecking=no",
                  local_path, f"{REMOTE}:{remote_path}"], deadline)


def execute(path, req):
    if path == "/v1/models":
        return 200, {"object": "list", "data": [
            {"id": f"{r}:{m}", "object": "model", "owned_by": p}
            for r, (p, m) in bridge.ROLE_MAP.items()]}
    role = req.get("role") or req.get("model")
    if role not in bridge.ROLE_MAP:
        role = "front"
    ok, used = bridge._budget_check(role)
    if not ok:
        bridge._log({"ts": time.time(), "role": role,
                     "result": "over_budget"})
        return 429, {"error": {
            "message": f"daily budget exhausted for role {role}",
            "type": "budget_exhausted"}}
    provider, model = bridge.ROLE_MAP[role]
    t0 = time.time()
    try:
        if path == "/v1/embeddings":
            text = req.get("input", "")
            if isinstance(text, list):
                text = text[0] if text else ""
            env = bridge.embed_helper(model, text)
            bridge._log({"ts": t0, "role": role,
                         "brain": f"{provider}/{model}",
                         "result": "ok", "used_today": used,
                         "via": "relay"})
            return 200, {"object": "list",
                         "data": [{"object": "embedding", "index": 0,
                                   "embedding": env["values"]}],
                         "model": model,
                         "brain_of_origin": f"{provider}/{model}"}
        messages = req.get("messages") or []
        prompt = "\n".join(m.get("content", "") for m in messages) \
            or req.get("prompt", "")
        env = bridge.call_helper(provider, model, prompt,
                                 int(req.get("max_tokens", 1024)))
        bridge._log({"ts": t0, "role": role,
                     "brain": f"{provider}/{model}", "result": "ok",
                     "used_today": used, "via": "relay",
                     "wall_s": round(time.time() - t0, 2)})
        return 200, {"id": f"bridge-{int(t0 * 1000)}",
                     "object": "chat.completion", "model": model,
                     "brain_of_origin": f"{provider}/{model}",
                     "choices": [{
                         "index": 0,
                         "message": {"role": "assistant",
                                     "content": env["content"]},
                         "finish_reason": env.get("finish_reason")}],
                     "usage": env.get("usage", {})}
    except Exception as err:
        bridge._log({"ts": t0, "role": role,
                     "brain": f"{provider}/{model}",
                     "result": f"error: {err}"[:200], "via": "relay"})
        return 502, {"error": {"message": str(err)[:300],
                               "type": "organ_unavailable"}}


def main():
    print("relay pump up", flush=True)
    while True:
        try:
            listing = ssh_run(f"ls {SPOOL}/req/ 2>/dev/null",
                              deadline=60)
            ids = [ln.strip()[:-5] for ln in listing.splitlines()
                   if ln.strip().endswith(".json")]
            for call_id in ids:
                local_req = os.path.join(TMP, f"{call_id}.req.json")
                scp_from(f"{SPOOL}/req/{call_id}.json", local_req,
                         deadline=60)
                with open(local_req, encoding="utf-8") as fh:
                    payload = json.load(fh)
                status, body = execute(payload["path"],
                                       payload["request"])
                local_resp = os.path.join(TMP, f"{call_id}.resp.json")
                with open(local_resp, "w", encoding="utf-8") as fh:
                    json.dump({"status": status, "body": body}, fh,
                              ensure_ascii=False)
                scp_to(local_resp,
                       f"{SPOOL}/resp/{call_id}.json.tmp",
                       deadline=60)
                ssh_run(f"mv {SPOOL}/resp/{call_id}.json.tmp "
                        f"{SPOOL}/resp/{call_id}.json", deadline=60)
                os.unlink(local_req)
                os.unlink(local_resp)
        except Exception as err:
            print(f"pump error: {err}", flush=True)
        time.sleep(POLL_S)


if __name__ == "__main__":
    main()
