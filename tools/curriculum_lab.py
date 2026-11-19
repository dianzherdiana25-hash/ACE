#!/usr/bin/env python3
"""Tulis laporan Markdown dari episode historis ke stdout."""
from __future__ import annotations

import argparse
from collections import defaultdict
from html import escape
import json
from pathlib import Path
from tempfile import TemporaryDirectory

if __package__:
    from . import curriculum_propose, pattern_distill
else:
    import curriculum_propose
    import pattern_distill


def _has_text(record, fields):
    return any(isinstance(record.get(key), str) and record[key].strip() for key in fields)


def _read_corpus(path):
    entries = {}
    if path is None:
        return entries
    for index, row in pattern_distill._read_evidence_records(path):
        task_id = row.get("id")
        if not isinstance(task_id, str) or not task_id.strip() or task_id in entries:
            raise ValueError(f"ID korpus kosong atau ganda pada entri {index}.")
        entries[task_id] = (index, row)
    return entries


def _prepare_history(episodes, corpus_path):
    corpus = _read_corpus(corpus_path)
    records = []
    references = []
    failures = defaultdict(list)
    excluded = 0
    no_shape = 0
    for index, episode in pattern_distill._read_evidence_records(episodes):
        accepted = pattern_distill._is_ratified(episode)
        rejected = episode.get("ratified") is False
        if (episode.get("error") or not (accepted or rejected)
                or not _has_text(episode, ("output", "response", "answer", "candidate", "code"))):
            excluded += 1
            continue

        task_id = episode.get("episode_id") or episode.get("id")
        if not isinstance(task_id, str) or not task_id.strip():
            raise ValueError(f"ID episode kosong pada entri {index}.")
        if not _has_text(episode, ("task_kind",)):
            raise ValueError(f"task_kind kosong pada entri {index} ({task_id}).")
        reference = f"{episodes.as_posix()}, entri {index} ({task_id})"
        if not _has_text(episode, ("instruction", "prompt", "problem", "title")):
            corpus_index, task = corpus.get(task_id, (None, {}))
            if task.get("task_kind") != episode["task_kind"] or not _has_text(task, ("instruction",)):
                raise ValueError(f"Instruksi historis tidak ditemukan untuk {reference}.")
            episode = {**episode, "instruction": task["instruction"]}
            reference += f"; instruksi {corpus_path.as_posix()}, entri {corpus_index}"

        records.append(episode)
        references.append(reference)
        if rejected:
            shape = pattern_distill._extract_task_shape(episode)
            keywords = tuple(sorted(shape["keywords"]))
            constraints = tuple(sorted(shape["constraints_detected"]))
            if keywords or constraints:
                failures[shape["task_kind"], keywords, constraints].append(reference)
            else:
                no_shape += 1
    return records, references, failures, excluded, no_shape


def _md(value):
    """Render teks sumber sebagai teks biasa di dalam daftar Markdown."""
    escaped = escape(" ".join(str(value).split()))
    return escaped.translate(str.maketrans({char: f"&#{ord(char)};" for char in r"\`*_[]~!|"}))


