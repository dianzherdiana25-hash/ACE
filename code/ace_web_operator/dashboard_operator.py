"""Jalankan inspeksi panel lokal dari daftar tampilan baca tersetujui.

Setiap tampilan harus berhasil mengonfirmasi judul dan indikator data.
Kontrol yang didaftarkan bertipe navigasi atau filter. Isi dashboard
direpresentasikan dengan hash bukti di receipt, tanpa mutasi admin.
"""
import argparse
from pathlib import Path
import sys

from . import browser_engine
from ._contracts import ContractError,canonical,checked,decode,entries,identifier,identity,obj,origin,read,schema,text,web_path


FORBIDDEN={"delete","edit","publish","submit","write","save","remove","transfer","checkout"}


def _controls(config):
    controls={}
    for row in entries(config["controls"],40):
        obj(row,("id","kind","test_id"))
        key=identifier(row["id"],"Kontrol panel")
        locator=identifier(row["test_id"],"Selector panel")
        if key in controls or row["kind"] not in ("tab","filter") or (FORBIDDEN & set(locator.split("_"))):
            raise ContractError("Kontrol mutasi atau kontrol tak dikenal tidak boleh masuk panel baca.")
        controls[key]=(row["kind"],locator)
    return controls


def plan_dashboard(plan,expected,panel):
    checked(plan,expected)
    schema(plan,"ace.web.dashboard-plan.v1",("source_ref","panel_sha256","permission_ref","browser","view","actions"))
    checked(panel,plan["panel_sha256"])
    schema(panel,"ace.web.dashboard-panel.v1",("source_ref","origin","views"))
    source=text(plan["source_ref"],"Sumber inspeksi")
    approval=text(plan["permission_ref"],"Rujukan izin baca")
    browser=obj(plan["browser"],("origin","allow_paths","timeout_ms","request_limit"))
    base,_=origin(browser["origin"])
    if base!=panel["origin"]:
        raise ContractError("Origin berbeda dari spesifikasi dashboard.")
    views={}
    for raw in entries(panel["views"],50,1):
        obj(raw,("id","path","title","controls","verify_test_id","verify_text","source_ref"))
        key=identifier(raw["id"],"Tampilan")
        if key in views:
            raise ContractError("Tampilan dashboard ganda.")
        views[key]=raw
    name=identifier(plan["view"],"Tampilan")
    if name not in views:
        raise ContractError("Tampilan tidak terdaftar.")
    current=views[name]
    path=web_path(current["path"])
    if any(FORBIDDEN & set(web_path(url).casefold().split("/")) for url in entries(browser["allow_paths"],70,1)):
        raise ContractError("Rute mutasi tidak boleh diizinkan.")
    controls=_controls(current)
    actions=[identifier(key,"Aksi baca") for key in entries(plan["actions"],20)]
    if set(actions)-controls.keys() or len(set(actions))!=len(actions):
        raise ContractError("Aksi dashboard ganda atau tidak terdaftar.")
    steps=[{"id":"open_dashboard","op":"navigate","path":path},
           {"id":"confirm_title","op":"expect_title","expected":text(current["title"],"Judul dashboard",200)}]
    for index,action in enumerate(actions,1):
        steps.append({"id":f"select_view_{index}","op":"click","test_id":controls[action][1]})
    steps.append({"id":"read_dashboard","op":"expect_text","test_id":identifier(current["verify_test_id"],"Selector bukti"),
                  "expected":text(current["verify_text"],"Isi harapan",350)})
    program={"schema":"ace.web.browser-plan.v1","source_ref":source,**browser,"steps":steps}
    browser_engine.compile_plan(program,identity(program))
    return program,{"source_ref":source,"permission_ref":approval,"view":name,
                    "view_ref":text(current["source_ref"],"Sumber tampilan"),"actions":actions}


def inspect(plan,expected,panel,*,browser=browser_engine.run):
    program,metadata=plan_dashboard(plan,expected,panel)
    anchor=identity(program)
    report=browser(program,anchor)
    if report.get("plan_sha256")!=anchor:
        raise ContractError("Receipt berbeda dari inspeksi dashboard.")
    complete=report["status"]=="completed"
    return {"schema":"ace.web.dashboard-receipt.v1","plan_sha256":expected,"browser_sha256":anchor,**metadata,
            "status":"verified_read" if complete else "held","reason":report["reason"],
            "proof":report["steps"][-1]["evidence"] if complete else None}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ("plan","panel"):
        parser.add_argument(key,type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        report=inspect(decode(read(args.plan)),args.expect_sha256,decode(read(args.panel)))
        sys.stdout.buffer.write(canonical(report)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return int(report["status"]!="verified_read")


if __name__=="__main__":
    raise SystemExit(main())
