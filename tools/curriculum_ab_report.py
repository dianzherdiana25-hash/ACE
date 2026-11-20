"""Laporan perbandingan A/B antara kurikulum tetap dan kurikulum tergenerasi (AG47).

Membandingkan hasil penutupan gap (gap closure) dari dua eksperimen atau
fixture—kurikulum tetap (fixed) versus kurikulum tergenerasi (generated)—dan
menghitung laju penutupan serta delta per keluarga gap maupun agregat.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


SCHEMA = "ace.curriculum-ab-report.v1"
_CLOSED_STATUSES = frozenset({"closed", "resolved", "passed", "success", "done"})


def _is_closed(entry: Mapping[str, Any]) -> bool:
    if "closed" in entry:
        return bool(entry["closed"])
    status = str(entry.get("status") or entry.get("outcome") or "").strip().lower()
    return status in _CLOSED_STATUSES


def _aggregate_family_counts(data: Any, label: str) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "closed": 0})
    if isinstance(data, Mapping):
        families_map = data.get("families")
        if isinstance(families_map, Mapping):
            for fam, payload in families_map.items():
                if not isinstance(payload, Mapping):
                    raise ValueError(f"{label}.families[{fam!r}] harus berupa objek JSON")
                counts[str(fam)]["total"] += int(payload.get("total", 0))
                counts[str(fam)]["closed"] += int(payload.get("closed", 0))
            return dict(counts)
        if isinstance(data.get("results"), list):
            data = data["results"]
        elif isinstance(data.get("records"), list):
            data = data["records"]
        else:
            raise ValueError(f"{label} harus berupa daftar hasil atau objek ber-field 'families'/'results'")

    if not isinstance(data, list):
        raise ValueError(f"{label} wajib berupa daftar hasil penutupan gap")

    for idx, row in enumerate(data):
        if not isinstance(row, Mapping):
            raise ValueError(f"{label}[{idx}] harus berupa objek JSON")
        family = str(
            row.get("family")
            or row.get("gap_family")
            or row.get("error_type")
            or "unknown"
        ).strip() or "unknown"
        counts[family]["total"] += 1
        if _is_closed(row):
            counts[family]["closed"] += 1
    return dict(counts)


def compare_curricula(fixed_input: Any, generated_input: Any) -> dict[str, Any]:
    """Hitung delta laju penutupan gap per keluarga dan agregat fixed vs generated."""
    fixed_counts = _aggregate_family_counts(fixed_input, "fixed")
    gen_counts = _aggregate_family_counts(generated_input, "generated")
    all_families = sorted(set(fixed_counts) | set(gen_counts))
    if not all_families:
        raise ValueError("Tidak ada keluarga gap pada kedua dataset A/B")

    by_family: dict[str, dict[str, Any]] = {}
    families_improved: list[str] = []
    families_regressed: list[str] = []
    families_tied: list[str] = []

    fixed_sum_total = 0
    fixed_sum_closed = 0
    gen_sum_total = 0
    gen_sum_closed = 0
    macro_fixed_rates: list[float] = []
    macro_gen_rates: list[float] = []

    for family in all_families:
        f_stat = fixed_counts.get(family, {"total": 0, "closed": 0})
        g_stat = gen_counts.get(family, {"total": 0, "closed": 0})

        f_total, f_closed = f_stat["total"], f_stat["closed"]
        g_total, g_closed = g_stat["total"], g_stat["closed"]
        fixed_sum_total += f_total
        fixed_sum_closed += f_closed
        gen_sum_total += g_total
        gen_sum_closed += g_closed

        f_rate = round(f_closed / f_total, 6) if f_total > 0 else None
        g_rate = round(g_closed / g_total, 6) if g_total > 0 else None
        if f_rate is not None:
            macro_fixed_rates.append(f_rate)
        if g_rate is not None:
            macro_gen_rates.append(g_rate)

        if f_rate is not None and g_rate is not None:
            delta: float | None = round(g_rate - f_rate, 6)
            if delta > 1e-9:
                winner = "generated"
                families_improved.append(family)
            elif delta < -1e-9:
                winner = "fixed"
                families_regressed.append(family)
            else:
                winner = "tie"
                families_tied.append(family)
        else:
            delta = None
            winner = "incomplete"

        by_family[family] = {
            "fixed_total": f_total,
            "fixed_closed": f_closed,
            "fixed_closure_rate": f_rate,
            "generated_total": g_total,
            "generated_closed": g_closed,
            "generated_closure_rate": g_rate,
            "closure_rate_delta": delta,
            "winner": winner,
        }

    fixed_agg_rate = (
        round(fixed_sum_closed / fixed_sum_total, 6) if fixed_sum_total > 0 else None
    )
    gen_agg_rate = (
        round(gen_sum_closed / gen_sum_total, 6) if gen_sum_total > 0 else None
    )
    agg_delta = (
        round(gen_agg_rate - fixed_agg_rate, 6)
        if fixed_agg_rate is not None and gen_agg_rate is not None
        else None
    )

    macro_fixed = (
        round(sum(macro_fixed_rates) / len(macro_fixed_rates), 6)
        if macro_fixed_rates
        else None
    )
    macro_gen = (
        round(sum(macro_gen_rates) / len(macro_gen_rates), 6)
        if macro_gen_rates
        else None
    )
    macro_delta = (
        round(macro_gen - macro_fixed, 6)
        if macro_fixed is not None and macro_gen is not None
        else None
    )

    if agg_delta is None:
        overall_winner = "incomplete"
    elif agg_delta > 1e-9:
        overall_winner = "generated"
    elif agg_delta < -1e-9:
        overall_winner = "fixed"
    else:
        overall_winner = "tie"

    return {
        "schema": SCHEMA,
        "aggregate": {
            "family_count": len(all_families),
            "fixed_total": fixed_sum_total,
            "fixed_closed": fixed_sum_closed,
            "fixed_closure_rate": fixed_agg_rate,
            "generated_total": gen_sum_total,
            "generated_closed": gen_sum_closed,
            "generated_closure_rate": gen_agg_rate,
            "closure_rate_delta": agg_delta,
            "macro_fixed_closure_rate": macro_fixed,
            "macro_generated_closure_rate": macro_gen,
            "macro_closure_rate_delta": macro_delta,
            "overall_winner": overall_winner,
            "families_improved": families_improved,
            "families_regressed": families_regressed,
            "families_tied": families_tied,
        },
        "by_family": by_family,
    }


def _load_ab_input(path: Path) -> Any:
    raw = Path(path).read_text(encoding="utf-8").strip()
    if not raw:
        raise ValueError(f"Berkas kosong: {path}")
    if raw.startswith("[") or (raw.startswith("{") and "\n" not in raw):
        return json.loads(raw)
    if raw.startswith("{"):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Bandingkan penutupan gap kurikulum fixed vs generated per keluarga dan agregat."
    )
    parser.add_argument("--fixed", required=True, help="Path hasil penutupan gap kurikulum tetap.")
    parser.add_argument("--generated", required=True, help="Path hasil penutupan gap kurikulum tergenerasi.")
    parser.add_argument("--out", help="Path output JSON opsional (default stdout).")
    args = parser.parse_args(argv)

    try:
        fixed_data = _load_ab_input(Path(args.fixed))
        gen_data = _load_ab_input(Path(args.generated))
        report = compare_curricula(fixed_data, gen_data)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
