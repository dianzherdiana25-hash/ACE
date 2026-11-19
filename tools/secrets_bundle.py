"""Bundel rahasia terenkripsi ACE — kredensial yang bisa bepergian antar-rumah
tanpa pernah tampil mentah.

Owner directive (2026-11-19): ACE must be able to work in any home
without depending on Ian. Identity and memory travel through this
(public) repo; secret VALUES must never appear in it in plaintext —
a token published raw on GitHub is revoked automatically and scraped
by bots within minutes, which would make ACE *less* portable, not
more. This bundle is the middle form: ciphertext that is safe to
publish, openable in any home with the single master passphrase the
owner holds.

Crypto engine: GnuPG symmetric encryption (AES-256, S2K SHA-512,
iterated+salted). No hand-rolled cryptography, no third-party Python
packages — `gpg` 2.x and `python3` are the only requirements, so any
plausible home can open the bundle.

Discipline enforced by this tool:

- the passphrase travels only via a pipe fd to gpg — never argv,
  never a file, never logged;
- secret values are read only via getpass (no echo) or, for `get`,
  written only to stdout — never to a plaintext file;
- the manifest (`secrets/manifest.json`) is a public register:
  names, services, notes, dates. It never contains values;
- decryption happens in memory; a wrong passphrase or a tampered
  bundle fails closed (GPG integrity check) with no partial output;
- writes are atomic (temp file + os.replace).

Layout (repo root): `secrets/bundle.gpg` + `secrets/manifest.json`,
created by `init`. The first `init` and every `add` are operator acts
on a home terminal — the passphrase and the values never pass through
chat or through an agent session.

Usage:
    python3 tools/secrets_bundle.py init
    python3 tools/secrets_bundle.py add NAME --service S [--note N]
    python3 tools/secrets_bundle.py list
    python3 tools/secrets_bundle.py verify
    python3 tools/secrets_bundle.py get NAME            # value -> stdout
    python3 tools/secrets_bundle.py remove NAME
    python3 tools/secrets_bundle.py rotate-passphrase

For scripted use on a home, ACE_BUNDLE_PASSPHRASE may carry the
passphrase in the operator's own environment. ACE_BUNDLE_S2K_COUNT
may tune the S2K iteration count at encryption time (floor 65536;
default 65011712).
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_BUNDLE = "ace.secrets-bundle.v1"
SCHEMA_MANIFEST = "ace.secrets-bundle-manifest.v1"
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
DEFAULT_S2K_COUNT = 65011712
MIN_S2K_COUNT = 65536


class BundleError(Exception):
    """Stable, value-free failure."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _bundle_paths(base: Path) -> tuple[Path, Path]:
    return base / "bundle.gpg", base / "manifest.json"


def _passphrase(confirm: bool = False) -> str:
    env = os.environ.get("ACE_BUNDLE_PASSPHRASE")
    if env:
        return env
    pw = getpass.getpass("Passphrase bundel: ")
    if not pw:
        raise BundleError("passphrase kosong ditolak")
    if confirm:
        again = getpass.getpass("Ulangi passphrase: ")
        if pw != again:
            raise BundleError("passphrase tidak cocok")
    return pw


def _s2k_count() -> int:
    raw = os.environ.get("ACE_BUNDLE_S2K_COUNT")
    if raw is None:
        return DEFAULT_S2K_COUNT
    try:
        value = int(raw)
    except ValueError:
        raise BundleError("ACE_BUNDLE_S2K_COUNT bukan angka")
    if value < MIN_S2K_COUNT:
        raise BundleError(f"ACE_BUNDLE_S2K_COUNT di bawah lantai {MIN_S2K_COUNT}")
    return value


def _gpg(passphrase: str, args: list[str], data: bytes | None) -> bytes:
    """Run gpg with the passphrase on a pipe fd — never in argv."""
    read_fd, write_fd = os.pipe()
    try:
        os.write(write_fd, passphrase.encode("utf-8") + b"\n")
    finally:
        os.close(write_fd)
    cmd = [
        "gpg", "--batch", "--yes", "--pinentry-mode", "loopback",
        "--passphrase-fd", str(read_fd),
    ] + args
    try:
        proc = subprocess.run(
            cmd, input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            pass_fds=(read_fd,),
        )
    finally:
        os.close(read_fd)
    if proc.returncode != 0:
        raise BundleError(
            "gpg gagal (passphrase salah atau bundel rusak): "
            + proc.stderr.decode("utf-8", "replace").strip().splitlines()[-1]
            if proc.stderr.strip() else "gpg gagal"
        )
    return proc.stdout


