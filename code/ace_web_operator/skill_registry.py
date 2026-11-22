"""Versikan registry skill dari bukti yang dapat dihitung ulang.

Verifier dijalankan ulang dari paket, suite, dan jawaban. Status
ACQUIRED memerlukan receipt controlled yang dicantumkan pada kebijakan
atestasi terpisah. Fixture, bukti kurang, dan temuan mendapat status sendiri.
"""
import argparse
from pathlib import Path
import sys

from . import skill_verifier
from ._contracts import ContractError,canonical,checked,decode,digest,entries,identifier,identity,integer,obj,read,schema,text
from .web_scheduler import time_value


STATES={"ACQUIRED","FIXTURE_VERIFIED","AWAITING_ATTESTATION","NEEDS_REVIEW"}
FIELDS=("skill","cluster","version","status","package_sha256","suite_sha256","verification_sha256",
         "score_bp","at","source_ref","attestation_ref")


def _current(raw):
    schema(raw,"ace.web.skill-registry.v1",("revision","source_ref","entries"))
    tier=integer(raw["revision"],"Revisi registry",0,2**53-2)
    text(raw["source_ref"],"Sumber registry")
    known={}
    for row in entries(raw["entries"],4000):
        obj(row,FIELDS)
        name=identifier(row["skill"],"Skill")
        identifier(row["cluster"],"Klaster")
        integer(row["version"],"Versi",1,100_000)
        integer(row["score_bp"],"Skor",0,10_000)
        time_value(row["at"])
        for key in ("package_sha256","suite_sha256","verification_sha256"):
            digest(row[key])
        if not isinstance(row["status"],str) or row["status"] not in STATES or name in known:
            raise ContractError("Status registry salah atau skill ganda.")
        text(row["source_ref"],"Rujukan entry")
        if row["status"]=="ACQUIRED":
            text(row["attestation_ref"],"Rujukan atestasi")
        elif row["attestation_ref"] is not None:
            raise ContractError("Atestasi disematkan pada status yang salah.")
        known[name]=row
    return tier,known


def _approved(plan):
    verified={}
    for row in entries(plan,4000):
        obj(row,("skill","verification_sha256","package_sha256","authority_ref"))
        name=identifier(row["skill"],"ID skill")
        verification=digest(row["verification_sha256"])
        anchor=digest(row["package_sha256"])
        if verification in verified:
            raise ContractError("Receipt atestasi ganda.")
        verified[verification]=(name,anchor,text(row["authority_ref"],"Rujukan atestasi"))
    return verified


def revise(current,policy,expected,candidates):
    checked(policy,expected)
    schema(policy,"ace.web.skill-registry-policy.v1",("source_ref","previous_sha256","batch_sha256","attested_receipts"))
    checked(current,policy["previous_sha256"])
    checked(candidates,policy["batch_sha256"])
    tier,known=_current(current)
    pointer=text(policy["source_ref"],"Sumber policy registry")
    admissions=_approved(policy["attested_receipts"])
    schema(candidates,"ace.web.skill-verification-batch.v1",("entries",))
    transitions={}
    calculated=[]
    for row in entries(candidates["entries"],120,1):
        obj(row,("source_ref","package","package_sha256","suite","answers","answer_sha256"))
        ref=text(row["source_ref"],"Sumber bundel verifier")
        data,_suite,answers=row["package"],row["suite"],row["answers"]
        proof=skill_verifier.evaluate(data,row["package_sha256"],_suite,answers,row["answer_sha256"])
        anchor=identity(proof)
        name=proof["skill"]
        version=integer(proof["version"],"Versi",1,100_000)
        cluster=identifier(proof["cluster"],"Klaster")
        if name in transitions:
            raise ContractError("Lebih dari satu perubahan skill per batch.")
        historical=known.get(name)
        if historical and (historical["cluster"]!=cluster or version<historical["version"] or
                            proof["at"]<=historical["at"] or version==historical["version"] and
                            historical["package_sha256"]!=proof["package_sha256"]):
            raise ContractError("Versi, klaster, atau urutan bukti tidak konsisten.")
        authority=admissions.get(anchor)
        attestation=None
        if not proof["passed"]:
            state="NEEDS_REVIEW"
        elif proof["scope"]=="fixture":
            state="FIXTURE_VERIFIED"
        elif authority is not None and authority[:2]==(name,proof["package_sha256"]):
            state,attestation="ACQUIRED",authority[2]
        else:
            state="AWAITING_ATTESTATION"
        if historical and historical["status"]=="ACQUIRED" and state=="FIXTURE_VERIFIED":
            raise ContractError("Fixture tidak dapat menggantikan bukti akuisisi yang sudah terdaftar.")
        entry={"skill":name,"cluster":cluster,"version":version,"status":state,
               "package_sha256":proof["package_sha256"],"suite_sha256":proof["suite_sha256"],"verification_sha256":anchor,
               "score_bp":proof["score_bp"],"at":proof["at"],"source_ref":ref,"attestation_ref":attestation}
        known[name]=entry
        transitions[name]={"skill":name,"from":historical["status"] if historical else None,"to":state,
                           "source_ref":ref,"verification_sha256":anchor,"attestation_ref":attestation}
        calculated.append(proof)
    if len(known)>4000:
        raise ContractError("Registry melampaui batas.")
    result={"schema":"ace.web.skill-registry.v1","revision":tier+1,"source_ref":pointer,
            "entries":[known[name] for name in sorted(known)]}
    report={"schema":"ace.web.skill-registry-revision.v1","policy_sha256":expected,"source_ref":pointer,
            "previous_sha256":policy["previous_sha256"],"registry_sha256":identity(result),"revision":tier+1,
            "transitions":[transitions[name] for name in sorted(transitions)],
            "verification_receipts":sorted(calculated,key=lambda row:row["skill"])}
    return result,report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ("registry","policy","batch","output"):
        parser.add_argument(key,type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        state,report=revise(decode(read(args.registry)),decode(read(args.policy)),args.expect_sha256,decode(read(args.batch)))
        with args.output.open("xb") as stream:
            stream.write(canonical(state)+b"\n")
        sys.stdout.buffer.write(canonical(report)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
