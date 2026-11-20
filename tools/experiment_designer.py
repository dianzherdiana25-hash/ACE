"""Perancang spesifikasi eksperimen pemalsuan terkecil dari hipotesis JSON (AG95).

Memilih desain eksperimen terkecil yang cukup untuk menggugurkan hipotesis antara
tiga tipe (``replay_audit``, ``fixture_arena``, dan ``ab_test`` berisiko rendah)
beserta taksiran biaya siklus (``estimated_cycles``), ukuran sampel minimum,
kriteria gugur eksplisit, dan penjaga keamanan.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


SCHEMA = "ace.experiment-design.v1"
BATCH_SCHEMA = "ace.experiment-design-batch.v1"
VALID_EXPERIMENT_TYPES = ("replay_audit", "fixture_arena", "ab_test")
_ISOLATION_DOMAINS = frozenset({"bridge", "executor", "failover", "security", "parser", "concurrency", "code"})
_REPLAY_DOMAINS = frozenset({"recall", "memory", "telemetry", "audit", "regression", "history"})


def _choose_experiment_type(hyp: Mapping[str, Any]) -> tuple[str, str]:
    risk = str(hyp.get("risk_level", "low")).lower()
    domain = str(hyp.get("domain", "umum")).lower()
    compares_variants = bool(hyp.get("compares_variants", False))
    historical_available = bool(hyp.get("historical_trace_available", False))
    requires_execution = bool(hyp.get("requires_synthetic_execution", False))
    evidence_source = str(hyp.get("evidence_source", "")).lower()

    # Risiko sedang/tinggi atau domain eksekusi wajib diisolasi di fixture_arena.
    if risk in {"medium", "high"} or requires_execution or domain in _ISOLATION_DOMAINS:
        return (
            "fixture_arena",
            "Memerlukan eksekusi terkendali terisolasi atas fixture tanpa menyentuh jalur live.",
        )

    # Klaim yang cukup diuji dari jejak historis atau log read-only memilih replay_audit termurah.
    if (
        (historical_available and not compares_variants)
        or evidence_source in {"logs", "receipts", "memory_chain", "heldout_trace"}
        or (domain in _REPLAY_DOMAINS and not compares_variants)
    ):
        return (
            "replay_audit",
            "Dapat diuji dan digugurkan secara read-only atas jejak historis yang sudah ada.",
        )

    # Pembandingan dua varian berisiko rendah menggunakan A/B berbatas sampel minimum.
    if compares_variants or risk == "low":
        return (
            "ab_test",
            "Membandingkan dua varian kebijakan berisiko rendah pada lengan kontrol vs kandidat.",
        )

    return (
        "fixture_arena",
        "Fallback isolasi deterministik ke fixture_arena.",
    )


def _estimate_cycle_cost(
    exp_type: str,
    hyp: Mapping[str, Any],
) -> tuple[int, int, str]:
    """Hitung (minimum_sample_size, estimated_cycles, cost_tier)."""
    confidence = float(hyp.get("confidence", 0.5))
    raw_min = hyp.get("minimum_trials")
    if isinstance(raw_min, int) and raw_min > 0:
        sample_size = raw_min
    elif exp_type == "replay_audit":
        sample_size = 20 if confidence >= 0.7 else 30
    elif exp_type == "fixture_arena":
        sample_size = 6 if confidence >= 0.6 else 10
    else:  # ab_test
        sample_size = 16 if confidence >= 0.6 else 24

    if exp_type == "replay_audit":
        # Satu siklus pemindaian replay read-only per ~20 catatan.
        cycles = max(1, math.ceil(sample_size / 20))
        cost_tier = "ultra_low"
    elif exp_type == "fixture_arena":
        # 1 siklus persiapan fixture + 1 siklus eksekusi per 5 skenario sintetis.
        cycles = 1 + math.ceil(sample_size / 5)
        cost_tier = "low"
    else:  # ab_test
        # Sepasang lengan A & B: 4 sampel gabungan per siklus.
        cycles = max(2, math.ceil(sample_size / 4))
        cost_tier = "moderate_bounded"
    return sample_size, cycles, cost_tier


def design_smallest_falsifying_experiment(hyp: Mapping[str, Any]) -> dict[str, Any]:
    """Susun spesifikasi eksperimen terkecil untuk menguji / menggugurkan ``hyp``."""
    hid = str(hyp.get("hypothesis_id") or "").strip()
    if not hid:
        raise ValueError("Hipotesis wajib memiliki hypothesis_id.")
    falsification_cond = str(
        hyp.get("falsification_condition") or hyp.get("falsification_criteria") or ""
    ).strip()
    prediction = str(hyp.get("measurable_prediction") or "").strip()
    if not falsification_cond or not prediction:
        raise ValueError(
            f"Hipotesis {hid!r} wajib memiliki measurable_prediction dan falsification_condition."
        )

    exp_type, rationale = _choose_experiment_type(hyp)
    sample_size, estimated_cycles, cost_tier = _estimate_cycle_cost(exp_type, hyp)
    risk_level = str(hyp.get("risk_level", "low")).lower()

    if exp_type == "ab_test" and risk_level != "low":
        raise ValueError("ab_test hanya diizinkan untuk hipotesis berisiko rendah ('low').")

    guard_map = {
        "replay_audit": "Read-only URI (?mode=ro) atas salinan log historis; nol mutasi state.",
        "fixture_arena": "Sandbox terisolasi atas data fixture sintetis; dilarang menyentuh live endpoint.",
        "ab_test": "Hanya untuk perubahan berisiko rendah; hentikan awal begitu ambang gagal tercapai.",
    }

    return {
        "schema": SCHEMA,
        "hypothesis_id": hid,
        "experiment_type": exp_type,
        "design_rationale": rationale,
        "minimum_sample_size": sample_size,
        "estimated_cycles": estimated_cycles,
        "cost_tier": cost_tier,
        "measurable_prediction": prediction,
        "falsification_criteria": falsification_cond,
        "early_stop_on_falsification": True,
        "safety_guard": guard_map[exp_type],
    }


def design_batch(hypotheses: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    specs = [design_smallest_falsifying_experiment(h) for h in hypotheses]
    total_cycles = sum(s["estimated_cycles"] for s in specs)
    by_type = {t: 0 for t in VALID_EXPERIMENT_TYPES}
    for s in specs:
        by_type[s["experiment_type"]] += 1
    return {
        "schema": BATCH_SCHEMA,
        "count": len(specs),
        "total_estimated_cycles": total_cycles,
        "by_type": by_type,
        "designs": specs,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Perancang eksperimen pemalsuan terkecil (AG95)")
    parser.add_argument("--hypotheses", required=True, help="Path JSON list/object hipotesis")
    args = parser.parse_args(argv)
    raw = json.loads(Path(args.hypotheses).read_text(encoding="utf-8"))
    if isinstance(raw, list):
        out = design_batch(raw)
    elif isinstance(raw, dict) and isinstance(raw.get("hypotheses"), list):
        out = design_batch(raw["hypotheses"])
    elif isinstance(raw, dict):
        out = design_smallest_falsifying_experiment(raw)
    else:
        raise ValueError("Berkas hipotesis harus objek JSON atau daftar objek.")
    print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
