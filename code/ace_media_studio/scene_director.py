"""Jaga kontinuitas kamera, pemeran dan waktu ketika storyboard dipecah menjadi shot."""
import argparse
from pathlib import Path
import sys

from ._contracts import (ContractError, canonical, checked, decode, entries,
                         identifier, integer, obj, read, schema, text)


SHOT_TYPES = {"establishing": 0, "wide": 1, "medium": 2, "close": 3, "insert": 4}


def _cast(catalog):
    available = {}
    for actor in entries(catalog, 32, 1):
        obj(actor, ("id", "wardrobe"))
        key = identifier(actor["id"], "Pemeran")
        clothing = [identifier(item, "Wardrobe") for item in entries(actor["wardrobe"], 16, 1)]
        if key in available or len(set(clothing)) != len(clothing):
            raise ContractError("Duplikat identitas pemeran atau wardrobe.")
        available[key] = set(clothing)
    return available


def direct(plan, expected):
    checked(plan, expected)
    schema(plan, "ace.media.storyboard.v1", ("project", "fps", "cast", "scenes"))
    key = identifier(plan["project"], "Proyek")
    fps = integer(plan["fps"], "FPS", 2, 60)
    cast = _cast(plan["cast"])
    shots = []
    scene_ids = set()
    shot_ids = set()
    pending = []
    cursor = 0
    for scene in entries(plan["scenes"], 40, 1):
        obj(scene, ("id", "location", "source_ref", "wardrobe_change", "shots"))
        scene_id = identifier(scene["id"], "Adegan")
        if scene_id in scene_ids:
            raise ContractError("ID adegan ganda.")
        scene_ids.add(scene_id)
        source = text(scene["source_ref"], "Rujukan storyboard")
        location = text(scene["location"], "Lokasi")
        allowed_changes = [identifier(actor, "Pemeran") for actor in entries(scene["wardrobe_change"], 32)]
        if len(set(allowed_changes)) != len(allowed_changes) or not set(allowed_changes) <= set(cast):
            raise ContractError("Daftar pergantian wardrobe tidak sah.")
        previous = None
        costumes = {}
        for raw in entries(scene["shots"], 50, 1):
            obj(raw, ("id", "type", "frames", "axis", "cast", "dialogue_words", "notes"))
            shot = identifier(raw["id"], "Shot")
            if shot in shot_ids or raw["type"] not in SHOT_TYPES or raw["axis"] not in ("left", "right", "neutral"):
                raise ContractError("ID, skala shot, atau sisi kamera tidak sah.")
            shot_ids.add(shot)
            frames = integer(raw["frames"], "Frame shot", 1, 3600)
            words = integer(raw["dialogue_words"], "Kata dialog", 0, 2000)
            actors = {}
            for appearance in entries(raw["cast"], 32):
                obj(appearance, ("id", "wardrobe"))
                actor = identifier(appearance["id"], "Pemeran")
                wardrobe = identifier(appearance["wardrobe"], "Wardrobe")
                if actor in actors or actor not in cast or wardrobe not in cast[actor]:
                    raise ContractError("Pemeran atau wardrobe tidak terdaftar.")
                actors[actor] = wardrobe
                if actor in costumes and wardrobe != costumes[actor] and actor not in allowed_changes:
                    pending.append({"shot": shot, "rule": "wardrobe_jump", "actor": actor,
                                    "before": costumes[actor], "after": wardrobe})
                costumes[actor] = wardrobe
            if previous is None and SHOT_TYPES[raw["type"]] > 1:
                pending.append({"shot": shot, "rule": "no_establishing_context"})
            if previous and {previous["axis"], raw["axis"]} == {"left", "right"} and not actors.keys().isdisjoint(previous["cast"]):
                pending.append({"shot": shot, "rule": "axis_flip", "previous_shot": previous["id"]})
            if words * fps > 3 * frames:
                pending.append({"shot": shot, "rule": "dialogue_time", "words": words, "frames": frames})
            result = {"id": shot, "source_ref": source, "scene": scene_id, "location": location,
                      "type": raw["type"], "axis": raw["axis"], "cast": actors, "first_frame": cursor,
                      "end_frame_exclusive": cursor + frames, "notes": text(raw["notes"], "Arahan shot")}
            previous = result
            shots.append(result)
            cursor += frames
            if len(shots) > 300 or cursor > fps * 1200:
                raise ContractError("Storyboard melampaui anggaran shot atau dua puluh menit.")
    return {"schema": "ace.media.director-plan.v1", "project": key, "plan_sha256": expected,
            "fps": fps, "frames": cursor, "shots": shots, "continuity_findings": pending,
            "status": "hold_for_review" if pending else "ready"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("storyboard", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        report = direct(decode(read(args.storyboard)), args.expect_sha256)
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, TypeError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return int(report["status"] != "ready")


if __name__ == "__main__":
    raise SystemExit(main())
