"""Backend FFmpeg dengan nama staging tetap, protokol lokal, dan pembacaan ulang."""
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess

from ._contracts import ContractError, read
from ._raster import ppm

MAX_MOVIE = 48_000_000


def _call(tool, options, root, timeout=60):
    binary = shutil.which(tool)
    if binary is None:
        raise ContractError(f"Backend {tool} tidak tersedia.")
    try:
        return subprocess.run([binary, *options], cwd=root, check=True, stdin=subprocess.DEVNULL,
                              capture_output=True, timeout=timeout).stdout
    except subprocess.TimeoutExpired as error:
        raise ContractError(f"Backend {tool} melewati batas waktu.") from error
    except subprocess.CalledProcessError as error:
        diagnostic = error.stderr.decode(errors="replace").splitlines()
        detail = diagnostic[-1][:240] if diagnostic else "keluar dengan status gagal"
        raise ContractError(f"Backend {tool}: {detail}.") from error


def probe_mp4(root, name="result.mp4"):
    raw = _call("ffprobe", ["-v", "error", "-protocol_whitelist", "file,pipe", "-show_streams",
                           "-show_format", "-count_frames", "-of", "json", name], root)
    info = json.loads(raw)
    videos = [stream for stream in info["streams"] if stream["codec_type"] == "video"]
    audio = [stream for stream in info["streams"] if stream["codec_type"] == "audio"]
    if len(videos) != 1 or len(audio) > 1 or "mp4" not in info["format"]["format_name"].split(","):
        raise ContractError("Jumlah stream atau container video tidak sesuai.")
    item = videos[0]
    fps = Fraction(item["avg_frame_rate"])
    if fps <= 0:
        raise ContractError("Frame rate hasil tidak terukur.")
    return {"width": item["width"], "height": item["height"], "fps": [fps.numerator, fps.denominator],
            "frames": int(item["nb_read_frames"]), "codec": item["codec_name"],
            "audio": audio[0]["codec_name"] if audio else None}


def encode_frames(root, frames, width, height, fps, sound=None, crf=20):
    count = 0
    for count, frame in enumerate(frames, 1):
        if count > 450 or (frame.width, frame.height) != (width, height):
            raise ContractError("Anggaran atau dimensi frame video berbeda dari rencana.")
        (root / f"f{count:06d}.ppm").write_bytes(ppm(frame))
    if not count:
        raise ContractError("Video perlu satu frame.")
    options = ["-hide_banner", "-loglevel", "error", "-nostdin", "-protocol_whitelist", "file,pipe",
               "-framerate", str(fps), "-i", "f%06d.ppm"]
    if sound is not None:
        (root / "sound.wav").write_bytes(sound)
        options.extend(["-protocol_whitelist", "file,pipe", "-i", "sound.wav",
                        "-map", "0:v:0", "-map", "1:a:0", "-c:a", "aac", "-b:a", "96k"])
    else:
        options.extend(["-map", "0:v:0"])
    options.extend(["-map_metadata", "-1", "-c:v", "libx264", "-preset", "fast", "-crf", str(crf),
                    "-threads", "1", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "result.mp4"])
    _call("ffmpeg", options, root)
    metadata = probe_mp4(root)
    if (metadata["width"], metadata["height"], metadata["fps"], metadata["frames"]) != (width, height, [fps, 1], count):
        raise ContractError("Dimensi, frame rate atau hitungan decode video berbeda.")
    if (metadata["audio"] is not None) != (sound is not None):
        raise ContractError("Stream audio hasil berbeda dari rencana.")
    content = read(root / "result.mp4", MAX_MOVIE)
    return content, {**metadata, "bytes": len(content), "mp4_sha256": sha256(content).hexdigest()}


def extract_frame(root, index, source="result.mp4"):
    data = _call("ffmpeg", ["-hide_banner", "-loglevel", "error", "-nostdin", "-protocol_whitelist",
                            "file,pipe", "-i", source, "-vf", f"select=eq(n\\,{index})", "-frames:v", "1",
                            "-f", "image2pipe", "-vcodec", "ppm", "pipe:1"], root)
    from ._raster import raster
    return raster(data)
