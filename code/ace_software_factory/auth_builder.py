"""Bangun login lokal dan batas peran dari kebijakan yang dapat diaudit.

Runtime menyimpan salted password digest dan hash sesi pada memori
proses. Tidak ada kredensial bawaan. Akses yang tidak terdaftar ditolak,
rotasi kata sandi membatalkan sesi, dan emitter tidak menyentuh akun.
"""
import argparse
from hashlib import sha256
from pathlib import Path
import sys

from ._contracts import ContractError, canonical, checked, decode, entries, identifier, integer, obj, read, schema, text
from .repo_scaffolder import materialize


RUNTIME = '''"""Login lokal stateless antar-restart, dengan RBAC eksplisit."""
from dataclasses import dataclass
from hashlib import pbkdf2_hmac, sha256
from hmac import compare_digest
import re
import secrets
from threading import RLock
import time


USER = re.compile(r"[a-z][a-z0-9_]{0,63}")


@dataclass(frozen=True)
class Credential:
    salt: bytes
    digest: bytes
    role: str


@dataclass(frozen=True)
class Session:
    subject: str
    expires: float


class Login:
    def __init__(self, *, clock=time.monotonic):
        self._clock = clock
        self._lock = RLock()
        self._credentials = {}
        self._sessions = {}
        self._decoy = secrets.token_bytes(24)

    @staticmethod
    def _digest(password, salt):
        return pbkdf2_hmac("sha256", password, salt, SETTINGS["iterations"])

    @staticmethod
    def _password(value):
        return isinstance(value, bytes) and 16 <= len(value) <= 1024

    @staticmethod
    def _subject(value):
        return isinstance(value, str) and USER.fullmatch(value) is not None

    @staticmethod
    def _key(token):
        if not isinstance(token, str) or len(token) != 43 or not token.isascii():
            return None
        return sha256(token.encode("ascii")).digest()

    def _revoke_subject(self, subject):
        for key, record in tuple(self._sessions.items()):
            if subject == record.subject:
                del self._sessions[key]

    def enroll(self, subject, password, role):
        if not self._subject(subject) or not self._password(password) or not isinstance(role, str) or role not in SETTINGS["roles"]:
            raise ValueError("Enrollment ditolak.")
        salt = secrets.token_bytes(24)
        record = Credential(salt, self._digest(password, salt), role)
        with self._lock:
            if subject in self._credentials:
                raise ValueError("Enrollment ditolak.")
            if len(self._credentials) >= SETTINGS["max_accounts"]:
                raise ValueError("Enrollment ditolak.")
            self._credentials[subject] = record

    def change_password(self, subject, current, replacement):
        if not self._subject(subject) or not self._password(current) or not self._password(replacement):
            return False
        with self._lock:
            record = self._credentials.get(subject)
            salt = record.salt if record else self._decoy
            current_digest = self._digest(current, salt)
            expected = record.digest if record else bytes(32)
            if not compare_digest(current_digest, expected) or record is None:
                return False
            salt = secrets.token_bytes(24)
            self._credentials[subject] = Credential(salt, self._digest(replacement, salt), record.role)
            self._revoke_subject(subject)
        return True

    def login(self, subject, password):
        if not self._subject(subject) or not self._password(password):
            return None
        with self._lock:
            credential = self._credentials.get(subject)
            salt = credential.salt if credential else self._decoy
            supplied = self._digest(password, salt)
            expected = credential.digest if credential else bytes(32)
            if not compare_digest(supplied, expected) or credential is None:
                return None
            now = self._clock()
            for key, record in tuple(self._sessions.items()):
                if record.expires <= now:
                    del self._sessions[key]
            if len(self._sessions) >= SETTINGS["max_sessions"]:
                return None
            token = secrets.token_urlsafe(32)
            self._sessions[self._key(token)] = Session(subject, now + SETTINGS["session_seconds"])
            return token

    def revoke(self, token):
        with self._lock:
            return self._sessions.pop(self._key(token), None) is not None

    def permits(self, token, permission):
        if not isinstance(permission, str):
            return False
        with self._lock:
            key = self._key(token)
            session = self._sessions.get(key)
            if session is None:
                return False
            if session.expires <= self._clock():
                self._sessions.pop(key)
                return False
            credential = self._credentials.get(session.subject)
            return credential is not None and permission in SETTINGS["roles"][credential.role]
'''


def build(plan, expected):
    checked(plan, expected)
    schema(plan, "ace.factory-auth-plan.v1", ("id", "session_seconds", "iterations", "max_accounts",
                                            "max_sessions", "permissions", "roles"))
    product = identifier(plan["id"], "Produk login")
    permissions = {}
    for item in entries(plan["permissions"], 100, minimum=1):
        obj(item, ("id", "source_ref"))
        key = identifier(item["id"], "ID permission")
        if key in permissions:
            raise ContractError("Permission ganda.")
        permissions[key] = text(item["source_ref"], "Rujukan permission", 200)
    roles = {}
    for item in entries(plan["roles"], 50, minimum=1):
        obj(item, ("id", "permissions", "source_ref"))
        key = identifier(item["id"], "ID peran")
        refs = [identifier(value, "Permission peran") for value in entries(item["permissions"], 100)]
        if key in roles or set(refs) - permissions.keys() or len(refs) != len(set(refs)):
            raise ContractError("Peran ganda atau permission tidak diakui.")
        roles[key] = {"permissions": sorted(refs), "source_ref": text(item["source_ref"], "Rujukan peran", 200)}
    settings = {"session_seconds": integer(plan["session_seconds"], "TTL sesi", 30, 86_400),
                "iterations": integer(plan["iterations"], "Iterasi PBKDF2", 120_000, 600_000),
                "max_accounts": integer(plan["max_accounts"], "Kapasitas akun", 1, 500),
                "max_sessions": integer(plan["max_sessions"], "Kapasitas sesi", 1, 1000),
                "roles": {key: item["permissions"] for key, item in sorted(roles.items())}}
    runtime = RUNTIME.replace("import time\n", f"import time\n\nSETTINGS = {settings!r}\n", 1).encode()
    report = {"schema": "ace.factory-auth-build.v1", "product_id": product, "plan_sha256": expected,
              "session_seconds": settings["session_seconds"], "password_storage": "pbkdf2_hmac_sha256",
              "permissions": [{"id": key, "source_ref": source} for key, source in sorted(permissions.items())],
              "roles": [{"id": key, **item} for key, item in sorted(roles.items())],
              "runtime": {"path": "product_auth.py", "sha256": sha256(runtime).hexdigest()}}
    return {"product_auth.py": runtime, "auth_manifest.json": canonical(report) + b"\n"}, report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        files, report = build(decode(read(args.plan)), args.expect_sha256)
        materialize(args.output, files)
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
