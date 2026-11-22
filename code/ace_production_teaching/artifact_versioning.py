"""Bekukan versi artefak dengan hash isi, parent yang terverifikasi, dan delta yang jelas."""
import argparse
from hashlib import sha256
from pathlib import Path
import sys

from ._artifacts import evidence, member_name
from ._contracts import (ProductionError, anchor, canonical, decode, digest, identifier,
                         integer, items, obj, read, schema, source_bytes)


def _parents(plan, root, name, revision):
    link = plan["parent"]
    if revision == 1:
        if link is not None:
            raise ProductionError("Versi pertama tidak memiliki parent.")
        return {}, None
    obj(link, ("path", "sha256"))
    raw = source_bytes(root, link["path"], link["sha256"], 500000)
    parent = decode(raw)
    schema(parent, "ace.production.artifact-version.v1", ("id", "version", "parent_sha256", "artifacts", "plan_sha256"))
    if parent["id"] != name or parent["version"] != revision - 1 or not isinstance(parent["artifacts"], dict):
        raise ProductionError("Identitas atau urutan parent tidak cocok.")
    for path, ref in parent["artifacts"].items():
        member_name(path)
        obj(ref, ("sha256", "bytes"))
        digest(ref["sha256"])
        integer(ref["bytes"], "Ukuran isi parent", 0, 16_000_000)
    return parent["artifacts"], link["sha256"]


def version(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.production.version-plan.v1", ("id", "version", "parent", "inputs"))
    name = identifier(plan["id"], "Artefak")
    revision = integer(plan["version"], "Versi", 1, 10000)
    earlier, parent = _parents(plan, root, name, revision)
    data = {}
    folded = set()
    total = 0
    for row in items(plan["inputs"], 150, 1):
        obj(row, ("path", "sha256", "name"))
        target = member_name(row["name"])
        if target.casefold() in folded or target.startswith("manifest.json/") or target.casefold() == "manifest.json":
            raise ProductionError("Path artefak mengulang atau menutupi manifest.")
        folded.add(target.casefold())
        raw = source_bytes(root, row["path"], row["sha256"], 16_000_000)
        total += len(raw)
        if total > 30_000_000:
            raise ProductionError("Versi artefak melampaui batas byte.")
        data[target] = raw
    if any(any(parent.as_posix().casefold() in folded for parent in Path(path).parents if parent != Path("."))
           for path in data):
        raise ProductionError("Anggota versi bertabrakan dengan direktori anggota lain.")
    now = evidence(data)
    change = {"added": sorted(now.keys() - earlier.keys()), "removed": sorted(earlier.keys() - now.keys()),
              "changed": sorted(key for key in earlier.keys() & now.keys() if now[key] != earlier[key]),
              "unchanged": sorted(key for key in earlier.keys() & now.keys() if now[key] == earlier[key])}
    manifest = {"schema": "ace.production.artifact-version.v1", "id": name, "version": revision,
                "plan_sha256": expected, "parent_sha256": parent, "artifacts": now}
    return data, {"schema": "ace.production.version-receipt.v1", "manifest": manifest,
                  "manifest_sha256": sha256(canonical(manifest) + b"\n").hexdigest(), "difference": change}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        files, receipt = version(decode(read(args.plan)), args.expect_sha256, args.root)
        args.output.mkdir()
        for name, raw in files.items():
            file = args.output / name
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(raw)
        (args.output / "manifest.json").write_bytes(canonical(receipt["manifest"]) + b"\n")
        sys.stdout.buffer.write(canonical(receipt) + b"\n")
    except (OSError, ValueError, TypeError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
