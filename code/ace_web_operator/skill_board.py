"""Tampilkan skill yang diminta dan bukti aktual dari registry terikat.

Roadmap menentukan denominator. Hanya status yang memiliki atestasi
dihitung sebagai acquired. Bukti basi tampil sebagai rapuh, dan fixture
atau status hilang tetap dipisahkan dari akuisisi.
"""
import argparse
from collections import Counter
from pathlib import Path
import sys

from ._contracts import ContractError,canonical,checked,decode,digest,entries,identifier,obj,read,schema,text
from .skill_registry import _current


def _freshness(raw):
    schema(raw,"ace.web.skill-staleness-report.v1",("plan_sha256","source_ref","registry_sha256","versions_sha256",
                                                    "as_of","skills","unregistered_versions"))
    values={}
    for row in entries(raw["skills"],4000):
        obj(row,("skill","cluster","status","reasons","age_seconds","verification_sha256","registry_ref","version_ref",
                 "age_rule_ref","retention"))
        key=identifier(row["skill"],"Skill staleness")
        state=row["status"]
        if key in values or not isinstance(state,str) or state not in ("CURRENT","STALE","UNKNOWN","UNVERIFIED"):
            raise ContractError("Status staleness ambigu.")
        digest(row["verification_sha256"])
        values[key]=row
    return values


def build(plan,expected,roadmap,registry,staleness=None):
    checked(plan,expected)
    schema(plan,"ace.web.skill-board-plan.v1",("source_ref","roadmap_sha256","registry_sha256","staleness_sha256"))
    checked(roadmap,plan["roadmap_sha256"])
    checked(registry,plan["registry_sha256"])
    source=text(plan["source_ref"],"Sumber papan")
    schema(roadmap,"ace.web.skill-roadmap.v1",("source_ref","clusters"))
    roadmap_ref=text(roadmap["source_ref"],"Sumber roadmap")
    _,known=_current(registry)
    states={}
    if plan["staleness_sha256"] is not None or staleness is not None:
        checked(staleness,plan["staleness_sha256"])
        states=_freshness(staleness)
        if staleness["registry_sha256"]!=plan["registry_sha256"]:
            raise ContractError("Staleness merujuk revisi registry yang berbeda.")
    clusters={}
    visited=set()
    counts=Counter()
    for raw in entries(roadmap["clusters"],250,1):
        obj(raw,("id","title","domain","source_ref","skills"))
        cluster=identifier(raw["id"],"Klaster")
        if cluster in clusters:
            raise ContractError("Klaster roadmap ganda.")
        title=text(raw["title"],"Judul klaster",90)
        domain=identifier(raw["domain"],"Domain")
        ref=text(raw["source_ref"],"Rujukan klaster")
        rows=[]
        for item in entries(raw["skills"],30,1):
            obj(item,("id","title","source_ref"))
            key=identifier(item["id"],"ID roadmap")
            if key in visited:
                raise ContractError("Skill roadmap ganda.")
            visited.add(key)
            label=text(item["title"],"Judul skill",120)
            pointer=text(item["source_ref"],"Rujukan skill")
            observed=known.get(key)
            current=states.get(key)
            if observed and observed["cluster"]!=cluster or current and current["cluster"]!=cluster or (
                    observed and current and observed["verification_sha256"]!=current["verification_sha256"]
            ):
                raise ContractError("Bukti skill tidak konsisten dengan roadmap.")
            if observed is None:
                status,reason="MISSING","registry_entry_absent"
            elif observed["status"]!="ACQUIRED":
                status,reason="MISSING",observed["status"]
            elif current and current["status"]!="CURRENT":
                status,reason="FRAGILE",current["status"]
            else:
                status,reason="ACQUIRED",None
            counts[status]+=1
            rows.append({"id":key,"title":label,"source_ref":pointer,"status":status,"reason":reason,
                         "registry_ref":observed["source_ref"] if observed else None,
                         "attestation_ref":observed["attestation_ref"] if observed else None,
                         "verification_sha256":observed["verification_sha256"] if observed else None,
                         "freshness_status":current["status"] if current else None})
        clusters[cluster]={"id":cluster,"title":title,"domain":domain,"source_ref":ref,"skills":rows}
    return {"schema":"ace.web.skill-board-report.v1","plan_sha256":expected,"source_ref":source,"roadmap_ref":roadmap_ref,
            "roadmap_sha256":plan["roadmap_sha256"],"registry_sha256":plan["registry_sha256"],
            "staleness_sha256":plan["staleness_sha256"],"counts":{status:counts[status] for status in ("ACQUIRED","FRAGILE","MISSING")},
            "skills_requested":len(visited),"clusters":[clusters[key] for key in sorted(clusters)],
            "unlisted_registry_skills":sorted(known.keys()-visited)}


def markdown(data):
    def clean(value):
        return value.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace("|","\\|")
    census=data["counts"]
    lines=["# Papan skill","",f"Roadmap {clean(data['roadmap_ref'])}.",
           f"Registry SHA-256 `{data['registry_sha256']}`.","",
           f"Diminta {data['skills_requested']} · ACQUIRED {census['ACQUIRED']} · FRAGILE {census['FRAGILE']} · MISSING {census['MISSING']}.",""]
    for cluster in data["clusters"]:
        lines.extend([f"## {clean(cluster['title'])}","",
                      "| Skill | Status | Penunjuk |","|---|---|---|"])
        for row in cluster["skills"]:
            pointer=row["attestation_ref"] if row["attestation_ref"] else row["source_ref"]
            lines.append(f"| {clean(row['title'])} | {row['status']} | {clean(pointer)} |")
        lines.append("")
    return "\n".join(lines)+"\n"


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ("plan","roadmap","registry"):
        parser.add_argument(key,type=Path)
    parser.add_argument("--staleness",type=Path)
    parser.add_argument("--expect-sha256",required=True)
    parser.add_argument("--markdown",action="store_true")
    args=parser.parse_args(argv)
    try:
        answer=build(decode(read(args.plan)),args.expect_sha256,decode(read(args.roadmap)),decode(read(args.registry)),
                     decode(read(args.staleness)) if args.staleness else None)
        sys.stdout.buffer.write(markdown(answer).encode() if args.markdown else canonical(answer)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
