"""Rakit paket draft unggahan terjadwal dari aset lokal yang terverifikasi.

Setiap rute publikasi diwakili alias yang diizinkan dan tanggal UTC.
Tool menyalin aset ke paket konten lokal dan memberi daftar preflight.
Worker upload eksternal tidak ikut dijalankan.
"""
import argparse
from hashlib import sha256
from pathlib import Path
import sys

from ._artifact import read_relative,write_new
from ._contracts import ContractError,canonical,checked,decode,digest,entries,identifier,integer,obj,read,relative_path,schema,text
from .web_scheduler import time_value


ALLOWED={"image/png":".png","image/jpeg":".jpg","text/plain":".txt","application/json":".json"}
MAX_BYTES=5_000_000


def _valid_media(payload,media):
    if media=="image/png":
        return payload.startswith(b"\x89PNG\r\n\x1a\n") and len(payload)>=33 and payload[12:16]==b"IHDR"
    if media=="image/jpeg":
        return len(payload)>8 and payload.startswith(b"\xff\xd8\xff") and payload.endswith(b"\xff\xd9")
    if media=="application/json":
        decode(payload)
        return True
    return bool(payload.decode("utf-8").strip())


def prepare(root,plan,expected):
    checked(plan,expected)
    schema(plan,"ace.web.upload-draft-plan.v1",("id","source_ref","channel","channel_ref","intent","as_of","scheduled_at",
                                                "title","description","assets"))
    key=identifier(plan["id"],"ID unggahan")
    source=text(plan["source_ref"],"Sumber unggahan")
    channel=identifier(plan["channel"],"Alias channel")
    channel_ref=text(plan["channel_ref"],"Rujukan channel")
    title=text(plan["title"],"Judul",120)
    caption=text(plan["description"],"Keterangan",500)
    now,due=(time_value(plan[field]) for field in ("as_of","scheduled_at"))
    if plan["intent"]!="draft" or not now<=due<=now+90*86400:
        raise ContractError("Paket perlu intent draft dan jadwal dalam jendela.")
    artifacts={}
    seen=set()
    roster=[]
    byte_count=0
    for row in entries(plan["assets"],12,1):
        obj(row,("id","path","mime","sha256","bytes","source_ref"))
        label=identifier(row["id"],"ID aset")
        mime=row["mime"]
        source_ref=text(row["source_ref"],"Rujukan aset")
        name=relative_path(row["path"])
        if label in seen or not isinstance(mime,str) or mime not in ALLOWED:
            raise ContractError("Aset ganda atau tipe tidak didukung.")
        seen.add(label)
        expected_bytes=integer(row["bytes"],"Ukuran aset",1,MAX_BYTES)
        byte_count+=expected_bytes
        if byte_count>MAX_BYTES:
            raise ContractError("Total aset melebihi anggaran paket.")
        anchor=digest(row["sha256"])
        data=read_relative(root,name,expected_bytes,anchor)
        if len(data)!=expected_bytes or not _valid_media(data,mime):
            raise ContractError(f"Jenis atau ukuran aktual aset berbeda pada {label}.")
        output=f"assets/{label}{ALLOWED[mime]}"
        artifacts[output]=data
        roster.append({"id":label,"relative_path":output,"mime":mime,"bytes":len(data),"sha256":anchor,"source_ref":source_ref})
    draft={"schema":"ace.web.upload-draft.v1","id":key,"channel":channel,"channel_ref":channel_ref,"title":title,
           "description":caption,"scheduled_at":plan["scheduled_at"],"status":"awaiting_operator",
           "assets":sorted(roster,key=lambda row:row["id"]),"plan_sha256":expected}
    payload=canonical(draft)+b"\n"
    report={"schema":"ace.web.upload-preflight.v1","source_ref":source,"plan_sha256":expected,
            "draft_sha256":sha256(payload).hexdigest(),"assets":len(roster),"asset_bytes":byte_count,
            "status":"prepared_locally","published":False,"checklist":["asset_bytes_verified","local_schedule_validated",
                                                                      "operator_review_pending"]}
    return {**artifacts,"upload_draft.json":payload,"preflight.json":canonical(report)+b"\n"},report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ("root","plan","output"):
        parser.add_argument(key,type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        files,result=prepare(args.root,decode(read(args.plan)),args.expect_sha256)
        write_new(args.output,files)
        sys.stdout.buffer.write(canonical(result)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
