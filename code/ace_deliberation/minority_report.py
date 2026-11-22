"""Susun dissent sebagai laporan yang tetap dapat dibaca setelah putusan.

Pengelompokan posisi hanya memakai pemetaan yang diberikan. Sanggahan yang
belum dipetakan tetap muncul dengan sumber asli. Status tanggapan menandai
rujukan dalam transcript, sehingga laporan tidak menyimpulkan persetujuan
atau menarik kembali dissent atas nama peserta.
"""
from collections import defaultdict
import json
from pathlib import Path
import re

from .debate_protocol import MAX_INPUT_BYTES, verify_report


MAX_POSITIONS = 250
_ESCAPE = re.compile(r"([\\`*_{}\[\]()<>#!|&])")


class MinorityError(ValueError):
    """Transcript atau pemetaan posisi tidak dapat ditelusuri."""


def _shape(value, required):
    if not isinstance(value, dict) or value.keys() != set(required):
        raise MinorityError("Objek laporan minoritas tidak sesuai skema.")


def _text(value, label, maximum):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum or "\0" in value:
        raise MinorityError(f"{label} tidak sah.")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise MinorityError(f"{label} bukan teks UTF-8 yang sah.") from exc
    return value.strip()


def _position(raw, available, covered):
    _shape(raw, ("id", "title", "objections", "alternative"))
    identifier, title = _text(raw["id"], "id posisi", 96), _text(raw["title"], "judul", 300)
    objections = raw["objections"]
    if not isinstance(objections, list) or not 1 <= len(objections) <= len(available):
        raise MinorityError("Posisi wajib merujuk satu atau lebih sanggahan.")
    refs = [_text(ref, "id sanggahan", 96) for ref in objections]
    if len(set(refs)) != len(refs) or any(ref not in available or ref in covered for ref in refs):
        raise MinorityError("Rujukan posisi ganda atau bukan sanggahan.")
    alternative = raw["alternative"]
    if alternative is not None:
        _shape(alternative, ("statement", "source_ref"))
        alternative = {"statement": _text(alternative["statement"], "alternatif", 5_000),
                       "source_ref": _text(alternative["source_ref"], "rujukan alternatif", 512)}
    covered.update(refs)
    return identifier, title, set(refs), alternative


def _turn(row, digest):
    return {"turn_id": row["turn_id"], "author": row["participant"], "statement": row["statement"],
            "source": {"sha256": digest, "turn_id": row["turn_id"]},
            "evidence_refs": row["evidence_refs"].copy()}


def build_report(raw):
    _shape(raw, ("debate", "positions"))
    debate = raw["debate"]
    if not verify_report(debate) or debate["decision"] is None:
        raise MinorityError("Laporan memerlukan transcript sah dengan putusan tercatat.")
    items = raw["positions"]
    if not isinstance(items, list) or len(items) > MAX_POSITIONS:
        raise MinorityError("Daftar posisi melampaui batas.")
    objections = debate["dissent_turns"]
    digest = debate["sha256"]
    known = set(objections)
    turns = {row["turn_id"]: row for row in debate["turns"]}
    responses = defaultdict(list)
    affected = defaultdict(list)
    for row in debate["turns"]:
        if row["move"] in ("synthesis", "response"):
            for target in row["targets"]:
                if target in known:
                    responses[target].append(_turn(row, digest))
        if row["move"] == "objection":
            for target in row["targets"]:
                affected[target].append(row["turn_id"])

    notes = {
        key: {**_turn(turns[key], digest), "contested_turns": turns[key]["targets"].copy(),
              "response_status": "referenced" if responses[key] else "open", "responses": responses[key]}
        for key in objections
    }
    covered = set()
    positions = {}
    for item in items:
        identifier, title, refs, alternative = _position(item, known, covered)
        if identifier in positions:
            raise MinorityError("ID posisi ganda.")
        selected = [notes[ref] for ref in objections if ref in refs]
        positions[identifier] = {
            "id": identifier, "title": title, "alternative": alternative, "objections": selected,
            "authors": sorted({note["author"] for note in selected}),
            "open_objections": [note["turn_id"] for note in selected if note["response_status"] == "open"],
        }

    return {
        "schema": "ace.minority-report.v1", "debate_id": debate["plan"]["debate_id"],
        "debate_sha256": digest, "outcome": debate["decision"]["outcome"],
        "positions": [positions[key] for key in sorted(positions)],
        "unassigned_objections": [notes[key] for key in objections if key not in covered],
        "contested_turns": [{"turn": _turn(turns[key], digest), "objection_ids": refs}
                            for key, refs in sorted(affected.items(), key=lambda item: (-len(item[1]), item[0]))],
        "author_count": len({note["author"] for note in notes.values()}),
        "objection_count": len(notes), "open_count": sum(not note["responses"] for note in notes.values()),
    }


def _escape(text):
    return _ESCAPE.sub(r"\\\1", " ".join(text.split()))


def _append_objections(lines, notes):
    for note in notes:
        lines.append(f"- {_escape(note['turn_id'])} · {_escape(note['author'])} — {_escape(note['statement'])}")
        lines.append("  - Menyanggah — " + ", ".join(_escape(ref) for ref in note["contested_turns"]))
        lines.extend(f"  - Rujukan — {_escape(ref)}" for ref in note["evidence_refs"])
        if not note["responses"]:
            lines.append("  - Belum ada tanggapan tercatat.")
        for response in note["responses"]:
            lines.append(f"  - Tanggapan {_escape(response['turn_id'])} — {_escape(response['statement'])}")


def render_markdown(report):
    lines = ["# Laporan minoritas", "", f"- Debat — {_escape(report['debate_id'])}",
             f"- SHA-256 transcript — `{report['debate_sha256']}`", f"- Outcome — {report['outcome']}", ""]
    for position in report["positions"]:
        lines.extend((f"## {_escape(position['title'])}", ""))
        alternative = position["alternative"]
        if alternative is not None:
            lines.append(f"- Alternatif tercatat — {_escape(alternative['statement'])}")
            lines.append(f"  - Sumber — {_escape(alternative['source_ref'])}")
        _append_objections(lines, position["objections"])
        lines.append("")
    if report["unassigned_objections"]:
        lines.extend(("## Sanggahan tanpa kelompok posisi", ""))
        _append_objections(lines, report["unassigned_objections"])
    elif not report["objection_count"]:
        lines.append("Transcript tidak memuat sanggahan.")
    if report["contested_turns"]:
        lines.extend(("", "## Klaim yang dipersoalkan", ""))
        for item in report["contested_turns"]:
            turn = item["turn"]
            ids = ", ".join(_escape(identifier) for identifier in item["objection_ids"])
            lines.append(f"- {_escape(turn['turn_id'])} — {_escape(turn['statement'])}")
            lines.append(f"  - Sanggahan — {ids}")
    return "\n".join(lines) + "\n"


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args(argv)
    try:
        with args.input.open("rb") as handle:
            data = handle.read(MAX_INPUT_BYTES + 1)
        if len(data) > MAX_INPUT_BYTES:
            raise MinorityError("Masukan laporan melebihi batas.")
        report = build_report(json.loads(data))
        if args.format == "markdown":
            print(render_markdown(report), end="")
        else:
            print(json.dumps(report, ensure_ascii=False, indent=2))
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
