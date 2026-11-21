"""Agregasikan bench per bulan UTC dan kelas dengan denominasi yang terlihat.

Setiap sesi dibaca ulang dengan protokol held-out yang tetap. Total
parsial dan angka lengkap dibedakan dengan cakupan minimum sesi.
Delta hanya berlaku antarbulan bersebelahan yang memiliki angka
lengkap, sehingga bulan kosong tidak diisi atau dilompati.
"""
import argparse
from collections import Counter,defaultdict
from fractions import Fraction
from hashlib import sha256
from pathlib import Path
import re
import sys

from . import _perception_io,_raster,_vision,perception_bench
from .audio_pipeline import _canonical,_integer,_sha
from .document_extractor import _token
from .perceptual_memory import _digest,_utc


MONTH = re.compile(r"([0-9]{4})-(0[1-9]|1[0-2])")
MAX_GROUP_SESSIONS = 96


def _months(start,count):
    found = MONTH.fullmatch(_token(start,"Bulan awal"))
    if not found or int(found[1]) == 0:
        raise ValueError("Bulan harus berbentuk YYYY-MM.")
    key = int(found[1])*12+int(found[2])-1
    if key+count > 120_000:
        raise ValueError("Bulan melampaui kalender.")
    return ["%04d-%02d" % (index//12,index%12+1) for index in range(key,key+count)]


def _sources(rows, months, latest):
    if not isinstance(rows,list) or len(rows)>MAX_GROUP_SESSIONS:
        raise ValueError("Jumlah sesi bulanan di luar batas.")
    groups=defaultdict(list)
    ids, refs, paths = set(),set(),set()
    total = 0
    for row in rows:
        if not isinstance(row,dict) or set(row)!={"id","at","ref","path","bytes","sha256"}:
            raise ValueError("Bentuk sesi bulanan tidak sah.")
        key,pointer = (_token(row[field],field) for field in ("id","ref"))
        stamp = _utc(row["at"])
        month = f"{stamp.year:04d}-{stamp.month:02d}"
        path = row["path"]
        _perception_io.relative_parts(path)
        if (key in ids or pointer in refs or path in paths or month not in months or stamp>latest):
            raise ValueError("Sesi ganda, bulan tidak terdaftar, atau waktu di masa depan.")
        ids.add(key)
        refs.add(pointer)
        paths.add(path)
        size=_integer(row["bytes"],1,_vision.MAX_SPEC_BYTES,"Ukuran sesi")
        total+=size
        groups[month].append((stamp,key,pointer,path,size,_digest(row["sha256"])))
    if total>32_000_000:
        raise ValueError("Anggaran byte sesi bulanan dilampaui.")
    return groups


def _rates(rows,minimum,kind,broken):
    numer=denom=complete=0
    for item in rows:
        if item["full_rate"] is not None:
            complete+=1
        denom+=item["rate_denominator"]
        numer+=sum(item.get(code,0) for code in ("substitutions","deletions","insertions")) if kind=="asr" else item.get("correct",0)
    partial = Fraction(numer,denom) if denom else None
    full = partial if not broken and complete == len(rows) and complete>=minimum else None
    return {"sessions":len(rows), "complete_sessions":complete, "numerator_count":numer,
            "denominator_count":denom, "observed_rate":_part(partial), "full_rate":_part(full)},full


def _part(value):
    return None if value is None else {"numerator":value.numerator,"denominator":value.denominator}


def summarize(root,protocol,plan,expected):
    raw = _vision.spec(plan,"ace.perception-monthly-plan.v1",("plan_ref","protocol_sha256","start_month",
                             "month_count","minimum_sessions_per_month","as_of","sessions"))
    if _sha(raw)!=_digest(expected):
        raise ValueError("Rencana bulanan berbeda dari anchor.")
    anchor=_digest(raw["protocol_sha256"])
    perception_bench._plan(protocol,anchor)
    minimum=_integer(raw["minimum_sessions_per_month"],1,MAX_GROUP_SESSIONS,"Jumlah sesi minimum")
    months=_months(raw["start_month"],_integer(raw["month_count"],1,36,"Jumlah bulan"))
    latest=_utc(raw["as_of"])
    groups=_sources(raw["sessions"],months,latest)
    previous={}
    reports=[]
    for month in months:
        refs=[]
        observed=defaultdict(list)
        invalid=0
        for stamp,key,ref,path,size,checksum in sorted(groups.get(month,())):
            status="observed"
            try:
                payload=_perception_io.read_relative(root,path,size,checksum)
                if len(payload)!=size:
                    raise ValueError("Ukuran sesi bulanan berubah.")
                result=perception_bench.report(protocol,payload,anchor)
            except (OSError,OverflowError,RecursionError,ValueError):
                status="invalid_receipt"
                invalid+=1
            else:
                for item in result["metrics"]:
                    observed[item["kind"]].append(item)
            refs.append({"id":key,"ref":ref,"at":stamp.isoformat(),"status":status,"sha256":checksum})
        dataset, here={},{}
        for kind in perception_bench.KINDS:
            stats,full=_rates(observed[kind],minimum,kind,invalid)
            prior=previous.get(kind)
            dataset[kind]={**stats,"delta_from_previous":_part(full-prior if full is not None and prior is not None else None)}
            here[kind]=full
        previous=here
        status="missing" if not refs else "complete" if all(rate is not None for rate in here.values()) else "incomplete"
        reports.append({"month":month,"status":status,"sessions":refs,"classes":dataset,
                        "status_counts":dict(Counter(row["status"] for row in refs))})
    return {"schema":"ace.perception-monthly-report.v1","plan_sha256":expected,"plan_bytes_sha256":sha256(plan).hexdigest(),
            "plan_ref":_token(raw["plan_ref"],"Rujukan laporan"),"protocol_sha256":anchor,
            "as_of":latest.isoformat(),"minimum_sessions_per_month":minimum,"months":reports}


def markdown(report):
    lines=["# Laporan persepsi bulanan","",f"Rencana: `{report['plan_sha256']}`","",
           "| Bulan UTC | Status | Akurasi dokumen | Akurasi tabel | WER |","|---|---|---:|---:|---:|"]
    for entry in report["months"]:
        values = [entry["classes"][kind]["full_rate"] for kind in perception_bench.KINDS]
        text = [f"{item['numerator']}/{item['denominator']}" if item is not None else "TIDAK TAHU" for item in values]
        lines.append("| "+" | ".join([entry["month"],entry["status"],*text])+" |")
    return "\n".join(lines)+"\n"


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ("root","protocol","plan"):
        parser.add_argument(name,type=Path)
    parser.add_argument("--expect-sha256",required=True)
    parser.add_argument("--format",choices=("json","markdown"),default="json")
    args=parser.parse_args(argv)
    try:
        result=summarize(args.root,_raster.read(args.protocol,_vision.MAX_SPEC_BYTES),
                         _raster.read(args.plan,_vision.MAX_SPEC_BYTES),args.expect_sha256)
        output=markdown(result).encode() if args.format=="markdown" else _canonical(result)+b"\n"
        sys.stdout.buffer.write(output)
    except (OSError,OverflowError,RecursionError,ValueError) as error:
        parser.exit(2,f"Error: {error}\n")
    return int(any(row["status"]!="complete" for row in result["months"]))


if __name__ == "__main__":
    raise SystemExit(main())
