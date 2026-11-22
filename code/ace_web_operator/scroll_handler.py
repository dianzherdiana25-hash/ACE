"""Ambil inventaris dari pagination atau panel gulir fixture secara berbatas.

Loop berhenti di penanda akhir, batas putaran, atau keadaan tanpa
kemajuan. ID record dideduplikasi lintas permukaan dan ditulis sebagai
hash. Cakupan tidak dinyatakan lengkap tanpa penanda akhir.
"""
import argparse
from pathlib import Path
import sys

from . import browser_engine
from ._contracts import ContractError,canonical,checked,decode,digest,entries,identifier,identity,integer,obj,read,schema,text,web_path


def collect(plan,expected,*,browser=browser_engine.run):
    checked(plan,expected)
    schema(plan,"ace.web.scroll-plan.v1",("source_ref","browser","path","list_test_id","end_test_id","next_test_id",
                                          "max_turns","minimum_items"))
    pointer=text(plan["source_ref"],"Rujukan pagination")
    config=obj(plan["browser"],("origin","allow_paths","timeout_ms","request_limit"))
    path=web_path(plan["path"])
    listing=identifier(plan["list_test_id"],"Selector daftar")
    end=identifier(plan["end_test_id"],"Selector penanda akhir")
    next_page=identifier(plan["next_test_id"],"Selector halaman lanjut") if plan["next_test_id"] is not None else None
    selectors=[listing,end]+([next_page] if next_page else [])
    if len(set(selectors))!=len(selectors):
        raise ContractError("Selector pagination ganda.")
    turns=integer(plan["max_turns"],"Batas langkah",1,12)
    minimum=integer(plan["minimum_items"],"Batas item",1,2000)
    job={"schema":"ace.web.browser-plan.v1","source_ref":pointer,**config,
         "steps":[{"id":"open_list","op":"navigate","path":path},
                   {"id":"collect_pages","op":"scroll_collect","test_id":listing,"end_test_id":end,
                    "next_test_id":next_page,"max_turns":turns}]}
    browser_engine.compile_plan(job,identity(job))
    anchor=identity(job)
    receipt=browser(job,anchor)
    if receipt.get("plan_sha256")!=anchor:
        raise ContractError("Receipt berasal dari sesi lain.")
    result={"schema":"ace.web.scroll-receipt.v1","plan_sha256":expected,"source_ref":pointer,"browser_sha256":anchor,
            "strategy":"pagination" if next_page else "infinite_scroll","status":"held","reason":receipt["reason"],
            "observed":[],"item_hashes":[],"unique":None}
    if receipt["status"]!="completed":
        return result
    evidence=obj(receipt["steps"][-1]["evidence"],("terminal","stalled","counts","member_sha256"))
    if type(evidence["terminal"]) is not bool or type(evidence["stalled"]) is not bool or (
            evidence["terminal"] and evidence["stalled"]):
        raise ContractError("Status traversal tidak konsisten.")
    hashes=[digest(value) for value in entries(evidence["member_sha256"],min(5200,(turns+1)*400))]
    rows=entries(evidence["counts"],turns+1,1)
    prior=0
    for index,row in enumerate(rows):
        obj(row,("turn","visible","unique"))
        count=integer(row["visible"],"Jumlah terlihat",0,400)
        prior=integer(row["unique"],"Jumlah kumulatif",prior,min(len(hashes),prior+count))
        if row["turn"]!=index or count>prior:
            raise ContractError("Urutan putaran atau hitungan tidak sah.")
    if prior!=len(hashes) or sorted(set(hashes))!=hashes:
        raise ContractError("Hash anggota atau jumlah traversal tidak cocok.")
    reason=("stalled" if evidence["stalled"] else "turn_limit" if not evidence["terminal"] else
            "minimum_items_missing" if len(hashes)<minimum else None)
    return {**result,"status":"complete" if reason is None else "partial","reason":reason,
            "observed":rows,"item_hashes":hashes,"unique":prior,"end_reached":evidence["terminal"]}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan",type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        report=collect(decode(read(args.plan)),args.expect_sha256)
        sys.stdout.buffer.write(canonical(report)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return int(report["status"]!="complete")


if __name__=="__main__":
    raise SystemExit(main())
