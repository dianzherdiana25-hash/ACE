"""Ambil keyframe video lokal dengan cap waktu dari stream yang sama.

Probe dan render hanya memakai demuxer setempat dengan batas waktu,
jumlah frame dan resolusi. Roster diwajibkan cocok secara berurutan
dengan frame yang berhasil dirender. Manifest mencatat SHA-256 rasters
dan rentang probe agar cuplikan tidak dianggap rekaman lengkap.
"""
import argparse
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

from . import _raster
from .audio_pipeline import _canonical, _integer
from .ocr_engine import _pairs


MAX_VIDEO_BYTES = 32_000_000
MAX_PROBE_BYTES = 2_000_000
MAX_FRAMES = 24
MAX_EDGE = 800
TIME_BASE = re.compile(r"showinfo[^\n]*config in time_base: ([0-9]{1,10})/([0-9]{1,10})")
FRAME_TIME = re.compile(r"showinfo[^\n]*?\bn:\s*([0-9]{1,8})\s+pts:\s*(-?[0-9]{1,18})")
FRAME_FILE = re.compile(r"frame-([0-9]{6})\.pgm")
ALLOWED_DEMUXERS = "matroska,webm,mov,mp4,m4a,3gp,3g2,mj2,avi"


def _timestamp(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{1,10}(?:\.[0-9]{1,9})?", value):
        raise ValueError("Cap waktu keyframe tidak dapat diperiksa.")
    try:
        return int(Decimal(value)*1_000_000)
    except (ValueError, InvalidOperation, OverflowError) as error:
        raise ValueError("Cap waktu keyframe tidak sah.") from error


def _entries(data, cap):
    raw = json.loads(data.decode("utf-8"), object_pairs_hook=_pairs)
    if not isinstance(raw, dict) or not isinstance(raw.get("frames"), list):
        raise ValueError("Probe video tidak mengembalikan daftar frame.")
    stamps = []
    previous = -1
    for row in raw["frames"]:
        if not isinstance(row, dict) or row.get("key_frame") != 1:
            raise ValueError("Probe mengembalikan frame di luar filter keyframe.")
        current = _timestamp(row.get("best_effort_timestamp_time"))
        if current <= previous:
            raise ValueError("Cap waktu keyframe tidak naik.")
        stamps.append(current)
        previous = current
    if not stamps:
        raise ValueError("Tidak ada keyframe pada horizon probe.")
    return stamps[:cap], len(stamps)


def _invoke(arguments, folder, timeout, stdout, stderr=subprocess.DEVNULL):
    try:
        process = subprocess.run(arguments, cwd=folder, stdin=subprocess.DEVNULL, stdout=stdout,
                                 stderr=stderr, check=False, timeout=timeout)
    except subprocess.TimeoutExpired as error:
        raise ValueError("Alat video melewati batas waktu.") from error
    if process.returncode:
        raise ValueError(f"Alat video berhenti dengan status {process.returncode}.")


def _check_render_times(log, expected):
    content = log.decode("utf-8", errors="replace")
    bases = {(int(a), int(b)) for a, b in TIME_BASE.findall(content)}
    rendered = FRAME_TIME.findall(content)
    if len(bases) != 1 or len(rendered) < len(expected):
        raise ValueError("Cap waktu render tidak lengkap.")
    numerator, denominator = bases.pop()
    if not numerator or not denominator:
        raise ValueError("Timebase frame render tidak sah.")
    for index, ((n, pts), wanted) in enumerate(zip(rendered, expected)):
        stamp = int(pts)*numerator*1_000_000//denominator
        if int(n) != index or abs(stamp-wanted) > 1:
            raise ValueError("Cap waktu frame render berbeda dari hasil probe.")


def _load_artifacts(stage, expected, edge):
    frames = {}
    for path in stage.iterdir():
        match = FRAME_FILE.fullmatch(path.name)
        if not match:
            if path.name in {"input.video", "roster.json", "render.log"}:
                continue
            raise ValueError("Renderer menghasilkan nama yang tidak terdaftar.")
        number = int(match[1])
        if number < 1 or number > len(expected) or path.is_symlink() or not path.is_file():
            raise ValueError("Frame hasil di luar roster.")
        data = _raster.read(path, edge*edge+512)
        image = _raster.decode(data)
        if max(image.width, image.height) > edge:
            raise ValueError("Resolusi frame melampaui batas.")
        frames[number] = {"file": path.name, "bytes": len(data), "sha256": sha256(data).hexdigest(),
                          "width": image.width, "height": image.height, "time_us": expected[number-1],
                          "data": data}
    if set(frames) != set(range(1, len(expected)+1)):
        raise ValueError("Jumlah frame render tidak cocok dengan roster.")
    outputs, records = {}, []
    for _, row in sorted(frames.items()):
        outputs[row["file"]] = row.pop("data")
        records.append(row)
    return outputs, records


def sample(video, *, maximum_frames=8, long_edge=640, scan_seconds=60, timeout_seconds=25):
    if not isinstance(video, bytes) or not 1 <= len(video) <= MAX_VIDEO_BYTES:
        raise ValueError("Berkas video terlalu besar atau kosong.")
    maximum = _integer(maximum_frames, 1, MAX_FRAMES, "Frame maksimum")
    edge = _integer(long_edge, 32, MAX_EDGE, "Sisi raster")
    scan = _integer(scan_seconds, 1, 300, "Horizon probe")
    timeout = _integer(timeout_seconds, 1, 120, "Timeout video")
    probe, render = shutil.which("ffprobe"), shutil.which("ffmpeg")
    if probe is None or render is None:
        raise ValueError("ffprobe dan ffmpeg lokal diperlukan.")
    common = ["-protocol_whitelist", "file", "-format_whitelist", ALLOWED_DEMUXERS]
    with TemporaryDirectory(prefix="ace-perception-video-") as folder:
        stage = Path(folder)
        (stage/"input.video").write_bytes(video)
        roster_path = stage/"roster.json"
        command = [probe, "-v", "error", *common, "-select_streams", "v:0", "-skip_frame", "nokey",
                   "-read_intervals", f"%+{scan}", "-show_frames",
                   "-show_entries", "frame=key_frame,best_effort_timestamp_time",
                   "-of", "json", "input.video"]
        with roster_path.open("wb") as stream:
            _invoke(command, stage, timeout, stream)
        stamps, observed = _entries(_raster.read(roster_path, MAX_PROBE_BYTES), maximum)
        filter_ = f"scale={edge}:{edge}:force_original_aspect_ratio=decrease,format=gray,showinfo"
        command = [render, "-v", "info", "-xerror", "-nostdin", "-copyts", *common, "-threads", "1", "-skip_frame", "nokey",
                   "-i", "input.video", "-map", "0:v:0", "-an", "-sn", "-dn", "-filter_threads", "1", "-vf", filter_,
                   "-fps_mode", "passthrough", "-frames:v", str(len(stamps)), "-c:v", "pgm", "frame-%06d.pgm"]
        render_log = stage/"render.log"
        with render_log.open("wb") as stream:
            _invoke(command, stage, timeout, subprocess.DEVNULL, stream)
        _check_render_times(_raster.read(render_log, MAX_PROBE_BYTES), stamps)
        files, frames = _load_artifacts(stage, stamps, edge)
    return files, {"schema": "ace.perception-video-keyframes.v1", "source_sha256": sha256(video).hexdigest(),
                   "time_basis": "best_effort_timestamp_us", "scan_seconds": scan,
                   "keyframes_in_probe": observed, "long_edge": edge, "frame_cap": maximum, "frames": frames}


def _write(directory, files, manifest):
    if any(not FRAME_FILE.fullmatch(item) for item in files):
        raise ValueError("Nama keyframe ekspor tidak sah.")
    directory.mkdir(mode=0o700)
    for name, data in files.items():
        with (directory/name).open("xb") as stream:
            stream.write(data)
    with (directory/"manifest.json").open("xb") as stream:
        stream.write(_canonical(manifest) + b"\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--maximum-frames", type=int, default=8)
    parser.add_argument("--long-edge", type=int, default=640)
    parser.add_argument("--scan-seconds", type=int, default=60)
    parser.add_argument("--timeout-seconds", type=int, default=25)
    args = parser.parse_args(argv)
    try:
        files, report = sample(_raster.read(args.video, MAX_VIDEO_BYTES), maximum_frames=args.maximum_frames,
                               long_edge=args.long_edge, scan_seconds=args.scan_seconds, timeout_seconds=args.timeout_seconds)
        _write(args.output_dir, files, report)
        sys.stdout.buffer.write(_canonical(report) + b"\n")
    except (OSError, OverflowError, RecursionError, ValueError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
