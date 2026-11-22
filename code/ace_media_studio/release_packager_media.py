"""Rakit draf rilis multiprofil hanya dari media, QA, dan metadata yang lolos preflight."""
import argparse
from hashlib import sha256
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

from ._assets import asset
from ._contracts import (ContractError, canonical, checked, decode, entries,
                         identifier, integer, obj, read, schema)
from ._raster import MAX_BYTES, raster
from ._video import MAX_MOVIE, load_movie


def pack_release(plan, expected, root):
    checked(plan, expected)
    schema(plan, "ace.media.release-plan.v1", ("project", "targets", "max_total_bytes"))
    project = identifier(plan["project"], "Proyek rilis")
    maximum = integer(plan["max_total_bytes"], "Batas rilis", 1000, 100_000_000)
    outputs = {}
    staged = []
    total = 0
    for row in entries(plan["targets"], 8, 1):
        obj(row, ("id", "video", "cover", "metadata", "brand_audit", "limits"))
        key = identifier(row["id"], "Profil rilis")
        if key in outputs:
            raise ContractError("Profil rilis ganda.")
        limits = obj(row["limits"], ("max_bytes", "max_width", "max_height", "requires_audio"))
        cap = integer(limits["max_bytes"], "Batas byte video", 256, MAX_MOVIE)
        width = integer(limits["max_width"], "Lebar video", 16, 960)
        height = integer(limits["max_height"], "Tinggi video", 16, 960)
        if type(limits["requires_audio"]) is not bool:
            raise ContractError("Kebutuhan audio perlu boolean.")
        work = {}
        for field, cap_bytes in (("video", cap), ("cover", MAX_BYTES), ("metadata", 100_000), ("brand_audit", 100_000)):
            ref = obj(row[field], ("path", "sha256"))
            work[field] = asset(root, ref["path"], ref["sha256"], cap_bytes)
        total += sum(map(len, work.values()))
        if total > maximum:
            raise ContractError("Draf rilis melampaui total byte.")
        metadata = decode(work["metadata"])
        audit = decode(work["brand_audit"])
        anchor = row["video"]["sha256"]
        if (not isinstance(metadata, dict) or metadata.get("schema") != "ace.media.metadata-receipt.v1"
                or metadata.get("status") != "ready" or metadata.get("media_sha256") != anchor
                or metadata.get("platform") != key or not isinstance(metadata.get("upload_fields"), dict)):
            raise ContractError(f"Metadata untuk {key} belum siap atau hash video berbeda.")
        if (not isinstance(audit, dict) or audit.get("schema") != "ace.media.brand-audit.v1"
                or audit.get("status") != "eligible_on_annotated_tracks" or audit.get("asset_sha256") != anchor
                or audit.get("coverage_gaps") != [] or audit.get("findings") != []):
            raise ContractError(f"Audit merek untuk {key} belum siap atau hash video berbeda.")
        with TemporaryDirectory(prefix="ace-media-release-check-") as temporary:
            frames, fps, pcm = load_movie(Path(temporary), work["video"])
        thumbnail = raster(work["cover"])
        size = [frames[0].width, frames[0].height]
        if size[0] > width or size[1] > height or (limits["requires_audio"] and pcm is None):
            raise ContractError(f"Video untuk {key} melampaui profil.")
        if thumbnail.width < 32 or thumbnail.height < 16 or not work["cover"].startswith(b"\x89PNG\r\n\x1a\n"):
            raise ContractError("Sampul perlu PNG dengan lebar minimum 32 dan tinggi minimum 16.")
        outputs[key] = {"video.mp4": work["video"], "cover.png": work["cover"],
                        "metadata.json": work["metadata"], "brand_audit.json": work["brand_audit"]}
        staged.append({"id": key, "dimensions": size, "frames": len(frames), "fps": fps,
                       "assets": {name: {"sha256": sha256(data).hexdigest(), "bytes": len(data)}
                                  for name, data in sorted(outputs[key].items())}})
    return outputs, {"schema": "ace.media.release-manifest.v1", "plan_sha256": expected, "project": project,
                     "state": "local_draft", "total_bytes": total, "targets": sorted(staged, key=lambda row: row["id"])}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("asset_root", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        bundles, report = pack_release(decode(read(args.plan)), args.expect_sha256, args.asset_root)
        args.output.mkdir()
        for key, files in bundles.items():
            target = args.output / key
            target.mkdir()
            for name, data in files.items():
                (target / name).write_bytes(data)
        (args.output / "manifest.json").write_bytes(canonical(report) + b"\n")
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, TypeError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
