from http.client import HTTPConnection
from pathlib import Path
import secrets
import sqlite3
from tempfile import TemporaryDirectory
from threading import Thread
import unittest

from ._contracts import PresenceError, canonical, decode
from ._journal import Journal, validate_chain
from .dialogue_server import create_server


def turn(key="opening", role="user", reply=None, message="Panel perlu kalibrasi.", speaker=None,
         date="2025-05-01T10:00:00Z", session="fixture"):
    return {"session": session, "id": key, "role": role, "speaker": speaker or ("quoted" if role == "user" else "ace"),
            "message": message, "at": date, "reply_to": reply,
            "refs": [] if role == "user" else ["fixture:evidence"]}


class DialogueServerTests(unittest.TestCase):
    def test_actual_http_loopback_restart_idempotence_and_chain(self):
        with TemporaryDirectory() as temporary:
            journal = Path(temporary) / "fixture.sqlite"
            token = secrets.token_urlsafe(32)
            with create_server(journal, token) as server:
                process = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
                process.start()
                try:
                    def call(method, url, payload=None, authed=True):
                        conn = HTTPConnection("127.0.0.1", server.server_port, timeout=3)
                        headers = {"Authorization": "Bearer " + token} if authed else {}
                        if payload is not None:
                            headers["Content-Type"] = "application/json"
                        try:
                            conn.request(method, url, canonical(payload) if payload is not None else None, headers=headers)
                            response = conn.getresponse()
                            return response.status, decode(response.read())
                        finally:
                            conn.close()

                    self.assertEqual(call("GET", "/v1/sessions/fixture", authed=False)[0], 401)
                    self.assertEqual(call("POST", "/v1/turn", turn())[0], 201)
                    status, retry = call("POST", "/v1/turn", turn())
                    self.assertEqual((status, retry["duplicate"]), (200, True))
                    self.assertEqual(call("POST", "/v1/turn", turn(message="Bentrok."))[0], 409)
                    self.assertEqual(call("POST", "/v1/turn", turn("reply", "assistant", "opening"))[0], 201)
                    _, snapshot = call("GET", "/v1/sessions/fixture")
                    self.assertEqual(len(snapshot["events"]), 2)
                    self.assertEqual(snapshot["head_sha256"], validate_chain("fixture", snapshot["events"]))
                finally:
                    server.shutdown()
                    process.join(2)
            self.assertEqual(Journal(journal).export("fixture"), snapshot)

    def test_unrelated_sqlite_is_read_only_and_nonloopback_refused(self):
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "unrelated.sqlite"
            with sqlite3.connect(path) as store:
                store.execute("CREATE TABLE unrelated (a INTEGER)")
            prior = path.read_bytes()
            with self.assertRaisesRegex(PresenceError, "bukan jurnal"):
                Journal(path)
            self.assertEqual(path.read_bytes(), prior)
            with self.assertRaisesRegex(PresenceError, "loopback"):
                create_server(path, secrets.token_urlsafe(32), host="0.0.0.0")
