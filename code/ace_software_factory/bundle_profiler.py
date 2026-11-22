"""Profil ukuran aset web dan model waktu transfer dari snapshot lokal.

Graf membaca HTML, CSS, dan import relatif ES module yang literal.
Angka waktu hanyalah estimasi dengan bandwidth dan latency dari rencana.
Resource eksternal atau tak dikenal dicatat tanpa jaringan.
"""
import argparse
from collections import deque
import gzip
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
import posixpath
import re
import sys
from urllib.parse import urlsplit

from ._artifact_io import read_relative
from ._contracts import ContractError,canonical,checked,decode,digest,entries,integer,obj,read,schema,text
from .repo_scaffolder import _relative


TEXT={".html",".css",".js",".mjs",".json",".webmanifest",".svg"}
CSS_REF=re.compile(r'''(?i)url\(\s*["']?([^"'\s)]+)["']?\s*\)|@import\s+["']([^"']+)["']''')
ES_IMPORT=re.compile(r'''(?m)^\s*(?:import\s+(?:[^;\n]+?\s+from\s+)?|export\s+[^;\n]+?\s+from\s+)["'](\.{1,2}/[^"']+)["']''')
HTML_LINKS={"stylesheet","manifest","preload","modulepreload","icon"}


class Links(HTMLParser):
    def __init__(self,value):
        super().__init__(convert_charrefs=True)
        self.paths=[]
        self.feed(value)
        self.close()

    def handle_starttag(self,tag,pairs):
        attrs=dict(pairs)
        if tag=="link" and set((attrs.get("rel") or "").lower().split()) & HTML_LINKS and attrs.get("href"):
            self.paths.append(attrs["href"])
        if tag in {"img","script","source","audio","video","iframe"} and attrs.get("src"):
            self.paths.append(attrs["src"])
        if tag=="video" and attrs.get("poster"):
            self.paths.append(attrs["poster"])
        srcset=attrs.get("srcset") if tag in {"img","source"} else None
        if srcset and "data:" not in srcset:
            self.paths.extend(part.strip().split()[0] for part in srcset.split(",") if part.strip())


def _dependencies(path,payload):
    ext=PurePosixPath(path).suffix.lower()
    if ext==".html":
        return Links(payload.decode()).paths
    if ext==".css":
        source=re.sub(r"/\*.*?\*/","",payload.decode(),flags=re.S)
        return [first or second for first,second in CSS_REF.findall(source)]
    if ext in (".js",".mjs"):
        return ES_IMPORT.findall(payload.decode())
    return []


def _resolve(parent,url):
    parsed=urlsplit(url.strip())
    if parsed.scheme=="data":
        return None,None
    if parsed.scheme or parsed.netloc:
        return None,"external"
    if not parsed.path:
        return None,None
    if "%" in parsed.path or "\\" in parsed.path:
        return None,"unsupported_path"
    if parsed.path.startswith("/"):
        raw=parsed.path.lstrip("/")
    else:
        raw=posixpath.join(posixpath.dirname(parent),parsed.path)
    normalized=posixpath.normpath(raw)
    try:
        _relative(normalized)
    except ContractError:
        return None,"path_escape"
    return normalized,None


def profile(root,plan,expected):
    checked(plan,expected)
    schema(plan,"ace.factory-bundle-plan.v1",("source_ref","entry","files","max_bytes","bandwidth_bps","latency_ms"))
    pointer=text(plan["source_ref"],"Sumber bundle")
    start=text(plan["entry"],"Entry HTML",250)
    bandwidth=integer(plan["bandwidth_bps"],"Bit per detik",10_000,10**10)
    rtt=integer(plan["latency_ms"],"Latensi asumsi",0,3000)
    budget=integer(plan["max_bytes"],"Anggaran transfer",1,30_000_000)
    manifest={}
    for row in entries(plan["files"],200,minimum=1):
        obj(row,("path","sha256"))
        path=text(row["path"],"Nama aset",250)
        _relative(path)
        if path in manifest:
            raise ContractError("Path aset ganda.")
        manifest[path]=digest(row["sha256"])
    if start not in manifest or not start.endswith(".html"):
        raise ContractError("Entry HTML perlu ada pada manifest.")
    remaining=deque([start])
    amount=0
    files={}
    findings=set()
    graph={}
    while remaining:
        path=remaining.popleft()
        if path in files:
            continue
        payload=read_relative(root,path,min(2_000_000,15_000_000-amount),manifest[path])
        amount+=len(payload)
        kind=PurePosixPath(path).suffix.lower()
        compressed=len(gzip.compress(payload,compresslevel=9,mtime=0)) if kind in TEXT else None
        files[path]={"path":path,"sha256":manifest[path],"raw_bytes":len(payload),"gzip_bytes":compressed,
                     "estimated_transfer_bytes":min(len(payload),compressed) if compressed is not None else len(payload)}
        connected=set()
        for dependency in _dependencies(path,payload):
            target,problem=_resolve(path,dependency)
            if problem:
                findings.add((problem,path,dependency))
            elif target is not None:
                if target not in manifest:
                    findings.add(("missing_dependency",path,target))
                else:
                    connected.add(target)
        graph[path]=sorted(connected)
        remaining.extend(graph[path])
    transfer=sum(row["estimated_transfer_bytes"] for row in files.values())
    milliseconds=(transfer*8*1000+bandwidth-1)//bandwidth
    invalid=any(code!="external" for code,_,_ in findings)
    status="incomplete" if invalid else "over_budget" if transfer>budget else (
        "external_dependencies" if findings else "within_budget")
    return {"schema":"ace.factory-bundle-profile.v1","plan_sha256":expected,"source_ref":pointer,"entry":start,
            "assets":[files[path] for path in sorted(files)],"graph":dict(sorted(graph.items())),
            "unreferenced":sorted(manifest.keys()-files.keys()),"raw_bytes":amount,"estimated_transfer_bytes":transfer,
            "findings":[{"code":code,"from":path,"reference":ref} for code,path,ref in sorted(findings)],
            "timing_assumptions":{"bandwidth_bps":bandwidth,"latency_ms":rtt,"per_request_without_multiplexing":True},
            "transfer_lower_ms":milliseconds+rtt,"transfer_sequential_ms":milliseconds+len(files)*rtt,
            "status":status}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root",type=Path)
    parser.add_argument("plan",type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        report=profile(args.root,decode(read(args.plan)),args.expect_sha256)
        sys.stdout.buffer.write(canonical(report)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return int(report["status"]!="within_budget")


if __name__=="__main__":
    raise SystemExit(main())
