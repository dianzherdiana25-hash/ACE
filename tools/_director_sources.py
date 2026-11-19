"""Read committed director audit sources without importing repository code."""
from __future__ import annotations

from decimal import Decimal, DecimalException
import json
import os
from pathlib import Path, PurePosixPath
import subprocess


class SourceError(ValueError):
    """A supplied source cannot be read or has an invalid structure."""


def _unique_object(pairs):
    result = dict(pairs)
    if len(result) != len(pairs):
        raise SourceError("Kunci JSON ganda.")
    return result


def _reject_constant(_constant):
    raise SourceError("Bilangan JSON wajib berhingga.")


def parse_json(text):
    try:
        return json.loads(text, parse_float=Decimal, parse_constant=_reject_constant,
                          object_pairs_hook=_unique_object)
    except json.JSONDecodeError as exc:
        raise SourceError(f"JSON tidak sah pada baris {exc.lineno}.") from None
    except SourceError:
        raise
    except (ValueError, DecimalException):
        raise SourceError("Angka JSON tidak dapat dibaca.") from None


def repo_path(value):
    if (not isinstance(value, str) or not value or "\\" in value
            or any(ord(char) < 32 for char in value)):
        raise SourceError("Path sumber harus relatif terhadap repo.")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or path == PurePosixPath("."):
        raise SourceError("Path sumber harus relatif terhadap repo.")
    return path.as_posix()


class GitSnapshot:
    def __init__(self, root: Path, revision: str = "HEAD"):
        self.root = Path(root)
        self.commit = self._git("rev-parse", "--verify", "--end-of-options",
                                f"{revision}^{{commit}}").decode("ascii").strip()
        self.entries = {}
        for item in self._git("ls-tree", "--full-tree", "-r", "-z", self.commit).split(b"\x00"):
            if item:
                header, path = item.split(b"\t", 1)
                mode, _, oid = header.decode("ascii").split()
                self.entries[path.decode("utf-8", errors="surrogateescape")] = (mode, oid)

    def _git(self, *args):
        try:
            return subprocess.run(["git", "-C", str(self.root), *args],
                                  capture_output=True, check=True,
                                  env={**os.environ, "GIT_NO_LAZY_FETCH": "1"}).stdout
        except (OSError, subprocess.CalledProcessError):
            raise SourceError("Snapshot Git tidak dapat dibaca.") from None

    def read_text(self, path):
        entry = self.entries.get(repo_path(path))
        if entry is None:
            raise SourceError("Berkas sumber tidak ada pada snapshot.")
        if entry[0] not in ("100644", "100755"):
            raise SourceError("Berkas sumber harus berupa blob reguler.")
        try:
            return self._git("cat-file", "blob", entry[1]).decode("utf-8")
        except UnicodeDecodeError:
            raise SourceError("Berkas sumber harus berupa UTF-8.") from None

    def read_json(self, path):
        return parse_json(self.read_text(path))


def write_json(payload):
    print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
