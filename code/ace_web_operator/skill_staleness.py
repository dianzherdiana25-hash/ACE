"""Periksa kesegaran skill dari versi, umur bukti, dan retensi terdaftar.

Bukti yang hilang tidak dinilai setara dengan bukti lama. Ambang waktu
ditetapkan per klaster, dan perubahan paket selalu tercatat terpisah.
Tool membaca snapshot tanpa mengubah registry.
"""
import argparse
from pathlib import Path
import sys

from ._contracts import ContractError,canonical,checked,decode,digest,entries,identifier,integer,obj,read,schema,text
from .skill_registry import _current
from .web_scheduler import time_value


def scan(plan,expected,registry,versions):
    checked(plan,expected)
    schema(plan,"ace.web.skill-staleness-plan.v1",("source_ref","registry_sha256","versions_sha256","as_of","cluster_limits"))
    checked(registry,plan["registry_sha256"])
    checked(versions,plan["versions_sha256"])
    _,recorded=_current(registry)
    schema(versions,"ace.web.skill-version-snapshot.v1",("source_ref","entries"))
    source=text(plan["source_ref"],"Sumber usia skill")
    now=time_value(plan["as_of"])
    limits={}
    for row in entries(plan["cluster_limits"],200,1):
        obj(row,("cluster","days","source_ref"))
        key=identifier(row["cluster"],"Klaster")
        if key in limits:
            raise ContractError("Kebijakan klaster ganda.")
        limits[key]=(integer(row["days"],"Retensi hari",1,1095),text(row["source_ref"],"Sumber ambang"))
    variants={}
    text(versions["source_ref"],"Sumber manifest versi")
    for row in entries(versions["entries"],4500):
        obj(row,("id","current_version","package_sha256","source_ref","retention"))
        key=identifier(row["id"],"Skill")
        if key in variants:
            raise ContractError("Versi aktif ganda.")
        proof=row["retention"]
        if proof is not None:
            obj(proof,("status","source_ref","package_sha256","receipt_sha256"))
            digest(proof["receipt_sha256"])
            digest(proof["package_sha256"])
            text(proof["source_ref"],"Sumber retensi")
            if proof["status"] not in ("retained","fragile","unmeasured"):
                raise ContractError("Status retensi tidak dikenal.")
        variants[key]=(integer(row["current_version"],"Versi",1,100_000),digest(row["package_sha256"]),
                       text(row["source_ref"],"Sumber versi"),proof)
    reports=[]
    for key,entry in sorted(recorded.items()):
        age=now-time_value(entry["at"])
        if age<0:
            raise ContractError("Bukti registry berasal dari masa depan.")
        reason=[]
        actual=variants.get(key)
        rule=limits.get(entry["cluster"])
        if entry["status"]!="ACQUIRED":
            state="UNVERIFIED"
            reason.append("acquisition_not_verified")
        else:
            if actual is None:
                reason.append("active_version_missing")
            elif (entry["version"],entry["package_sha256"])!=actual[:2]:
                reason.append("version_drift")
            elif actual[3] and actual[3]["package_sha256"]!=entry["package_sha256"]:
                reason.append("retention_scope_mismatch")
            elif actual[3] and actual[3]["status"]=="fragile":
                reason.append("retention_dropped")
            if not rule:
                reason.append("cluster_age_limit_missing")
            elif age>=rule[0]*86400:
                reason.append("verification_expired")
            if {"version_drift","retention_dropped","verification_expired"}&set(reason):
                state="STALE"
            elif reason:
                state="UNKNOWN"
            else:
                state="CURRENT"
        reports.append({"skill":key,"cluster":entry["cluster"],"status":state,"reasons":reason,"age_seconds":age,
                        "verification_sha256":entry["verification_sha256"],"registry_ref":entry["source_ref"],
                        "version_ref":actual[2] if actual else None,"age_rule_ref":rule[1] if rule else None,
                        "retention":actual[3] if actual else None})
    return {"schema":"ace.web.skill-staleness-report.v1","plan_sha256":expected,"source_ref":source,
            "registry_sha256":plan["registry_sha256"],"versions_sha256":plan["versions_sha256"],"as_of":plan["as_of"],
            "skills":reports,"unregistered_versions":sorted(variants.keys()-recorded.keys())}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ("plan","registry","versions"):
        parser.add_argument(key,type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        data=scan(decode(read(args.plan)),args.expect_sha256,decode(read(args.registry)),decode(read(args.versions)))
        sys.stdout.buffer.write(canonical(data)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
