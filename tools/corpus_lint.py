#!/usr/bin/env python3
"""Linter mekanis untuk memvalidasi berkas kandidat corpus JSONL ACE.

Memeriksa integritas setiap baris JSONL kandidat corpus:
- JSON sah berbentuk objek dengan schema persis {id, kind, task_kind, instruction}
- kind == "episode" dan task_kind berada pada {"code", "language"}
- id unik dan (bila --prefix diberikan) mengikuti pola prefix serta berurutan 1..N
- untuk task_kind == "code", instruction wajib memuat "docstring Bahasa Indonesia"
- untuk mode --frozen, menolak kandidat yang 60 karakter pertama instruksinya
  tumpang tindih dengan berkas corpus beku mana pun.

Exit code:
- 0: bersih (tidak ada pelanggaran)
- 1: ditemukan pelanggaran corpus (termasuk berkas kosong)
- 2: masukan CLI atau berkas pendukung (--frozen) tidak sah
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any

REQUIRED_FIELDS = frozenset({"id", "kind", "task_kind", "instruction"})
ALLOWED_TASK_KINDS = frozenset({"code", "language"})
REQUIRED_CODE_PHRASE = "docstring Bahasa Indonesia"
FROZEN_PREFIX_LEN = 60


class InvalidInputError(ValueError):
    """Kesalahan masukan CLI, path berkas, atau berkas corpus beku tidak sah."""


def _parse_csv_args(values: list[str] | None) -> list[str]:
    """Pecah argumen opsional yang bisa diulang atau dipisah koma."""
    if not values:
        return []
    result: list[str] = []
    for raw in values:
        for item in raw.split(","):
            cleaned = item.strip()
            if not cleaned:
                raise InvalidInputError("Nilai argumen daftar tidak boleh kosong.")
            result.append(cleaned)
    return result


def load_frozen_prefixes(frozen_paths: list[Path]) -> dict[str, dict[str, Any]]:
    """Muat awalan 60 karakter instruksi dari seluruh berkas corpus beku."""
    prefixes: dict[str, dict[str, Any]] = {}
    for path in frozen_paths:
        if not path.is_file():
            raise InvalidInputError(f"Berkas corpus beku tidak ditemukan: {path}")
        try:
            raw_text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise InvalidInputError(f"Gagal membaca corpus beku '{path}': {exc}") from exc

        for line_no, raw_line in enumerate(raw_text.splitlines(), start=1):
            if not raw_line.strip():
                raise InvalidInputError(
                    f"Baris kosong tidak sah pada corpus beku '{path}' baris {line_no}."
                )
            try:
                obj = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                raise InvalidInputError(
                    f"JSON tidak sah pada corpus beku '{path}' baris {line_no}: {exc.msg}"
                ) from exc
            if not isinstance(obj, dict) or not isinstance(obj.get("instruction"), str):
                raise InvalidInputError(
                    f"Baris corpus beku '{path}' baris {line_no} wajib objek dengan field 'instruction' string."
                )
            prefix60 = obj["instruction"][:FROZEN_PREFIX_LEN]
            prefixes.setdefault(
                prefix60,
                {
                    "frozen_file": str(path),
                    "frozen_id": str(obj.get("id", "")),
                    "frozen_line": line_no,
                },
            )
    return prefixes


def _match_prefix(item_id: str, prefixes: list[str]) -> tuple[str, str] | None:
    """Cocokkan id terhadap daftar prefix terurut dari yang terpanjang."""
    for prefix in sorted(prefixes, key=len, reverse=True):
        if item_id.startswith(prefix):
            return prefix, item_id[len(prefix) :]
    return None


def lint_lines(
    lines: list[str],
    *,
    corpus_name: str = "<memory>",
    prefixes: list[str] | None = None,
    frozen_prefixes: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Jalankan seluruh pemeriksaan corpus pada daftar baris JSONL."""
    active_prefixes = prefixes or []
    active_frozen = frozen_prefixes or {}
    violations: list[dict[str, Any]] = []
    seen_ids: dict[str, int] = {}
    prefix_counters: dict[str, int] = {p: 0 for p in active_prefixes}
    task_kind_counts = {"code": 0, "language": 0}

    def add_violation(line_no: int, code: str, message: str, item_id: str = "") -> None:
        violations.append(
            {
                "line": line_no,
                "id": item_id,
                "code": code,
                "message": message,
            }
        )

    if not lines:
        add_violation(0, "empty_corpus", "Berkas corpus kosong (0 baris).")

    for line_no, raw_line in enumerate(lines, start=1):
        if not raw_line.strip():
            add_violation(line_no, "blank_line", "Baris kosong tidak diizinkan pada berkas JSONL.")
            continue

        try:
            obj = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            add_violation(line_no, "invalid_json", f"JSON tidak sah: {exc.msg}")
            continue

        if not isinstance(obj, dict):
            add_violation(line_no, "not_json_object", "Setiap baris JSONL wajib berupa objek JSON.")
            continue

        raw_id = obj.get("id")
        item_id_label = raw_id if isinstance(raw_id, str) else ""

        keys = set(obj.keys())
        if keys != REQUIRED_FIELDS:
            missing = sorted(REQUIRED_FIELDS - keys)
            extra = sorted(keys - REQUIRED_FIELDS)
            parts: list[str] = []
            if missing:
                parts.append(f"kurang field {missing}")
            if extra:
                parts.append(f"field berlebih {extra}")
            add_violation(
                line_no,
                "invalid_schema",
                f"Schema tidak persis {{id, kind, task_kind, instruction}}: {', '.join(parts)}.",
                item_id=item_id_label,
            )

        # Validasi field id: wajib string tak kosong, unik, dan berurutan bila --prefix aktif.
        if not isinstance(raw_id, str) or not raw_id.strip():
            add_violation(line_no, "invalid_id", "Field 'id' wajib berupa string tidak kosong.")
        else:
            if raw_id in seen_ids:
                add_violation(
                    line_no,
                    "duplicate_id",
                    f"ID duplikat '{raw_id}' (pertama muncul di baris {seen_ids[raw_id]}).",
                    item_id=raw_id,
                )
            else:
                seen_ids[raw_id] = line_no

            if active_prefixes:
                matched = _match_prefix(raw_id, active_prefixes)
                if matched is None:
                    add_violation(
                        line_no,
                        "invalid_id_prefix",
                        f"ID '{raw_id}' tidak cocok dengan prefix yang diizinkan {active_prefixes}.",
                        item_id=raw_id,
                    )
                else:
                    matched_prefix, suffix = matched
                    if not re.fullmatch(r"[0-9]+", suffix):
                        add_violation(
                            line_no,
                            "invalid_id_sequence",
                            f"Akhiran ID '{raw_id}' setelah prefix '{matched_prefix}' wajib berupa angka.",
                            item_id=raw_id,
                        )
                    else:
                        seq_num = int(suffix)
                        expected_seq = prefix_counters[matched_prefix] + 1
                        if seq_num != expected_seq:
                            add_violation(
                                line_no,
                                "non_sequential_id",
                                f"Nomor urut ID '{raw_id}' tidak berurutan: diharapkan {expected_seq}, aktual {seq_num}.",
                                item_id=raw_id,
                            )
                        prefix_counters[matched_prefix] = seq_num

        # Validasi kind == "episode".
        kind_val = obj.get("kind")
        if kind_val != "episode":
            add_violation(
                line_no,
                "invalid_kind",
                f"Field 'kind' wajib bernilai 'episode', aktual {kind_val!r}.",
                item_id=item_id_label,
            )

        # Validasi task_kind ∈ {"code", "language"}.
        task_kind = obj.get("task_kind")
        if task_kind not in ALLOWED_TASK_KINDS:
            add_violation(
                line_no,
                "invalid_task_kind",
                f"Field 'task_kind' wajib 'code' atau 'language', aktual {task_kind!r}.",
                item_id=item_id_label,
            )
        else:
            task_kind_counts[task_kind] += 1

        # Validasi instruction dan aturan khusus task_kind / frozen.
        instruction = obj.get("instruction")
        if not isinstance(instruction, str) or not instruction.strip():
            add_violation(
                line_no,
                "invalid_instruction",
                "Field 'instruction' wajib berupa string tidak kosong.",
                item_id=item_id_label,
            )
        else:
            if task_kind == "code" and REQUIRED_CODE_PHRASE not in instruction:
                add_violation(
                    line_no,
                    "missing_code_docstring_phrase",
                    f"Instruksi task_kind 'code' wajib memuat frasa '{REQUIRED_CODE_PHRASE}'.",
                    item_id=item_id_label,
                )

            if active_frozen:
                cand_prefix = instruction[:FROZEN_PREFIX_LEN]
                hit = active_frozen.get(cand_prefix)
                if hit is not None:
                    add_violation(
                        line_no,
                        "frozen_prefix_overlap",
                        (
                            f"Awalan {FROZEN_PREFIX_LEN} karakter instruksi tumpang tindih dengan "
                            f"corpus beku '{hit['frozen_file']}' (id={hit['frozen_id']!r}, baris={hit['frozen_line']})."
                        ),
                        item_id=item_id_label,
                    )

    return {
        "corpus": corpus_name,
        "valid": len(violations) == 0,
        "total_lines": len(lines),
        "violation_count": len(violations),
        "violations": violations,
        "summary": {
            "by_task_kind": task_kind_counts,
            "prefixes_checked": active_prefixes,
            "frozen_files_checked": sorted({info["frozen_file"] for info in active_frozen.values()}),
        },
    }


