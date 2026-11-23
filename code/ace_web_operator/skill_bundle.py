"""Rakit bundel bukti Gelombang 3 per skill dan agregat per klaster.

Mengikuti pola kustodi repo: JSON kanonik, setiap artefak ditambat
SHA-256 byte, folder dibuat sekali (write_new, tidak menimpa), dan
rantai antar-dokumen diperiksa sebelum satu byte pun ditulis.
Bundel per skill memuat suite, plan, sources, package, absorb
receipt, answers, verification, attempts, dan MANIFEST hash.
Agregat klaster menyusun keluaran registry yang sudah ada
(registry sebelum/sesudah, policy, batch, laporan revisi, tinjauan
kampanye, laporan papan) plus hash manifest tiap skill ke dalam
CLUSTER_MANIFEST.
"""
import argparse
from hashlib import sha256
from pathlib import Path
import sys

from ._artifact import read_relative,write_new
from ._contracts import ContractError,canonical,checked,decode,digest,entries,identifier,identity,obj,read,schema,text
from .web_scheduler import time_value


MAX_ARTIFACT=12_000_000


def _load(root,ref):
    obj(ref,("path","sha256"))
    raw=read_relative(root,ref["path"],MAX_ARTIFACT,digest(ref["sha256"]))
    return raw,decode(raw)


def _attempts(raw,skill,source):
    rows=[]
    for row in entries(raw,200):
        obj(row,("at","status","answers_sha256","verification_sha256","source_ref"))
        time_value(row["at"])
        for key in ("answers_sha256","verification_sha256"):
            if row[key] is not None:
                digest(row[key])
        rows.append({"at":row["at"],"status":text(row["status"],"Status percobaan",60),
                     "answers_sha256":row["answers_sha256"],"verification_sha256":row["verification_sha256"],
                     "source_ref":text(row["source_ref"],"Sumber percobaan")})
    return {"schema":"ace.web.skill-attempts.v1","skill":skill,"source_ref":source,"attempts":rows}


def assemble_skill(root,plan,expected):
    checked(plan,expected)
    schema(plan,"ace.web.skill-bundle-plan.v1",("source_ref","skill","cluster","suite","plan","sources",
                                                 "package","absorb_receipt","answers","verification","attempts"))
    source=text(plan["source_ref"],"Sumber bundel")
    skill=identifier(plan["skill"],"Skill")
    cluster=identifier(plan["cluster"],"Klaster")
    suite_raw,suite=_load(root,plan["suite"])
    plan_raw,absorb_plan=_load(root,plan["plan"])
    package_raw,package=_load(root,plan["package"])
    receipt_raw,receipt=_load(root,plan["absorb_receipt"])
    schema(suite,"ace.web.heldout-suite.v1",("skill","scope","source_ref","evaluator_ref",
                                             "min_cases_per_objective","target_bp","cases"))
    schema(absorb_plan,"ace.web.skill-absorb-plan.v1",("id","cluster","version","source_ref","heldout_sha256",
                                                       "sources","objectives","lessons","practice"))
    schema(package,"ace.web.skill-package.v1",("id","cluster","version","source_ref","plan_sha256","heldout_sha256",
                                                "sources","objectives","lessons","practice"))
    schema(receipt,"ace.web.skill-absorb-receipt.v1",("skill","cluster","version","source_ref","package_sha256",
                                                      "heldout_sha256","sources","objectives","lessons","practice","status"))
    if package["id"]!=skill or package["cluster"]!=cluster or suite["skill"]!=skill:
        raise ContractError("Bundel tidak tertambat pada skill dan klaster yang sama.")
    if package["plan_sha256"]!=identity(absorb_plan) or package["heldout_sha256"]!=identity(suite):
        raise ContractError("Rantai plan atau suite paket tidak cocok.")
    if receipt["package_sha256"]!=identity(package) or receipt["skill"]!=skill:
        raise ContractError("Absorb receipt tidak menunjuk paket bundel.")
    files={"suite.json":suite_raw,"plan.json":plan_raw,"package.json":package_raw,
           "absorb_receipt.json":receipt_raw}
    known_sources={(row["path"],row["sha256"]) for row in package["sources"]}
    for ref in entries(plan["sources"],40,1):
        obj(ref,("path","sha256"))
        if (ref["path"],digest(ref["sha256"])) not in known_sources:
            raise ContractError("Sumber bundel tidak tercantum dalam paket.")
        files["sources/"+ref["path"]]=read_relative(root,ref["path"],MAX_ARTIFACT,ref["sha256"])
    answers_anchor=None
    verification_anchor=None
    if plan["answers"] is not None:
        answers_raw,answers=_load(root,plan["answers"])
        schema(answers,"ace.web.heldout-answers.v1",("package_sha256","suite_sha256","source_ref","solver_ref",
                                                     "at","answers"))
        if answers["package_sha256"]!=identity(package) or answers["suite_sha256"]!=identity(suite):
            raise ContractError("Jawaban tidak tertambat pada paket dan suite bundel.")
        files["answers.json"]=answers_raw
        answers_anchor=identity(answers)
    if plan["verification"] is not None:
        if answers_anchor is None:
            raise ContractError("Verifikasi tanpa jawaban dalam bundel.")
        verification_raw,verification=_load(root,plan["verification"])
        schema(verification,"ace.web.skill-verification-receipt.v1",
               ("skill","cluster","version","package_sha256","suite_sha256","answer_sha256","scope","at",
                "source_ref","suite_ref","solver_ref","evaluator_ref","score_bp","objectives","cases",
                "passed","status"))
        if (verification["skill"]!=skill or verification["package_sha256"]!=identity(package)
                or verification["suite_sha256"]!=identity(suite) or verification["answer_sha256"]!=answers_anchor):
            raise ContractError("Receipt verifikasi tidak cocok rantai bundel.")
        files["verification.json"]=verification_raw
        verification_anchor=identity(verification)
    attempts=_attempts(plan["attempts"],skill,source)
    files["attempts.json"]=canonical(attempts)+b"\n"
    manifest={"schema":"ace.web.skill-bundle-manifest.v1","skill":skill,"cluster":cluster,"source_ref":source,
              "package_sha256":identity(package),"suite_sha256":identity(suite),
              "answers_sha256":answers_anchor,"verification_sha256":verification_anchor,
              "files":{name:sha256(payload).hexdigest() for name,payload in sorted(files.items())}}
    files["MANIFEST.json"]=canonical(manifest)+b"\n"
    receipt_out={"schema":"ace.web.skill-bundle-receipt.v1","skill":skill,"cluster":cluster,
                 "manifest_sha256":sha256(files["MANIFEST.json"]).hexdigest(),"files":len(files),
                 "status":"assembled"}
    return files,receipt_out


