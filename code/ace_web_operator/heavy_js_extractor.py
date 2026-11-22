"""Ekstrak HTML hasil render fixture setelah penanda kesiapan terbukti.

Isi DOM diperoleh dari satu wilayah yang ditentukan. Runner menambatkan
byte capture sebelum parser field berjalan. Laporan data mengacu pada
snapshot hasil render dan bukti bahwa kondisi siap sudah terpenuhi.
"""
import argparse
from base64 import b64decode
from binascii import Error as InvalidBase64
from hashlib import sha256
from pathlib import Path
import sys

from . import browser_engine,page_extractor
from ._artifact import write_new
from ._contracts import ContractError,canonical,checked,decode,digest,identifier,identity,integer,obj,read,schema,text,web_path


def _bytes(raw):
    obj(raw,("html_base64","bytes","sha256"))
    cap=integer(raw["bytes"],"Ukuran DOM",1,160_000)
    anchor=digest(raw["sha256"])
    value=raw["html_base64"]
    if not isinstance(value,str) or len(value)>220_000:
        raise ContractError("Capture DOM tidak sah.")
    try:
        payload=b64decode(value,validate=True)
    except InvalidBase64 as error:
        raise ContractError("Capture DOM bukan base64.") from error
    if len(payload)!=cap or sha256(payload).hexdigest()!=anchor:
        raise ContractError("Hash DOM tidak cocok.")
    return payload,anchor


def extract(plan,expected,*,browser=browser_engine.run):
    checked(plan,expected)
    schema(plan,"ace.web.dynamic-extract-plan.v1",("source_ref","browser","path","ready","container","layout","min_records"))
    source=text(plan["source_ref"],"Rujukan ekstraksi")
    config=obj(plan["browser"],("origin","allow_paths","timeout_ms","request_limit"))
    path=web_path(plan["path"])
    ready=obj(plan["ready"],("test_id","text"))
    location=identifier(plan["container"],"Area DOM")
    witness=identifier(ready["test_id"],"Penanda siap")
    signal=text(ready["text"],"Kondisi siap",250)
    rules=obj(plan["layout"],("row_tag","row_class","primary","fields"))
    floor=integer(plan["min_records"],"Baris minimum",1,1500)
    recipe={"schema":"ace.web.browser-plan.v1","source_ref":source,**config,
            "steps":[{"id":"open","op":"navigate","path":path},
                     {"id":"wait","op":"wait_text","test_id":witness,"expected":signal},
                     {"id":"capture","op":"capture_dom","test_id":location}]}
    browser_engine.compile_plan(recipe,identity(recipe))
    job=identity(recipe)
    receipt=browser(recipe,job)
    if receipt.get("plan_sha256")!=job:
        raise ContractError("Receipt browser tidak sesuai rencana ekstraksi.")
    output={"schema":"ace.web.dynamic-extract-receipt.v1","plan_sha256":expected,"browser_sha256":job,
            "source_ref":source,"status":"held","reason":receipt["reason"],"extraction":None}
    if receipt["status"]!="completed":
        return {},output
    dom,key=_bytes(receipt["steps"][-1]["evidence"])
    name=f"rendered-{key[:20]}.html"
    spec={"schema":"ace.web.extract-plan.v1","source_ref":source,"html_ref":name,"html_sha256":key,**rules}
    report=page_extractor.extract(dom,spec,identity(spec))
    status="extracted" if report["status"]=="complete" and report["valid"]>=floor else "held"
    output.update(status=status,reason=None if status=="extracted" else "extraction_incomplete",extraction=report)
    return {name:dom,"dynamic_receipt.json":canonical(output)+b"\n"},output


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan",type=Path)
    parser.add_argument("output",type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        artifacts,report=extract(decode(read(args.plan)),args.expect_sha256)
        if artifacts:
            write_new(args.output,artifacts)
        sys.stdout.buffer.write(canonical(report)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return int(report["status"]!="extracted")


if __name__=="__main__":
    raise SystemExit(main())