def _encrypt(passphrase: str, plaintext: bytes, dest: Path) -> None:
    fd, tmp_name = tempfile.mkstemp(dir=str(dest.parent), prefix=".bundle-")
    os.close(fd)
    tmp = Path(tmp_name)
    try:
        _gpg(passphrase, [
            "--symmetric", "--cipher-algo", "AES256",
            "--s2k-digest-algo", "SHA512", "--s2k-count", str(_s2k_count()),
            "--compress-algo", "none", "--output", str(tmp),
        ], plaintext)
        os.replace(tmp, dest)
    finally:
        if tmp.exists():
            tmp.unlink()


def _decrypt(passphrase: str, src: Path) -> bytes:
    if not src.is_file():
        raise BundleError(f"bundel tidak ditemukan: {src}")
    return _gpg(passphrase, ["--decrypt", str(src)], b"")


def _load_manifest(base: Path) -> dict:
    _bundle, manifest_path = _bundle_paths(base)
    if not manifest_path.is_file():
        raise BundleError("manifest tidak ditemukan — jalankan `init` dulu")
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        raise BundleError(f"manifest tidak terbaca: {exc}")
    if data.get("schema") != SCHEMA_MANIFEST:
        raise BundleError("skema manifest tidak dikenal")
    return data


def _save_manifest(base: Path, manifest: dict) -> None:
    _bundle, manifest_path = _bundle_paths(base)
    manifest["entries"] = sorted(manifest["entries"], key=lambda e: e["name"])
    text = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    fd, tmp_name = tempfile.mkstemp(dir=str(base), prefix=".manifest-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp_name, manifest_path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def _load_values(passphrase: str, base: Path) -> dict:
    bundle_path, _manifest = _bundle_paths(base)
    raw = _decrypt(passphrase, bundle_path)
    try:
        data = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise BundleError("isi bundel tidak valid (bukan JSON skema bundel)")
    if data.get("schema") != SCHEMA_BUNDLE or not isinstance(data.get("values"), dict):
        raise BundleError("skema bundel tidak dikenal")
    return data


def _store_values(passphrase: str, base: Path, data: dict) -> None:
    bundle_path, _manifest = _bundle_paths(base)
    raw = (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    _encrypt(passphrase, raw, bundle_path)


def _check_name(name: str) -> str:
    if not NAME_RE.match(name):
        raise BundleError(
            f"nama tidak sah: {name!r} (huruf kecil/angka, lalu [a-z0-9._-])"
        )
    return name


def cmd_init(base: Path) -> int:
    bundle_path, manifest_path = _bundle_paths(base)
    if bundle_path.exists() or manifest_path.exists():
        raise BundleError("bundel sudah ada — init menolak menimpa")
    base.mkdir(parents=True, exist_ok=True)
    pw = _passphrase(confirm=True)
    _store_values(pw, base, {"schema": SCHEMA_BUNDLE, "values": {}})
    _save_manifest(base, {
        "schema": SCHEMA_MANIFEST,
        "created_at": _utc_now(),
        "entries": [],
    })
    print(f"Bundel dibuat: {bundle_path} (0 entri). Manifest: {manifest_path}")
    return 0


def cmd_add(base: Path, name: str, service: str, note: str, force: bool,
            value_stdin: bool) -> int:
    _check_name(name)
    manifest = _load_manifest(base)
    known = {e["name"] for e in manifest["entries"]}
    if name in known and not force:
        raise BundleError(f"entri {name!r} sudah ada — pakai --force untuk mengganti")
    pw = _passphrase()
    data = _load_values(pw, base)
    if value_stdin:
        # Provisioning pattern: the value arrives on a pipe, never via
        # argv (visible in ps) and never via a plaintext file.
        value = sys.stdin.read().rstrip("\n")
        if not value:
            raise BundleError("nilai dari stdin kosong ditolak")
    else:
        value = getpass.getpass(f"Nilai rahasia untuk {name!r} (tidak ditampilkan): ")
        if not value:
            raise BundleError("nilai kosong ditolak")
        again = getpass.getpass("Ulangi nilai: ")
        if value != again:
            raise BundleError("nilai tidak cocok")
    data["values"][name] = value
    _store_values(pw, base, data)
    entry = {"name": name, "service": service, "note": note, "updated_at": _utc_now()}
    manifest["entries"] = [e for e in manifest["entries"] if e["name"] != name] + [entry]
    _save_manifest(base, manifest)
    print(f"Entri {name!r} tersimpan (nilai tidak ditampilkan).")
    return 0


def cmd_remove(base: Path, name: str) -> int:
    _check_name(name)
    manifest = _load_manifest(base)
    if name not in {e["name"] for e in manifest["entries"]}:
        raise BundleError(f"entri {name!r} tidak ada")
    pw = _passphrase()
    data = _load_values(pw, base)
    data["values"].pop(name, None)
    _store_values(pw, base, data)
    manifest["entries"] = [e for e in manifest["entries"] if e["name"] != name]
    _save_manifest(base, manifest)
    print(f"Entri {name!r} dihapus.")
    return 0


def cmd_list(base: Path) -> int:
    manifest = _load_manifest(base)
    print(f"{'NAMA':<28} {'LAYANAN':<20} DIPERBARUI")
    for e in manifest["entries"]:
        print(f"{e['name']:<28} {e.get('service',''):<20} {e.get('updated_at','')}")
    print(f"Total: {len(manifest['entries'])} entri (nilai tidak pernah ditampilkan).")
    return 0


def cmd_verify(base: Path) -> int:
    manifest = _load_manifest(base)
    pw = _passphrase()
    data = _load_values(pw, base)
    names_manifest = {e["name"] for e in manifest["entries"]}
    names_values = set(data["values"].keys())
    if names_manifest != names_values:
        raise BundleError(
            "manifest dan isi bundel tidak sinkron: "
            f"hanya di manifest={sorted(names_manifest - names_values)}, "
            f"hanya di bundel={sorted(names_values - names_manifest)}"
        )
    print(f"OK: bundel terdekripsi, {len(names_values)} entri, manifest sinkron.")
    return 0


def cmd_get(base: Path, name: str) -> int:
    _check_name(name)
    pw = _passphrase()
    data = _load_values(pw, base)
    if name not in data["values"]:
        raise BundleError(f"entri {name!r} tidak ada")
    sys.stdout.write(str(data["values"][name]))
    sys.stdout.flush()
    return 0


def cmd_rotate(base: Path) -> int:
    old = _passphrase()
    data = _load_values(old, base)
    env = os.environ.get("ACE_BUNDLE_PASSPHRASE")
    if env:
        raise BundleError(
            "rotate membaca passphrase baru lewat prompt — "
            "jalankan tanpa ACE_BUNDLE_PASSPHRASE"
        )
    new = getpass.getpass("Passphrase baru: ")
    if not new:
        raise BundleError("passphrase baru kosong ditolak")
    again = getpass.getpass("Ulangi passphrase baru: ")
    if new != again:
        raise BundleError("passphrase baru tidak cocok")
    _store_values(new, base, data)
    print("Passphrase bundel diganti; isi tidak berubah.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--dir", type=Path, default=_repo_root() / "secrets",
        help="direktori bundel (default: <repo>/secrets)",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    p_add = sub.add_parser("add")
    p_add.add_argument("name")
    p_add.add_argument("--service", default="")
    p_add.add_argument("--note", default="")
    p_add.add_argument("--force", action="store_true")
    p_add.add_argument("--value-stdin", action="store_true",
                       help="baca nilai dari stdin (pola provisioning), bukan prompt")
    p_rm = sub.add_parser("remove")
    p_rm.add_argument("name")
    sub.add_parser("list")
    sub.add_parser("verify")
    p_get = sub.add_parser("get")
    p_get.add_argument("name")
    sub.add_parser("rotate-passphrase")
    args = parser.parse_args(argv)
    base: Path = args.dir
    try:
        if args.cmd == "init":
            return cmd_init(base)
        if args.cmd == "add":
            return cmd_add(base, args.name, args.service, args.note, args.force,
                           args.value_stdin)
        if args.cmd == "remove":
            return cmd_remove(base, args.name)
        if args.cmd == "list":
            return cmd_list(base)
        if args.cmd == "verify":
            return cmd_verify(base)
        if args.cmd == "get":
            return cmd_get(base, args.name)
        if args.cmd == "rotate-passphrase":
            return cmd_rotate(base)
    except BundleError as exc:
        print(f"GAGAL: {exc}", file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
