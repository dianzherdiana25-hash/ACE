"""Baca halaman hasil pencarian yang disimpan dan ringkas secara ekstraktif.

Urutan sumber dipertahankan. Deduplikasi memakai URL kanonis, dan
cuplikan hanya berasal dari elemen snippet hasil. Tidak ada akses ke
mesin pencari atau link hasil.
"""
import argparse
from hashlib import sha256
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit,urlunsplit

from ._contracts import ContractError,canonical,checked,decode,digest,integer,read,schema,text
from .page_extractor import MAX_HTML,Snapshot,_descendants


HOST=re.compile(r"[a-z0-9-]+(?:\.[a-z0-9-]+)+")


def address(raw):
    source=text(raw,"URL hasil",900)
    if "\\" in source:
        raise ContractError("URL hasil tidak sah.")
    url=urlsplit(source)
    host=url.hostname or ""
    if url.scheme not in ("http","https") or not HOST.fullmatch(host) or url.username is not None or url.password is not None:
        raise ContractError("URL hasil tidak sah.")
    port=url.port
    plain=(url.scheme=="https" and port==443) or (url.scheme=="http" and port==80)
    netloc=host if port is None or plain else f"{host}:{port}"
    return urlunsplit((url.scheme,netloc,url.path or "/",url.query,"")),host


def extract(html,plan,expected):
    checked(plan,expected)
    schema(plan,"ace.web.search-reader-plan.v1",("source_ref","query","snapshot_sha256","snapshot_ref","max_results","max_chars"))
    pointer=text(plan["source_ref"],"Sumber pencarian")
    query=text(plan["query"],"Query dicatat",240)
    source=text(plan["snapshot_ref"],"Rujukan snapshot",250)
    anchor=digest(plan["snapshot_sha256"])
    if not isinstance(html,bytes) or len(html)>MAX_HTML or sha256(html).hexdigest()!=anchor:
        raise ContractError("Snapshot pencarian tidak cocok dengan anchor.")
    cap=integer(plan["max_results"],"Batas hasil",1,50)
    width=integer(plan["max_chars"],"Panjang cuplikan",40,450)
    records=[]
    findings=[]
    found={}
    scanned=0
    for node in Snapshot(html).elements:
        if node.attrs.get("data-search-result")!="true":
            continue
        scanned+=1
        children=list(_descendants(node))
        links=[child for child in children if child.tag=="a" and child.attrs.get("data-role")=="title"]
        snippets=[child for child in children if child.attrs.get("data-role")=="snippet"]
        context={"source_ref":source,"line":node.line,"rank":scanned}
        if len(links)!=1 or len(snippets)>1 or not links[0].text():
            findings.append({**context,"reason":"ambiguous_result"})
            continue
        try:
            url,host=address(links[0].attrs.get("href"))
        except ValueError:
            findings.append({**context,"reason":"invalid_address"})
            continue
        if url in found:
            findings.append({**context,"reason":"duplicate","first_line":found[url]})
            continue
        found[url]=node.line
        if len(records)==cap:
            continue
        excerpt=snippets[0].text() if snippets else None
        records.append({**context,"title":links[0].text()[:240],"url":url,"host":host,
                        "excerpt":excerpt[:width] if excerpt else None,"truncated":bool(excerpt and len(excerpt)>width)})
    brief=[{"rank":row["rank"],"title":row["title"],"excerpt":row["excerpt"],"source_ref":row["source_ref"],
            "line":row["line"]} for row in records if row["excerpt"] is not None]
    return {"schema":"ace.web.search-reader-report.v1","plan_sha256":expected,"snapshot_sha256":anchor,
            "source_ref":pointer,"query":query,"scanned":scanned,"results":records,"brief":brief,
            "findings":findings,"omitted_by_limit":len(found)-len(records),"status":"extracted" if records else "empty"}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("html",type=Path)
    parser.add_argument("plan",type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        output=extract(read(args.html,MAX_HTML),decode(read(args.plan)),args.expect_sha256)
        sys.stdout.buffer.write(canonical(output)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
