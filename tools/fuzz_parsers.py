#!/usr/bin/env python3
"""Harness fuzz ringan berbasis stdlib untuk parser non-verdict di `tools/`.

Menjalankan generator masukan acak deterministik (`random.Random(seed)`)
terhadap seluruh parser `tools/` yang tersedia di workspace untuk memastikan
parser hanya mengembalikan hasil terstruktur atau melempar exception kontrak
yang diharapkan (tanpa crash tak tertangani seperti `KeyError`/`TypeError`).
"""
from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path
import random
import sys
import tempfile
from typing import Any, Callable

FUZZ_SCHEMA = "ace.tools-fuzz.v1"
DEFAULT_SEED = 20261117
DEFAULT_ITERATIONS = 150
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _random_text(rng: random.Random, max_len: int = 120) -> str:
    alphabet = (
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        " \t\n:.,;=[]{}\"'\\/-_+*@#?!"
    )
    length = rng.randint(0, max_len)
    return "".join(rng.choice(alphabet) for _ in range(length))


def _random_json_value(rng: random.Random, depth: int = 0) -> Any:
    if depth >= 3:
        return rng.choice([None, True, False, 0, -1, 42, 3.14, "", "ok", _random_text(rng, 24)])
    kind = rng.randint(0, 5)
    if kind == 0:
        return None
    if kind == 1:
        return rng.choice([True, False, rng.randint(-1000, 1000), rng.uniform(-100, 100)])
    if kind == 2:
        return _random_text(rng, 40)
    if kind == 3:
        return [_random_json_value(rng, depth + 1) for _ in range(rng.randint(0, 4))]
    keys = rng.sample(
        [
            "id",
            "kind",
            "task_kind",
            "instruction",
            "episode_id",
            "status",
            "error",
            "ratified",
            "score",
            "label",
            "path",
            "sha256",
            "size",
            "schema",
            "corpora",
            "files",
            "hypothesis_id",
            "ai_answered",
        ],
        k=rng.randint(0, 5),
    )
    return {k: _random_json_value(rng, depth + 1) for k in keys}


def _random_jsonl_payload(rng: random.Random) -> str:
    mode = rng.randint(0, 4)
    if mode == 0:
        return ""
    if mode == 1:
        return _random_text(rng, 200)
    if mode == 2:
        # JSON valid atau rusak sebagian per baris
        lines = []
        for _ in range(rng.randint(1, 6)):
            val = _random_json_value(rng)
            raw = json.dumps(val, ensure_ascii=False)
            if rng.random() < 0.35 and len(raw) > 2:
                cut = rng.randint(1, len(raw) - 1)
                raw = raw[:cut]
            lines.append(raw)
        return "\n".join(lines) + ("\n" if rng.random() < 0.5 else "")
    if mode == 3:
        # Objek tunggal dengan variasi field wajib
        return json.dumps(_random_json_value(rng), ensure_ascii=False)
    return "\n" * rng.randint(1, 4)


def _fuzz_ace_mobile_logs(rng: random.Random, iterations: int, _tmp: Path) -> list[dict[str, Any]]:
    from tools import ace_mobile_dashboard as amd

    crashes: list[dict[str, Any]] = []
    prefixes = [
        "[2026-11-17] [Daemon] ",
        "Problem: ",
        "Hypothesis: ",
        "Decision: ACCEPTED ",
        "Decision:   ACCEPTED ",
        "(Param): ",
        "Host Status: ",
        "Janitor: ",
        "Push successful for Cycle ",
    ]
    for i in range(iterations):
        lines = [
            (rng.choice(prefixes) if rng.random() < 0.6 else "") + _random_text(rng, 160)
            for _ in range(rng.randint(0, 15))
        ]
        try:
            stories = amd.parse_logs_to_stories(lines)
            if not isinstance(stories, list) or len(stories) > 10:
                raise AssertionError(f"Output stories tidak valid: {type(stories).__name__}")
        except Exception as exc:
            crashes.append({"iteration": i, "exc_type": type(exc).__name__, "message": str(exc)})
    return crashes


