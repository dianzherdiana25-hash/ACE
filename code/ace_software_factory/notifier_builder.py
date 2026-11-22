"""Buat paket notifikasi lokal dari template bersumber dan permintaan terdaftar.

Placeholder dikompilasi sebagai daftar field teks, tanpa evaluasi Python.
Artefak menyimpan rujukan penerima lokal dan isi yang siap ditelaah.
Builder menolak replay bentrok dan tidak membuka transport pengiriman.
"""
import argparse
from hashlib import sha256
from pathlib import Path
import string
import sys

from ._contracts import ContractError, canonical, checked, decode, entries, identifier, identity, integer, obj, read, schema, text
from .repo_scaffolder import materialize


CHANNELS = {"email_draft", "in_app"}
FORMATTER = string.Formatter()


def _compile(template, registered, label, maximum, *, multiline=False):
    if not isinstance(template, str) or not template.strip() or len(template) > maximum:
        raise ContractError(f"{label} perlu teks dengan batas.")
    if not all(char.isprintable() or (multiline and char == "\n") for char in template):
        raise ContractError(f"{label} mengandung karakter kontrol.")
    parsed = list(FORMATTER.parse(template))
    for _, field, formatting, conversion in parsed:
        if field is not None and (field not in registered or formatting or conversion):
            raise ContractError(f"{label} mengandung placeholder di luar deklarasi.")
    return parsed


def _render(code, values):
    return "".join(literal + (values[field] if field is not None else "")
                   for literal, field, _, _ in code)


def prepare(manifest, requests, expected):
    checked(manifest, expected)
    schema(manifest, "ace.factory-notifier.v1", ("source_ref", "max_message_bytes", "templates"))
    source = text(manifest["source_ref"], "Sumber template")
    maximum = integer(manifest["max_message_bytes"], "Byte maksimum", 80, 10_000)
    templates = {}
    for raw in entries(manifest["templates"], 50, minimum=1):
        obj(raw, ("id", "channel", "fields", "subject", "body", "source_ref"))
        key = identifier(raw["id"], "ID template")
        lane = raw["channel"]
        if key in templates or not isinstance(lane, str) or lane not in CHANNELS:
            raise ContractError("Template ganda atau kanal tidak didukung.")
        selected = [identifier(field, "Nama field") for field in entries(raw["fields"], 25)]
        if len(selected) != len(set(selected)):
            raise ContractError("Field template ganda.")
        registered = set(selected)
        subject = _compile(raw["subject"], registered, "Subjek", 180)
        body = _compile(raw["body"], registered, "Isi", 5000, multiline=True)
        if {field for _, field, _, _ in subject + body if field is not None} != registered:
            raise ContractError("Deklarasi field harus sama dengan placeholder yang digunakan.")
        templates[key] = (lane, registered, subject, body, text(raw["source_ref"], "Rujukan template"))

    schema(requests, "ace.factory-notifier-requests.v1", ("templates_sha256", "requests"))
    if requests["templates_sha256"] != expected:
        raise ContractError("Permintaan memakai versi template berbeda.")
    queue = {}
    replayed = []
    for raw in entries(requests["requests"], 1000):
        obj(raw, ("id", "template", "recipient_ref", "values", "source_ref"))
        key = identifier(raw["id"], "ID pesan")
        ref = identifier(raw["template"], "ID template")
        recipient = identifier(raw["recipient_ref"], "Referensi penerima")
        anchor = identity(raw)
        if key in queue:
            if queue[key]["request_sha256"] != anchor:
                raise ContractError("ID notifikasi merujuk permintaan berbeda.")
            replayed.append(key)
            continue
        if ref not in templates:
            raise ContractError("Template tidak dikenal.")
        lane, registered, title, body, template_source = templates[ref]
        values = obj(raw["values"], registered)
        clean = {field: text(value, "Nilai template", 500) for field, value in values.items()}
        message = {"schema": "ace.factory-notification-draft.v1", "id": key, "channel": lane,
                   "recipient_ref": recipient, "subject": _render(title, clean), "body": _render(body, clean),
                   "template": ref, "template_ref": template_source, "request_sha256": anchor,
                   "request_ref": text(raw["source_ref"], "Sumber permintaan"), "status": "draft"}
        if len(message["subject"]) > 180 or len(canonical(message)) > maximum:
            raise ContractError("Notifikasi melampaui batas byte atau judul.")
        queue[key] = message
    files = {f"messages/{key}.json": canonical(row) + b"\n" for key, row in sorted(queue.items())}
    report = {"schema": "ace.factory-notification-report.v1", "templates_sha256": expected, "template_ref": source,
              "drafts": [{"path": path, "sha256": sha256(data).hexdigest()} for path, data in files.items()],
              "identical_replays": replayed}
    return {**files, "notification_report.json": canonical(report) + b"\n"}, report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("templates", "requests", "output"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        files, report = prepare(decode(read(args.templates)), decode(read(args.requests)), args.expect_sha256)
        materialize(args.output, files)
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
