#!/usr/bin/env python3
"""Buat rencana cutover yang bisa ditelaah sebelum alamat engine berubah.

Konfigurasi JSON wajib memuat repo, helpers, budget_state, call_log,
stdout_log, pid_file (path absolut), port, dan current_bridge_url.
Bridge langsung menggantikan alamat relay. Jalur lama tetap tersedia untuk
rollback sampai jam review operator selesai. Preflight membaca PID yang
ditunjuk dan memeriksa keberadaan proses dengan sinyal 0. Pemeriksaan
kredensial hanya memakai nama entri di manifest publik bundle. Generator
mencetak teks atau JSON tanpa meluncurkan proses.

Jika PID masih hidup, `expected_process_name` opsional menentukan nama
proses yang diharapkan. Nama yang beda atau tak terbaca perlu pemeriksaan
operator. Kecocokan nama meloloskan pemeriksaan PID saja.
"""
import argparse
import json
import os
from pathlib import Path
import shlex
from urllib.parse import urlsplit


PATH_FIELDS = ("repo", "helpers", "budget_state", "call_log", "stdout_log", "pid_file")
BUNDLE_MANIFEST_SCHEMA = "ace.secrets-bundle-manifest.v1"
REQUIRED_ENTRY_NAMES = ("groq-api-key", "gemini-api-key", "gonka-api-key")


def _pid_running(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _pid_identity(pid):
    return Path(f"/proc/{pid}/comm").read_text(encoding="utf-8").strip()


def _check_pid_file(path, probe, expected_name, identity_probe):
    try:
        pid = int(path.read_text(encoding="utf-8").strip())
    except FileNotFoundError:
        return {"state": "missing", "safe_to_continue": True}
    except (OSError, ValueError):
        return {"state": "unverified", "safe_to_continue": False}
    if not 0 < pid <= 2**31 - 1:
        return {"state": "unverified", "safe_to_continue": False}
    try:
        running = probe(pid)
    except OSError:
        return {"state": "unverified", "safe_to_continue": False}
    if running is False:
        return {"state": "stale", "safe_to_continue": True}
    if running is not True:
        return {"state": "unverified", "safe_to_continue": False}
    if expected_name is None:
        return {"state": "live", "safe_to_continue": False, "reason": "identity_unverified"}
    try:
        observed = identity_probe(pid)
    except (OSError, UnicodeError):
        observed = None
    if not isinstance(observed, str) or not observed.strip():
        return {"state": "unverified", "safe_to_continue": False, "reason": "identity_unverified"}
    if observed.strip() != expected_name:
        return {"state": "identity_mismatch", "safe_to_continue": False}
    return {"state": "live", "safe_to_continue": True, "reason": "identity_matched"}


def _check_bundle_markers(path):
    if path is None:
        return {"state": "unverified", "missing_names": list(REQUIRED_ENTRY_NAMES)}
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if (not isinstance(manifest, dict) or manifest.get("schema") != BUNDLE_MANIFEST_SCHEMA
                or not isinstance(manifest.get("entries"), list)):
            raise ValueError
        names = set()
        for entry in manifest["entries"]:
            if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
                raise ValueError
            names.add(entry["name"])
    except (OSError, ValueError):
        return {"state": "unverified", "missing_names": list(REQUIRED_ENTRY_NAMES)}
    missing = [name for name in REQUIRED_ENTRY_NAMES if name not in names]
    return {"state": "missing" if missing else "present", "missing_names": missing}


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


def plan_home(config, *, bundle_manifest=None, pid_probe=_pid_running, identity_probe=_pid_identity):
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
    expected_name = config.get("expected_process_name")
    if expected_name is not None and (
        not isinstance(expected_name, str) or not expected_name.strip() or not expected_name.isprintable()
    ):
        raise ValueError("expected_process_name wajib berupa satu nama proses.")
    pid_check = _check_pid_file(Path(paths["pid_file"]), pid_probe,
                               expected_name.strip() if expected_name is not None else None, identity_probe)
    credentials = _check_bundle_markers(bundle_manifest)
    argv = ["nohup", "python3", str(Path(paths["repo"]) / "tools" / "brain_bridge.py"),
            "--port", str(port), "--state", paths["budget_state"], "--log", paths["call_log"],
            "--helpers", paths["helpers"]]
    quote = shlex.quote
    command = (f"{shlex.join(argv)} > {quote(paths['stdout_log'])} 2>&1 < /dev/null & "
               f"printf '%s\\n' \"$!\" > {quote(paths['pid_file'])}")
    launch_verify = f"Cocokkan PID baru di {paths['pid_file']} dengan proses bridge."
    if pid_check.get("reason") == "identity_matched":
        command = "Gunakan kembali proses bridge yang tercatat."
        launch_verify = f"Periksa health proses yang ada lewat {_health(target)}."
    steps = [
        {"id": "preflight", "action": "Siapkan direktori dan credential untuk proses bridge. Pertahankan jalur lama.",
         "verify": f"Pastikan direktori keluaran bisa ditulis dan health lama lolos lewat {_health(previous)}."},
        {"id": "launch", "action": command, "verify": launch_verify},
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
            "target_bridge_url": target, "steps": steps, "rollback": rollback,
            "preflight": {"pid_file": pid_check, "credential_markers": credentials,
                          "safe_to_continue": (pid_check["safe_to_continue"]
                                               and credentials["state"] == "present")}}


def markdown(plan):
    lines = ["# Checklist cutover bridge", ""]
    for step in plan["steps"]:
        lines.append(f"- [ ] **{step['id']}** — {step['action']}")
        lines.append(f"  - Verifikasi — {step['verify']}")
        if step["id"] == "preflight" and "preflight" in plan:
            preflight = plan["preflight"]
            pid = preflight["pid_file"]
            status = "aman-untuk-lanjut" if pid["safe_to_continue"] else "perlu pemeriksaan operator"
            lines.append(f"  - PID file — {pid['state']} ({status})")
            credentials = preflight["credential_markers"]
            lines.append(f"  - Penanda kredensial — {credentials['state']}")
            if credentials["missing_names"]:
                lines.append("  - Nama entri belum terverifikasi — " + ", ".join(credentials["missing_names"]))
    lines.extend(["", "## Langkah mundur", ""])
    lines.extend(f"- [ ] {step}" for step in plan["rollback"])
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("--bundle-manifest", type=Path, help="Manifest publik berisi nama entri.")
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    args = parser.parse_args(argv)
    try:
        result = plan_home(json.loads(args.config.read_text(encoding="utf-8")),
                           bundle_manifest=args.bundle_manifest)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    print(markdown(result) if args.format == "markdown" else json.dumps(result, indent=2), end="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
