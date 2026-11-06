"""Small audited MCP transports over the real ACEBridge (stdlib-only).

stdio is suitable for an MCP client that can launch a trusted local process.
HTTP is deliberately restricted to loopback or a separately controlled private
network; a bearer token is mandatory. This is NOT an OAuth authorization server,
and must NOT be exposed directly as a public ChatGPT plugin endpoint.
"""
from __future__ import annotations

import argparse
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import sys
from urllib.parse import urlsplit

from .bridge import ACEBridge, PROTOCOL, json_rpc

MAX_REQUEST_BYTES = 262144


def stdio(bridge, source=None, sink=None):
    source = source if source is not None else sys.stdin
    sink = sink if sink is not None else sys.stdout
    for line in source:
        if len(line.encode("utf-8")) > MAX_REQUEST_BYTES:
            response = {"jsonrpc": "2.0", "id": None,
                        "error": {"code": -32600, "message": "Request too large"}}
        else:
            try:
                request = json.loads(line)
            except ValueError:
                response = {"jsonrpc": "2.0", "id": None,
                            "error": {"code": -32700, "message": "Parse error"}}
            else:
                response = json_rpc(request, bridge)
        if response is not None:
            sink.write(json.dumps(response, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n")
            sink.flush()


def make_http_server(host, port, bridge, *, token, allowed_origins=()):
    if type(token) is not str or len(token) < 32:
        raise ValueError("HTTP requires a secret bearer token of at least 32 characters")
    if host not in ("127.0.0.1", "::1", "localhost"):
        raise ValueError("MCP HTTP binds only to loopback; use a reviewed authenticated TLS gateway for remote access")
    if type(allowed_origins) not in (list, tuple, frozenset):
        raise ValueError("invalid allowed_origins")
    origins = set(allowed_origins)
    if any(not isinstance(o,str) or not o.startswith("https://") for o in origins):
        raise ValueError("allowed origins must be HTTPS")

    class Handler(BaseHTTPRequestHandler):
        server_version = "ACE-MCP/0.1"
        sys_version = ""
        def log_message(self, format, *args):
            # Avoid logging bearer tokens, tool payloads and user task strings.
            pass

        def reply(self, status, data=None, extra_headers=None):
            body = b"" if data is None else json.dumps(
                data, sort_keys=True, separators=(",", ":"), allow_nan=False
            ).encode("utf-8")
            self.send_response(status)
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            if data is not None:
                self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            if extra_headers:
                for key,value in extra_headers.items():
                    self.send_header(key,value)
            self.end_headers()
            if body:
                self.wfile.write(body)

        def allowed(self):
            origin = self.headers.get("Origin")
            if origin is not None and origin not in origins:
                self.reply(403, {"error": "Origin not allowed"})
                return False
            supplied = self.headers.get("Authorization", "")
            if not hmac.compare_digest(supplied.encode("utf-8"), ("Bearer " + token).encode("utf-8")):
                self.reply(401, {"error": "Unauthorized"},
                           {"WWW-Authenticate": 'Bearer realm="ACE-MCP"'})
                return False
            return True

        def do_GET(self):
            if self.path == "/healthz":
                self.reply(200, {"ready": True})
                return
            if self.path == "/mcp":
                if not self.allowed():
                    return
                self.reply(405, {"error": "SSE GET transport not supported"},
                           {"Allow": "POST"})
                return
            self.reply(404, {"error": "Not Found"})

        def do_POST(self):
            if self.path != "/mcp":
                self.reply(404, {"error": "Not Found"})
                return
            if not self.allowed():
                return
            try:
                declared = self.headers.get("Content-Length")
                length = int(declared) if declared is not None else -1
            except ValueError:
                length = -1
            if not 0 <= length <= MAX_REQUEST_BYTES:
                self.reply(413, {"error": "Invalid request length"})
                return
            if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
                self.reply(415, {"error": "Content-Type application/json required"})
                return
            requested_version = self.headers.get("MCP-Protocol-Version")
            if requested_version is not None and requested_version != PROTOCOL:
                self.reply(400, {"error": "Unsupported MCP protocol version",
                                 "supported": [PROTOCOL]})
                return
            try:
                body = json.loads(self.rfile.read(length))
            except (ValueError, UnicodeError):
                self.reply(400, {"jsonrpc": "2.0", "id": None,
                                 "error": {"code": -32700, "message": "Parse error"}})
                return
            response = json_rpc(body, bridge)
            if response is None:
                self.reply(202)
            else:
                self.reply(200, response)

    return ThreadingHTTPServer((host,port), Handler)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--transport", choices=("stdio","http"), default="stdio")
    parser.add_argument("--read-write", action="store_true",
                        help="Operator opt-in: allow changing ACE workspace and running bounded tasks")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8735)
    parser.add_argument("--allowed-origin", action="append", default=[])
    args = parser.parse_args(argv)
    bridge = ACEBridge(args.workspace, allow_writes=args.read_write)
    if args.transport == "stdio":
        stdio(bridge)
    else:
        secret = os.environ.get("ACE_MCP_HTTP_TOKEN","")
        server = make_http_server(args.host,args.port,bridge,
                                  token=secret,allowed_origins=args.allowed_origin)
        try:
            server.serve_forever(poll_interval=0.1)
        finally:
            server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