def _fuzz_ace_ai_diagnostic(rng: random.Random, iterations: int, tmp: Path) -> list[dict[str, Any]]:
    from tools import ace_ai_diagnostic as aid

    crashes: list[dict[str, Any]] = []
    allowed = (ValueError, json.JSONDecodeError, OSError)
    target = tmp / "ai_consultations.json"
    for i in range(iterations):
        mode = rng.randint(0, 2)
        if mode == 0:
            raw = _random_text(rng, 120)
        elif mode == 1:
            raw = json.dumps(_random_json_value(rng), ensure_ascii=False)
        else:
            records = []
            for _ in range(rng.randint(0, 4)):
                rec = _random_json_value(rng)
                if isinstance(rec, dict) and rng.random() < 0.5:
                    rec["ai_answered"] = rng.choice(
                        [
                            None,
                            123,
                            "def ace_v04_f(length, density, stride_val):\n    return 1\n",
                            "import os\n",
                            _random_text(rng, 80),
                        ]
                    )
                records.append(rec)
            raw = json.dumps(records, ensure_ascii=False)
        target.write_text(raw, encoding="utf-8")
        try:
            aid.audit_consultations(target, limit=rng.randint(1, 5))
        except allowed:
            pass
        except Exception as exc:
            crashes.append({"iteration": i, "exc_type": type(exc).__name__, "message": str(exc)})
    return crashes


def _fuzz_dashboard_rp_to_int(rng: random.Random, iterations: int, _tmp: Path) -> list[dict[str, Any]]:
    from tools import dashboard_state_build as dsb

    crashes: list[dict[str, Any]] = []
    for i in range(iterations):
        s = _random_text(rng, 32)
        try:
            out = dsb.rp_to_int(s)
            if not isinstance(out, int):
                raise AssertionError(f"Expected int, got {type(out).__name__}")
        except ValueError:
            pass
        except Exception as exc:
            crashes.append({"iteration": i, "exc_type": type(exc).__name__, "message": str(exc)})
    return crashes


def _make_optional_corpus_lint_fuzzer():
    try:
        mod = importlib.import_module("tools.corpus_lint")
    except ImportError:
        return None

    def _run(rng: random.Random, iterations: int, tmp: Path) -> list[dict[str, Any]]:
        crashes: list[dict[str, Any]] = []
        target = tmp / "fuzz_corpus.jsonl"
        for i in range(iterations):
            target.write_text(_random_jsonl_payload(rng), encoding="utf-8")
            try:
                mod.lint_file(target)
            except (mod.InvalidInputError, OSError):
                pass
            except Exception as exc:
                crashes.append({"iteration": i, "exc_type": type(exc).__name__, "message": str(exc)})
        return crashes

    return _run


def _make_optional_screen_census_fuzzer():
    try:
        mod = importlib.import_module("tools.screen_census")
    except ImportError:
        return None

    def _run(rng: random.Random, iterations: int, tmp: Path) -> list[dict[str, Any]]:
        crashes: list[dict[str, Any]] = []
        target = tmp / "fuzz_screen.jsonl"
        for i in range(iterations):
            if i % 10 == 0:
                adv = "\n".join(
                    [
                        json.dumps({"id": _random_json_value(rng), "score": 10**400}),
                        '{"id": "x", "score": ' + ("9" * 5000) + "}",
                        json.dumps({"id": "x", "ratified": rng.choice([True, False]), "error": _random_json_value(rng)}),
                    ]
                )
                target.write_text(adv, encoding="utf-8")
            else:
                target.write_text(_random_jsonl_payload(rng), encoding="utf-8")
            try:
                mod.compute_census([target])
            except (mod.CensusInputError, OSError):
                pass
            except Exception as exc:
                crashes.append({"iteration": i, "exc_type": type(exc).__name__, "message": str(exc)})
        return crashes

    return _run


