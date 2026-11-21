"""Arsipkan berkas web lokal dengan manifest dan verifikasi byte ulang.

Sumber, izin fixture, media type, serta hash yang diharapkan diberikan
sebelum pengambilan. Arsip hanya dibentuk jika setiap sumber cocok.
Manifest menautkan URL rute ke objek beralamat hash, tanpa duplikasi.
"""
import argparse
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import stat
import sys
from zipfile import BadZipFile,ZIP_STORED,ZipFile,ZipInfo

from ._contracts import ContractError,canonical,checked,decode,digest,entries,integer,obj,origin,read,schema,text,web_path
from ._http import fetch


STAMP=(1980,1,1,0,0,0)
MANIFEST="capture_manifest.json"
MAX_BYTES=8_000_000
FILE_BYTES=1_000_000
ALLOWED={"text/html","text/plain","application/json","application/pdf","image/png","image/jpeg","text/csv"}


def _spec(row):
    obj(row,("path","media_type","sha256","bytes","source_ref"))
    path=web_path(row["path"])
    if not isinstance(row["media_type"],str) or row["media_type"] not in ALLOWED:
        raise ContractError("MIME capture belum didukung.")
    return path,digest(row["sha256"]),integer(row["bytes"],"Ukuran capture",1,FILE_BYTES)


def _member(path):
    entry=ZipInfo(path,STAMP)
    entry.create_system=3
    entry.external_attr=(stat.S_IFREG|0o644)<<16
    entry.compress_type=ZIP_STORED
    return entry


def capture(plan,expected,*,transport=fetch):
    checked(plan,expected)
    schema(plan,"ace.web.archive-plan.v1",("origin","source_ref","permission_ref","sources"))
    base,_=origin(plan["origin"])
    source=text(plan["source_ref"],"Rujukan rencana")
    permission=text(plan["permission_ref"],"Bukti izin fixture")
    sources={}
    total=0
    for row in entries(plan["sources"],25,1):
        path,anchor,size=_spec(row)
        if path in sources:
            raise ContractError("Sumber capture ganda.")
        total+=size
        if total>MAX_BYTES:
            raise ContractError("Capture melampaui anggaran total.")
        sources[path]=(anchor,size,row["media_type"],text(row["source_ref"],"Sumber capture"))
    objects={}
    records=[]
    for path,(anchor,size,media,ref) in sorted(sources.items()):
        observed=transport(base,path,cap=size)
        if (observed.status!=200 or observed.error is not None or observed.media_type!=media
                or len(observed.body)!=size or sha256(observed.body).hexdigest()!=anchor):
            raise ContractError(f"Capture tidak cocok pada {path}.")
        objects[f"objects/{anchor}"]=observed.body
        records.append({"path":path,"media_type":media,"sha256":anchor,"bytes":size,"source_ref":ref})
    manifest={"schema":"ace.web.capture-manifest.v1","plan_sha256":expected,"origin":base,
              "source_ref":source,"permission_ref":permission,"sources":records}
    metadata=canonical(manifest)+b"\n"
    with BytesIO() as stream:
        with ZipFile(stream,"w",allowZip64=False) as archive:
            for path,payload in sorted({MANIFEST:metadata,**objects}.items()):
                archive.writestr(_member(path),payload)
        blob=stream.getvalue()
    return blob,{"schema":"ace.web.archive-receipt.v1","plan_sha256":expected,"archive_sha256":sha256(blob).hexdigest(),
                 "manifest_sha256":sha256(metadata).hexdigest(),"sources":len(records),"objects":len(objects),"bytes":len(blob)}


def verify(blob,expected_manifest):
    digest(expected_manifest)
    if not isinstance(blob,bytes) or len(blob)>MAX_BYTES+150_000:
        raise ContractError("Arsip melebihi batas.")
    try:
        with ZipFile(BytesIO(blob)) as archive:
            names=archive.namelist()
            if names!=sorted(set(names)) or MANIFEST not in names or not 2<=len(names)<=26:
                raise ContractError("Anggota arsip ganda atau manifest absen.")
            if any(member.file_size>FILE_BYTES or member.file_size!=member.compress_size or member.compress_type!=ZIP_STORED
                   or member.date_time!=STAMP or member.external_attr!=_member(member.filename).external_attr
                   for member in archive.infolist()):
                raise ContractError("Metadata anggota arsip tidak cocok.")
            metadata=archive.read(MANIFEST)
            if sha256(metadata).hexdigest()!=expected_manifest:
                raise ContractError("Manifest berbeda dari anchor.")
            report=decode(metadata)
            schema(report,"ace.web.capture-manifest.v1",("plan_sha256","origin","source_ref","permission_ref","sources"))
            origin(report["origin"])
            digest(report["plan_sha256"])
            text(report["source_ref"],"Sumber arsip")
            text(report["permission_ref"],"Bukti izin")
            targets={}
            for row in entries(report["sources"],25,1):
                path,anchor,size=_spec(row)
                text(row["source_ref"],"Sumber capture")
                if path in targets:
                    raise ContractError("Rute di manifest ganda.")
                targets[path]=(anchor,size)
            if set(names)!={MANIFEST,*[f"objects/{anchor}" for anchor,_ in targets.values()]}:
                raise ContractError("Inventaris objek berbeda.")
            for path,(anchor,size) in sorted(targets.items()):
                data=archive.read(f"objects/{anchor}")
                if len(data)!=size or sha256(data).hexdigest()!=anchor:
                    raise ContractError(f"Objek rusak untuk {path}.")
    except (BadZipFile,RuntimeError,NotImplementedError) as error:
        raise ContractError("Bentuk ZIP tidak sah.") from error
    return {"schema":"ace.web.archive-verification.v1","manifest_sha256":expected_manifest,
            "archive_sha256":sha256(blob).hexdigest(),"sources":len(targets),"status":"verified"}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest="mode",required=True)
    archive=sub.add_parser("capture")
    archive.add_argument("plan",type=Path)
    archive.add_argument("output",type=Path)
    archive.add_argument("--expect-sha256",required=True)
    validate=sub.add_parser("verify")
    validate.add_argument("archive",type=Path)
    validate.add_argument("--manifest-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        if args.mode=="capture":
            data,result=capture(decode(read(args.plan)),args.expect_sha256)
            with args.output.open("xb") as stream:
                stream.write(data)
        else:
            result=verify(read(args.archive,MAX_BYTES+150_000),args.manifest_sha256)
        sys.stdout.buffer.write(canonical(result)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
