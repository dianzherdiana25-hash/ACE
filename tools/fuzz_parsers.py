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
FUZZ_MATRIX_SCHEMA = "ace.tools-fuzz-matrix.v1"
DEFAULT_SEED = 20261117
DEFAULT_ITERATIONS = 150
STANDARD_SEEDS = (20261117, 20261118, 20261119)
STANDARD_ITERATIONS = 300
REPO_ROOT = Path(__file__).resolve().parents[1]
CODE_ROOT = REPO_ROOT / "code"
for _p in (str(CODE_ROOT), str(REPO_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


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


def _fuzz_visual_bridge_process(rng: random.Random, iterations: int, _tmp: Path) -> list[dict[str, Any]]:
    from ace_visual_bridge import cli as vb_cli

    crashes: list[dict[str, Any]] = []
    allowed = (TypeError, ValueError, KeyError)
    for i in range(iterations):
        mode = rng.choice(["plan", "review"])
        payload = _random_json_value(rng)
        if isinstance(payload, dict) and rng.random() < 0.5:
            payload["schema"] = "ace.ava.request.v1"
            if rng.random() < 0.5:
                payload["anchor"] = _random_json_value(rng)
            if rng.random() < 0.5:
                payload["observations"] = _random_json_value(rng)
        try:
            vb_cli.process(mode, payload)  # type: ignore[arg-type]
        except allowed:
            pass
        except Exception as exc:
            crashes.append({"iteration": i, "exc_type": type(exc).__name__, "message": str(exc)})
    return crashes


def _fuzz_host_exchange_contracts(rng: random.Random, iterations: int, _tmp: Path) -> list[dict[str, Any]]:
    from ace_host_exchange import contracts

    crashes: list[dict[str, Any]] = []
    for i in range(iterations):
        req = _random_json_value(rng)
        cand = _random_json_value(rng)
        try:
            res_req = contracts.verify_request(req)
            res_cand = contracts.verify_candidate(req, cand)
            if not isinstance(res_req, bool) or not isinstance(res_cand, bool):
                raise AssertionError("verify_request/verify_candidate must return bool")
        except Exception as exc:
            crashes.append({"iteration": i, "exc_type": type(exc).__name__, "message": str(exc)})
    return crashes


def _fuzz_autonomy_budget_ceiling(rng: random.Random, iterations: int, _tmp: Path) -> list[dict[str, Any]]:
    from ace_autonomy.errors import PolicyError
    from ace_autonomy.policy import BudgetCeiling

    crashes: list[dict[str, Any]] = []
    for i in range(iterations):
        raw = _random_json_value(rng)
        if isinstance(raw, dict) and rng.random() < 0.4:
            raw = {
                rng.choice(["max_steps", "max_candidates", "max_retries_per_step", "wall_seconds", "cpu_seconds"]): rng.choice(
                    [True, False, None, -1, 0, 1, 999, float("nan"), "10", _random_json_value(rng)]
                )
            }
        try:
            BudgetCeiling.from_dict(raw)  # type: ignore[arg-type]
        except PolicyError:
            pass
        except Exception as exc:
            crashes.append({"iteration": i, "exc_type": type(exc).__name__, "message": str(exc)})
    return crashes


def _fuzz_codebase_reader_history(rng: random.Random, iterations: int, tmp: Path) -> list[dict[str, Any]]:
    from ace_code_agent.codebase_reader import CodebaseReader

    crashes: list[dict[str, Any]] = []
    reader = CodebaseReader(tmp)
    state_file = tmp / "fuzz_research_state.json"
    for i in range(iterations):
        state_file.write_text(_random_jsonl_payload(rng), encoding="utf-8")
        try:
            out = reader.read_failure_history("fuzz_research_state.json")
            if not isinstance(out, dict):
                raise AssertionError(f"Expected dict, got {type(out).__name__}")
        except Exception as exc:
            crashes.append({"iteration": i, "exc_type": type(exc).__name__, "message": str(exc)})
    return crashes


def _make_optional_pattern_distill_fuzzer():
    try:
        mod = importlib.import_module("tools.pattern_distill")
    except ImportError:
        return None

    def _run(rng: random.Random, iterations: int, tmp: Path) -> list[dict[str, Any]]:
        crashes: list[dict[str, Any]] = []
        ev = tmp / "fuzz_ev.jsonl"
        st = tmp / "fuzz_staging.jsonl"
        for i in range(iterations):
            ev.write_text(_random_jsonl_payload(rng), encoding="utf-8")
            try:
                mod.distill_patterns([ev], out_path=st)
            except (mod.PatternDistillError, OSError):
                pass
            except Exception as exc:
                crashes.append({"iteration": i, "exc_type": type(exc).__name__, "message": str(exc)})
        return crashes

    return _run


def _make_optional_four_arm_fuzzer():
    try:
        mod = importlib.import_module("tools.four_arm_report")
    except ImportError:
        return None

    def _run(rng: random.Random, iterations: int, tmp: Path) -> list[dict[str, Any]]:
        crashes: list[dict[str, Any]] = []
        arm = tmp / "fuzz_arm.jsonl"
        for i in range(iterations):
            arm.write_text(_random_jsonl_payload(rng), encoding="utf-8")
            try:
                mod.build_report([arm], strict=False)
            except (mod.FourArmReportError, OSError):
                pass
            except Exception as exc:
                crashes.append({"iteration": i, "exc_type": type(exc).__name__, "message": str(exc)})
        return crashes

    return _run


def _make_optional_corpus_tag_fuzzer():
    try:
        mod = importlib.import_module("tools.corpus_tag")
    except ImportError:
        return None

    def _run(rng: random.Random, iterations: int, tmp: Path) -> list[dict[str, Any]]:
        crashes: list[dict[str, Any]] = []
        cand = tmp / "fuzz_tag_cand.jsonl"
        hist = tmp / "fuzz_tag_hist.jsonl"
        for i in range(iterations):
            cand.write_text(_random_jsonl_payload(rng), encoding="utf-8")
            hist.write_text(_random_jsonl_payload(rng), encoding="utf-8")
            try:
                mod.tag_corpus(corpus_path=cand, history_paths=[hist])
            except (mod.CorpusTagError, OSError):
                pass
            except Exception as exc:
                crashes.append({"iteration": i, "exc_type": type(exc).__name__, "message": str(exc)})
        return crashes

    return _run


def _make_optional_cover_check_fuzzer():
    try:
        mod = importlib.import_module("tools.cover_check")
    except ImportError:
        return None

    def _run(rng: random.Random, iterations: int, tmp: Path) -> list[dict[str, Any]]:
        crashes: list[dict[str, Any]] = []
        img = tmp / "fuzz_cover.bin"
        for i in range(iterations):
            mode = rng.randint(0, 2)
            if mode == 0:
                raw = mod.PNG_SIGNATURE + bytes(rng.randint(0, 255) for _ in range(rng.randint(0, 32)))
            elif mode == 1:
                raw = mod.JPEG_SOI + bytes(rng.randint(0, 255) for _ in range(rng.randint(0, 48)))
            else:
                raw = bytes(rng.randint(0, 255) for _ in range(rng.randint(0, 48)))
            img.write_bytes(raw)
            try:
                mod.check_cover(img)
            except (mod.CoverCheckInputError, mod.CoverDecodeError, OSError):
                pass
            except Exception as exc:
                crashes.append({"iteration": i, "exc_type": type(exc).__name__, "message": str(exc)})
        return crashes

    return _run


def _make_optional_royalty_track_fuzzer():
    try:
        mod = importlib.import_module("tools.royalty_track")
    except ImportError:
        return None

    def _run(rng: random.Random, iterations: int, tmp: Path) -> list[dict[str, Any]]:
        crashes: list[dict[str, Any]] = []
        csv_p = tmp / "fuzz_royalty.csv"
        for i in range(iterations):
            csv_p.write_text(_random_text(rng, 200), encoding="utf-8")
            try:
                mod.summarize_royalties([csv_p])
            except (mod.RoyaltyTrackError, OSError):
                pass
            except Exception as exc:
                crashes.append({"iteration": i, "exc_type": type(exc).__name__, "message": str(exc)})
        return crashes

    return _run


def _make_optional_kbm_schedule_fuzzer():
    try:
        mod = importlib.import_module("tools.kbm_schedule")
    except ImportError:
        return None

    def _run(rng: random.Random, iterations: int, tmp: Path) -> list[dict[str, Any]]:
        crashes: list[dict[str, Any]] = []
        cat = tmp / "fuzz_catalog.json"
        for i in range(iterations):
            cat.write_text(
                json.dumps(_random_json_value(rng)) if rng.random() < 0.7 else _random_text(rng, 100),
                encoding="utf-8",
            )
            try:
                mod.build_schedule(cat)
            except (mod.KbmScheduleError, OSError):
                pass
            except Exception as exc:
                crashes.append({"iteration": i, "exc_type": type(exc).__name__, "message": str(exc)})
        return crashes

    return _run


def _make_optional_kbm_split_fuzzer():
    try:
        mod = importlib.import_module("tools.kbm_split")
    except ImportError:
        return None

    def _run(rng: random.Random, iterations: int, tmp: Path) -> list[dict[str, Any]]:
        crashes: list[dict[str, Any]] = []
        ms = tmp / "fuzz_manuscript.md"
        out_dir = tmp / "fuzz_split_out"
        for i in range(iterations):
            ms.write_text(_random_text(rng, 200), encoding="utf-8")
            try:
                mod.split_manuscript(ms, out_dir, min_words=5)
            except (mod.KbmSplitError, OSError):
                pass
            except Exception as exc:
                crashes.append({"iteration": i, "exc_type": type(exc).__name__, "message": str(exc)})
        return crashes

    return _run


def collect_targets() -> dict[str, Callable[[random.Random, int, Path], list[dict[str, Any]]]]:
    """Kumpulkan seluruh target parser `tools/` dan parser `code/` non-verdict."""
    targets: dict[str, Callable[[random.Random, int, Path], list[dict[str, Any]]]] = {
        "ace_mobile_dashboard.parse_logs_to_stories": _fuzz_ace_mobile_logs,
        "ace_ai_diagnostic.audit_consultations": _fuzz_ace_ai_diagnostic,
        "dashboard_state_build.rp_to_int": _fuzz_dashboard_rp_to_int,
        "code.ace_visual_bridge.cli.process": _fuzz_visual_bridge_process,
        "code.ace_host_exchange.contracts.verify": _fuzz_host_exchange_contracts,
        "code.ace_autonomy.policy.BudgetCeiling": _fuzz_autonomy_budget_ceiling,
        "code.ace_code_agent.read_failure_history": _fuzz_codebase_reader_history,
    }
    optionals = {
        "corpus_lint.lint_file": _make_optional_corpus_lint_fuzzer(),
        "screen_census.compute_census": _make_optional_screen_census_fuzzer(),
        "corpus_registry": _make_optional_corpus_registry_fuzzer(),
        "stage_verify.verify_stage": _make_optional_stage_verify_fuzzer(),
        "bench_table.summarize_bench": _make_optional_bench_table_fuzzer(),
        "pack_evidence.verify_evidence": _make_optional_pack_evidence_fuzzer(),
        "pattern_distill.distill_patterns": _make_optional_pattern_distill_fuzzer(),
        "four_arm_report.build_report": _make_optional_four_arm_fuzzer(),
        "corpus_tag.tag_corpus": _make_optional_corpus_tag_fuzzer(),
        "cover_check.check_cover": _make_optional_cover_check_fuzzer(),
        "royalty_track.summarize_royalties": _make_optional_royalty_track_fuzzer(),
        "kbm_schedule.build_schedule": _make_optional_kbm_schedule_fuzzer(),
        "kbm_split.split_manuscript": _make_optional_kbm_split_fuzzer(),
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


def run_fuzz_matrix(
    *,
    seeds: tuple[int, ...] | list[int] = STANDARD_SEEDS,
    iterations: int = STANDARD_ITERATIONS,
    only_targets: list[str] | None = None,
) -> dict[str, Any]:
    """Jalankan matrix fuzz multi-seed (default standar: 3 seed x 300 iterasi)."""
    seed_list = [int(s) for s in seeds]
    if not seed_list:
        raise ValueError("Minimal satu seed harus diberikan.")
    runs = [
        run_fuzz(seed=s, iterations=iterations, only_targets=only_targets)
        for s in seed_list
    ]
    total_crashes = sum(r["total_crashes"] for r in runs)
    return {
        "schema": FUZZ_MATRIX_SCHEMA,
        "seeds": seed_list,
        "iterations_per_target": iterations,
        "target_count": runs[0]["target_count"],
        "total_runs": len(runs),
        "total_crashes": total_crashes,
        "passed": total_crashes == 0,
        "runs": runs,
    }


def _parse_seeds_arg(raw: str) -> list[int]:
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if not parts:
        raise ValueError("--seeds tidak boleh kosong.")
    try:
        return [int(p) for p in parts]
    except ValueError as exc:
        raise ValueError(f"--seeds memuat nilai non-integer: {raw!r}") from exc


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fuzz harness ringan ber-seed untuk parser non-verdict di tools/ dan code/."
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="Seed PRNG deterministik tunggal.")
    parser.add_argument(
        "--seeds",
        default=None,
        help="Daftar seed dipisah koma untuk matrix multi-seed (mis. 20261117,20261118,20261119).",
    )
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
        if args.seeds is not None:
            seed_list = _parse_seeds_arg(args.seeds)
            report = run_fuzz_matrix(
                seeds=seed_list,
                iterations=args.iterations,
                only_targets=args.targets,
            )
        else:
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
