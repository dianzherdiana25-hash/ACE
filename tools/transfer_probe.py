"""Validator paket transfer & probe evaluasi antar-domain (AG63).

Memuat suite pasangan domain berbagi struktur (``tools/fixtures/transfer_suite_v1.jsonl``),
memvalidasi keutuhan tugas sumber/target/pembangkit tugas jembatan, serta
menjalankan probe penilaian atas solver terinjeksi.
"""

from __future__ import annotations

import argparse
from collections import deque
import json
from pathlib import Path
import re
import sys
from typing import Any, Callable, Mapping, Sequence


SCHEMA = "ace.transfer-suite-probe.v1"
DEFAULT_SUITE_PATH = Path(__file__).resolve().parent / "fixtures" / "transfer_suite_v1.jsonl"
REQUIRED_PAIR_IDS = (
    "pair-1-dedup-reconcile",
    "pair-2-graph-dep",
    "pair-3-text-match",
)
_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


def load_transfer_suite(path: Path = DEFAULT_SUITE_PATH) -> list[dict[str, Any]]:
    """Muat paket suite transfer dari berkas JSONL."""
    items: list[dict[str, Any]] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s:
            items.append(json.loads(s))
    if not items:
        raise ValueError(f"Suite transfer kosong: {path}")
    return items


def generate_bridge_task(pair: Mapping[str, Any], *, seed: int = 0) -> dict[str, Any]:
    """Bangkitkan satu tugas jembatan terparameterisasi secara deterministik dari seed."""
    spec = pair.get("bridge_task_spec")
    if not isinstance(spec, Mapping):
        raise ValueError(f"Pasangan {pair.get('pair_id')!r} tidak memiliki bridge_task_spec")
    kind = str(spec.get("kind") or "")
    seed_inputs = spec.get("seed_inputs")
    if not isinstance(seed_inputs, list) or not seed_inputs:
        raise ValueError(f"Pasangan {pair.get('pair_id')!r} memiliki seed_inputs kosong")

    chosen = seed_inputs[abs(int(seed)) % len(seed_inputs)]
    pid = str(pair["pair_id"])

    if kind == "canonical_key_bridge":
        return {
            "id": f"{pid}-bridge-s{seed}",
            "role": "bridge",
            "pair_id": pid,
            "prompt": "Kanonisasi setiap item string (trim spasi sekeliling ':' lalu huruf kecil) dan hilangkan duplikat terurut.",
            "input": list(chosen["items"]),
            "evaluator": {"kind": "json_equal", "expected": list(chosen["expected"])},
        }
    if kind == "bfs_reachability_bridge":
        return {
            "id": f"{pid}-bridge-s{seed}",
            "role": "bridge",
            "pair_id": pid,
            "prompt": f"Hitung jarak hop BFS terpendek dari {chosen['start']} ke {chosen['target']}.",
            "input": {
                "edges": list(chosen["edges"]),
                "start": chosen["start"],
                "target": chosen["target"],
            },
            "evaluator": {"kind": "numeric_tolerance", "expected": chosen["expected"], "tolerance": 0.0},
        }
    if kind == "token_jaccard_bridge":
        return {
            "id": f"{pid}-bridge-s{seed}",
            "role": "bridge",
            "pair_id": pid,
            "prompt": "Pilih kandidat dengan skor tumpang tindih token Jaccard tertinggi terhadap kueri.",
            "input": {"query": chosen["query"], "candidates": list(chosen["candidates"])},
            "evaluator": {"kind": "exact_match", "expected": chosen["expected"]},
        }
    raise ValueError(f"Jenis bridge generator tidak dikenal: {kind!r}")


def _evaluate_answer(spec: Mapping[str, Any], answer: Any) -> bool:
    kind = spec.get("kind")
    if kind == "exact_match":
        return str(answer or "").strip() == str(spec.get("expected") or "").strip()
    if kind == "numeric_tolerance":
        try:
            got = float(str(answer).strip()) if not isinstance(answer, (int, float)) else float(answer)
            return abs(got - float(spec["expected"])) <= float(spec.get("tolerance", 0.0))
        except (ValueError, TypeError):
            return False
    if kind == "json_equal":
        if isinstance(answer, str):
            try:
                answer = json.loads(answer)
            except json.JSONDecodeError:
                return False
        return answer == spec.get("expected")
    raise ValueError(f"Evaluator tidak dikenal: {kind!r}")