def run_lab(episodes: Path, *, corpus: Path | None = None,
            max_chars: int = pattern_distill.DEFAULT_MAX_CHARS) -> str:
    """Rangkai distilasi dan pengusulan dengan berkas sementara milik lab."""
    records, references, failures, excluded, no_shape = _prepare_history(episodes, corpus)
    gaps = []
    gap_evidence = {}
    for number, (kind, keywords, constraints) in enumerate(sorted(failures), 1):
        gap_id = f"gap-{number:04d}"
        evidence = failures[kind, keywords, constraints]
        gaps.append({"id": gap_id, "priority": len(evidence), "task_kind": kind,
                     "keywords": list(keywords), "constraints_detected": list(constraints)})
        gap_evidence[gap_id] = evidence

    with TemporaryDirectory(prefix="ace-curriculum-lab-") as directory:
        work = Path(directory)
        history = work / "episodes.json"  # Larik JSON juga bisa mewakili nol episode.
        patterns = work / "patterns.jsonl"
        gap_list = work / "gaps.json"
        history.write_text(json.dumps(records), encoding="utf-8")
        gap_list.write_text(json.dumps(gaps), encoding="utf-8")
        summary = pattern_distill.distill_evidence(
            [history], patterns, allow_empty=True, max_chars=max_chars,
        )
        result = curriculum_propose.propose_curriculum(patterns, gap_list)
        pattern_refs = {}
        with patterns.open(encoding="utf-8") as staging:
            for line in staging:
                pattern = json.loads(line)
                provenance = pattern["provenance"]
                key = (pattern["source_episode"], provenance["output_sha256"])
                pattern_refs[key] = references[provenance["entry_index"] - 1]

    lines = [
        "# Kurikulum yang AKAN diusulkan", "",
        "Analisis baca-saja atas episode historis untuk ditelaah.", "",
        f"- Sumber episode — {_md(episodes.as_posix())}",
        f"- Pola terdistilasi — {summary['distilled_count']}",
        f"- Usulan — {len(result['proposals'])}",
        f"- Celah terbuka — {len(result['open_gaps'])}",
        f"- Episode dikecualikan — {excluded}",
        f"- Episode tak teratifikasi tanpa ciri — {no_shape}",
        f"- Batas karakter per pola — {max_chars}", "",
        "## Cara menghitung celah", "",
        "Episode dengan error, tanpa keluaran, atau tanpa status yang dikenali dikecualikan. "
        "Celah berasal dari episode dengan `ratified: false` dan keluaran tercatat. "
        "Jika teks tugas kosong, instruksi diambil dari korpus historis dengan ID dan jenis tugas yang sama. "
        "Nomor entri berbasis satu mengikuti baris JSONL atau posisi episode di JSON. "
        "Ciri memakai ekstraksi distiler. Episode tanpa kata kunci dan kendala dilewati.", "",
        "Episode dikelompokkan menurut jenis tugas dan himpunan kata kunci serta kendala yang sama. "
        "Prioritas adalah jumlah entri historis dalam kelompok. ID celah mengikuti urutan leksikal "
        "kelompok. Pengusul mengurutkan prioritas menurun, lalu ID menaik. Satu pola pendukung "
        "harus memiliki jenis tugas yang sama dan memuat seluruh ciri celah.", "",
    ]

    def describe_gap(gap):
        gap_id = gap["id"]
        lines.append(f"- **{gap_id}** — {_md(gap['task_kind'])}, prioritas {gap['priority']}")
        lines.append(f"  - Kata kunci — {_md(', '.join(gap['keywords'])) or '∅'}")
        lines.append(f"  - Kendala — {_md(', '.join(gap['constraints_detected'])) or '∅'}")
        lines.extend(f"  - Bukti celah — {_md(ref)}" for ref in gap_evidence[gap_id])

    lines.extend(["## Usulan", ""])
    if not result["proposals"]:
        lines.append("- Nihil.")
    for proposal in result["proposals"]:
        describe_gap(proposal["gap"])
        for source in proposal["source_patterns"]:
            key = (source["source_episode"], source["output_sha256"])
            lines.append(f"  - Pola pendukung — `{key[1]}` · {_md(pattern_refs[key])}")
            lines.extend(f"    - Langkah — {_md(step)}" for step in source["approach"])
            lines.extend(f"    - Pitfall — {_md(note)}" for note in source["pitfalls"])
    lines.extend(["", "## Celah terbuka", ""])
    if not result["open_gaps"]:
        lines.append("- Nihil.")
    for gap in result["open_gaps"]:
        describe_gap(gap)
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episodes", type=Path, required=True, help="Berkas episode historis.")
    parser.add_argument("--corpus", type=Path, help="Korpus historis jika episode tidak memuat instruksi.")
    parser.add_argument("--max-chars", type=int, default=pattern_distill.DEFAULT_MAX_CHARS)
    args = parser.parse_args(argv)
    try:
        report = run_lab(args.episodes, corpus=args.corpus, max_chars=args.max_chars)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    print(report, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
