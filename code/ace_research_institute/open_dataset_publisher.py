"""Siapkan dataset lokal dengan lisensi, kolom rilis eksplisit dan pemeriksaan kelompok kecil."""
import argparse
from collections import Counter
import csv
from hashlib import sha256
from io import StringIO
from pathlib import Path
import sys

from ._contracts import (ResearchError, anchor, canonical, decode, identifier, integer, items,
                         obj, read, schema, source_bytes, text)
from ._tabular import load, serialize


def prepare_dataset(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.institute.open-dataset-plan.v1", ("dataset", "format", "columns", "policy", "license"))
    dataset = obj(plan["dataset"], ("path", "sha256"))
    table = load(source_bytes(root, dataset["path"], dataset["sha256"], 3_000_000), dataset["sha256"], plan["format"])
    policy = obj(plan["policy"], ("min_group", "rare_groups"))
    minimum = integer(policy["min_group"], "Ukuran kelompok minimum", 2, 100)
    action = policy["rare_groups"]
    if action not in ("suppress", "hold"):
        raise ResearchError("Kebijakan kelompok kecil perlu suppress atau hold.")
    license = obj(plan["license"], ("id", "path", "sha256", "approved_scope"))
    license_id = text(license["id"], "Lisensi", 70)
    decision = text(license["approved_scope"], "Pointer persetujuan cakupan")
    if not source_bytes(root, license["path"], license["sha256"], 100000).strip():
        raise ResearchError("Bukti izin belum memiliki isi.")
    roles = {}
    for row in items(plan["columns"], 80, 1):
        obj(row, ("id", "release_role"))
        name = identifier(row["id"], "Kolom rilis")
        if name in roles or name not in table.columns or row["release_role"] not in (
                "public", "quasi_identifier", "direct_identifier", "restricted"):
            raise ResearchError("Klasifikasi kolom ganda atau tidak sah.")
        roles[name] = row["release_role"]
    if roles.keys() != table.columns.keys():
        raise ResearchError("Kolom tanpa klasifikasi rilis.")
    disclosed = [name for name in table.columns if roles[name] in ("public", "quasi_identifier")]
    quasi = [name for name in disclosed if roles[name] == "quasi_identifier"]
    if not disclosed:
        raise ResearchError("Tidak ada kolom rilis.")
    grouped = [tuple(row["cells"][field] for field in quasi) for row in table.rows]
    counts = Counter(grouped)
    keep = [index for index, key in enumerate(grouped) if counts[key] >= minimum and None not in key]
    withheld = len(grouped) - len(keep)
    release = bool(keep) and not table.rejected and (not withheld or action == "suppress")
    raw = None
    if release:
        stream = StringIO(newline="")
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(disclosed)
        for index in keep:
            cells = table.rows[index]["cells"]
            writer.writerow([serialize(cells[name], table.columns[name]) for name in disclosed])
        raw = stream.getvalue().encode()
    data = {"schema": "ace.institute.dataset-draft.v1", "plan_sha256": expected, "state": "local_draft" if release else "hold",
            "dataset": dataset, "license": {**license, "id": license_id, "approved_scope": decision},
            "columns": disclosed, "dropped_columns": [key for key in table.columns if key not in disclosed],
            "min_group": minimum, "rare_groups_policy": action, "suppressed_rows": withheld,
            "rejected_records": len(table.rejected), "written_rows": len(keep) if release else 0,
            "csv_sha256": sha256(raw).hexdigest() if raw is not None else None,
            "basis": "declared_roles_and_quasi_identifier_counts"}
    return raw, data


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        payload, report = prepare_dataset(decode(read(args.plan)), args.expect_sha256, args.root)
        if payload is not None:
            args.output.mkdir()
            (args.output / "dataset.csv").write_bytes(payload)
            (args.output / "manifest.json").write_bytes(canonical(report) + b"\n")
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, KeyError, TypeError, ArithmeticError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return int(payload is None)


if __name__ == "__main__":
    raise SystemExit(main())