def _make_optional_corpus_registry_fuzzer():
    try:
        mod = importlib.import_module("tools.corpus_registry")
    except ImportError:
        return None

    def _run(rng: random.Random, iterations: int, tmp: Path) -> list[dict[str, Any]]:
        crashes: list[dict[str, Any]] = []
        handover = tmp / "handover_fuzz"
        handover.mkdir(exist_ok=True)
        corpus_file = handover / "FUZZ_CORPUS_V1.jsonl"
        idx_file = tmp / "registry_fuzz.json"
        for i in range(iterations):
            if i % 10 == 0:
                corpus_file.write_text('{"id":"1","val":' + ("9" * 5000) + "}\n", encoding="utf-8")
            else:
                corpus_file.write_text(_random_jsonl_payload(rng), encoding="utf-8")
            try:
                reg = mod.scan_corpora(handover)
                idx_file.write_text(json.dumps(reg, ensure_ascii=False), encoding="utf-8")
                mod.check_drift(handover, idx_file)
            except (mod.RegistryError, OSError):
                pass
            except Exception as exc:
                crashes.append({"iteration": i, "exc_type": type(exc).__name__, "message": str(exc)})

            # Juga uji file indeks korup / sembarang JSON
            idx_file.write_text(
                '{"schema":"ace.frozen-corpus-registry.v1","corpora":[{"name":"FUZZ_CORPUS_V1.jsonl","line_count":'
                + ("9" * 5000)
                + "}]}"
                if i % 10 == 0
                else _random_jsonl_payload(rng),
                encoding="utf-8",
            )
            corpus_file.write_text('{"id":"1","kind":"episode","task_kind":"code","instruction":"x"}\n', encoding="utf-8")
            try:
                mod.check_drift(handover, idx_file)
            except (mod.RegistryError, OSError):
                pass
            except Exception as exc:
                crashes.append({"iteration": i, "exc_type": type(exc).__name__, "message": str(exc)})
        return crashes

    return _run


def _make_optional_stage_verify_fuzzer():
    try:
        mod = importlib.import_module("tools.stage_verify")
    except ImportError:
        return None

    def _run(rng: random.Random, iterations: int, tmp: Path) -> list[dict[str, Any]]:
        crashes: list[dict[str, Any]] = []
        stage = tmp / "stage_fuzz"
        stage.mkdir(exist_ok=True)
        (stage / "a.txt").write_text("ok", encoding="utf-8")
        manifest = tmp / "stage_manifest.json"
        for i in range(iterations):
            if i % 10 == 0:
                raw = json.dumps(
                    {
                        "files": [
                            {
                                "path": rng.choice(["a\x00b.txt", "../escape", "a.txt", _random_json_value(rng)]),
                                "sha256": rng.choice(["0" * 64, _random_json_value(rng)]),
                                "size": rng.choice([2, -1, True, 10**400, _random_json_value(rng)]),
                            }
                        ]
                    }
                )
            else:
                raw = _random_text(rng, 100) if rng.random() < 0.3 else json.dumps(_random_json_value(rng))
            manifest.write_text(raw, encoding="utf-8")
            try:
                mod.verify_stage(stage, manifest)
            except (mod.StageVerifyError, OSError):
                pass
            except Exception as exc:
                crashes.append({"iteration": i, "exc_type": type(exc).__name__, "message": str(exc)})
        return crashes

    return _run


def _make_optional_bench_table_fuzzer():
    try:
        mod = importlib.import_module("tools.bench_table")
    except ImportError:
        return None

    def _run(rng: random.Random, iterations: int, tmp: Path) -> list[dict[str, Any]]:
        crashes: list[dict[str, Any]] = []
        target = tmp / "bench_fuzz.jsonl"
        for i in range(iterations):
            if i % 10 == 0:
                raw = "\n".join(
                    [
                        json.dumps({"label": "a", "m": rng.choice([1e308, 10**400, _random_json_value(rng)])}),
                        json.dumps({"label": "a", "m": 1e308}),
                    ]
                )
                target.write_text(raw, encoding="utf-8")
            else:
                target.write_text(_random_jsonl_payload(rng), encoding="utf-8")
            try:
                summary = mod.summarize_bench(target)
                mod.render_markdown_table(summary)
            except (mod.BenchTableError, OSError):
                pass
            except Exception as exc:
                crashes.append({"iteration": i, "exc_type": type(exc).__name__, "message": str(exc)})
        return crashes

    return _run


