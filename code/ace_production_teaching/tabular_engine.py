"""Transformasi tabel deterministik dengan lineage, join yang jelas, dan pivot tanpa imputasi."""
import argparse
import csv
from decimal import Decimal
from hashlib import sha256
from io import StringIO
from pathlib import Path
import sys

from ._contracts import (ProductionError, anchor, canonical, decode, fmt, identifier, integer,
                         items, number, obj, read, schema, source_bytes)


def _read_csv(raw, expected, maximum):
    if sha256(raw).hexdigest() != expected:
        raise ProductionError("Anchor tabel berbeda.")
    source = csv.reader(StringIO(raw.decode("utf-8"), newline=""), strict=True)
    try:
        names = [identifier(value, "Kolom CSV") for value in next(source, ())]
        if not 1 <= len(names) <= 80 or len(set(names)) != len(names):
            raise ProductionError("Header CSV kosong, kelewat lebar, atau berulang.")
        records = []
        end_line = source.line_num
        for row in source:
            start_line = end_line + 1
            end_line = source.line_num
            if len(records) >= maximum or len(row) != len(names) or any(len(value) > 800 for value in row):
                raise ProductionError(f"Baris tabel {start_line} tidak sesuai batas atau lebar schema.")
            records.append((tuple(row), ((expected, start_line),)))
    except csv.Error as error:
        raise ProductionError("CSV tidak dapat diparse secara ketat.") from error
    return names, records


def _axes(keys, names, label, minimum=1):
    result = [identifier(value, label) for value in items(keys, 30, minimum)]
    if not set(result) <= set(names) or len(set(result)) != len(result):
        raise ProductionError("Kolom transformasi ganda atau belum terdaftar.")
    return [names.index(name) for name in result]


def _join(left, right, rule, max_rows):
    names, entries = left
    cols, additional = right
    obj(rule, ("op", "kind", "right", "left_keys", "right_keys", "prefix"))
    key_a = _axes(rule["left_keys"], names, "Kunci kiri")
    key_b = _axes(rule["right_keys"], cols, "Kunci kanan")
    prefix = identifier(rule["prefix"], "Awalan join")
    if len(key_a) != len(key_b) or rule["kind"] not in ("left", "inner"):
        raise ProductionError("Join perlu kunci berpasangan dan jenis left/inner.")
    remaining = [index for index in range(len(cols)) if index not in key_b]
    targets = [identifier(prefix + "_" + cols[index], "Kolom hasil join") for index in remaining]
    if set(targets) & set(names):
        raise ProductionError("Kolom join bertabrakan dengan tabel kiri.")
    by_keys = {}
    for values, evidence in additional:
        key = tuple(values[index] for index in key_b)
        if not all(key) or key in by_keys:
            raise ProductionError("Join many-to-one membutuhkan kunci kanan unik dan terisi.")
        by_keys[key] = tuple(values[index] for index in remaining), evidence
    joined = []
    for values, evidence in entries:
        key = tuple(values[index] for index in key_a)
        match = by_keys.get(key)
        if match is None and rule["kind"] == "inner":
            continue
        extension, source = match if match else (("",) * len(remaining), ())
        joined.append((values + extension, evidence + source))
        if len(joined) > max_rows:
            raise ProductionError("Jumlah baris join melewati batas.")
    return names + targets, joined


def _reducer(operation, values):
    if operation == "count":
        return str(len(values))
    if not values:
        return ""
    vals = [number(value, "Sel agregasi") for value in values]
    if operation == "sum":
        result = sum(vals, Decimal(0))
    elif operation == "mean":
        result = sum(vals, Decimal(0)) / len(vals)
    elif operation == "min":
        result = min(vals)
    else:
        result = max(vals)
    return fmt(result)


