"""Rakit draf kampanye dengan dependensi aset, slot waktu, dan cakupan grant dari berkas."""
import argparse
from datetime import datetime
from hashlib import sha256
from pathlib import Path
import sys

from ._assets import asset
from ._contracts import (ContractError, canonical, checked, decode, digest, entries,
                         identity, identifier, integer, obj, read, schema, text)
from ._raster import MAX_BYTES, raster
from .asset_rights import check_rights
from ._video import MAX_MOVIE


ROLES = {"main": ("mp4", MAX_MOVIE), "teaser": ("mp4", MAX_MOVIE), "cover": ("png", MAX_BYTES),
         "caption": ("txt", 100000), "subtitles": ("vtt", 100000)}


def _timestamp(raw):
    if not isinstance(raw, str):
        raise ContractError("Jadwal butuh waktu UTC.")
    try:
        result = datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as error:
        raise ContractError("Jadwal butuh waktu UTC kanonis.") from error
    if result.strftime("%Y-%m-%dT%H:%M:%SZ") != raw:
        raise ContractError("Jadwal butuh waktu UTC kanonis.")
    return result


def _media(data, extension):
    if extension == "png":
        raster(data)
        if not data.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ContractError("Bahan sampul bukan PNG.")
    elif extension == "mp4":
        if data[4:8] != b"ftyp" or len(data) < 32:
            raise ContractError("Bahan video tidak memiliki header MP4.")
    elif not data.decode("utf-8").strip() or (extension == "vtt" and not data.startswith(b"WEBVTT\n")):
        raise ContractError("Bahan teks kosong atau subtitle tidak sesuai WebVTT.")


def campaign(plan, expected, root):
    checked(plan, expected)
    schema(plan, "ace.media.campaign-plan.v1", ("id", "source_ref", "rights_registry", "max_total_bytes", "releases"))
    campaign_id = identifier(plan["id"], "Kampanye")
    source = text(plan["source_ref"], "Pointer brief kampanye")
    max_bytes = integer(plan["max_total_bytes"], "Batas total kampanye", 1000, 100_000_000)
    rights = obj(plan["rights_registry"], ("path", "sha256"))
    registry = decode(asset(root, rights["path"], rights["sha256"], 1_000_000))
    registry_anchor = identity(registry)
    payloads = {}
    upcoming = []
    slots = set()
    previous = set()
    total = 0
    for row in entries(plan["releases"], 36, 1):
        obj(row, ("id", "channel", "at_utc", "after", "intent", "assets"))
        key = identifier(row["id"], "Rilis")
        channel = identifier(row["channel"], "Kanal")
        timestamp = _timestamp(row["at_utc"])
        intent_ref = obj(row["intent"], ("path", "sha256"))
        intent = decode(asset(root, intent_ref["path"], intent_ref["sha256"], 500_000))
        result = check_rights(registry, registry_anchor, intent, identity(intent))
        if (result["status"] != "recorded_grants_cover_intent" or intent["use"] != "campaign"
                or intent["date"] != timestamp.date().isoformat()):
            raise ContractError("Grant kampanye belum mencakup penggunaan pada tanggal rilis.")
        allowed = {item["sha256"] for item in result["assets"]}
        slot = (channel, timestamp)
        if key in previous or slot in slots:
            raise ContractError("ID atau slot kanal rilis ganda.")
        previous.add(key)
        slots.add(slot)
        dependencies = [identifier(item, "Ketergantungan rilis") for item in entries(row["after"], 36)]
        if len(set(dependencies)) != len(dependencies):
            raise ContractError("Ketergantungan rilis ganda.")
        roster = {}
        for ref in entries(row["assets"], len(ROLES), 3):
            obj(ref, ("role", "path", "sha256"))
            role = ref["role"]
            if role not in ROLES or role in roster or digest(ref["sha256"]) not in allowed:
                raise ContractError("Peran aset ganda/tidak sah atau hash tanpa grant.")
            suffix, cap = ROLES[role]
            contents = asset(root, ref["path"], ref["sha256"], cap)
            _media(contents, suffix)
            total += len(contents)
            if total > max_bytes:
                raise ContractError("Jumlah byte kampanye melebihi batas.")
            target = f"{key}/{role}.{suffix}"
            payloads[target] = contents
            roster[role] = {"file": target, "sha256": sha256(contents).hexdigest(), "bytes": len(contents)}
        if "cover" not in roster or "caption" not in roster or len({"main", "teaser"} & roster.keys()) != 1:
            raise ContractError("Setiap rilis perlu sampul, caption, dan tepat satu video.")
        upcoming.append({"id": key, "channel": channel, "at_utc": row["at_utc"], "after": dependencies,
                         "intent_sha256": intent_ref["sha256"], "assets": roster})
    times = {row["id"]: _timestamp(row["at_utc"]) for row in upcoming}
    for row in upcoming:
        if any(dependency not in times or times[dependency] >= times[row["id"]] for dependency in row["after"]):
            raise ContractError("Rilis ketergantungan harus ada dan mendahului pemakai.")
    ordered = sorted(upcoming, key=lambda row: (row["at_utc"], row["channel"], row["id"]))
    return payloads, {"schema": "ace.media.campaign-manifest.v1", "plan_sha256": expected, "id": campaign_id,
                      "source_ref": source, "rights_registry_sha256": rights["sha256"], "total_bytes": total,
                      "status": "local_draft", "schedule": ordered}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("asset_root", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        files, report = campaign(decode(read(args.plan)), args.expect_sha256, args.asset_root)
        args.output.mkdir()
        for name, data in files.items():
            path = args.output / name
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(data)
        (args.output / "campaign.json").write_bytes(canonical(report) + b"\n")
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, TypeError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