def _make_optional_pack_evidence_fuzzer():
    try:
        mod = importlib.import_module("tools.pack_evidence")
    except ImportError:
        return None

    def _run(rng: random.Random, iterations: int, tmp: Path) -> list[dict[str, Any]]:
        crashes: list[dict[str, Any]] = []
        bundle = tmp / "pack_fuzz"
        bundle.mkdir(exist_ok=True)
        (bundle / "sample.txt").write_text("evidence", encoding="utf-8")
        manifest = tmp / "pack_manifest.json"
        for i in range(iterations):
            if rng.random() < 0.25:
                try:
                    mod.pack_evidence(bundle, manifest_path=manifest)
                except (mod.EvidencePackError, OSError):
                    pass
                except Exception as exc:
                    crashes.append({"iteration": i, "exc_type": type(exc).__name__, "message": str(exc)})
            if i % 10 == 0:
                raw = json.dumps(
                    {
                        "schema": "ace.evidence-bundle.v1",
                        "files": [
                            {
                                "path": rng.choice(["bad\x00file.txt", "../x", "sample.txt", _random_json_value(rng)]),
                                "size_bytes": rng.choice([8, True, 10**400, _random_json_value(rng)]),
                                "sha256": rng.choice(["0" * 64, _random_json_value(rng)]),
                            }
                        ],
                    }
                )
            else:
                raw = _random_text(rng, 100) if rng.random() < 0.3 else json.dumps(_random_json_value(rng))
            manifest.write_text(raw, encoding="utf-8")
            try:
                mod.verify_evidence(bundle, manifest_path=manifest)
            except (mod.EvidencePackError, OSError):
                pass
            except Exception as exc:
                crashes.append({"iteration": i, "exc_type": type(exc).__name__, "message": str(exc)})
        return crashes

    return _run


def collect_targets() -> dict[str, Callable[[random.Random, int, Path], list[dict[str, Any]]]]:
    """Kumpulkan seluruh target parser `tools/` yang tersedia di lingkungan."""
    targets: dict[str, Callable[[random.Random, int, Path], list[dict[str, Any]]]] = {
        "ace_mobile_dashboard.parse_logs_to_stories": _fuzz_ace_mobile_logs,
        "ace_ai_diagnostic.audit_consultations": _fuzz_ace_ai_diagnostic,
        "dashboard_state_build.rp_to_int": _fuzz_dashboard_rp_to_int,
    }
    optionals = {
        "corpus_lint.lint_file": _make_optional_corpus_lint_fuzzer(),
        "screen_census.compute_census": _make_optional_screen_census_fuzzer(),
        "corpus_registry": _make_optional_corpus_registry_fuzzer(),
        "stage_verify.verify_stage": _make_optional_stage_verify_fuzzer(),
        "bench_table.summarize_bench": _make_optional_bench_table_fuzzer(),
        "pack_evidence.verify_evidence": _make_optional_pack_evidence_fuzzer(),
    }
    for name, fn in optionals.items():
        if fn is not None:
            targets[name] = fn
    return dict(sorted(targets.items()))


def run_fuzz(
    *,
    seed: int = DEFAULT_SEED,
    iterations: int = DEFAULT_ITERATIONS,
    only_targets: list[str] | None = None,
) -> dict[str, Any]:
    """Jalankan fuzz ber-seed terhadap target parser dan laporkan ringkasan."""
    if iterations < 1:
        raise ValueError("iterations harus >= 1")
    targets = collect_targets()
    if only_targets is not None:
        missing = sorted(t for t in only_targets if t not in targets)
        if missing:
            raise ValueError(f"Target fuzz tidak ditemukan: {missing}")
        targets = {k: targets[k] for k in only_targets}

    rng = random.Random(seed)
    results: dict[str, Any] = {}
    total_crashes = 0
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        for name, fn in targets.items():
            crashes = fn(rng, iterations, tmp_path)
            total_crashes += len(crashes)
            results[name] = {
                "iterations": iterations,
                "crash_count": len(crashes),
                "crashes": crashes[:5],
            }

    return {
        "schema": FUZZ_SCHEMA,
        "seed": seed,
        "iterations_per_target": iterations,
        "target_count": len(results),
        "total_crashes": total_crashes,
        "passed": total_crashes == 0,
        "targets": results,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fuzz harness ringan ber-seed untuk parser non-verdict di tools/."
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="Seed PRNG deterministik.")
    parser.add_argument("--iterations", type=int, default=DEFAULT_ITERATIONS, help="Iterasi per target.")
    parser.add_argument(
        "--target",
        action="append",
        dest="targets",
        default=None,
        help="Filter target spesifik (dapat diulang).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
        report = run_fuzz(seed=args.seed, iterations=args.iterations, only_targets=args.targets)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["passed"] else 1
    except SystemExit as exc:
        return 0 if exc.code == 0 else 2
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
