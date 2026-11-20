"""Pakai nama remote agar label stabil walaupun checkout dipindah."""

from pathlib import Path
import re
import subprocess
from urllib.parse import urlsplit


def canonical_repo_name(root: Path) -> str:
    """Ambil basename remote origin lokal, atau pakai nama direktori."""
    if not (root / ".git").exists():
        return root.name
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "config", "--local", "--get", "remote.origin.url"],
            capture_output=True, encoding="utf-8", check=True, timeout=5,
        )
        remote = result.stdout.strip()
        if "://" in remote:
            path = urlsplit(remote).path
        else:
            # Git menerima bentuk SCP host:path selain path lokal.
            path = re.sub(r"^[^/:]+:", "", remote, count=1)
    except (OSError, ValueError, subprocess.SubprocessError):
        return root.name

    name = path.rstrip("/").rsplit("/", 1)[-1].removesuffix(".git")
    return name if name and name not in {".", ".."} and name.isprintable() else root.name
