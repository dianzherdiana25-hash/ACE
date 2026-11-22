"""Ekspor snapshot akun pemilik sendiri menurut otorisasi yang di-anchor.

Grant memilih akun, snapshot, dan field eksplisit. Field rahasia tidak
masuk skema keluaran. Tool mengeluarkan artefak lokal baru dan receipt
hash, tanpa membuka sesi akun atau mengirim data ke layanan.
"""
import argparse
from hashlib import sha256
from pathlib import Path
import sys

from ._contracts import ContractError,canonical,checked,decode,entries,identifier,integer,obj,read,schema,text
from .web_scheduler import time_value


EXPORTABLE={"public_alias","created_at","ui_locale","activity_count","category","title","updated_at","visible"}


def _value(name,raw):
    if name in ("created_at","updated_at"):
        time_value(raw)
        return raw
    if name=="activity_count":
        return integer(raw,"Jumlah aktivitas",0,10**12)
    if name=="visible":
        if type(raw) is not bool:
            raise ContractError("Visibilitas perlu boolean.")
        return raw
    return text(raw,"Nilai export",200)


def export(plan,expected,grant,snapshot):
    checked(plan,expected)
    schema(plan,"ace.web.account-export-plan.v1",("source_ref","account","grant_sha256","snapshot_sha256","at"))
    checked(grant,plan["grant_sha256"])
    checked(snapshot,plan["snapshot_sha256"])
    source=text(plan["source_ref"],"Sumber export")
    key=identifier(plan["account"],"Akun fixture")
    schema(grant,"ace.web.self-export-authorization.v1",("account","scope","source_ref","snapshot_sha256","expires_at","fields"))
    schema(snapshot,"ace.web.owner-snapshot.v1",("account","source_ref","kind","records"))
    proof=text(grant["source_ref"],"Rujukan izin")
    before=time_value(plan["at"])
    expiry=time_value(grant["expires_at"])
    if (key!=grant["account"] or key!=snapshot["account"] or grant["scope"]!="own_account_export" or
            grant["snapshot_sha256"]!=plan["snapshot_sha256"] or before>=expiry):
        raise ContractError("Grant tidak mencakup akun, snapshot atau window yang diminta.")
    snapshot_ref=text(snapshot["source_ref"],"Rujukan data")
    kind=identifier(snapshot["kind"],"Jenis record")
    fields=[identifier(name,"Field export") for name in entries(grant["fields"],len(EXPORTABLE),1)]
    if len(set(fields))!=len(fields) or set(fields)-EXPORTABLE:
        raise ContractError("Field export ganda atau tidak diizinkan.")
    rows={}
    count_omitted=0
    for internal in entries(snapshot["records"],2500):
        obj(internal,("id","source_ref","values"))
        ref=identifier(internal["id"],"ID record")
        pointer=text(internal["source_ref"],"Sumber record")
        values=internal["values"]
        if ref in rows or not isinstance(values,dict) or not set(fields)<=values.keys():
            raise ContractError("Record ganda atau kehilangan field yang diberikan grant.")
        allowed={name:_value(name,values[name]) for name in sorted(fields)}
        count_omitted+=len(values)-len(allowed)
        rows[ref]={"id":ref,"source_ref":pointer,"values":allowed}
    data={"schema":"ace.web.account-export.v1","account":key,"kind":kind,
          "snapshot_sha256":plan["snapshot_sha256"],"snapshot_ref":snapshot_ref,"authorization_ref":proof,
          "records":[rows[name] for name in sorted(rows)]}
    output=canonical(data)+b"\n"
    report={"schema":"ace.web.account-export-receipt.v1","plan_sha256":expected,"source_ref":source,
            "grant_sha256":plan["grant_sha256"],"snapshot_sha256":plan["snapshot_sha256"],"snapshot_ref":snapshot_ref,
            "authorization_ref":proof,"status":"exported_locally","rows":len(rows),"omitted_fields":count_omitted,
            "export_sha256":sha256(output).hexdigest(),"bytes":len(output)}
    return output,report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ("plan","authorization","snapshot","output"):
        parser.add_argument(key,type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        contents,report=export(decode(read(args.plan)),args.expect_sha256,decode(read(args.authorization)),
                               decode(read(args.snapshot)))
        with args.output.open("xb") as stream:
            stream.write(contents)
        sys.stdout.buffer.write(canonical(report)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
