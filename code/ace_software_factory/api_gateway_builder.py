"""Bangun gateway JSON untuk rute tetap ke API lokal lama.

Peta rute melarang upstream di luar IPv4 loopback serta path dinamis.
Runtime membuka koneksi tanpa proxy lingkungan, redirect follow, atau
header kredensial. Respon dibatasi ukuran dan bentuk datanya.
"""
import argparse
from hashlib import sha256
from pathlib import Path
import re
import sys

from ._contracts import ContractError, canonical, checked, decode, entries, identifier, integer, obj, read, schema, text
from .repo_scaffolder import materialize


ROUTE = re.compile(r"/[a-z0-9][a-z0-9_-]*(?:/[a-z0-9][a-z0-9_-]*)*")
RUNTIME = r'''"""Gateway dua API lokal dengan rute dan timeout yang eksplisit."""
import argparse
from contextlib import closing
from http.client import HTTPConnection, HTTPException
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json


def json_bytes(value):
    return json.dumps(value,ensure_ascii=True,sort_keys=True,separators=(",",":"),allow_nan=False).encode()


def unique(items):
    result={}
    for key,value in items:
        if key in result:
            raise ValueError("duplicate_key")
        result[key]=value
    return result


def reject_number(value):
    raise ValueError("nonfinite")


def parse(data):
    return json.loads(data.decode("utf-8"),object_pairs_hook=unique,parse_constant=reject_number)


def dispatch(method, path, data):
    matching=[row for row in CONFIG["routes"] if row["client_path"]==path]
    if not matching:
        return 404,{"error":"route_unknown"}
    rule=next((row for row in matching if row["method"]==method),None)
    if rule is None:
        return 405,{"error":"method_not_allowed"}
    headers={"Accept":"application/json"}
    payload=None
    if method=="POST":
        if not isinstance(data,dict):
            return 400,{"error":"json_object_required"}
        payload=json_bytes(data)
        if len(payload)>CONFIG["max_bytes"]:
            return 413,{"error":"body_too_large"}
        headers["Content-Type"]="application/json"
    try:
        with closing(HTTPConnection("127.0.0.1",rule["upstream_port"],timeout=CONFIG["timeout"])) as client:
            client.request(method,rule["upstream_path"],body=payload,headers=headers)
            response=client.getresponse()
            if response.status>=500 or 300<=response.status<400:
                return 502,{"error":"upstream_status"}
            if response.headers.get_content_type()!="application/json":
                return 502,{"error":"upstream_type"}
            body=response.read(CONFIG["max_bytes"]+1)
            if len(body)>CONFIG["max_bytes"]:
                return 502,{"error":"upstream_size"}
            result=parse(body)
            if not isinstance(result,(dict,list)):
                return 502,{"error":"upstream_shape"}
            return response.status,result
    except TimeoutError:
        return 504,{"error":"upstream_timeout"}
    except (OSError, HTTPException, ValueError, RecursionError):
        return 502,{"error":"upstream_unavailable"}


class Handler(BaseHTTPRequestHandler):
    def log_message(self,format,*args):
        pass

    def respond(self,status,data):
        body=json_bytes(data)
        self.send_response(status)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(body)))
        self.send_header("Cache-Control","no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._dispatch()

    def do_POST(self):
        self._dispatch()

    def _dispatch(self):
        if self.headers.get("Host")!=f"127.0.0.1:{self.server.server_port}" or self.headers.get("Transfer-Encoding"):
            self.respond(400,{"error":"request_rejected"})
            return
        data=None
        if self.command=="POST":
            length=self.headers.get("Content-Length","")
            if not length.isascii() or not length.isdigit() or len(length)>7 or not 0<int(length)<=CONFIG["max_bytes"]:
                self.respond(413,{"error":"body_too_large_or_empty"})
                return
            if self.headers.get_content_type()!="application/json":
                self.respond(415,{"error":"json_required"})
                return
            try:
                data=parse(self.rfile.read(int(length)))
            except (ValueError, RecursionError):
                self.respond(400,{"error":"bad_json"})
                return
        self.respond(*dispatch(self.command,self.path,data))


def server(port=0):
    listener=ThreadingHTTPServer(("127.0.0.1",port),Handler)
    for route in CONFIG["routes"]:
        if route["upstream_port"]==listener.server_port:
            listener.server_close()
            raise ValueError("gateway_self_route")
    return listener


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port",type=int,default=0)
    args=parser.parse_args()
    with server(args.port) as listener:
        print(listener.server_port,flush=True)
        try: listener.serve_forever()
        except KeyboardInterrupt: pass


if __name__=="__main__":
    main()
'''


def build(plan, expected):
    checked(plan, expected)
    schema(plan, "ace.factory-gateway-plan.v1", ("id", "source_ref", "routes", "timeout_seconds", "max_bytes"))
    product = identifier(plan["id"], "Produk gateway")
    pointer = text(plan["source_ref"], "Sumber rute")
    routes = {}
    for raw in entries(plan["routes"], 80, minimum=1):
        obj(raw, ("client_path", "method", "upstream_host", "upstream_port", "upstream_path", "source_ref"))
        method = raw["method"]
        old = text(raw["upstream_path"], "Rute API lama", 160)
        new = text(raw["client_path"], "Rute klien", 160)
        if method not in ("GET", "POST") or raw["upstream_host"] != "127.0.0.1" or (
                not ROUTE.fullmatch(old) or not ROUTE.fullmatch(new)):
            raise ContractError("Gateway hanya menerima rute tetap GET/POST ke loopback.")
        key = (new, method)
        if key in routes:
            raise ContractError("Rute dan metode ganda.")
        routes[key] = {"client_path": new, "method": method, "upstream_path": old,
                       "upstream_port": integer(raw["upstream_port"], "Port API lama", 1024, 65535),
                       "source_ref": text(raw["source_ref"], "Sumber rute", 250)}
    config = {"routes": [routes[key] for key in sorted(routes)],
              "timeout": integer(plan["timeout_seconds"], "Timeout gateway", 1, 20),
              "max_bytes": integer(plan["max_bytes"], "Batas payload", 64, 250_000)}
    content = RUNTIME.replace("import json\n", f"import json\n\nCONFIG = {config!r}\n", 1).encode()
    report = {"schema": "ace.factory-gateway-build.v1", "product_id": product, "source_ref": pointer,
              "plan_sha256": expected, "routes": config["routes"], "network_scope": "loopback",
              "runtime": {"path": "product_gateway.py", "sha256": sha256(content).hexdigest()}}
    return {"product_gateway.py": content, "gateway_manifest.json": canonical(report)+b"\n"}, report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        files, report = build(decode(read(args.plan)), args.expect_sha256)
        materialize(args.output, files)
        sys.stdout.buffer.write(canonical(report)+b"\n")
    except (OSError, ValueError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
