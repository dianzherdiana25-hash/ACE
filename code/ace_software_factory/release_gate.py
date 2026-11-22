"""Nilai kesiapan rilis lokal dari acceptance, coverage, SAST dan ZIP.

Bukti harus terikat pada snapshot sumber yang sama. Gerbang memeriksa
berkas receipt terhadap hash yang ditentukan kebijakan. Hasil hanya
daftar blokir atau kesiapan untuk telaah, tanpa tindakan rilis.
"""
import argparse
from pathlib import Path
import sys

from ._contracts import ContractError, canonical, checked, decode, digest, entries, identity, integer, obj, read, schema, text
from .build_loop import _path


KINDS=("acceptance","coverage","scan","archive")


def evaluate(policy,expected,evidence):
    checked(policy,expected)
    schema(policy,"ace.factory-release-gate-policy.v1",("source_ref","artifact_sha256","zip_sha256","zip_manifest_sha256",
                                                       "expected_criteria","required_modules","evidence_sha256"))
    pointer=text(policy["source_ref"],"Sumber kebijakan")
    artifact=digest(policy["artifact_sha256"])
    archive_key=digest(policy["zip_sha256"])
    manifest=digest(policy["zip_manifest_sha256"])
    accept_min=integer(policy["expected_criteria"],"Jumlah kriteria",1,1000)
    anchors=obj(policy["evidence_sha256"],KINDS)
    minima={}
    for raw in entries(policy["required_modules"],80,minimum=1):
        obj(raw,("path","min_bp","source_ref"))
        path=_path(raw["path"])
        if not path.endswith(".py") or path in minima:
            raise ContractError("Modul wajib ganda atau bukan Python.")
        minima[path]=(integer(raw["min_bp"],"Coverage basis points",0,10_000),
                      text(raw["source_ref"],"Sumber ambang"))
    if not isinstance(evidence,dict) or set(evidence)-set(KINDS):
        raise ContractError("Jenis receipt tidak dikenal.")

    checks=[]
    for name in KINDS:
        anchor=digest(anchors[name])
        row=evidence.get(name)
        expected_schema={"acceptance":"ace.factory-acceptance-report.v1","coverage":"ace.factory-coverage-report.v1",
                         "scan":"ace.factory-sast-report.v1","archive":"ace.factory-release-verification.v1"}[name]
        if row is None:
            status="missing"
        elif (not isinstance(row,dict) or row.get("schema")!=expected_schema or identity(row)!=anchor):
            status="unverified"
        else:
            status="bound"
        checks.append({"evidence":name,"sha256":anchor,"status":status})
    blockers=[{"rule":row["status"],"evidence":row["evidence"]} for row in checks if row["status"]!="bound"]
    used={row["evidence"] for row in checks if row["status"]=="bound"}

    def hold(rule, **fields):
        blockers.append({"rule":rule,**fields})

    if "acceptance" in used:
        acceptance=evidence["acceptance"]
        counts=acceptance.get("counts")
        correct=isinstance(counts,dict) and counts=={"passed":accept_min,"failed":0,"missing_rule":0,"missing_observation":0}
        if acceptance.get("status")!="passed" or acceptance.get("artifact_sha256")!=artifact or not correct:
            hold("acceptance_not_certified",evidence="acceptance")

    source_hashes={}
    if "coverage" in used:
        coverage=evidence["coverage"]
        sources=coverage.get("files",[])
        modules={item.get("path"):item for item in coverage.get("modules",[])}
        if coverage.get("status")!="measured" or identity(sources)!=artifact or coverage.get("skipped")!=0:
            hold("coverage_snapshot_not_certified",evidence="coverage")
        for entry in sources:
            source_hashes[entry["path"]]=entry["sha256"]
        for path,(minimum,ref) in sorted(minima.items()):
            stats=modules.get(path,{})
            ratio=stats.get("ratio_bp")
            if (not isinstance(stats.get("sha256"),str) or stats["sha256"]!=source_hashes.get(path)
                    or type(ratio) is not int or not minimum<=ratio<=10_000):
                hold("coverage_below_requirement",path=path,reference=ref,minimum_bp=minimum,observed_bp=ratio)

    if "scan" in used:
        scan=evidence["scan"]
        if scan.get("status")!="no_rule_matches" or scan.get("findings")!=[] or scan.get("unscanned")!=[]:
            hold("scan_has_open_findings",evidence="scan")
        scanned={item.get("path"):item for item in scan.get("sources",[])}
        for path in sorted(minima):
            row=scanned.get(path,{})
            if not row.get("parse_ok") or row.get("sha256")!=source_hashes.get(path) or path not in source_hashes:
                hold("scan_different_or_missing_source",path=path)

    if "archive" in used:
        release=evidence["archive"]
        if (release.get("status")!="verified" or release.get("zip_sha256")!=archive_key
                or release.get("manifest_sha256")!=manifest or type(release.get("verified_files")) is not int
                or release["verified_files"]<1):
            hold("archive_unverified",evidence="archive")

    return {"schema":"ace.factory-release-gate-report.v1","policy_sha256":expected,
            "source_ref":pointer,"artifact_sha256":artifact,"checks":checks,"blockers":blockers,
            "status":"held" if blockers else "ready_for_review"}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("policy",type=Path)
    parser.add_argument("--expect-sha256",required=True)
    for key in KINDS:
        parser.add_argument(f"--{key}",type=Path)
    args=parser.parse_args(argv)
    try:
        evidence={key:decode(read(path)) for key in KINDS if (path:=getattr(args,key)) is not None}
        result=evaluate(decode(read(args.policy)),args.expect_sha256,evidence)
        sys.stdout.buffer.write(canonical(result)+b"\n")
    except (OSError,KeyError,TypeError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return int(result["status"]!="ready_for_review")


if __name__=="__main__":
    raise SystemExit(main())
