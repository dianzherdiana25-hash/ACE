#!/usr/bin/env python3
"""Buat rencana cutover yang bisa ditelaah sebelum alamat engine berubah.

Konfigurasi JSON wajib memuat repo, helpers, budget_state, call_log,
stdout_log, pid_file (path absolut), port, dan current_bridge_url.
Bridge langsung menggantikan alamat relay. Jalur lama tetap tersedia untuk
rollback sampai jam review operator selesai. Credential disiapkan oleh
operator sebelum peluncuran. Generator hanya mencetak teks atau JSON.
"""
import argparse
import json
from pathlib import Path
import shlex
from urllib.parse import urlsplit


PATH_FIELDS = ("repo", "helpers", "budget_state", "call_log", "stdout_log", "pid_file")


def _url(url):
    if not isinstance(url, str) or not url or any(ord(char) < 33 for char in url):
        raise ValueError("Alamat bridge lama tidak sah.")
    parts = urlsplit(url)
    if (parts.scheme not in {"http", "https"} or not parts.hostname
            or parts.username is not None or parts.query or parts.fragment):
        raise ValueError("Alamat bridge lama harus HTTP(S) tanpa credential atau query.")
    return url.rstrip("/")


def _health(url):
    return shlex.join(["curl", "--fail", "--silent", "--show-error", "--max-time", "5",
                       "--", url + "/health"])


def plan_home(config):
    if not isinstance(config, dict):
        raise ValueError("Konfigurasi wajib berupa objek JSON.")
    paths = {}
    for field in PATH_FIELDS:
        value = config.get(field)
        if (not isinstance(value, str) or not Path(value).is_absolute()
                or any(ord(char) < 32 for char in value) or ".." in Path(value).parts):
            raise ValueError(f"{field} wajib berupa path absolut.")
        paths[field] = str(Path(value))
    files = [paths[field] for field in ("budget_state", "call_log", "stdout_log", "pid_file")]
    if len(set(files)) != len(files):
        raise ValueError("Path state, log, dan PID wajib berbeda.")
    port = config.get("port")
    if type(port) is not int or not 1 <= port <= 65_535:
        raise ValueError("port wajib integer 1–65535.")
    previous = _url(config.get("current_bridge_url"))
    target = f"http://127.0.0.1:{port}"
    if target == previous:
        raise ValueError("Alamat bridge lama dan baru wajib berbeda.")
    argv = ["nohup", "python3", str(Path(paths["repo"]) / "tools" / "brain_bridge.py"),
            "--port", str(port), "--state", paths["budget_state"], "--log", paths["call_log"],
            "--helpers", paths["helpers"]]
    quote = shlex.quote
    command = (f"{shlex.join(argv)} > {quote(paths['stdout_log'])} 2>&1 < /dev/null & "
               f"printf '%s\\n' \"$!\" > {quote(paths['pid_file'])}")
    steps = [
        {"id": "preflight", "action": "Siapkan direktori dan credential untuk proses bridge. Pertahankan jalur lama.",
         "verify": f"Pastikan direktori keluaran bisa ditulis dan health lama lolos lewat {_health(previous)}."},
        {"id": "launch", "action": command,
         "verify": f"Cocokkan PID baru di {paths['pid_file']} dengan proses bridge."},
        {"id": "health", "action": _health(target),
         "verify": "Periksa ok=true dan role yang diharapkan. Lanjut setelah health lulus."},
        {"id": "cutover", "action": f"Terapkan ACE_BRAIN_BRIDGE_URL={target} pada konfigurasi engine.",
         "verify": "Operator memeriksa status engine dan audit panggilan bridge setelah restart terkontrol."},
    ]
    rollback = [
        f"Pulihkan ACE_BRAIN_BRIDGE_URL={previous} pada konfigurasi engine.",
        f"Periksa health lama dengan {_health(previous)}, lalu jalankan restart engine terkontrol.",
        "Konfirmasi status engine pada jalur lama. Setelah itu hentikan proses bridge baru sesuai PID terverifikasi.",
    ]
    return {"schema": "ace.bridge-home-plan.v1", "current_bridge_url": previous,
            "target_bridge_url": target, "steps": steps, "rollback": rollback}


def markdown(plan):
    lines = ["# Checklist cutover bridge", ""]
    for step in plan["steps"]:
        lines.append(f"- [ ] **{step['id']}** — {step['action']}")
        lines.append(f"  - Verifikasi — {step['verify']}")
    lines.extend(["", "## Langkah mundur", ""])
    lines.extend(f"- [ ] {step}" for step in plan["rollback"])
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    args = parser.parse_args(argv)
    try:
        result = plan_home(json.loads(args.config.read_text(encoding="utf-8")))
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    print(markdown(result) if args.format == "markdown" else json.dumps(result, indent=2), end="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
