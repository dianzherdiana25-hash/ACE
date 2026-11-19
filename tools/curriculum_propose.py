#!/usr/bin/env python3
"""Usulkan kurikulum lokal dari katalog pattern_distilled dan daftar celah JSON.

Contoh satu daftar celah:
[{"id":"interval-kosong","priority":3,"task_kind":"code","keywords":["interval"],
  "constraints_detected":["edge_empty"]}]

priority adalah bilangan bulat. keywords dan constraints_detected boleh
diabaikan, tetapi gabungannya wajib memuat minimal satu ciri. Seluruh ciri
harus cocok persis (peka kapital) dalam task_shape dari satu pola dengan
task_kind yang sama. Gunakan kosakata katalog. Tidak ada pencocokan sinonim.

Satu usulan per celah yang cocok. gap menyimpan kriteria asal; setiap
source_patterns memuat pasangan identitas katalog (source_episode,
output_sha256) beserta approach dan pitfalls dalam urutan dari distiler.
open_gaps memuat celah yang belum didukung. Kedua daftar celah diurutkan
menurut priority menurun, lalu id menaik. Pola pendukung diurutkan menurut
source_episode, lalu output_sha256, keduanya menaik menurut kode poin Unicode.
Identitas ganda ditolak. Daftar ciri merupakan himpunan dan ditulis terurut.
JSON keluaran menggunakan UTF-8, LF, dan kunci terurut.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from tempfile import NamedTemporaryFile


def _text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} wajib berupa teks berisi.")
    return value


def _strings(value, field):
    if not isinstance(value, list):
        raise ValueError(f"{field} wajib berupa daftar teks.")
    return [_text(item, field) for item in value]


def _read_catalog(path):
    patterns = {}
    with path.open(encoding="utf-8") as catalog:
        for number, line in enumerate(catalog, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                if (not isinstance(record, dict)
                        or record.get("schema") != "ace.pattern-distilled.v1"
                        or record.get("event_class") != "pattern_distilled"):
                    raise ValueError("Diperlukan record ace.pattern-distilled.v1.")
                shape = record.get("task_shape")
                provenance = record.get("provenance")
                if not isinstance(shape, dict) or not isinstance(provenance, dict):
                    raise ValueError("task_shape dan provenance wajib berupa objek.")
                episode = _text(record.get("source_episode"), "source_episode")
                digest = _text(provenance.get("output_sha256"), "output_sha256")
                if not re.fullmatch("[0-9a-f]{64}", digest):
                    raise ValueError("output_sha256 tidak sah.")
                key = (episode, digest)
                if key in patterns:
                    raise ValueError("Identitas pola ganda.")
                steps = _strings(record.get("approach"), "approach")
                if not steps:
                    raise ValueError("approach kosong.")
                patterns[key] = (
                    _text(shape.get("task_kind"), "task_kind"),
                    set(_strings(shape.get("keywords"), "keywords")),
                    set(_strings(shape.get("constraints_detected"), "constraints_detected")),
                    {"source_episode": episode, "output_sha256": digest, "approach": steps,
                     "pitfalls": _strings(record.get("pitfalls"), "pitfalls")},
                )
            except ValueError as exc:
                raise ValueError(f"Katalog baris {number}: {exc}") from exc
    return [patterns[key] for key in sorted(patterns)]


def _read_gaps(path):
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError("Daftar celah wajib berupa larik JSON.")
    gaps = {}
    for row in rows:
        if not isinstance(row, dict) or row.keys() - {
            "id", "priority", "task_kind", "keywords", "constraints_detected"
        }:
            raise ValueError("Objek celah atau nama field tidak sah.")
        gap_id = _text(row.get("id"), "id")
        if gap_id in gaps:
            raise ValueError(f"ID celah ganda: {gap_id}")
        if type(row.get("priority")) is not int:
            raise ValueError(f"Celah {gap_id}: priority wajib bilangan bulat.")
        keywords = sorted(set(_strings(row.get("keywords", []), "keywords")))
        constraints = sorted(set(_strings(row.get("constraints_detected", []), "constraints_detected")))
        if not keywords and not constraints:
            raise ValueError(f"Celah {gap_id} memerlukan minimal satu ciri.")
        gaps[gap_id] = {
            "id": gap_id, "priority": row["priority"],
            "task_kind": _text(row.get("task_kind"), "task_kind"),
            "keywords": keywords, "constraints_detected": constraints,
        }
    return sorted(gaps.values(), key=lambda gap: (-gap["priority"], gap["id"]))


def propose_curriculum(patterns_path: Path, gaps_path: Path) -> dict:
    """Kembalikan usulan dan celah terbuka tanpa mengubah kedua berkas asal."""
    patterns = _read_catalog(patterns_path)
    proposals = []
    open_gaps = []
    for gap in _read_gaps(gaps_path):
        support = [
            source for kind, keywords, constraints, source in patterns
            if kind == gap["task_kind"]
            and keywords.issuperset(gap["keywords"])
            and constraints.issuperset(gap["constraints_detected"])
        ]
        if support:
            proposals.append({"gap": gap, "source_patterns": support})
        else:
            open_gaps.append(gap)
    return {"schema": "ace.curriculum-proposal.v1", "proposals": proposals, "open_gaps": open_gaps}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--patterns", required=True, type=Path)
    parser.add_argument("--gaps", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    tmp_path = None
    try:
        if args.output.resolve() in (args.patterns.resolve(), args.gaps.resolve()):
            raise ValueError("Berkas keluaran berimpit dengan masukan.")
        result = propose_curriculum(args.patterns, args.gaps)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(dir=args.output.parent, delete=False) as tmp:
            tmp_path = Path(tmp.name)
            payload = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2)
            tmp.write((payload + "\n").encode("utf-8"))
        tmp_path.replace(args.output)
    except (ValueError, OSError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
