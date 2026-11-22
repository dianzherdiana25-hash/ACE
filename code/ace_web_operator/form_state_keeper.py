"""Simpan state field biasa agar form fixture dapat dilanjutkan.

Checkpoint ditambatkan ke versi form, scope field dan waktu simpan.
Scope menolak field credential atau pembayaran. Restore memeriksa
seluruh checkpoint sebelum menyusun pengisian tanpa submit.
"""
import argparse
from pathlib import Path
import re
import sys

from . import browser_engine,form_filler
from ._contracts import ContractError,canonical,checked,decode,digest,entries,identifier,identity,schema,read,text
from .web_scheduler import time_value


SENSITIVE=re.compile(r"(?:^|_)(password|passcode|pin|token|secret|payment|credit|api_key|card|credential)(?:_|$)")


def _scope(policy,expected,form):
    checked(policy,expected)
    schema(policy,"ace.web.form-checkpoint-policy.v1",("source_ref","form_sha256","fields","expires_at"))
    checked(form,policy["form_sha256"])
    text(policy["source_ref"],"Rujukan checkpoint")
    permit=[identifier(name,"Field checkpoint") for name in entries(policy["fields"],30,1)]
    if any(SENSITIVE.search(name) for name in permit) or len(set(permit))!=len(permit):
        raise ContractError("Scope field ganda atau sensitif.")
    schema(form,"ace.web.form-plan.v1",("source_ref","browser","path","fields"))
    known={row["id"]:row for row in form["fields"]}
    if set(permit)-known.keys() or any(SENSITIVE.search(known[name]["test_id"]) for name in permit):
        raise ContractError("Scope checkpoint di luar field aman yang terdaftar.")
    time_value(policy["expires_at"])
    return set(permit)


def save(policy,expected,form,assignment,at):
    allowed=_scope(policy,expected,form)
    schema(assignment,"ace.web.form-assignment.v1",("form_sha256","values","source_ref"))
    vals=assignment["values"]
    when=time_value(at)
    if not isinstance(vals,dict) or vals.keys()-allowed or when>=time_value(policy["expires_at"]):
        raise ContractError("Assignment di luar scope atau waktu checkpoint.")
    form_filler.compile_form(form,assignment,policy["form_sha256"])
    return {"schema":"ace.web.form-checkpoint.v1","policy_sha256":expected,"form_sha256":policy["form_sha256"],
            "at":at,"source_ref":policy["source_ref"],"assignment_sha256":identity(assignment),"assignment":assignment}


def restore(policy,expected,form,checkpoint,anchor,now,*,browser=browser_engine.run):
    allowed=_scope(policy,expected,form)
    checked(checkpoint,anchor)
    schema(checkpoint,"ace.web.form-checkpoint.v1",("policy_sha256","form_sha256","at","source_ref",
                                                    "assignment_sha256","assignment"))
    raw=checkpoint["assignment"]
    checked(raw,checkpoint["assignment_sha256"])
    lower,upper=time_value(checkpoint["at"]),time_value(policy["expires_at"])
    current=time_value(now)
    if (checkpoint["policy_sha256"]!=expected or checkpoint["form_sha256"]!=policy["form_sha256"]
            or raw["values"].keys()-allowed or not lower<=current<upper):
        raise ContractError("Checkpoint tidak berlaku untuk versi form atau waktu saat ini.")
    observed=form_filler.fill(form,raw,policy["form_sha256"],browser=browser)
    return {"schema":"ace.web.form-restore-receipt.v1","policy_sha256":expected,"checkpoint_sha256":anchor,
            "form_sha256":policy["form_sha256"],"source_ref":policy["source_ref"],"submitted":False,
            "status":"restored_locally" if observed["status"]=="filled_locally" else "held","receipt":observed}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action",choices=("save","restore"))
    for key in ("policy","form","input"):
        parser.add_argument(key,type=Path)
    parser.add_argument("--expect-sha256",required=True)
    parser.add_argument("--checkpoint-sha256")
    parser.add_argument("--at",required=True)
    parser.add_argument("--output",type=Path)
    args=parser.parse_args(argv)
    try:
        source=decode(read(args.policy)),args.expect_sha256,decode(read(args.form)),decode(read(args.input))
        if args.action=="save":
            if args.output is None:
                parser.error("Save perlu --output.")
            entity=save(*source,args.at)
            with args.output.open("xb") as stream:
                stream.write(canonical(entity)+b"\n")
            result={"status":"saved","checkpoint_sha256":identity(entity),"form_sha256":entity["form_sha256"]}
        else:
            result=restore(*source,digest(args.checkpoint_sha256),args.at)
        sys.stdout.buffer.write(canonical(result)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return int(result["status"]=="held")


if __name__=="__main__":
    raise SystemExit(main())
