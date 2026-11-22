"""Pisahkan profil fixture berdasarkan akun, asal, dan namespace lokal.

Setiap direktori memiliki marker yang mengikat kebijakan dan akun.
Pemeriksaan menolak symlink, direktori yang berbagi inode, dan marker
yang berpindah, tanpa membaca cookie, token, atau isi browser.
"""
import argparse
from pathlib import Path
import stat
import sys

from ._artifact import read_relative,write_new
from ._contracts import ContractError,canonical,checked,decode,entries,identifier,identity,obj,origin,read,schema,text


MARKER="scope.json"


def roster(policy,expected):
    checked(policy,expected)
    schema(policy,"ace.web.account-separation.v1",("source_ref","accounts"))
    text(policy["source_ref"],"Sumber otorisasi")
    accounts={}
    names=set()
    for row in entries(policy["accounts"],30,1):
        obj(row,("ref","origin","namespace","owner_ref"))
        key=identifier(row["ref"],"Alias akun")
        scope=identifier(row["namespace"],"Namespace profil")
        base,_=origin(row["origin"])
        if key in accounts or scope in names:
            raise ContractError("Alias atau namespace profil ganda.")
        names.add(scope)
        accounts[key]={"schema":"ace.web.account-scope.v1","policy_sha256":expected,"account_ref":key,
                       "namespace":scope,"origin":base,"owner_ref":text(row["owner_ref"],"Rujukan kepemilikan")}
    return accounts


def initialize(root,policy,expected):
    scopes=roster(policy,expected)
    write_new(root,{f"{row['namespace']}/{MARKER}":canonical(row)+b"\n" for row in scopes.values()})
    return inspect(root,policy,expected)


def inspect(root,policy,expected):
    root_info=root.lstat()
    if not stat.S_ISDIR(root_info.st_mode):
        raise ContractError("Root profil bukan direktori langsung.")
    expected_profiles=roster(policy,expected)
    links=set()
    seen_names=set()
    states=[]
    for alias,row in sorted(expected_profiles.items()):
        directory=row["namespace"]
        seen_names.add(directory)
        path=root/directory
        reason=None
        try:
            info=path.lstat()
            node=(info.st_dev,info.st_ino)
            if not stat.S_ISDIR(info.st_mode) or node in links:
                reason="profile_not_isolated"
            else:
                links.add(node)
                payload=read_relative(root,f"{directory}/{MARKER}",5000)
                last=path.lstat()
                if payload!=canonical(row)+b"\n" or (last.st_dev,last.st_ino,last.st_ctime_ns)!=(
                        info.st_dev,info.st_ino,info.st_ctime_ns):
                    reason="profile_marker_mismatch_or_race"
        except (OSError,ValueError):
            reason="profile_unreadable"
        states.append({"account_ref":alias,"namespace":directory,"origin":row["origin"],"scope_sha256":identity(row),
                       "status":"bound" if reason is None else "held","reason":reason})
    extra=sorted(p.name for p in root.iterdir() if p.name not in seen_names)
    return {"schema":"ace.web.account-isolation-report.v1","policy_sha256":expected,"source_ref":policy["source_ref"],
            "profiles":states,"undeclared_profiles":extra,
            "status":"isolated_markers" if not extra and all(row["status"]=="bound" for row in states) else "held"}


def permit(root,policy,expected,account,target_origin):
    _site,_port=origin(target_origin)
    key=identifier(account,"Alias akun")
    report=inspect(root,policy,expected)
    record=next((row for row in report["profiles"] if row["account_ref"]==key),None)
    ok=report["status"]=="isolated_markers" and record is not None and record["origin"]==_site
    return {"schema":"ace.web.account-permit.v1","policy_sha256":expected,"account_ref":key,
            "status":"allowed" if ok else "held","namespace":record["namespace"] if ok else None,
            "reason":None if ok else "profile_or_origin_not_verified"}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root",type=Path)
    parser.add_argument("policy",type=Path)
    parser.add_argument("--expect-sha256",required=True)
    parser.add_argument("--initialize",action="store_true")
    args=parser.parse_args(argv)
    try:
        policy=decode(read(args.policy))
        function=initialize if args.initialize else inspect
        result=function(args.root,policy,args.expect_sha256)
        sys.stdout.buffer.write(canonical(result)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return int(result["status"]=="held")


if __name__=="__main__":
    raise SystemExit(main())
