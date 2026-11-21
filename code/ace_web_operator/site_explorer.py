"""Jelajahi tautan fixture dengan BFS di dalam origin dan prefix terdaftar.

Penjelajah membaca HTML saja untuk discovery, menghormati kuota dan
jeda, serta menolak redirect. Peta menyimpan hash halaman dan frontier
yang belum sempat dibaca agar cakupan yang kurang tetap terlihat.
"""
import argparse
from collections import deque
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path
import sys
from time import sleep

from ._contracts import ContractError,canonical,checked,decode,entries,integer,origin,read,schema,text,web_path
from ._http import fetch,related


class Anchors(HTMLParser):
    def __init__(self,source):
        super().__init__(convert_charrefs=True)
        self.links=[]
        self.feed(source.decode("utf-8"))
        self.close()

    def handle_starttag(self,tag,attrs):
        if tag=="a":
            href=dict(attrs).get("href")
            if href is not None:
                self.links.append(href)
                if len(self.links)>1200:
                    raise ContractError("Batas tautan per halaman terlampaui.")


def _within(path,prefixes):
    return any(prefix=="/" or path==prefix.rstrip("/") or path.startswith(prefix.rstrip("/")+"/") for prefix in prefixes)


def configuration(plan,expected):
    checked(plan,expected)
    schema(plan,"ace.web.explore-plan.v1",("source_ref","origin","entry","allow_prefixes","deny_prefixes","max_pages",
                                           "max_depth","max_bytes","min_spacing_ms"))
    anchor=text(plan["source_ref"],"Rujukan eksplorasi")
    base,_=origin(plan["origin"])
    initial=web_path(plan["entry"])
    scopes=[web_path(item) for item in entries(plan["allow_prefixes"],30,1)]
    denied=[web_path(item) for item in entries(plan["deny_prefixes"],30)]
    if initial in denied or not _within(initial,scopes) or _within(initial,denied):
        raise ContractError("Titik masuk di luar rute yang diizinkan.")
    return anchor,base,initial,sorted(set(scopes)),sorted(set(denied)),{
        "max_pages":integer(plan["max_pages"],"Jumlah halaman",1,45),
        "max_depth":integer(plan["max_depth"],"Kedalaman",0,10),
        "max_bytes":integer(plan["max_bytes"],"Batas byte halaman",200,400_000),
        "min_spacing_ms":integer(plan["min_spacing_ms"],"Jeda request",80,2000),
    }


def explore(plan,expected,*,transport=fetch,wait=sleep):
    pointer,base,initial,scopes,deny,limits=configuration(plan,expected)
    waiting=deque([(initial,0,None)])
    seen={initial}
    reported=[]
    deferred={}
    while waiting and len(reported)<limits["max_pages"]:
        path,depth,from_path=waiting.popleft()
        if reported:
            wait(limits["min_spacing_ms"]/1000)
        outcome=transport(base,path,cap=limits["max_bytes"])
        record={"path":path,"discovered_from":from_path,"depth":depth,"status":outcome.status,
                "media_type":outcome.media_type,"error":outcome.error,
                "body_sha256":sha256(outcome.body).hexdigest() if outcome.error is None else None,
                "links":[],"rejected_links":0}
        reported.append(record)
        if outcome.error is not None or outcome.status!=200 or outcome.media_type!="text/html":
            continue
        try:
            raw=Anchors(outcome.body).links
        except (ValueError,RecursionError):
            record["error"]="parse_incomplete"
            continue
        targets=set()
        for link in raw:
            target=related(base,path,link)
            if target is None or not _within(target,scopes) or _within(target,deny):
                record["rejected_links"]+=1
            else:
                targets.add(target)
        record["links"]=sorted(targets)
        for target in sorted(targets):
            if target in seen:
                continue
            if depth>=limits["max_depth"]:
                deferred.setdefault(target,{"path":target,"from":path,"reason":"depth_limit"})
            else:
                seen.add(target)
                waiting.append((target,depth+1,path))
    frontier=[{"path":path,"from":parent,"reason":"page_budget"} for path,_,parent in waiting]
    frontier.extend(row for path,row in sorted(deferred.items()) if path not in seen)
    return {"schema":"ace.web.exploration-receipt.v1","plan_sha256":expected,"source_ref":pointer,
            "pages":reported,"frontier":frontier,
            "status":"partial" if frontier or any(row["error"] or row["status"]!=200 for row in reported) else "complete"}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan",type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        result=explore(decode(read(args.plan)),args.expect_sha256)
        sys.stdout.buffer.write(canonical(result)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return int(result["status"]!="complete")


if __name__=="__main__":
    raise SystemExit(main())
