"""Build and check a local batch of future candidate episodes."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from tools.corpus_factory_code import generate_code_episodes
from tools.corpus_factory_lang import generate_lang_episodes, verify_constraint_spec
from tools.corpus_lint import FROZEN_PREFIX_LEN, lint_lines

PREFIXES = ["candidate_code_", "candidate_lang_"]
SCHEMA = "ace.candidate-corpus-quality.v1"


def _encode(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def validate_corpus(payload: bytes) -> dict:
    lines = payload.decode("utf-8").splitlines()
    rows = [json.loads(line, object_pairs_hook=_unique_keys) for line in lines]
    for row in rows:
        # Validate the shape before handing off to the existing house linter.
        if not isinstance(row, dict) or any(type(value) is not str for value in row.values()):
            raise ValueError("episode fields must be strings")
        if not re.fullmatch(r"candidate_(?:code|lang)_[0-9]{3,6}", row.get("id", "")):
            raise ValueError("invalid candidate episode ID")
        expected = "code" if row["id"].startswith(PREFIXES[0]) else "language"
        if row.get("task_kind") != expected:
            raise ValueError("candidate ID and task kind disagree")
    lint = lint_lines(lines, prefixes=PREFIXES)
    if not lint["valid"]:
        raise ValueError("house corpus lint failed: " + ", ".join(
            sorted({entry["code"] for entry in lint["violations"]})))
    normalized = [" ".join(row["instruction"].casefold().split()) for row in rows]
    prefixes = {entry[:FROZEN_PREFIX_LEN] for entry in normalized}
    if len(set(normalized)) != len(rows) or len(prefixes) != len(rows):
        raise ValueError("duplicate instruction or normalized instruction prefix")
    return {
        "schema": SCHEMA,
        "episodes": len(rows),
        "task_kinds": lint["summary"]["by_task_kind"],
        "distinct_normalized_prefixes": len(prefixes),
        "corpus_sha256": hashlib.sha256(payload).hexdigest(),
        "house_lint_passed": True,
    }


def build_batch(*, code_count=128, language_count=96, seed=711):
    code = generate_code_episodes(count=code_count, seed=seed, prefix=PREFIXES[0])
    language = generate_lang_episodes(count=language_count, seed=seed, prefix=PREFIXES[1])
    lines = code["lines"] + language["lines"]
    corpus = ("\n".join(lines) + "\n").encode()
    report = validate_corpus(corpus)
    specs = language["specs"]
    samples = {row["episode_id"]: row["answer_text"] for row in language["samples"]}
    language_ids = {json.loads(line)["id"] for line in language["lines"]}
    spec_ids = [spec["episode_id"] for spec in specs]
    if set(spec_ids) != language_ids or set(samples) != language_ids or len(spec_ids) != len(language_ids):
        raise ValueError("language evidence does not cover each episode exactly once")
    for spec in specs:
        if not verify_constraint_spec(samples[spec["episode_id"]], spec)["passed"]:
            raise ValueError("language sample failed constraint verification")
    sidecar = _encode({"specs": specs, "samples": samples})
    report.update(
        seed=seed,
        code_template_families=code["family_counts"],
        language_domains=dict(sorted(Counter(spec["domain"] for spec in specs).items())),
        language_samples_verified=len(samples),
        language_evidence_sha256=hashlib.sha256(sidecar).hexdigest(),
        code_solutions_checked=0,
        frozen_overlap_checked=False,
        sampling_status="candidate_only",
    )
    return {"episodes.jsonl": corpus, "language-evidence.json": sidecar, "quality.json": _encode(report)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    generate = commands.add_parser("generate")
    generate.add_argument("output", type=Path)
    generate.add_argument("--code-count", type=int, default=128)
    generate.add_argument("--language-count", type=int, default=96)
    generate.add_argument("--seed", type=int, default=711)
    validate = commands.add_parser("validate")
    validate.add_argument("corpus", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            print(_encode(validate_corpus(args.corpus.read_bytes())).decode(), end="")
            return 0
        outputs = build_batch(code_count=args.code_count, language_count=args.language_count, seed=args.seed)
        args.output.mkdir(mode=0o700)
        # Write the quality receipt last. A partial output has no receipt.
        for name, payload in outputs.items():
            with (args.output / name).open("xb") as stream:
                stream.write(payload)
    except (ValueError, OSError) as exc:
        parser.exit(1, f"candidate corpus: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