def assemble_cluster(root,plan,expected):
    checked(plan,expected)
    schema(plan,"ace.web.skill-cluster-bundle-plan.v1",("source_ref","cluster","registry_before","registry_after",
                                                         "policy","batch","revision_report","campaign_review",
                                                         "board_report","skill_manifests"))
    source=text(plan["source_ref"],"Sumber bundel klaster")
    cluster=identifier(plan["cluster"],"Klaster")
    loaded={}
    for key in ("registry_before","registry_after","policy","batch","revision_report","campaign_review","board_report"):
        loaded[key]=_load(root,plan[key])
    before=loaded["registry_before"][1]
    after=loaded["registry_after"][1]
    policy=loaded["policy"][1]
    batch=loaded["batch"][1]
    revision=loaded["revision_report"][1]
    campaign=loaded["campaign_review"][1]
    board=loaded["board_report"][1]
    schema(before,"ace.web.skill-registry.v1",("revision","source_ref","entries"))
    schema(after,"ace.web.skill-registry.v1",("revision","source_ref","entries"))
    schema(policy,"ace.web.skill-registry-policy.v1",("source_ref","previous_sha256","batch_sha256","attested_receipts"))
    schema(batch,"ace.web.skill-verification-batch.v1",("entries",))
    schema(revision,"ace.web.skill-registry-revision.v1",("policy_sha256","source_ref","previous_sha256",
                                                          "registry_sha256","revision","transitions",
                                                          "verification_receipts"))
    if not isinstance(campaign,dict) or campaign.get("schema")!="ace.web.skill-campaign-review.v1":
        raise ContractError("Tinjauan kampanye tidak sah.")
    if not isinstance(board,dict) or board.get("schema")!="ace.web.skill-board-report.v1":
        raise ContractError("Laporan papan tidak sah.")
    if policy["previous_sha256"]!=identity(before) or policy["batch_sha256"]!=identity(batch):
        raise ContractError("Policy tidak menambat registry sebelum dan batch klaster.")
    if (revision["previous_sha256"]!=identity(before) or revision["registry_sha256"]!=identity(after)
            or revision["policy_sha256"]!=identity(policy)):
        raise ContractError("Laporan revisi tidak cocok rantai registry klaster.")
    if identity(campaign["registry_candidate"])!=identity(after):
        raise ContractError("Registry kandidat kampanye berbeda dari registry sesudah.")
    if board["registry_sha256"]!=identity(after):
        raise ContractError("Laporan papan tidak menunjuk registry sesudah.")
    manifests=[]
    for ref in entries(plan["skill_manifests"],40,1):
        obj(ref,("skill","path","sha256"))
        name=identifier(ref["skill"],"Skill")
        raw=read_relative(root,ref["path"],MAX_ARTIFACT,digest(ref["sha256"]))
        doc=decode(raw)
        if (not isinstance(doc,dict) or doc.get("schema")!="ace.web.skill-bundle-manifest.v1"
                or doc.get("skill")!=name or doc.get("cluster")!=cluster):
            raise ContractError("Manifest skill tidak sah atau di luar klaster.")
        manifests.append({"skill":name,"manifest_sha256":sha256(raw).hexdigest()})
    files={key+".json":loaded[key][0] for key in
           ("registry_before","registry_after","policy","batch","revision_report","campaign_review","board_report")}
    manifest={"schema":"ace.web.skill-cluster-manifest.v1","cluster":cluster,"source_ref":source,
              "registry_before_sha256":identity(before),"registry_after_sha256":identity(after),
              "files":{name:sha256(payload).hexdigest() for name,payload in sorted(files.items())},
              "skill_manifests":manifests}
    files["CLUSTER_MANIFEST.json"]=canonical(manifest)+b"\n"
    receipt_out={"schema":"ace.web.skill-cluster-bundle-receipt.v1","cluster":cluster,
                 "cluster_manifest_sha256":sha256(files["CLUSTER_MANIFEST.json"]).hexdigest(),
                 "files":len(files),"status":"assembled"}
    return files,receipt_out


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    kinds=parser.add_subparsers(dest="kind",required=True)
    for name in ("skill","cluster"):
        child=kinds.add_parser(name)
        for key in ("root","plan","output"):
            child.add_argument(key,type=Path)
        child.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        build=assemble_skill if args.kind=="skill" else assemble_cluster
        files,receipt=build(args.root,decode(read(args.plan)),args.expect_sha256)
        write_new(args.output,files)
        sys.stdout.buffer.write(canonical(receipt)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