def validate_suite_integrity(suite: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Pastikan ketiga pasangan hadir lengkap beserta tugas jembatan deterministik."""
    errors: list[str] = []
    pair_ids: list[str] = []
    for idx, pair in enumerate(suite):
        pid = str(pair.get("pair_id") or "")
        pair_ids.append(pid)
        if not pid:
            errors.append(f"pair[{idx}] tanpa pair_id")
            continue
        for req_key in ("source_domain", "target_domain", "shared_structure", "source_task", "target_task", "bridge_task_spec"):
            if req_key not in pair:
                errors.append(f"{pid}: field wajib {req_key!r} hilang")
        for task_key in ("source_task", "target_task"):
            t = pair.get(task_key)
            if not isinstance(t, Mapping) or not t.get("id") or not t.get("prompt") or not isinstance(t.get("evaluator"), Mapping):
                errors.append(f"{pid}: {task_key} tidak lengkap")
        try:
            b0_a = generate_bridge_task(pair, seed=0)
            b0_b = generate_bridge_task(pair, seed=0)
            if b0_a != b0_b:
                errors.append(f"{pid}: generator tugas jembatan tidak deterministik pada seed=0")
        except ValueError as exc:
            errors.append(f"{pid}: gagal bangkitkan tugas jembatan ({exc})")

    missing_required = [req for req in REQUIRED_PAIR_IDS if req not in pair_ids]
    if missing_required:
        errors.append(f"Pasangan wajib belum ada: {missing_required}")

    return {
        "schema": SCHEMA,
        "valid": len(errors) == 0,
        "pair_count": len(suite),
        "pair_ids": pair_ids,
        "errors": errors,
    }


def structural_toy_solver(task: Mapping[str, Any]) -> Any:
    """Solver struktural mainan yang benar-benar memecahkan seluruh domain lewat struktur."""
    tid = str(task.get("id") or "")
    inp = task.get("input")

    if tid == "p1-src-dedup":
        seen: list[str] = []
        for raw in inp:
            norm = raw.strip().lower()
            if norm not in seen:
                seen.append(norm)
        return seen
    if tid == "p1-tgt-reconcile":
        right_keys = {" ".join(part.strip().lower() for part in r["k"].split("|")) for r in inp["right"]}
        matched, orphans = [], []
        for row in inp["left"]:
            norm_k = " ".join(part.strip().lower() for part in row["k"].split("|"))
            (matched if norm_k in right_keys else orphans).append(row["id"])
        return {"matched": matched, "orphans": orphans}
    if "pair-1-dedup-reconcile-bridge" in tid:
        seen_b: list[str] = []
        for raw in inp:
            key = ":".join(p.strip().lower() for p in raw.split(":"))
            if key not in seen_b:
                seen_b.append(key)
        return seen_b

    if tid == "p2-src-bfs" or "pair-2-graph-dep-bridge" in tid:
        adj: dict[str, list[str]] = {}
        for u, v in inp["edges"]:
            adj.setdefault(u, []).append(v)
        q = deque([(inp["start"], 0)])
        seen_nodes = {inp["start"]}
        while q:
            node, dist = q.popleft()
            if node == inp["target"]:
                return dist
            for nxt in adj.get(node, []):
                if nxt not in seen_nodes:
                    seen_nodes.add(nxt)
                    q.append((nxt, dist + 1))
        return -1

    if tid == "p2-tgt-dep":
        deps = inp["deps"]
        order: list[str] = []
        seen_mods = {inp["root"]}
        q_dep = deque(sorted(deps.get(inp["root"], [])))
        while q_dep:
            mod = q_dep.popleft()
            if mod in seen_mods:
                continue
            seen_mods.add(mod)
            order.append(mod)
            for nxt in sorted(deps.get(mod, [])):
                if nxt not in seen_mods:
                    q_dep.append(nxt)
        return order

    if tid in {"p3-src-text"} or "pair-3-text-match-bridge" in tid:
        q_tok = {t.lower() for t in _TOKEN_RE.findall(inp["query"])}
        return max(
            inp["candidates"],
            key=lambda c: len(q_tok & {t.lower() for t in _TOKEN_RE.findall(c)})
            / max(1, len(q_tok | {t.lower() for t in _TOKEN_RE.findall(c)})),
        )
    if tid == "p3-tgt-match":
        q_tok = {t.lower() for t in _TOKEN_RE.findall(inp["noisy"])}
        best = max(
            inp["catalog"],
            key=lambda row: len(q_tok & {t.lower() for t in _TOKEN_RE.findall(row["desc"])}),
        )
        return best["id"]

    return None


def run_transfer_probe(
    suite: Sequence[Mapping[str, Any]],
    solver: Callable[[Mapping[str, Any]], Any],
    *,
    seed: int = 0,
) -> dict[str, Any]:
    """Jalankan probe evaluasi transfer pada source, bridge, dan target per pasangan."""
    integrity = validate_suite_integrity(suite)
    if not integrity["valid"]:
        raise ValueError(f"Suite transfer tidak utuh: {integrity['errors']}")

    per_pair: list[dict[str, Any]] = []
    source_hits = 0
    bridge_hits = 0
    target_hits = 0

    for pair in suite:
        src_task = dict(pair["source_task"])
        tgt_task = dict(pair["target_task"])
        brd_task = generate_bridge_task(pair, seed=seed)

        src_ok = _evaluate_answer(src_task["evaluator"], solver(src_task))
        brd_ok = _evaluate_answer(brd_task["evaluator"], solver(brd_task))
        tgt_ok = _evaluate_answer(tgt_task["evaluator"], solver(tgt_task))

        source_hits += int(src_ok)
        bridge_hits += int(brd_ok)
        target_hits += int(tgt_ok)

        s_score = 1.0 if src_ok else 0.0
        b_score = 1.0 if brd_ok else 0.0
        t_score = 1.0 if tgt_ok else 0.0
        per_pair.append(
            {
                "pair_id": pair["pair_id"],
                "shared_structure": pair["shared_structure"],
                "source_domain": pair["source_domain"],
                "target_domain": pair["target_domain"],
                "source_score": s_score,
                "bridge_score": b_score,
                "target_score": t_score,
                "transfer_gap": round(t_score - s_score, 4),
            }
        )

    n = len(suite)
    src_rate = round(source_hits / n, 6)
    brd_rate = round(bridge_hits / n, 6)
    tgt_rate = round(target_hits / n, 6)

    return {
        "schema": SCHEMA,
        "seed": seed,
        "integrity": integrity,
        "summary": {
            "pair_count": n,
            "source_score": src_rate,
            "bridge_score": brd_rate,
            "target_score": tgt_rate,
            "transfer_gap": round(tgt_rate - src_rate, 6),
        },
        "pairs": per_pair,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validasi paket suite transfer dan jalankan skoring probe struktur."
    )
    parser.add_argument(
        "--suite",
        default=str(DEFAULT_SUITE_PATH),
        help="Path fixture JSONL paket transfer.",
    )
    parser.add_argument("--seed", type=int, default=0, help="Seed pembangkit tugas jembatan.")
    parser.add_argument(
        "--mode",
        choices=("probe", "validate"),
        default="probe",
        help="validate: hanya cek keutuhan paket; probe: uji dengan solver mainan bawaan.",
    )
    parser.add_argument("--out", help="Path output JSON opsional (default stdout).")
    args = parser.parse_args(argv)

    try:
        suite = load_transfer_suite(Path(args.suite))
        if args.mode == "validate":
            result = validate_suite_integrity(suite)
            ok = result["valid"]
        else:
            result = run_transfer_probe(suite, structural_toy_solver, seed=args.seed)
            ok = result["integrity"]["valid"]
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    payload = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.out:
        op = Path(args.out)
        op.parent.mkdir(parents=True, exist_ok=True)
        op.write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
