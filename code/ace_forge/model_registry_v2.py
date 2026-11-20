"""Catat asal-usul dan hasil review artefak tempa dalam registry lokal.

Replay mengikuti rantai hash yang ditambatkan pemanggil. Pencatatan
membutuhkan rujukan artefak, lineage, dan bukti review. Perintah
propose menghasilkan satu baris untuk ditelaah. Pemeriksaan ini
murni file dan tidak mengubah registry atau status aktivasi runtime.
"""
import argparse
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import sys

from ._forge_io import InputError, canonical, decode, digest, entries, identity, integer, object_fields, read_bytes, string
from ._numeric import reference
from .dataset_forge import MAX_BYTES


MAX_RECORDS = 25_000
GENESIS = identity({"schema": "ace.forge-registry.v2", "records": []})
PARENTS = {"base": (0, 0), "adapter": (1, 1), "merged": (2, 12), "quantized": (1, 1)}


def _utc(value):
    value = string(value, "cap waktu")
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("Timezone hilang")
        return parsed.astimezone(timezone.utc)
    except (ValueError, OverflowError) as exc:
        raise InputError("Cap waktu perlu ISO-8601 bertimezone.") from exc


@dataclass(slots=True)
class Registry:
    head: str = GENESIS
    length: int = 0
    newest: datetime | None = None
    artifacts: dict = field(default_factory=dict)
    seen_refs: set = field(default_factory=set)

    def _new_ref(self, pointer, staged, label):
        parsed = reference(pointer, staged, label)
        if parsed in self.seen_refs:
            raise InputError(f"{label} ganda.")
        return parsed

    def _register(self, key, values, staged):
        object_fields(values, ("kind", "artifact_ref", "recipe_ref", "parent_sha256", "domain"))
        kind = string(values["kind"], "jenis artefak")
        if kind not in PARENTS or key in self.artifacts:
            raise InputError("Jenis tidak dikenal atau artefak sudah terdaftar.")
        parents = [digest(value) for value in entries(values["parent_sha256"], 12)]
        low, high = PARENTS[kind]
        if (not low <= len(parents) <= high or len(set(parents)) != len(parents)
                or set(parents) - self.artifacts.keys()):
            raise InputError("Parent lineage tidak sah atau belum terdaftar.")
        return {
            "sha256": key, "kind": kind, "parent_sha256": sorted(parents),
            "domain": string(values["domain"], "domain"),
            "artifact_ref": self._new_ref(values["artifact_ref"], staged, "rujukan artefak"),
            "recipe_ref": string(values["recipe_ref"], "rujukan resep"),
            "status": "registered", "review": None,
        }

    def _review(self, key, values, staged):
        object_fields(values, ("verdict", "result_ref", "regression_ref", "held_out_sha256"))
        item = self.artifacts.get(key)
        if item is None or item["status"] != "registered":
            raise InputError("Review memerlukan artefak terdaftar yang belum dinilai.")
        status = values["verdict"]
        if status not in ("qualified", "rejected"):
            raise InputError("Verdict review tidak dikenal.")
        result = self._new_ref(values["result_ref"], staged, "rujukan penilaian")
        guard = self._new_ref(values["regression_ref"], staged, "rujukan regresi")
        return {**item, "status": status, "review": {"result_ref": result, "regression_ref": guard,
                                                    "held_out_sha256": digest(values["held_out_sha256"])}}

    def _retire(self, key, values, staged):
        object_fields(values, ("reason_ref",))
        item = self.artifacts.get(key)
        if item is None or item["status"] not in ("qualified", "rejected"):
            raise InputError("Retire memerlukan artefak yang sudah dinilai.")
        reason = self._new_ref(values["reason_ref"], staged, "rujukan retire")
        return {**item, "status": "retired", "status_before_retire": item["status"], "reason_ref": reason}

    def apply(self, entry):
        object_fields(entry, ("sequence", "previous_sha256", "event", "sha256"))
        header = {key: value for key, value in entry.items() if key != "sha256"}
        if (integer(entry["sequence"], 1, MAX_RECORDS) != self.length + 1 or entry["previous_sha256"] != self.head
                or digest(entry["sha256"]) != identity(header)):
            raise InputError("Urutan atau rantai hash registry tidak cocok.")
        event = entry["event"]
        object_fields(event, ("type", "at", "artifact_sha256", "event_ref", "values"))
        time = _utc(event["at"])
        if self.newest is not None and time < self.newest:
            raise InputError("Cap waktu event tidak boleh mundur.")
        action = event["type"]
        key = digest(event["artifact_sha256"])
        handlers = {"register": self._register, "review": self._review, "retire": self._retire}
        if not isinstance(action, str) or action not in handlers:
            raise InputError("Jenis event registry tidak didukung.")
        staged = set()
        pointer = self._new_ref(event["event_ref"], staged, "rujukan event")
        artifact = handlers[action](key, event["values"], staged)
        self.seen_refs.update(staged)
        self.artifacts[key] = {**artifact, "last_event_ref": pointer, "last_event_at": time.isoformat()}
        self.head = entry["sha256"]
        self.length = entry["sequence"]
        self.newest = time

    def export(self):
        return {"schema": "ace.forge-registry-report.v2", "head_sha256": self.head, "events": self.length,
                "artifacts": [self.artifacts[key] for key in sorted(self.artifacts)]}


def _replay(records, expected_head):
    registry = Registry()
    for index, record in enumerate(entries(records, MAX_RECORDS), 1):
        try:
            registry.apply(record)
        except (ValueError, RecursionError) as exc:
            raise InputError(f"Record registry {index}: {exc}") from exc
    if registry.head != digest(expected_head):
        raise InputError("Head registry berbeda dari anchor.")
    return registry


def inspect(records, expected_head):
    return _replay(records, expected_head).export()


def propose(records, expected_head, event):
    registry = _replay(records, expected_head)
    header = {"sequence": registry.length + 1, "previous_sha256": registry.head, "event": event}
    entry = {**header, "sha256": identity(header)}
    registry.apply(entry)
    return entry


def _load(path):
    data = read_bytes(path, MAX_BYTES)
    if data and not data.endswith(b"\n"):
        raise InputError("Berkas registry harus berakhir dengan LF.")
    records = []
    for number, line in enumerate(data.splitlines(), 1):
        try:
            row = decode(line)
            if canonical(row) != line:
                raise InputError("Baris registry wajib JSON kanonis.")
            records.append(row)
            if len(records) > MAX_RECORDS:
                raise InputError("Registry melampaui batas event.")
        except (ValueError, RecursionError) as exc:
            raise InputError(f"Baris registry {number}: {exc}") from exc
    return records


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("registry", type=Path)
    parser.add_argument("--expect-head", required=True)
    parser.add_argument("--propose-event", type=Path)
    args = parser.parse_args(argv)
    try:
        records = _load(args.registry)
        if args.propose_event:
            result = propose(records, args.expect_head, decode(read_bytes(args.propose_event, 100_000)))
        else:
            result = inspect(records, args.expect_head)
        sys.stdout.write(canonical(result).decode("utf-8") + "\n")
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
