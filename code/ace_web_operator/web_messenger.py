"""Siapkan draf pesan pada thread fixture bila izin per tugas cocok.

Izin diikat ke browser, thread, dan body. Runner hanya memverifikasi
nama thread dan nilai kontrol draf, dengan receipt tanpa body atau
aksi kirim. Pesan eksternal tetap berada di meja operator.
"""
import argparse
from pathlib import Path
import sys

from . import browser_engine
from ._contracts import ContractError,canonical,checked,decode,digest,entries,identifier,identity,obj,origin,read,schema,text,web_path


FORBIDDEN={"send","publish","submit","deliver"}


def compile_message(plan,approval,expected):
    checked(plan,expected)
    schema(plan,"ace.web.message-draft-plan.v1",("source_ref","approval_sha256","browser","path","thread_id",
          "thread_selector","thread_label","message_selector","message"))
    checked(approval,plan["approval_sha256"])
    schema(approval,"ace.web.message-authorization.v1",("task","origin","path","thread_id","message_sha256","scope","source_ref"))
    source=text(plan["source_ref"],"Sumber pesan")
    ref=text(approval["source_ref"],"Bukti izin per tugas")
    task=identifier(approval["task"],"Referensi tugas")
    browser=obj(plan["browser"],("origin","allow_paths","timeout_ms","request_limit"))
    base,_=origin(browser["origin"])
    path=web_path(plan["path"])
    thread=identifier(plan["thread_id"],"Thread")
    select_thread=identifier(plan["thread_selector"],"Kontrol thread")
    select_message=identifier(plan["message_selector"],"Kontrol isi")
    body=text(plan["message"],"Isi draf",400)
    label=text(plan["thread_label"],"Label thread",120)
    if ((base,path,thread)!=tuple(approval[field] for field in ("origin","path","thread_id")) or
            approval["scope"]!="draft_only" or digest(approval["message_sha256"])!=identity(body)):
        raise ContractError("Izin berbeda dari draf yang diminta.")
    if select_thread==select_message or FORBIDDEN & set(select_message.split("_")):
        raise ContractError("Kontrol kirim tidak boleh menjadi kontrol draf.")
    if any(set(web_path(value).casefold().split("/"))&FORBIDDEN for value in entries(browser["allow_paths"],70,1)):
        raise ContractError("Rute kirim, publikasi, atau submit dilarang.")
    program={"schema":"ace.web.browser-plan.v1","source_ref":source,**browser,
             "steps":[{"id":"open_thread","op":"navigate","path":path},
                      {"id":"confirm_thread","op":"expect_text","test_id":select_thread,"expected":label},
                      {"id":"draft_message","op":"fill","test_id":select_message,"value":body},
                      {"id":"verify_draft","op":"expect_value","test_id":select_message,"expected":body}]}
    browser_engine.compile_plan(program,identity(program))
    return program,{"source_ref":source,"task":task,"thread_id":thread,"approval_ref":ref,
                    "approval_sha256":plan["approval_sha256"],"message_sha256":approval["message_sha256"]}


def draft(plan,approval,expected,*,browser=browser_engine.run):
    program,metadata=compile_message(plan,approval,expected)
    anchor=identity(program)
    record=browser(program,anchor)
    if record.get("plan_sha256")!=anchor:
        raise ContractError("Receipt menunjuk draft lain.")
    return {"schema":"ace.web.message-draft-receipt.v1","plan_sha256":expected,"browser_sha256":anchor,**metadata,
            "status":"drafted_locally" if record["status"]=="completed" else "held","reason":record["reason"],"sent":False}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan",type=Path)
    parser.add_argument("approval",type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        result=draft(decode(read(args.plan)),decode(read(args.approval)),args.expect_sha256)
        sys.stdout.buffer.write(canonical(result)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return int(result["status"]!="drafted_locally")


if __name__=="__main__":
    raise SystemExit(main())
