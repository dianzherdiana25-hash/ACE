"""Tulis XLSX yang menyimpan formula hidup dan hasil cache yang dihitung secara lokal."""
import argparse
from collections import defaultdict
from decimal import Decimal, localcontext
from pathlib import Path
import sys

from ._artifacts import a, e, evidence, package, xml
from ._contracts import (ProductionError, anchor, canonical, decode, fmt, items,
                         number, obj, read, schema, text)
from ._formula import Formula, address, evaluate, locator


NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
TYPES = "http://schemas.openxmlformats.org/package/2006/content-types"
REL = "http://schemas.openxmlformats.org/package/2006/relationships"
OFFICE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _sheet(row):
    obj(row, ("name", "cells"))
    name = text(row["name"], "Nama lembar", 31)
    if any(value in name for value in "[]:*?/\\") or name.startswith("'") or name.endswith("'"):
        raise ProductionError("Nama lembar mengandung karakter terlarang.")
    cells = {}
    refs = {}
    active = set()
    for record in items(row["cells"], 5000, 1):
        obj(record, ("at", "kind", "value", "source_ref"))
        location = address(record["at"])
        if location in cells:
            raise ProductionError("Sel lembar diisi ganda.")
        pointer = text(record["source_ref"], "Pointer sel")
        kind = record["kind"]
        if kind == "number":
            value = number(record["value"], "Nilai sel")
        elif kind == "text":
            value = text(record["value"], "Teks sel", 1000)
        elif kind == "formula":
            value = Formula(record["value"])
        else:
            raise ProductionError("Tipe sel belum didukung.")
        cells[location] = value
        refs[location] = pointer
    cache = {}
    lookups = 0

    def resolve(location):
        nonlocal lookups
        lookups += 1
        if lookups > 1_000_000:
            raise ProductionError("Anggaran lookup formula terlampaui.")
        if location in cache:
            return cache[location]
        if location in active or len(active) > 256:
            raise ProductionError("Formula membentuk siklus atau rantai terlalu panjang.")
        value = cells.get(location)
        if isinstance(value, Formula):
            active.add(location)
            solved = evaluate(value.tree, resolve)
            active.remove(location)
            value = Decimal(0) if solved is None else solved
            if not isinstance(value, Decimal) or not value.is_finite() or value and abs(value.adjusted()) > 300:
                raise ProductionError("Hasil formula harus numerik, berhingga dan terjangkau XLSX.")
        cache[location] = value
        return value

    by_row = defaultdict(list)
    receipt = []
    with localcontext() as ctx:
        ctx.prec = 24
        for (y, x), value in sorted(cells.items()):
            at = locator(y, x)
            result = resolve((y, x))
            if isinstance(value, Formula):
                snippet = f'<c r="{at}"><f>{e(value.source)}</f><v>{fmt(result)}</v></c>'
                receipt.append({"at": at, "formula": "=" + value.source, "cached": fmt(result), "source_ref": refs[y, x]})
            elif isinstance(value, Decimal):
                snippet = f'<c r="{at}"><v>{fmt(value)}</v></c>'
            else:
                snippet = f'<c r="{at}" t="inlineStr"><is><t xml:space="preserve">{e(value)}</t></is></c>'
            by_row[y].append(snippet)
    rows = "".join(f'<row r="{y}">{"".join(parts)}</row>' for y, parts in by_row.items())
    sheet = xml(f'<worksheet xmlns="{NS}"><sheetData>{rows}</sheetData></worksheet>')
    return name, sheet, {"name": name, "cells": len(cells), "formulas": receipt}


def make_workbook(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.production.workbook-plan.v1", ("sheets",))
    packed = [_sheet(row) for row in items(plan["sheets"], 12, 1)]
    names = [item[0].casefold() for item in packed]
    if len(set(names)) != len(names):
        raise ProductionError("Nama lembar XLSX ganda.")
    parts = {
        "_rels/.rels": xml(f'<Relationships xmlns="{REL}"><Relationship Id="rId1" Type="{OFFICE}/officeDocument" Target="xl/workbook.xml"/></Relationships>'),
    }
    relationships = []
    overrides = []
    tags = []
    for index, (name, content, _) in enumerate(packed, 1):
        tags.append(f'<sheet name={a(name)} sheetId="{index}" r:id="rId{index}"/>')
        target = f"worksheets/sheet{index}.xml"
        relationships.append(f'<Relationship Id="rId{index}" Type="{OFFICE}/worksheet" Target="{target}"/>')
        overrides.append(f'<Override PartName="/xl/{target}" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>')
        parts["xl/" + target] = content
    parts["xl/workbook.xml"] = xml(f'<workbook xmlns="{NS}" xmlns:r="{OFFICE}"><sheets>{"".join(tags)}</sheets>'
                                    '<calcPr calcId="191029" fullCalcOnLoad="1"/></workbook>')
    parts["xl/_rels/workbook.xml.rels"] = xml(f'<Relationships xmlns="{REL}">{"".join(relationships)}</Relationships>')
    parts["[Content_Types].xml"] = xml(f'<Types xmlns="{TYPES}">'
                                       '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                                       '<Default Extension="xml" ContentType="application/xml"/>'
                                       '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                                       + "".join(overrides) + "</Types>")
    raw = package(parts)
    return raw, {"schema": "ace.production.workbook-receipt.v1", "plan_sha256": expected,
                 "output": evidence({"workbook.xlsx": raw}), "sheets": [receipt for _, _, receipt in packed],
                 "formula_subset": "numeric_same_sheet_local"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        raw, report = make_workbook(decode(read(args.plan)), args.expect_sha256)
        with args.output.open("xb") as stream:
            stream.write(raw)
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, TypeError, ArithmeticError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
