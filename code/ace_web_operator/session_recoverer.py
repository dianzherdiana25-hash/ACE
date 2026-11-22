"""Pulihkan kemacetan workflow dari checkpoint terbaca dan bertanda hash.

Resume membangun ulang halaman serta assertion checkpoint, lalu
meneruskan langkah baca yang terdaftar. Field tertulis atau aksi yang
mungkin sudah berefek ditahan untuk pemeriksaan operator.
"""
import argparse
from pathlib import Path
import sys

from . import browser_engine
from ._contracts import ContractError,canonical,checked,decode,digest,entries,identifier,identity,obj,read,schema,text,web_path


REPLAY_SAFE={"navigate","expect_url","expect_title","expect_text","read_text"}


def _compile(plan,checkpoint,expected):
    checked(plan,expected)
    schema(plan,"ace.web.resume-plan.v1",("source_ref","workflow_sha256","checkpoint_sha256","browser","steps"))
    source=text(plan["source_ref"],"Sumber resume")
    workflow=digest(plan["workflow_sha256"])
    checked(checkpoint,plan["checkpoint_sha256"])
    schema(checkpoint,"ace.web.session-checkpoint.v1",("workflow_sha256","source_ref","current_path","assertion",
           "confirmed_steps","unconfirmed_effect"))
    pointer=text(checkpoint["source_ref"],"Rujukan checkpoint")
    if checkpoint["workflow_sha256"]!=workflow or type(checkpoint["unconfirmed_effect"]) is not bool:
        raise ContractError("Checkpoint berbeda dari workflow yang dikonfirmasi.")
    profile=obj(plan["browser"],("origin","allow_paths","timeout_ms","request_limit"))
    current=web_path(checkpoint["current_path"])
    assertion=obj(checkpoint["assertion"],("test_id","expected"))
    witness=identifier(assertion["test_id"],"Selector checkpoint")
    expected_value=text(assertion["expected"],"Bukti checkpoint",400)
    verified=[identifier(key,"ID langkah selesai") for key in entries(checkpoint["confirmed_steps"],100)]
    if len(set(verified))!=len(verified):
        raise ContractError("Checkpoint memuat ID langkah ganda.")
    remaining=[]
    for row in entries(plan["steps"],browser_engine.MAX_OPERATIONS-2,1):
        if not isinstance(row,dict):
            raise ContractError("Langkah resume perlu objek.")
        key=identifier(row.get("id"),"ID tahap resume")
        if key not in verified:
            remaining.append(row)
    result={"schema":"ace.web.resume-receipt.v1","plan_sha256":expected,"workflow_sha256":workflow,
            "checkpoint_sha256":plan["checkpoint_sha256"],"source_ref":source,"checkpoint_ref":pointer,
            "completed_before":verified,"resumed_steps":[],"status":"held","reason":"effect_requires_operator"}
    if checkpoint["unconfirmed_effect"] or any(row.get("op") not in REPLAY_SAFE for row in remaining):
        return None,result
    operations=[{"id":"restore_checkpoint","op":"navigate","path":current},
                {"id":"verify_checkpoint","op":"expect_text","test_id":witness,"expected":expected_value},*remaining]
    browser={"schema":"ace.web.browser-plan.v1","source_ref":source,**profile,"steps":operations}
    browser_engine.compile_plan(browser,identity(browser))
    return browser,result


def recover(plan,checkpoint,expected,*,browser=browser_engine.run):
    job,report=_compile(plan,checkpoint,expected)
    if job is None:
        return report
    anchor=identity(job)
    evidence=browser(job,anchor)
    if evidence.get("plan_sha256")!=anchor:
        raise ContractError("Receipt resume menunjuk kontrak browser berbeda.")
    observations=evidence["steps"]
    reopened=len(observations)>=2 and observations[1]["status"]=="ok"
    state="resumed" if evidence["status"]=="completed" else "held"
    return {**report,"status":state,"reason":evidence["reason"],"browser_sha256":anchor,
            "checkpoint_reverified":reopened,"resumed_steps":observations[2:] if reopened else []}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ("plan","checkpoint"):
        parser.add_argument(key,type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        result=recover(decode(read(args.plan)),decode(read(args.checkpoint)),args.expect_sha256)
        sys.stdout.buffer.write(canonical(result)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return int(result["status"]!="resumed")


if __name__=="__main__":
    raise SystemExit(main())
