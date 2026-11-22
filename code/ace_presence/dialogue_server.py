"""Buka server dialog lokal ber-token dengan urutan turn, batas request dan jurnal tahan retry."""
import argparse
from hashlib import sha256
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from ipaddress import IPv4Address
import os
from pathlib import Path
import re
import sqlite3

from ._contracts import PresenceError, canonical, decode, identifier, integer
from ._journal import Journal


TOKEN = re.compile(r"[A-Za-z0-9_-]{24,128}")
SESSION = re.compile(r"/v1/sessions/([a-z][a-z0-9_]{0,63})")
MAX_BODY = 28_000


def create_server(path, credential, host="127.0.0.1", port=0):
    if not isinstance(credential, str) or not TOKEN.fullmatch(credential):
        raise PresenceError("Server dialog perlu token lokal berukuran 24–128 karakter.")
    if not IPv4Address(host).is_loopback:
        raise PresenceError("Server dialog harus di-bind ke loopback IPv4.")
    integer(port, "Port dialog", 0, 65535)
    permitted = sha256(credential.encode("ascii")).digest()
    journal = Journal(path)

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.0"

        def setup(self):
            self.request.settimeout(4)
            super().setup()

        def log_message(self, *_):
            # URL dan data autentikasi tidak ditulis oleh handler.
            return

        def _respond(self, status, value):
            raw = canonical(value) + b"\n"
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(raw)

        def _granted(self):
            header = self.headers.get("Authorization", "")
            provided = header[7:] if header.startswith("Bearer ") else ""
            if TOKEN.fullmatch(provided) and hmac.compare_digest(permitted, sha256(provided.encode("ascii")).digest()):
                return True
            self._respond(401, {"error": "authorization_required"})
            return False

        def do_GET(self):
            if not self._granted():
                return
            match = SESSION.fullmatch(self.path)
            if match is None:
                self._respond(404, {"error": "unknown_route"})
                return
            try:
                self._respond(200, journal.export(identifier(match[1], "Sesi")))
            except (PresenceError, OSError, sqlite3.Error, ValueError, KeyError, TypeError, RecursionError):
                self._respond(409, {"error": "journal_unavailable"})

        def do_POST(self):
            if not self._granted():
                return
            if self.path != "/v1/turn":
                self._respond(404, {"error": "unknown_route"})
                return
            if self.headers.get_content_type() != "application/json" or self.headers.get("Transfer-Encoding"):
                self._respond(415, {"error": "unsupported_content"})
                return
            lengths = self.headers.get_all("Content-Length", failobj=[])
            length = lengths[0] if len(lengths) == 1 else ""
            if not length.isascii() or not length.isdecimal() or len(length) > 5 or not 0 < int(length) <= MAX_BODY:
                self._respond(413, {"error": "invalid_message_length"})
                return
            try:
                size = int(length)
                data = self.rfile.read(size)
                if len(data) != size:
                    raise PresenceError("Request terpotong.")
                receipt, duplicate = journal.append(decode(data))
            except PresenceError:
                self._respond(409, {"error": "invalid_or_conflicting_turn"})
                return
            except (ValueError, TypeError, KeyError, OSError, RecursionError):
                self._respond(400, {"error": "invalid_input"})
                return
            except sqlite3.Error:
                self._respond(503, {"error": "journal_unavailable"})
                return
            self._respond(200 if duplicate else 201, {"turn": receipt, "duplicate": duplicate})

    return ThreadingHTTPServer((host, port), Handler)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("journal", type=Path)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--token-env", default="ACE_PRESENCE_LOCAL_TOKEN")
    args = parser.parse_args(argv)
    try:
        with create_server(args.journal, os.environ.get(args.token_env), port=args.port) as server:
            server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        return 0
    except (OSError, sqlite3.Error, ValueError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
