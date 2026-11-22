"""Bandingkan pin dependensi dengan katalog dan advisori yang dibekukan.

Analisis lokal memakai subset versi X.Y.Z dan interval eksplisit.
Saran pin hanya memilih rilis yang terdaftar, dalam rentang kebijakan,
dan bebas kecocokan pada snapshot advisori yang disediakan.
"""
import argparse
from pathlib import Path
import re
import sys

from ._contracts import ContractError, canonical, checked, decode, digest, entries, obj, read, schema, text


PACKAGE = re.compile(r"[a-zA-Z0-9](?:[a-zA-Z0-9._-]{0,100}[a-zA-Z0-9])?")
VERSION = re.compile(r"(0|[1-9][0-9]{0,8})\.(0|[1-9][0-9]{0,8})\.(0|[1-9][0-9]{0,8})")


def _name(value):
    if not isinstance(value, str) or not PACKAGE.fullmatch(value):
        raise ContractError("Nama dependensi tidak sah.")
    return re.sub(r"[-_.]+", "-", value.casefold())


def _version(value):
    match = VERSION.fullmatch(value) if isinstance(value, str) else None
    if match is None:
        raise ContractError("Versi perlu format final X.Y.Z.")
    return tuple(int(part) for part in match.groups())


def _interval(raw):
    obj(raw, ("min_inclusive", "max_exclusive"))
    limits = tuple(_version(raw[key]) if raw[key] is not None else None for key in ("min_inclusive", "max_exclusive"))
    if all(limit is not None for limit in limits) and limits[0] >= limits[1]:
        raise ContractError("Interval versi terbalik atau kosong.")
    return limits


def _includes(limits, version):
    lower, upper = limits
    return (lower is None or lower <= version) and (upper is None or version < upper)


def _index(catalog, advisories):
    schema(catalog, "ace.factory-package-catalog.v1", ("ref", "packages"))
    schema(advisories, "ace.factory-package-advisories.v1", ("ref", "advisories"))
    text(catalog["ref"], "Rujukan katalog")
    text(advisories["ref"], "Rujukan advisori")
    releases = {}
    for row in entries(catalog["packages"], 500):
        obj(row, ("name", "releases"))
        package = _name(row["name"])
        if package in releases:
            raise ContractError("Nama paket katalog ganda setelah normalisasi.")
        known = {}
        for raw in entries(row["releases"], 500):
            obj(raw, ("version", "sha256", "yanked"))
            version = _version(raw["version"])
            if version in known or type(raw["yanked"]) is not bool:
                raise ContractError("Versi katalog ganda atau status yanked tidak sah.")
            known[version] = {"version": raw["version"], "sha256": digest(raw["sha256"]), "yanked": raw["yanked"]}
        releases[package] = known
    all_advisories = set()
    risks = {}
    for entry in entries(advisories["advisories"], 2000):
        obj(entry, ("id", "package", "affected", "source_ref"))
        key = text(entry["id"], "ID advisori", 100)
        if key in all_advisories:
            raise ContractError("ID advisori ganda.")
        all_advisories.add(key)
        interval = _interval(entry["affected"])
        if interval == (None, None):
            raise ContractError("Advisori perlu minimal satu batas eksplisit.")
        row = {"id": key, "source_ref": text(entry["source_ref"], "Rujukan advisori", 250)}
        risks.setdefault(_name(entry["package"]), []).append((interval, row))
    return releases, risks


def inspect(plan, catalog, advisories, expected):
    checked(plan, expected)
    schema(plan, "ace.factory-dependency-plan.v1", ("source_ref", "catalog_sha256", "advisories_sha256", "pins"))
    text(plan["source_ref"], "Rujukan pin")
    checked(catalog, plan["catalog_sha256"])
    checked(advisories, plan["advisories_sha256"])
    inventory, risks = _index(catalog, advisories)
    report = {}
    for raw in entries(plan["pins"], 500):
        obj(raw, ("name", "version", "sha256", "allowed", "source_ref"))
        name = _name(raw["name"])
        if name in report:
            raise ContractError("Dependensi ganda setelah normalisasi.")
        version = _version(raw["version"])
        anchor = digest(raw["sha256"])
        allowed = _interval(raw["allowed"])
        source = text(raw["source_ref"], "Rujukan dependensi", 250)
        known = inventory.get(name, {})
        pinned = known.get(version)
        issues = []
        if pinned is None:
            issues.append("pin_not_in_catalog")
        else:
            if pinned["sha256"] != anchor:
                issues.append("pin_hash_mismatch")
            if pinned["yanked"]:
                issues.append("pin_yanked")
        if not _includes(allowed, version):
            issues.append("pin_outside_policy")
        rules = risks.get(name, ())
        matched = sorted((row for span, row in rules if _includes(span, version)), key=lambda row: row["id"])
        if matched:
            issues.append("advisory_match")
        target = next((known[candidate] for candidate in sorted(known)
                       if candidate > version and _includes(allowed, candidate) and not known[candidate]["yanked"]
                       and not any(_includes(span, candidate) for span, _ in rules)), None)
        report[name] = {"name": name, "pin": raw["version"], "sha256": anchor, "source_ref": source, "issues": issues,
                        "advisories": matched, "next_allowed_pin": target}
    rows = [report[key] for key in sorted(report)]
    return {"schema": "ace.factory-dependency-report.v1", "plan_sha256": expected,
            "catalog_ref": catalog["ref"], "advisories_ref": advisories["ref"], "pins": rows,
            "status": "review_required" if any(row["issues"] for row in rows) else "snapshot_checks_passed"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("plan", "catalog", "advisories"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        result = inspect(*(decode(read(getattr(args, name))) for name in ("plan", "catalog", "advisories")),
                         args.expect_sha256)
        sys.stdout.buffer.write(canonical(result) + b"\n")
    except (OSError, ValueError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return int(result["status"] == "review_required")


if __name__ == "__main__":
    raise SystemExit(main())
