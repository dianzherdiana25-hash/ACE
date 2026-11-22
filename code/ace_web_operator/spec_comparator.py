"""Bandingkan spesifikasi dari sumber tersendiri dengan unit yang eksplisit.

Nilai dimensional dinormalisasi dengan Decimal. Kriteria per field
menentukan kesetaraan, urutan, atau perbedaan. Nilai absen dan unit
yang tidak sebanding tetap tercatat dengan pointer data asalnya.
"""
import argparse
from decimal import Decimal
from pathlib import Path
import re
import sys

from ._contracts import ContractError,canonical,checked,decode,digest,entries,identifier,obj,read,schema,text


NUMBER=re.compile(r"-?(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,6})?")
FAMILIES={"length_mm":{"mm":Decimal(1),"cm":Decimal(10),"m":Decimal(1000)},
          "mass_g":{"g":Decimal(1),"kg":Decimal(1000),"mg":Decimal("0.001")},
          "memory_mib":{"mib":Decimal(1),"gib":Decimal(1024)}}


def _decimal(value):
    if not isinstance(value,str) or not NUMBER.fullmatch(value):
        raise ContractError("Nilai numerik perlu Decimal kanonis.")
    return Decimal(value)


def _number(value):
    encoded=format(value,"f")
    if "." in encoded:
        return encoded.rstrip("0").rstrip(".")
    return "0" if value==0 else encoded


def _fields(rows):
    by_name={}
    for row in entries(rows,80,1):
        obj(row,("id","type","prefer","tolerance","source_ref"))
        key=identifier(row["id"],"Kriteria spesifikasi")
        flavor=row["type"]
        preference=row["prefer"]
        if key in by_name or not isinstance(flavor,str) or flavor not in {"text",*FAMILIES} or preference not in (
            "equal","less","more"
        ):
            raise ContractError("Kriteria ganda atau jenis pembanding tidak dikenal.")
        if flavor=="text":
            if preference!="equal" or row["tolerance"] is not None:
                raise ContractError("Teks hanya mendukung kesetaraan casefold.")
            tolerance=None
        else:
            tolerance=_decimal(row["tolerance"])
            if tolerance<0:
                raise ContractError("Toleransi tidak boleh negatif.")
        by_name[key]=(flavor,preference,tolerance,text(row["source_ref"],"Sumber kriteria"))
    return by_name


def _normalize(raw,flavor):
    obj(raw,("value","unit","source_ref"))
    ref=text(raw["source_ref"],"Sumber nilai")
    if flavor=="text" and raw["unit"] is None:
        return text(raw["value"],"Teks spesifikasi",240).casefold(),ref,None
    if flavor not in FAMILIES or raw["unit"] not in FAMILIES[flavor]:
        return None,ref,"incompatible_unit"
    return _decimal(raw["value"])*FAMILIES[flavor][raw["unit"]],ref,None


def compare(plan,expected,snapshot):
    checked(plan,expected)
    schema(plan,"ace.web.spec-compare-plan.v1",("source_ref","snapshot_sha256","fields"))
    checked(snapshot,plan["snapshot_sha256"])
    schema(snapshot,"ace.web.spec-snapshot.v1",("source_ref","records"))
    source=text(plan["source_ref"],"Rujukan pembanding")
    data_ref=text(snapshot["source_ref"],"Rujukan snapshot")
    fields=_fields(plan["fields"])
    available={}
    for row in entries(snapshot["records"],100,2):
        obj(row,("id","source_ref","artifact_sha256","fields"))
        sku=identifier(row["id"],"Produk pembanding")
        data=row["fields"]
        if sku in available or not isinstance(data,dict) or data.keys()-fields.keys():
            raise ContractError("Produk ganda atau memakai field tidak terdaftar.")
        available[sku]=(data,digest(row["artifact_sha256"]),text(row["source_ref"],"Sumber produk"))
    compare_rows=[]
    for key,(flavor,preference,tolerance,ref) in sorted(fields.items()):
        norms={}
        observed=[]
        for sku,(row,anchor,pointer) in sorted(available.items()):
            if key not in row:
                value,source_ref,problem=None,None,"missing"
            else:
                value,source_ref,problem=_normalize(row[key],flavor)
            if value is not None:
                norms[sku]=value
            shown=_number(value) if isinstance(value,Decimal) else value
            observed.append({"id":sku,"normalized":shown,"unit":flavor if flavor!="text" else None,"finding":problem,
                             "source_ref":source_ref,"product_ref":pointer,"artifact_sha256":anchor})
        leaders=[]
        if len(norms)<2:
            outcome="insufficient_comparable_values"
        elif flavor=="text":
            outcome="equal" if len(set(norms.values()))==1 else "different"
        else:
            minimum,maximum=min(norms.values()),max(norms.values())
            if maximum-minimum<=tolerance:
                outcome="within_tolerance"
            else:
                outcome="different"
                if preference in ("less","more"):
                    rank=minimum if preference=="less" else maximum
                    leaders=sorted(sku for sku,value in norms.items() if abs(value-rank)<=tolerance)
        compare_rows.append({"field":key,"source_ref":ref,"preference":preference,"status":outcome,
                             "comparable_count":len(norms),"leaders":leaders,"values":observed})
    return {"schema":"ace.web.spec-compare-report.v1","plan_sha256":expected,"source_ref":source,
            "snapshot_sha256":plan["snapshot_sha256"],"snapshot_ref":data_ref,"fields":compare_rows}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan",type=Path)
    parser.add_argument("snapshot",type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        output=compare(decode(read(args.plan)),args.expect_sha256,decode(read(args.snapshot)))
        sys.stdout.buffer.write(canonical(output)+b"\n")
    except (OSError,TypeError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
