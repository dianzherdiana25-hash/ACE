"""Bekukan kontrak render dan periksa bahwa replay lokal menghasilkan byte yang sama."""
import argparse
from hashlib import sha256
from pathlib import Path
import sys

from ._contracts import ContractError, canonical, checked, decode, digest, identity, obj, read, schema
from .cover_maker import make_cover
from .image_generator import render
from .voice_generator import synthesize


_PROFILES = {
    "geometry_png": (render, ("image_generator.py", "_raster.py", "_contracts.py")),
    "cover_png": (make_cover, ("cover_maker.py", "image_generator.py", "image_qa.py",
                               "_lettering.py", "_raster.py", "_contracts.py")),
    "formant_wav": (synthesize, ("voice_generator.py", "_audio.py", "_contracts.py")),
}


def _build_id(profile):
    _, local_files = _PROFILES[profile]
    root = Path(__file__).parent
    return identity({name: sha256((root / name).read_bytes()).hexdigest() for name in sorted(local_files)})


def _execute(profile, plan, expected):
    if profile not in _PROFILES:
        raise ContractError("Profil resep render belum terdaftar.")
    call, _ = _PROFILES[profile]
    data, proof = call(plan, expected)
    if (profile == "cover_png" and proof["status"] != "pass"
            or profile == "geometry_png" and plan["format"] != "png"):
        raise ContractError("Render belum boleh dibekukan untuk profil resep.")
    return data


def freeze_recipe(profile, plan, expected):
    data = _execute(profile, plan, expected)
    recipe = {"schema": "ace.media.render-recipe.v1", "profile": profile, "input": plan,
              "input_sha256": expected, "implementation_sha256": _build_id(profile),
              "result": {"sha256": sha256(data).hexdigest(), "bytes": len(data)}}
    return data, recipe


def replay(recipe, expected):
    checked(recipe, expected)
    schema(recipe, "ace.media.render-recipe.v1",
           ("profile", "input", "input_sha256", "implementation_sha256", "result"))
    name = recipe["profile"]
    if name not in _PROFILES or _build_id(name) != digest(recipe["implementation_sha256"]):
        raise ContractError("Build renderer berbeda dari resep.")
    outcome = obj(recipe["result"], ("sha256", "bytes"))
    data = _execute(name, recipe["input"], recipe["input_sha256"])
    measured = {"sha256": sha256(data).hexdigest(), "bytes": len(data)}
    if measured != outcome:
        raise ContractError("Replay tidak byte-identik terhadap keluaran yang dibekukan.")
    return data, {"schema": "ace.media.render-replay.v1", "recipe_sha256": expected, "profile": name,
                  "artifact": measured, "byte_identical": True}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    make = modes.add_parser("freeze")
    make.add_argument("profile", choices=tuple(_PROFILES))
    make.add_argument("recipe_output", type=Path)
    run = modes.add_parser("replay")
    for mode in (make, run):
        mode.add_argument("input", type=Path)
        mode.add_argument("media_output", type=Path)
        mode.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        contract = decode(read(args.input))
        if args.mode == "freeze":
            data, report = freeze_recipe(args.profile, contract, args.expect_sha256)
            with args.recipe_output.open("xb") as stream:
                stream.write(canonical(report) + b"\n")
        else:
            data, report = replay(contract, args.expect_sha256)
        with args.media_output.open("xb") as stream:
            stream.write(data)
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, TypeError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
