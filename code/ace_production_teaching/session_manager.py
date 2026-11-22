"""Jalankan sesi belajar lokal bergiliran dan catat hash payload setiap transisi."""
import argparse
from pathlib import Path
import sys

from ._contracts import (ProductionError, anchor, canonical, decode, identifier,
                         identity, items, obj, read, schema, text)
from .grader import assess


class Session:
    """Satu sesi lokal dengan urutan prompt → jawaban → receipt evaluasi."""

    def __init__(self, plan, expected):
        anchor(plan, expected)
        schema(plan, "ace.teaching.session-plan.v1", ("id", "consent_ref", "tasks"))
        self.id = identifier(plan["id"], "Sesi")
        self.plan_sha256 = expected
        self.consent_ref = text(plan["consent_ref"], "Rujukan persetujuan")
        self.tasks = []
        known = set()
        for item in items(plan["tasks"], 80, 1):
            obj(item, ("id", "prompt", "source_ref", "rubric"))
            key = identifier(item["id"], "Tugas")
            if key in known:
                raise ProductionError("Tugas sesi ganda.")
            known.add(key)
            self.tasks.append({"id": key, "prompt": text(item["prompt"], "Prompt", 1600),
                               "source_ref": text(item["source_ref"], "Rujukan tugas"), "rubric": item["rubric"]})
        self.pending = False
        self.closed = False
        self.position = 0
        self.events = []
        self.head = identity({"session": self.id, "plan_sha256": expected, "consent_ref": self.consent_ref})

    def _receipt(self, action, values):
        body = {"session": self.id, "event": len(self.events) + 1, "action": action,
                "previous_sha256": self.head, **values}
        self.head = identity(body)
        entry = {**body, "event_sha256": self.head}
        self.events.append(entry)
        return entry

    def receive(self, command):
        if self.closed or not isinstance(command, dict):
            raise ProductionError("Sesi tertutup atau perintah bukan objek.")
        action = command.get("action")
        if action == "next":
            obj(command, ("action",))
            if self.pending or self.position >= len(self.tasks):
                raise ProductionError("Sesi sedang menunggu jawaban atau tugas telah habis.")
            item = self.tasks[self.position]
            self.pending = True
            return self._receipt("prompt", {key: item[key] for key in ("id", "prompt", "source_ref")})
        if action == "answer":
            obj(command, ("action", "id", "text", "source_ref"))
            if not self.pending or command["id"] != self.tasks[self.position]["id"]:
                raise ProductionError("Jawaban tidak menunjuk prompt aktif.")
            item = self.tasks[self.position]
            rubric = obj(item["rubric"], ("criteria", "passing_bp"))
            grading = {"schema": "ace.teaching.open-grade-plan.v1", "exercise": item["id"], **rubric,
                       "response": {"text": command["text"], "source_ref": command["source_ref"]}}
            result = assess(grading, identity(grading))
            value = self._receipt("graded", {"id": item["id"], "response_sha256": identity(command["text"]),
                                               "response_ref": result["response_source"], "grade": result})
            self.position += 1
            self.pending = False
            return value
        if action == "close":
            obj(command, ("action",))
            if self.pending:
                raise ProductionError("Jawaban prompt aktif perlu diselesaikan sebelum penutupan.")
            self.closed = True
            return self._receipt("closed", {"completed": self.position, "total": len(self.tasks)})
        raise ProductionError("Jenis tindakan sesi masih belum dikenal.")


def verify_session(events, initial):
    head = initial
    for ordinal, entry in enumerate(events, 1):
        payload = {key: value for key, value in entry.items() if key != "event_sha256"}
        if payload["event"] != ordinal or payload["previous_sha256"] != head:
            raise ProductionError("Rantai receipt sesi melompat.")
        head = identity(payload)
        if head != entry["event_sha256"]:
            raise ProductionError("Hash receipt sesi berbeda.")
    return head


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        session = Session(decode(read(args.plan)), args.expect_sha256)
        with args.receipt.open("xb") as log:
            for line, content in enumerate(sys.stdin.buffer, 1):
                if line > 162 or len(content) > 12000:
                    raise ProductionError("Perintah sesi melampaui anggaran.")
                entry = session.receive(decode(content))
                encoded = canonical(entry) + b"\n"
                log.write(encoded)
                log.flush()
                sys.stdout.buffer.write(encoded)
                sys.stdout.buffer.flush()
                if session.closed:
                    break
    except (OSError, ValueError, KeyError, TypeError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return int(not session.closed)


if __name__ == "__main__":
    raise SystemExit(main())
