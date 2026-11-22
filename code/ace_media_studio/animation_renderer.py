"""Render keyframe geometri 3D lokal dengan resep yang bisa diaudit ulang."""
import argparse
from hashlib import sha256
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

from ._contracts import (ContractError, canonical, checked, decode, entries,
                         identifier, integer, obj, read, schema)
from ._raster import MAX_BYTES, color, raster
from ._video import encode_frames
from .video_composer import video_size


_BLENDER_JOB = r"""
import bpy
import json
from pathlib import Path
from mathutils import Vector

root = Path(__file__).resolve().parent
with (root / "project.json").open(encoding="utf-8") as source:
    plan = json.load(source)
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = 3
scene.cycles.use_denoising = False
scene.render.threads_mode = "FIXED"
scene.render.threads = 1
scene.render.resolution_x = plan["width"]
scene.render.resolution_y = plan["height"]
scene.render.resolution_percentage = 100
scene.render.fps = plan["fps"]
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGB"
scene.frame_start = 1
scene.frame_end = plan["frames"]
scene.render.filepath = "//render"

world = bpy.data.worlds.new("Studio")
world.use_nodes = True
background = world.node_tree.nodes.get("Background")
background.inputs[0].default_value = (0.025, 0.025, 0.025, 1)
background.inputs[1].default_value = 1
scene.world = world

def point_at(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()

def units(vector):
    return [value / 1000 for value in vector]

camera = bpy.data.objects.new("Fixture camera", bpy.data.cameras.new("Local camera"))
scene.collection.objects.link(camera)
camera.location = units(plan["camera"])
camera.data.type = "ORTHO"
camera.data.ortho_scale = 7
point_at(camera, (0, 0, 0))
scene.camera = camera

light = bpy.data.objects.new("Key light", bpy.data.lights.new("Key light", "AREA"))
scene.collection.objects.link(light)
light.location = (3, -5, 7)
point_at(light, (0, 0, 0))
light.data.energy = 1300
light.data.shape = "DISK"
light.data.size = 5

for item in plan["objects"]:
    if item["shape"] == "cube":
        bpy.ops.mesh.primitive_cube_add()
    else:
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=12)
    obj = bpy.context.object
    obj.name = item["id"]
    obj.scale = units(item["scale"])
    mat = bpy.data.materials.new(item["id"] + "_material")
    mat.use_nodes = True
    mat.node_tree.nodes.get("Principled BSDF").inputs["Base Color"].default_value = [
        value / 255 for value in item["rgb"]] + [1]
    obj.data.materials.append(mat)
    for key in item["keyframes"]:
        obj.location = units(key["location"])
        obj.keyframe_insert(data_path="location", frame=key["frame"])

for frame in range(1, plan["frames"] + 1):
    scene.frame_set(frame)
    scene.render.filepath = str(root / ("render%04d.png" % frame))
    bpy.ops.render.render(write_still=True)
"""


def _vector(raw, label, floor, ceiling):
    if not isinstance(raw, list) or len(raw) != 3:
        raise ContractError(f"{label} perlu tiga sumbu.")
    return [integer(item, label, floor, ceiling) for item in raw]


def _prepare(plan):
    schema(plan, "ace.media.animation-plan.v1", ("width", "height", "fps", "frames", "camera", "objects"))
    width, height = video_size(plan["width"], plan["height"])
    count = integer(plan["frames"], "Jumlah frame", 2, 64)
    fps = integer(plan["fps"], "Frame rate", 2, 30)
    if width * height * count > 3_000_000:
        raise ContractError("Anggaran piksel-frame animasi terlampaui.")
    camera = _vector(plan["camera"], "Posisi kamera", -20000, 20000)
    if sum(axis * axis for axis in camera) < 4_000_000:
        raise ContractError("Posisi kamera terlalu dekat dengan titik pandang.")
    used = set()
    objects = []
    for item in entries(plan["objects"], 20, 1):
        obj(item, ("id", "shape", "color", "scale", "keyframes"))
        key = identifier(item["id"], "Objek")
        if key in used or item["shape"] not in ("cube", "sphere"):
            raise ContractError("ID duplikat atau bentuk objek tidak didukung.")
        used.add(key)
        rgb = color(item["color"])
        if rgb[3] != 255:
            raise ContractError("Material transparan belum didukung.")
        scale = _vector(item["scale"], "Skala objek", 50, 3000)
        nodes = []
        previous = 0
        for state in entries(item["keyframes"], count, 2):
            obj(state, ("frame", "location"))
            frame = integer(state["frame"], "Frame key", previous + 1, count)
            nodes.append({"frame": frame, "location": _vector(state["location"], "Lokasi", -5000, 5000)})
            previous = frame
        if nodes[0]["frame"] != 1 or nodes[-1]["frame"] != count:
            raise ContractError("Keyframe harus menambatkan awal dan akhir adegan.")
        objects.append({"id": key, "shape": item["shape"], "rgb": list(rgb[:3]), "scale": scale, "keyframes": nodes})
    return {"width": width, "height": height, "fps": fps, "frames": count, "camera": camera, "objects": objects}


def _run_blender(root, project):
    blender = shutil.which("blender")
    if blender is None:
        raise ContractError("Backend Blender tidak tersedia.")
    (root / "project.json").write_bytes(canonical(project))
    (root / "render_job.py").write_text(_BLENDER_JOB, encoding="utf-8")
    try:
        result = subprocess.run([blender, "--factory-startup", "--disable-autoexec", "--background",
                                 "--python-exit-code", "4", "--python", str(root / "render_job.py")],
                                cwd=root, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, check=True, timeout=180)
    except subprocess.TimeoutExpired as error:
        raise ContractError("Render Blender melewati batas waktu.") from error
    except subprocess.CalledProcessError as error:
        details = error.output.decode(errors="replace").splitlines()[-7:]
        raise ContractError("Render Blender gagal: " + " ".join(details)[:480]) from error
    frames = [raster(read(root / f"render{index:04d}.png", MAX_BYTES))
              for index in range(1, project["frames"] + 1)]
    version = next((line for line in result.stdout.decode(errors="replace").splitlines()
                    if line.startswith("Blender ")), "Blender")
    return frames, version


def animate(plan, expected):
    checked(plan, expected)
    project = _prepare(plan)
    with TemporaryDirectory(prefix="ace-media-animation-") as temporary:
        root = Path(temporary)
        frames, version = _run_blender(root, project)
        content, video = encode_frames(root, frames, project["width"], project["height"], project["fps"])
    return content, {"schema": "ace.media.animation-receipt.v1", "plan_sha256": expected,
                     "renderer": version, "backend": "cycles_cpu",
                     "project_sha256": sha256(canonical(project)).hexdigest(),
                     "objects": [{key: item[key] for key in ("id", "shape", "keyframes")} for item in project["objects"]],
                     "rgb_frame_sha256": [frame.receipt()["rgb_sha256"] for frame in frames], **video}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        content, receipt = animate(decode(read(args.plan)), args.expect_sha256)
        with args.output.open("xb") as stream:
            stream.write(content)
        sys.stdout.buffer.write(canonical(receipt) + b"\n")
    except (OSError, ValueError, TypeError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