def _aggregate(table, rule):
    obj(rule, ("op", "keys", "metrics"))
    names, records = table
    axes = _axes(rule["keys"], names, "Kolom group", 0)
    terms = []
    result = [names[index] for index in axes]
    for row in items(rule["metrics"], 30, 1):
        obj(row, ("name", "column", "function"))
        key = identifier(row["name"], "Metrik")
        field = identifier(row["column"], "Kolom agregat")
        function = row["function"]
        if key in result or field not in names or function not in ("count", "sum", "mean", "min", "max"):
            raise ProductionError("Nama, kolom atau fungsi agregat tidak sah.")
        result.append(key)
        terms.append((names.index(field), function))
    groups = {}
    for entry, evidence in records:
        key = tuple(entry[index] for index in axes)
        groups.setdefault(key, []).append((entry, evidence))
    output = []
    for key, group in sorted(groups.items()):
        values = tuple(_reducer(operation, [row[index] for row, _ in group if row[index] != ""])
                       for index, operation in terms)
        proof = tuple(sorted({site for _, evidence in group for site in evidence}))
        output.append((key + values, proof))
    return result, output


def _pivot(table, rule):
    obj(rule, ("op", "rows", "pivot", "measure", "function"))
    names, records = table
    axes = _axes(rule["rows"], names, "Indeks pivot")
    xi, value_index = [_axes([rule[key]], names, "Kolom pivot")[0] for key in ("pivot", "measure")]
    if len({*axes, xi, value_index}) != len(axes) + 2 or rule["function"] not in ("count", "sum", "mean", "min", "max"):
        raise ProductionError("Indeks, dimensi dan nilai pivot perlu berbeda.")
    keys = sorted({row[xi] for row, _ in records})
    if not keys or len(keys) > 60:
        raise ProductionError("Pivot membutuhkan 1–60 nilai dimensi.")
    headers = [names[index] for index in axes] + [identifier("by_" + key, "Label pivot") for key in keys]
    if len(set(headers)) != len(headers):
        raise ProductionError("Nama kolom pivot bertabrakan.")
    subgroups = {}
    trails = {}
    for row, proof in records:
        slot = tuple(row[index] for index in axes)
        subgroups.setdefault(slot, {}).setdefault(row[xi], []).append(row[value_index])
        trails.setdefault(slot, set()).update(proof)
    result = []
    for slot, entries in sorted(subgroups.items()):
        computed = tuple(_reducer(rule["function"], [value for value in entries[key] if value != ""])
                         if key in entries else "" for key in keys)
        result.append((slot + computed, tuple(sorted(trails[slot]))))
    return headers, result


def transform(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.production.table-plan.v1", ("tables", "input", "steps", "max_rows"))
    maximum = integer(plan["max_rows"], "Batas baris tabel", 1, 30000)
    tables = {}
    for row in items(plan["tables"], 12, 1):
        obj(row, ("id", "path", "sha256"))
        key = identifier(row["id"], "Tabel")
        if key in tables:
            raise ProductionError("ID tabel ganda.")
        raw = source_bytes(root, row["path"], row["sha256"], 3_000_000)
        tables[key] = _read_csv(raw, row["sha256"], maximum)
    selected = identifier(plan["input"], "Tabel masukan")
    if selected not in tables:
        raise ProductionError("Tabel masukan tidak ada.")
    table = tables[selected]
    trace = []
    for step in items(plan["steps"], 20, 1):
        if not isinstance(step, dict):
            raise ProductionError("Langkah tabel harus objek.")
        operation = step.get("op")
        before = len(table[1])
        if operation == "join":
            target = step.get("right")
            if target not in tables:
                raise ProductionError("Tabel kanan join belum terdaftar.")
            table = _join(table, tables[target], step, maximum)
        elif operation == "aggregate":
            table = _aggregate(table, step)
        elif operation == "pivot":
            table = _pivot(table, step)
        else:
            raise ProductionError("Langkah tabel belum didukung.")
        trace.append({"op": operation, "before": before, "after": len(table[1]), "columns": table[0]})
    output = StringIO(newline="")
    destination = csv.writer(output, lineterminator="\n")
    destination.writerow(table[0])
    destination.writerows(values for values, _ in table[1])
    raw = output.getvalue().encode()
    return raw, {"schema": "ace.production.table.v1", "plan_sha256": expected,
                 "rows": len(table[1]), "columns": table[0], "steps": trace, "output_sha256": sha256(raw).hexdigest(),
                 "row_provenance": [{"output_row": index, "input": [{"sha256": pointer, "line": line} for pointer, line in proof]}
                                    for index, (_, proof) in enumerate(table[1], 2)]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        payload, report = transform(decode(read(args.plan)), args.expect_sha256, args.root)
        with args.output.open("xb") as stream:
            stream.write(payload)
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, KeyError, TypeError, ArithmeticError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
