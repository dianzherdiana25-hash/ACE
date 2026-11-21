"""Bangun mode offline versi tetap dari aset web yang di-anchor.

Service worker menginstal cache hanya setelah mengecek setiap byte.
Request GET same-origin yang terdaftar diambil dari cache. Navigasi
yang tak dapat mencapai jaringan memakai halaman fallback eksplisit.
"""
import argparse
from hashlib import sha256
from pathlib import Path
import re
import sys

from ._artifact_io import read_relative
from ._contracts import ContractError, canonical, checked, decode, digest, entries, identifier, obj, read, schema, text
from .repo_scaffolder import materialize


SAFE = re.compile(r"[a-zA-Z0-9_-]+(?:/[a-zA-Z0-9_-]+)*/?[a-zA-Z0-9_.-]*")
EXTENSIONS = {".html",".css",".js",".png",".jpg",".jpeg",".webmanifest",".json"}
RESERVED = {"ace-offline-worker.js","register-offline.js","offline_report.json"}
MAX_ASSET=1_000_000
MAX_TOTAL=4_000_000
WORKER = r'''"use strict";

const prefix = "ace-offline:" + POLICY.id + ":";
const active = prefix + POLICY.tree;
const assets = new Map(POLICY.assets.map(row => [new URL(row.path, self.registration.scope).href,row]));
const fallback = new URL(POLICY.fallback,self.registration.scope).href;

async function hex(data) {
    const hash = new Uint8Array(await crypto.subtle.digest("SHA-256",data));
    return Array.from(hash,value => value.toString(16).padStart(2,"0")).join("");
}

async function install() {
    const candidate = await caches.open(active);
    try {
        for (const [url, asset] of assets) {
            const input = await fetch(url,{cache:"no-store",credentials:"omit",redirect:"error"});
            if (!input.ok || input.type === "opaque") throw new Error("asset_unreachable");
            const content = await input.clone().arrayBuffer();
            if (content.byteLength !== asset.bytes || await hex(content) !== asset.sha256) {
                throw new Error("asset_sha256_mismatch");
            }
            await candidate.put(url,input);
        }
    } catch (error) {
        await caches.delete(active);
        throw error;
    }
}

async function activate() {
    for (const key of (await caches.keys())) {
        if (key.startsWith(prefix) && key !== active) await caches.delete(key);
    }
    await self.clients.claim();
}

async function handle(request) {
    const cache = await caches.open(active);
    if (assets.has(request.url)) {
        const item = await cache.match(request.url);
        if (item) return item;
        return new Response("Cache belum lengkap.",{status:503,headers:{"Content-Type":"text/plain"}});
    }
    try {
        return await fetch(request);
    } catch (error) {
        if (request.mode !== "navigate") throw error;
        return (await cache.match(fallback)) || new Response("Offline.",{status:503});
    }
}

self.addEventListener("install", event => event.waitUntil(install()));
self.addEventListener("activate", event => event.waitUntil(activate()));
self.addEventListener("fetch", event => {
    const request = event.request;
    const url = new URL(request.url);
    const scope = new URL(self.registration.scope);
    if (request.method !== "GET" || url.origin !== scope.origin || !url.pathname.startsWith(scope.pathname)) return;
    if (assets.has(request.url) || request.mode === "navigate") event.respondWith(handle(request));
});
'''
REGISTER = br'''"use strict";

const worker = document.currentScript.src;
if ("serviceWorker" in navigator && window.isSecureContext) {
    const path = new URL("ace-offline-worker.js",worker);
    navigator.serviceWorker.register(path).catch(() => {
        document.dispatchEvent(new CustomEvent("ace-offline-unavailable"));
    });
}
'''


def _path(value):
    name=text(value,"Path aset",240)
    if (not SAFE.fullmatch(name) or any(part in ("",".","..") or part.startswith(".") for part in name.split("/"))
            or Path(name).suffix.lower() not in EXTENSIONS or name in RESERVED):
        raise ContractError("Path aset offline tidak didukung.")
    return name


def build(root, plan, expected):
    checked(plan,expected)
    schema(plan,"ace.factory-offline-plan.v1",("id","source_ref","assets","fallback"))
    product=identifier(plan["id"],"ID cache aplikasi")
    pointer=text(plan["source_ref"],"Rujukan offline")
    fallback=_path(plan["fallback"])
    if not fallback.endswith(".html"):
        raise ContractError("Fallback perlu HTML lokal.")
    observed={}
    payload={}
    total=0
    for entry in entries(plan["assets"],180,minimum=1):
        obj(entry,("path","sha256"))
        path=_path(entry["path"])
        if path in observed:
            raise ContractError("Aset offline ganda.")
        anchor=digest(entry["sha256"])
        value=read_relative(root,path,min(MAX_ASSET,MAX_TOTAL-total),anchor)
        total+=len(value)
        observed[path]={"path":path,"sha256":anchor,"bytes":len(value)}
        payload[path]=value
    if fallback not in observed:
        raise ContractError("Fallback belum terdaftar.")
    manifest=[observed[path] for path in sorted(observed)]
    cache=sha256(canonical({"assets":manifest,"fallback":fallback,"worker_template_sha256":sha256(WORKER.encode()).hexdigest()})).hexdigest()
    config={"id":product,"tree":cache,"fallback":fallback,"assets":manifest}
    runtime=b"const POLICY = "+canonical(config)+b";\n"+WORKER.encode()
    result={"schema":"ace.factory-offline-build.v1","plan_sha256":expected,"source_ref":pointer,
            "assets":manifest,"scope_id":product,"cache_tree_sha256":cache,"fallback":fallback,
            "worker_sha256":sha256(runtime).hexdigest()}
    payload.update({"ace-offline-worker.js":runtime,"register-offline.js":REGISTER,"offline_report.json":canonical(result)+b"\n"})
    return payload,result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ("root","plan","output"):
        parser.add_argument(key,type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        files,report=build(args.root,decode(read(args.plan)),args.expect_sha256)
        materialize(args.output,files)
        sys.stdout.buffer.write(canonical(report)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
