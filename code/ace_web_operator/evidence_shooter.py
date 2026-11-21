"""Tangkap satu wilayah bukti yang didaftarkan dari browser loopback.

Screenshot hanya diambil setelah assertion lulus. Artefak PNG dan
receipt menunjuk hash yang sama. Receipt tidak memuat byte gambar,
dan area capture dibatasi oleh selector fixture serta geometri.
"""
import argparse
from base64 import b64decode
from binascii import Error as B64Error
from hashlib import sha256
from pathlib import Path
from struct import unpack
import sys

from . import browser_engine
from ._contracts import ContractError,canonical,checked,decode,digest,identifier,identity,integer,obj,read,schema,text,web_path


PNG=b"\x89PNG\r\n\x1a\n"


def inspect_png(record):
    obj(record,("png_base64","sha256","bytes"))
    size=integer(record["bytes"],"Ukuran capture",33,600_000)
    anchor=digest(record["sha256"])
    encoded=record["png_base64"]
    if not isinstance(encoded,str) or len(encoded)>800_000:
        raise ContractError("Capture base64 di luar batas.")
    try:
        picture=b64decode(encoded,validate=True)
    except B64Error as error:
        raise ContractError("Capture base64 tidak sah.") from error
    if len(picture)!=size or sha256(picture).hexdigest()!=anchor or not picture.startswith(PNG) or picture[12:16]!=b"IHDR":
        raise ContractError("Capture tidak cocok dengan hash atau PNG.")
    width,height=unpack(">II",picture[16:24])
    if not 1<=width<=1101 or not 1<=height<=801:
        raise ContractError("Dimensi capture di luar batas.")
    return picture,{"sha256":anchor,"bytes":size,"width":width,"height":height}


def shoot(plan,expected,*,browser=browser_engine.run):
    checked(plan,expected)
    schema(plan,"ace.web.screenshot-plan.v1",("source_ref","browser","path","test_id","assertion","capture_ref"))
    source=text(plan["source_ref"],"Sumber rencana")
    output_ref=text(plan["capture_ref"],"Rujukan artefak")
    target=identifier(plan["test_id"],"Selector screenshot")
    settings=obj(plan["browser"],("origin","allow_paths","timeout_ms","request_limit"))
    path=web_path(plan["path"])
    assertion=obj(plan["assertion"],("test_id","expected"))
    proof=identifier(assertion["test_id"],"Selector assertion")
    required=text(assertion["expected"],"Teks harapan",400)
    job={"schema":"ace.web.browser-plan.v1","source_ref":source,**settings,
         "steps":[{"id":"open_page","op":"navigate","path":path},
                  {"id":"verify_page","op":"expect_text","test_id":proof,"expected":required},
                  {"id":"capture","op":"screenshot","test_id":target}]}
    anchor=identity(job)
    receipt=browser(job,anchor)
    if receipt.get("plan_sha256")!=anchor:
        raise ContractError("Receipt capture menunjuk rencana berbeda.")
    result={"schema":"ace.web.screenshot-receipt.v1","plan_sha256":expected,"browser_sha256":anchor,
            "source_ref":source,"capture_ref":output_ref,"path":path,"status":"held","reason":receipt["reason"],"png":None}
    if receipt["status"]!="completed":
        return None,result
    if [row["id"] for row in receipt["steps"]]!=["open_page","verify_page","capture"]:
        raise ContractError("Receipt capture tidak lengkap.")
    picture,metadata=inspect_png(receipt["steps"][-1]["evidence"])
    return picture,{**result,"status":"captured","reason":None,"png":metadata}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan",type=Path)
    parser.add_argument("output",type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        data,result=shoot(decode(read(args.plan)),args.expect_sha256)
        if data is not None:
            with args.output.open("xb") as stream:
                stream.write(data)
        sys.stdout.buffer.write(canonical(result)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return int(result["status"]!="captured")


if __name__=="__main__":
    raise SystemExit(main())
