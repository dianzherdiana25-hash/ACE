"""Cocokkan rencana penggunaan aset dengan hibah lisensi yang tercatat dan tertambat."""
import argparse
from datetime import date
from pathlib import Path
import re
import sys

from ._contracts import (ContractError, canonical, checked, decode, digest, entries,
                         identifier, obj, read, schema, text)


COUNTRY = re.compile(r"[A-Z]{2}")


def _date(raw):
    try:
        parsed = date.fromisoformat(raw)
    except (TypeError, ValueError) as error:
        raise ContractError("Tanggal lisensi perlu format YYYY-MM-DD.") from error
    if raw != parsed.isoformat():
        raise ContractError("Tanggal lisensi harus kanonis.")
    return parsed


def _countries(raw):
    countries = entries(raw, 180, 1)
    if any(not isinstance(item, str) or (item != "*" and not COUNTRY.fullmatch(item)) for item in countries):
        raise ContractError("Wilayah lisensi perlu kode negara atau *.")
    return set(countries)


def check_rights(policy, expected, usage, usage_anchor):
    checked(policy, expected)
    checked(usage, usage_anchor)
    schema(policy, "ace.media.rights-registry.v1", ("grants",))
    schema(usage, "ace.media.rights-intent.v1", ("use", "date", "territories", "assets"))
    operation = identifier(usage["use"], "Tujuan penggunaan")
    date_used = _date(usage["date"])
    territories = _countries(usage["territories"])
    grants = {}
    labels = set()
    for row in entries(policy["grants"], 400, 1):
        obj(row, ("id", "asset_sha256", "license_ref", "uses", "territories", "effective", "expires", "credit"))
        key = identifier(row["id"], "Hibah")
        if key in labels:
            raise ContractError("ID hibah aset ganda.")
        labels.add(key)
        asset = digest(row["asset_sha256"])
        allowed = {identifier(purpose, "Penggunaan lisensi") for purpose in entries(row["uses"], 30, 1)}
        country = _countries(row["territories"])
        date_start, date_stop = _date(row["effective"]), _date(row["expires"])
        if date_stop < date_start:
            raise ContractError("Akhir masa lisensi mendahului awal.")
        credit = None if row["credit"] is None else text(row["credit"], "Teks kredit")
        pointer = text(row["license_ref"], "Pointer bukti lisensi")
        grants.setdefault(asset, []).append((key, allowed, country, date_start, date_stop, pointer, credit))
    result = []
    seen = set()
    for row in entries(usage["assets"], 200, 1):
        obj(row, ("id", "sha256", "credits"))
        key = identifier(row["id"], "Aset rencana")
        if key in seen:
            raise ContractError("ID aset rencana ganda.")
        seen.add(key)
        anchor = digest(row["sha256"])
        credits = {text(line, "Teks atribusi") for line in entries(row["credits"], 40)}
        eligible = []
        denials = []
        for grant, uses, countries, start, end, pointer, credit in sorted(grants.get(anchor, [])):
            reasons = []
            if operation not in uses:
                reasons.append("use")
            if "*" not in countries and not territories <= countries:
                reasons.append("territory")
            if not start <= date_used <= end:
                reasons.append("date")
            if credit is not None and credit not in credits:
                reasons.append("credit")
            decision = {"grant": grant, "license_ref": pointer}
            if reasons:
                denials.append({**decision, "reasons": reasons})
            else:
                eligible.append(decision)
        result.append({"id": key, "sha256": anchor, "eligible_grants": eligible, "denials": denials,
                       "status": "covered" if eligible else ("gap" if denials else "unlisted")})
    return {"schema": "ace.media.rights-check.v1", "registry_sha256": expected, "intent_sha256": usage_anchor,
            "basis": "recorded_grants_only", "assets": result,
            "status": "recorded_grants_cover_intent" if all(row["eligible_grants"] for row in result) else "hold"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("registry", type=Path)
    parser.add_argument("intent", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    parser.add_argument("--intent-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        report = check_rights(decode(read(args.registry)), args.expect_sha256,
                              decode(read(args.intent)), args.intent_sha256)
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, TypeError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return int(report["status"] == "hold")


if __name__ == "__main__":
    raise SystemExit(main())
