"""Bangun jalur ekspor dan impor data produk untuk CSV dan JSON.

Kontrak mencatat tipe, nullable, dan primary key. CSV hasil ekspor
menjaga teks yang berpotensi dibaca sebagai formula, dan importer
memeriksa encoding kanonis sebelum mengembalikan record produk.
"""
import argparse
import csv
from hashlib import sha256
from io import StringIO
from pathlib import Path
import re
import sys

from ._contracts import ContractError, canonical, checked, decode, entries, identifier, identity, integer, obj, read, schema, text


MAX_ROWS=5000
MAX_BYTES=3_000_000
KINDS={"text","integer","boolean"}
FORMULA=re.compile(r"^[\t\r\n =+\-@']")
INTEGER=re.compile(r"-?(?:0|[1-9][0-9]{0,18})")
NULL="\\N"


def _layout(rule, expected):
    checked(rule,expected)
    schema(rule,"ace.factory-data-port.v1",("id","source_ref","columns","primary"))
    identifier(rule["id"],"ID import/export")
    text(rule["source_ref"],"Sumber skema")
    columns={}
    for row in entries(rule["columns"],80,minimum=1):
        obj(row,("id","type","nullable"))
        key=identifier(row["id"],"Nama kolom")
        kind=row["type"]
        if key in columns or not isinstance(kind,str) or kind not in KINDS or type(row["nullable"]) is not bool:
            raise ContractError("Kolom ganda atau tipe data tidak sah.")
        columns[key]=(kind,row["nullable"])
    primary=tuple(identifier(key,"Primary key") for key in entries(rule["primary"],len(columns),minimum=1))
    if len(set(primary))!=len(primary) or set(primary)-columns.keys() or any(columns[key][1] for key in primary):
        raise ContractError("Primary key ganda, nullable, atau tak dikenal.")
    return columns,primary


def _value(raw, kind, nullable):
    if raw is None and nullable:
        return None
    if kind=="integer":
        return integer(raw,"Nilai integer",-2**63,2**63-1)
    if kind=="boolean" and type(raw) is bool:
        return raw
    if kind=="text" and isinstance(raw,str) and len(raw)<=2048 and all(c.isprintable() or c in "\r\n\t" for c in raw):
        return raw
    raise ContractError("Nilai tidak sesuai tipe atau batas.")


def _records(source, columns, primary):
    validated=[]
    seen=set()
    for index,item in enumerate(entries(source,MAX_ROWS),1):
        obj(item,columns)
        try:
            record={key:_value(item[key],*columns[key]) for key in sorted(columns)}
        except ValueError as error:
            raise ContractError(f"Nilai tidak sah pada record {index}.") from error
        key=tuple(record[field] for field in primary)
        if key in seen:
            raise ContractError(f"Primary key ganda pada record {index}.")
        seen.add(key)
        validated.append(record)
    return sorted(validated,key=lambda row:tuple(row[field] for field in primary))


def _serialize_field(value, kind):
    if value is None:
        return NULL
    if kind=="boolean":
        return "true" if value else "false"
    if kind=="text" and (value==NULL or FORMULA.match(value)):
        return "'"+value
    return str(value)


def _read_field(value, kind, nullable):
    if value==NULL and nullable:
        return None
    if kind=="integer" and INTEGER.fullmatch(value):
        return int(value)
    if kind=="boolean" and value in ("true","false"):
        return value=="true"
    if kind=="text":
        restored=value[1:] if value.startswith("'") else value
        if _serialize_field(restored,kind)==value:
            return restored
    raise ContractError("Encoding sel CSV tidak kanonis.")


def export(source, rule, expected, format_name):
    columns,primary=_layout(rule,expected)
    records=_records(source,columns,primary)
    if format_name=="json":
        output=canonical(records)+b"\n"
    elif format_name=="csv":
        stream=StringIO(newline="")
        sink=csv.writer(stream,lineterminator="\r\n")
        sink.writerow(columns)
        for item in records:
            sink.writerow(_serialize_field(item[key],kind) for key,(kind,_) in columns.items())
        output=stream.getvalue().encode()
    else:
        raise ContractError("Format ekspor tidak didukung.")
    if len(output)>MAX_BYTES:
        raise ContractError("Ekspor melampaui anggaran.")
    return output,_report(output,records,expected,format_name)


def _report(data, records, expected, format_name):
    return {"schema":"ace.factory-data-port-report.v1","format":format_name,"plan_sha256":expected,
            "file_sha256":sha256(data).hexdigest(),"bytes":len(data),"records":len(records),
            "dataset_sha256":identity(records)}


def ingest(data, rule, expected, format_name):
    columns,primary=_layout(rule,expected)
    if not isinstance(data,bytes) or len(data)>MAX_BYTES:
        raise ContractError("Impor melampaui anggaran.")
    if format_name=="json":
        observed=decode(data)
    elif format_name=="csv":
        stream=csv.reader(StringIO(data.decode("utf-8-sig"),newline=""),strict=True)
        if next(stream,[])!=list(columns):
            raise ContractError("Header CSV berbeda dari kontrak.")
        observed=[]
        for index,row in enumerate(stream,1):
            if index>MAX_ROWS or len(row)!=len(columns):
                raise ContractError(f"Jumlah kolom/baris berbeda pada record {index}.")
            try:
                observed.append({key:_read_field(cell,*info) for (key,info),cell in zip(columns.items(),row,strict=True)})
            except ContractError as error:
                raise ContractError(f"Encoding CSV tidak sah pada record {index}.") from error
    else:
        raise ContractError("Format impor tidak didukung.")
    validated=_records(observed,columns,primary)
    return validated,_report(data,validated,expected,format_name)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action",choices=("export","import"))
    parser.add_argument("format",choices=("json","csv"))
    for key in ("input","plan","output"):
        parser.add_argument(key,type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        plan=decode(read(args.plan))
        source=read(args.input,MAX_BYTES)
        if args.action=="export":
            data,report=export(decode(source),plan,args.expect_sha256,args.format)
        else:
            records,report=ingest(source,plan,args.expect_sha256,args.format)
            data=canonical(records)+b"\n"
        with args.output.open("xb") as handle:
            handle.write(data)
        sys.stdout.buffer.write(canonical(report)+b"\n")
    except (OSError,ValueError,csv.Error,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