def lint_file(
    corpus_path: Path,
    *,
    prefixes: list[str] | None = None,
    frozen_paths: list[Path] | None = None,
) -> dict[str, Any]:
    """Baca berkas kandidat corpus dari disk dan validasi seluruh isinya."""
    if not corpus_path.is_file():
        raise InvalidInputError(f"Berkas corpus tidak ditemukan: {corpus_path}")
    try:
        raw_text = corpus_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise InvalidInputError(f"Gagal membaca berkas corpus '{corpus_path}': {exc}") from exc

    frozen_prefixes = load_frozen_prefixes(frozen_paths or [])
    report = lint_lines(
        raw_text.splitlines(),
        corpus_name=str(corpus_path),
        prefixes=prefixes,
        frozen_prefixes=frozen_prefixes,
    )
    if frozen_paths:
        report["summary"]["frozen_files_checked"] = [str(p) for p in frozen_paths]
    return report


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validator mekanis berkas kandidat corpus JSONL ACE."
    )
    parser.add_argument("corpus", type=Path, help="Path berkas kandidat corpus (.jsonl)")
    parser.add_argument(
        "--prefix",
        action="append",
        default=None,
        help="Pola prefix ID berurutan (mis. w4-code- atau daftar dipisah koma)",
    )
    parser.add_argument(
        "--frozen",
        action="append",
        default=None,
        help="Daftar berkas corpus beku dipisah koma untuk deteksi tumpang tindih 60 karakter awal",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Titik masuk CLI corpus linter."""
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
        prefixes = _parse_csv_args(args.prefix)
        frozen_paths = [Path(p) for p in _parse_csv_args(args.frozen)]
        report = lint_file(
            args.corpus,
            prefixes=prefixes or None,
            frozen_paths=frozen_paths or None,
        )
    except SystemExit as exc:
        # Konversi error argumen argparse menjadi kode 2 sesuai kontrak CLI.
        return 0 if exc.code == 0 else 2
    except InvalidInputError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
