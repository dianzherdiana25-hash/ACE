"""Periksa tautan dokumen dari arsip asal dan respon yang direkam.

Fragment internal diperiksa terhadap ID di snapshot. URL eksternal
hanya dinilai dari daftar probe yang tertambat; tautan tanpa data
diberi status unknown. Validator sendiri tidak membuka jaringan.
"""
import argparse
from pathlib import Path
import sys
from urllib.parse import unquote,urljoin,urlsplit,urlunsplit

from ._artifact import read_relative
from ._contracts import ContractError,canonical,checked,decode,digest,entries,integer,obj,read,relative_path,schema,text
from .page_extractor import MAX_HTML,Snapshot
from .search_reader import address


def _link(base,href):
    if not isinstance(href,str) or len(href)>1000 or "\\" in href or not href.strip():
        raise ContractError("Tautan di luar subset.")
    raw=urlsplit(urljoin(base,href.strip()))
    url,host=address(urlunsplit((raw.scheme,raw.netloc,raw.path,raw.query,"")))
    return url,host,unquote(raw.fragment,errors="strict") if raw.fragment else None


def validate(root,plan,expected,probe):
    checked(plan,expected)
    schema(plan,"ace.web.link-validation-plan.v1",("source_ref","probe_sha256","documents"))
    checked(probe,plan["probe_sha256"])
    schema(probe,"ace.web.link-probes.v1",("entries",))
    pointer=text(plan["source_ref"],"Sumber audit tautan")
    attempts={}
    for raw in entries(probe["entries"],5000):
        obj(raw,("url","status","source_ref","evidence_sha256"))
        url,host,fragment=_link(raw["url"],raw["url"])
        if fragment or url in attempts:
            raise ContractError("Probe ganda atau mengandung fragment.")
        attempts[url]=(integer(raw["status"],"HTTP status",100,599),
                       text(raw["source_ref"],"Sumber probe"),digest(raw["evidence_sha256"]))
    pages={}
    files=set()
    for row in entries(plan["documents"],200,1):
        obj(row,("path","url","sha256","source_ref"))
        path=relative_path(row["path"])
        url,host,fragment=_link(row["url"],row["url"])
        anchor=digest(row["sha256"])
        if fragment or path in files or url in pages:
            raise ContractError("Path/URL dokumen ganda atau berfragment.")
        files.add(path)
        data=Snapshot(read_relative(root,path,MAX_HTML,anchor)).elements
        ids={node.attrs["id"] for node in data if node.attrs.get("id")}
        pages[url]=(host,data,ids,text(row["source_ref"],"Sumber dokumen"),anchor,path)
    result=[]
    for url,(host,page,_,source,anchor,path) in sorted(pages.items()):
        for node in page:
            if node.tag!="a" or "href" not in node.attrs:
                continue
            record={"document":path,"source_ref":source,"line":node.line,"document_sha256":anchor,
                    "target":None,"fragment":None,"probe_ref":None,"status":"invalid"}
            try:
                destination,target_host,fragment=_link(url,node.attrs["href"])
            except ValueError:
                result.append(record)
                continue
            record.update(target=destination,fragment=fragment)
            if destination in pages:
                document=pages[destination]
                record.update(status="missing_fragment" if fragment is not None and fragment not in document[2] else "verified_snapshot",
                              probe_ref=document[3])
            elif destination in attempts:
                status,ref,evidence=attempts[destination]
                record.update(status="verified_response" if 200<=status<300 else "broken_response",
                              probe_ref=ref,probe_sha256=evidence,http_status=status)
                if fragment and 200<=status<300:
                    record["status"]="fragment_unverified"
            else:
                record["status"]="unobserved_same_host" if target_host==host else "unobserved_external"
            result.append(record)
            if len(result)>6000:
                raise ContractError("Tautan yang dinilai melebihi anggaran.")
    counts={}
    for row in result:
        counts[row["status"]]=counts.get(row["status"],0)+1
    return {"schema":"ace.web.link-validation-report.v1","plan_sha256":expected,"probe_sha256":plan["probe_sha256"],
            "source_ref":pointer,"documents":len(pages),"checks":result,"counts":dict(sorted(counts.items()))}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root",type=Path)
    parser.add_argument("plan",type=Path)
    parser.add_argument("probes",type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        report=validate(args.root,decode(read(args.plan)),args.expect_sha256,decode(read(args.probes)))
        sys.stdout.buffer.write(canonical(report)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
