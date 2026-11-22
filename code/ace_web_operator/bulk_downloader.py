"""Buat snapshot unduhan dataset berizin dengan resume dan budget.

Sumber hanya fixture loopback dan tiap aset bertanda hash, lisensi,
serta byte yang diharapkan. Hasil valid boleh dipakai ulang dari snapshot
lama, sedangkan berkas gagal tetap tercatat tanpa menghasilkan objek.
"""
import argparse
from hashlib import sha256
from pathlib import Path
import sys

from ._artifact import read_relative,write_new
from ._contracts import ContractError,canonical,checked,decode,digest,entries,identifier,integer,obj,origin,read,schema,text,web_path
from ._http import fetch


LICENSES={"CC0-1.0","CC-BY-4.0","ODC-BY-1.0","ODbL-1.0"}
MEDIA={"text/csv","text/plain","application/json","application/octet-stream","application/zip"}


def _records(plan,expected):
    checked(plan,expected)
    schema(plan,"ace.web.bulk-download-plan.v1",("source_ref","origin","access_ref","max_total_bytes","datasets"))
    source=text(plan["source_ref"],"Sumber unduhan")
    access=text(plan["access_ref"],"Izin unduh")
    base,_=origin(plan["origin"])
    ceiling=integer(plan["max_total_bytes"],"Total byte",1,16_000_000)
    items={}
    reserved=0
    paths=set()
    for row in entries(plan["datasets"],40,1):
        obj(row,("id","path","bytes","sha256","media_type","license","license_ref","source_ref"))
        key=identifier(row["id"],"Dataset")
        path=web_path(row["path"])
        license_name=row["license"]
        media=row["media_type"]
        if (key in items or path in paths or not isinstance(license_name,str) or license_name not in LICENSES
                or not isinstance(media,str) or media not in MEDIA):
            raise ContractError("Dataset ganda atau lisensi/media di luar scope.")
        paths.add(path)
        size=integer(row["bytes"],"Ukuran dataset",1,4_000_000)
        reserved+=size
        if reserved>ceiling:
            raise ContractError("Manifest melampaui budget total.")
        items[key]={"id":key,"path":path,"bytes":size,"sha256":digest(row["sha256"]),"media_type":media,
                    "license":license_name,"license_ref":text(row["license_ref"],"Bukti lisensi"),
                    "source_ref":text(row["source_ref"],"Rujukan dataset")}
    return source,access,base,items


def download(plan,expected,*,resume=None,transport=fetch):
    source,access,base,items=_records(plan,expected)
    copied={}
    records=[]
    for key,row in sorted(items.items()):
        name=f"datasets/{row['sha256']}"
        size=row["bytes"]
        anchor=row["sha256"]
        status="downloaded"
        problem=None
        data=None
        if name in copied:
            data=copied[name]
            status="deduplicated"
        elif resume is not None:
            try:
                data=read_relative(resume,name,size,anchor)
                status="resumed"
            except FileNotFoundError:
                pass
            except (OSError,ValueError):
                problem="invalid_resume_object"
        if data is None and problem is None:
            outcome=transport(base,row["path"],cap=size)
            if outcome.error is not None:
                problem=outcome.error
            elif outcome.status!=200 or outcome.media_type!=row["media_type"]:
                problem="status_or_media_mismatch"
            else:
                data=outcome.body
        if problem is None and (data is None or len(data)!=size or sha256(data).hexdigest()!=anchor):
            problem="content_mismatch"
        if problem is None:
            copied[name]=data
        records.append({**row,"status":status if problem is None else "held","reason":problem,
                        "object":name if problem is None else None})
    held=sum(row["status"]=="held" for row in records)
    result={"schema":"ace.web.bulk-download-receipt.v1","plan_sha256":expected,"source_ref":source,
            "access_ref":access,"records":records,"objects":len(copied),"object_bytes":sum(map(len,copied.values())),
            "held":held,"status":"partial" if held else "complete"}
    return {**copied,"download_receipt.json":canonical(result)+b"\n"},result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan",type=Path)
    parser.add_argument("output",type=Path)
    parser.add_argument("--expect-sha256",required=True)
    parser.add_argument("--resume",type=Path)
    args=parser.parse_args(argv)
    try:
        files,report=download(decode(read(args.plan)),args.expect_sha256,resume=args.resume)
        write_new(args.output,files)
        sys.stdout.buffer.write(canonical(report)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return int(report["status"]!="complete")


if __name__=="__main__":
    raise SystemExit(main())
