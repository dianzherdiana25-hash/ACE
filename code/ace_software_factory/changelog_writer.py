"""Susun catatan rilis dari rentang commit Git yang diikat penuh.

Git dibaca tanpa publikasi dan tanpa catatan identitas author. Nama
commit dikelompokkan dari Conventional Commits, dengan daftar perubahan
breaking dari judul atau trailer yang eksplisit.
"""
import argparse
import os
from pathlib import Path
import re
import subprocess
import sys

from ._contracts import ContractError,canonical,checked,decode,read,schema,text
from .docs_writer import escape


COMMIT=re.compile(r"(?:[a-f0-9]{40}|[a-f0-9]{64})")
CONVENTIONAL=re.compile(r"([a-z]+)(?:\(([a-zA-Z0-9_.-]+)\))?(!)?:\s+(.+)")
BREAKING=re.compile(r"(?m)^BREAKING(?: CHANGE|-CHANGE):\s*(.+)$")
SECTIONS={"feat":"Fitur","fix":"Perbaikan","perf":"Performa","docs":"Dokumentasi",
          "test":"Tes","refactor":"Refactor","build":"Build","ci":"CI","chore":"Pemeliharaan","other":"Lainnya"}
MAX_OUTPUT=2_000_000


def _git(root,*arguments):
    command=["git","-C",os.fspath(root),"-c","core.hooksPath=/dev/null","-c","color.ui=never",*arguments]
    result=subprocess.run(command,stdin=subprocess.DEVNULL,capture_output=True,check=False,timeout=12)
    if result.returncode or len(result.stdout)>MAX_OUTPUT:
        raise ContractError("Riwayat tidak tersedia, rentang bukan turunan, atau anggaran Git terlampaui.")
    return result.stdout


def _commit(raw):
    if not isinstance(raw,str) or not COMMIT.fullmatch(raw):
        raise ContractError("Gunakan hash commit penuh.")
    return raw


def inspect(root,plan,expected):
    checked(plan,expected)
    schema(plan,"ace.factory-changelog-plan.v1",("source_ref","version","base","head"))
    pointer=text(plan["source_ref"],"Sumber rilis")
    version=text(plan["version"],"Versi produk",50)
    base,head=_commit(plan["base"]),_commit(plan["head"])
    for object_id in (base,head):
        if _git(root,"cat-file","-t",object_id)!=b"commit\n":
            raise ContractError("Batas riwayat tidak menunjuk commit.")
    _git(root,"merge-base","--is-ancestor",base,head)
    payload=_git(root,"log","-z","--reverse","--topo-order","--max-count=1001",
                 "--no-notes","--no-show-signature","--no-decorate","--format=%H%x00%cs%x00%s%x00%b",
                 f"{base}..{head}","--")
    fields=payload.decode("utf-8").split("\x00") if payload else []
    if fields and fields.pop()!="":
        raise ContractError("Output log Git tidak memiliki terminator.")
    if len(fields)%4 or len(fields)>4000:
        raise ContractError("Bentuk atau jumlah commit melampaui batas.")
    groups={key:[] for key in SECTIONS}
    changes=[]
    for offset in range(0,len(fields),4):
        anchor,date,raw,body=fields[offset:offset+4]
        _commit(anchor)
        match=CONVENTIONAL.fullmatch(raw)
        if match:
            kind,scope,flag,title=match.groups()
            category=kind if kind in SECTIONS else "other"
        else:
            category,scope,flag,title="other",None,None,raw
        title=title or "(tanpa judul)"
        text(title,"Judul commit",400)
        notes=[text(value.strip(),"Catatan breaking",500) for value in BREAKING.findall(body)]
        record={"commit":anchor,"date":date,"title":title,"scope":scope,"breaking":bool(flag or notes),
                "breaking_notes":notes}
        groups[category].append(record)
        if record["breaking"]:
            changes.append(record)
    report={"schema":"ace.factory-changelog-report.v1","plan_sha256":expected,"source_ref":pointer,
            "version":version,"base":base,"head":head,"commits":len(fields)//4,"sections":groups,"breaking":changes}
    return report


def markdown(report):
    lines=[f"# Rilis {escape(report['version'])}","",f"Rentang `{report['base']}` hingga `{report['head']}`.",
           f"Sumber {escape(report['source_ref'])}."]
    if report["breaking"]:
        lines.extend(["","## Perubahan breaking",""])
        for row in report["breaking"]:
            lines.append(f"- {escape(row['title'])} · `{row['commit'][:10]}`")
            lines.extend(f"  - {escape(note)}" for note in row["breaking_notes"])
    for key,label in SECTIONS.items():
        if not report["sections"][key]:
            continue
        lines.extend(["",f"## {label}",""])
        for row in report["sections"][key]:
            scope=f"**{escape(row['scope'])}** " if row["scope"] else ""
            lines.append(f"- {scope}{escape(row['title'])} · `{row['commit'][:10]}`")
    if not report["commits"]:
        lines.extend(["","Tidak ada perubahan pada rentang ini."])
    return "\n".join(lines)+"\n"


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo",type=Path)
    parser.add_argument("plan",type=Path)
    parser.add_argument("--expect-sha256",required=True)
    parser.add_argument("--json",action="store_true")
    args=parser.parse_args(argv)
    try:
        report=inspect(args.repo,decode(read(args.plan)),args.expect_sha256)
        sys.stdout.buffer.write(canonical(report)+b"\n" if args.json else markdown(report).encode())
    except (OSError,ValueError,RecursionError,subprocess.SubprocessError) as error:
        parser.exit(2,f"Error: {error}\n")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
