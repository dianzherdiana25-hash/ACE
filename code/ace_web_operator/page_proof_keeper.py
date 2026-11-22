"""Bekukan byte HTML dan locator dalam artefak bukti halaman.

Pembuat artefak mengikat status, waktu dan URL yang disetujui pada
snapshot. Verifier membandingkan hash manifest eksternal dan hash isi
sebelum menghasilkan verdict. Dua artefak baru ditulis bersama.
"""
import argparse
from hashlib import sha256
from pathlib import Path
import sys

from ._contracts import ContractError,canonical,checked,decode,digest,integer,origin,read,schema,text,web_path
from .page_extractor import MAX_HTML,Snapshot
from .web_scheduler import time_value


def _details(record):
    site,_=origin(record["origin"])
    path=web_path(record["path"])
    time_value(record["captured_at"])
    text(record["permission_ref"],"Rujukan izin")
    text(record["source_ref"],"Sumber halaman")
    return site+path


def preserve(html,plan,expected):
    checked(plan,expected)
    schema(plan,"ace.web.proof-plan.v1",("site_id","origin","path","captured_at","source_ref","permission_ref",
                                        "html_sha256","status"))
    url=_details(plan)
    site=text(plan["site_id"],"ID situs",140)
    anchor=digest(plan["html_sha256"])
    code=integer(plan["status"],"Status HTTP",200,299)
    if not isinstance(html,bytes) or not 1<=len(html)<=MAX_HTML or sha256(html).hexdigest()!=anchor:
        raise ContractError("Hash atau ukuran HTML tidak sesuai.")
    if not Snapshot(html).elements:
        raise ContractError("HTML tidak memiliki elemen yang dapat ditambatkan.")
    file_name=f"page-{anchor[:20]}.html"
    details={"schema":"ace.web.page-proof.v1","plan_sha256":expected,"site_id":site,"url":url,
             "origin":plan["origin"],"path":plan["path"],"captured_at":plan["captured_at"],"status":code,
             "source_ref":plan["source_ref"],"permission_ref":plan["permission_ref"],"html_sha256":anchor,
             "html_bytes":len(html),"artifact":file_name}
    metadata=canonical(details)+b"\n"
    return {file_name:html,"page_proof.json":metadata},_verification(details,sha256(metadata).hexdigest())


def _verification(details,anchor):
    return {"schema":"ace.web.page-proof-verification.v1","status":"verified","manifest_sha256":anchor,
            "html_sha256":details["html_sha256"],"source_ref":details["source_ref"],"url":details["url"],
            "artifact":details["artifact"],"captured_at":details["captured_at"]}


def verify(html,manifest,expected):
    if not isinstance(manifest,bytes) or len(manifest)>5000 or sha256(manifest).hexdigest()!=digest(expected):
        raise ContractError("Manifest tidak cocok dengan anchor receipt.")
    details=decode(manifest)
    schema(details,"ace.web.page-proof.v1",("plan_sha256","site_id","origin","path","captured_at","status",
           "source_ref","permission_ref","html_sha256","html_bytes","artifact","url"))
    target=_details(details)
    text(details["site_id"],"ID situs",140)
    digest(details["plan_sha256"])
    anchor=digest(details["html_sha256"])
    integer(details["status"],"Status",200,299)
    if details["url"]!=target or details["artifact"]!=f"page-{anchor[:20]}.html" or canonical(details)+b"\n"!=manifest:
        raise ContractError("Locator manifest tidak kanonis.")
    expected_size=integer(details["html_bytes"],"Ukuran HTML",1,MAX_HTML)
    if not isinstance(html,bytes) or len(html)!=expected_size or sha256(html).hexdigest()!=anchor:
        raise ContractError("HTML tidak sama dengan manifest bukti.")
    return _verification(details,expected)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    modes=parser.add_subparsers(dest="mode",required=True)
    keep=modes.add_parser("preserve")
    keep.add_argument("html",type=Path)
    keep.add_argument("plan",type=Path)
    keep.add_argument("output",type=Path)
    keep.add_argument("--expect-sha256",required=True)
    check=modes.add_parser("verify")
    check.add_argument("html",type=Path)
    check.add_argument("manifest",type=Path)
    check.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        contents=read(args.html,MAX_HTML)
        if args.mode=="preserve":
            files,result=preserve(contents,decode(read(args.plan)),args.expect_sha256)
            args.output.mkdir(mode=0o700)
            for path,payload in sorted(files.items()):
                with (args.output/path).open("xb") as stream:
                    stream.write(payload)
        else:
            result=verify(contents,read(args.manifest,5000),args.expect_sha256)
        sys.stdout.buffer.write(canonical(result)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
