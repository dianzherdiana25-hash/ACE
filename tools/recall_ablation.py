#!/usr/bin/env python3
"""Bandingkan dua lengan fixture agar kontribusi recall bisa dihitung ulang.

Store CLI berupa objek query → daftar keputusan berperingkat. Tugas berupa
larik objek id, query, cold_decision, expected (semua string). Keputusan
adalah hasil recall pertama atau cold_decision bila kosong. Skor adalah
kecocokan persis dengan expected. Seed mengatur urutan tugas untuk kedua
lengan. Ringkasan menyimpan hash byte JSONL agar hasil dapat diperiksa.

Mode `--anchored` memakai store berisi records (query → daftar objek
decision dan based_on) serta verified_refs. Hanya kandidat dengan semua
ref terverifikasi yang masuk ke lengan anchored.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import random
import re
import sqlite3
import sys
from urllib.parse import quote


def _tokenize_query(text):
    return set(re.findall(r"[a-z0-9_]+", str(text).lower()))


def load_sqlite_ablation_store(db_path, tasks, *, anchored=False, pool_cleanup=False,
                                semantic=False, embedder=None, top_k=3):
    """Baca OperationalStore SQLite secara read-only (URI mode=ro) dan petakan ke store ablation."""
    if semantic and not callable(embedder):
        raise ValueError("Mode semantik memerlukan embedder callable.")
    if not isinstance(tasks, list) or not tasks:
        raise ValueError("Daftar tugas wajib berupa larik berisi.")
    resolved = Path(db_path).resolve()
    if not resolved.is_file():
        raise ValueError(f"Berkas SQLite tidak ditemukan: {db_path}")

    uri = f"file:{quote(str(resolved))}?mode=ro"
    candidates = []
    verified_refs = set()
    refs_by_task = {}

    try:
        conn = sqlite3.connect(uri, uri=True)
    except sqlite3.Error as exc:
        raise ValueError(f"Gagal membuka SQLite secara read-only: {exc}") from None
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only = ON")
        tables = {
            row["name"]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }

        if "receipts" in tables:
            for row in conn.execute("SELECT receipt_id, task_id, passed FROM receipts ORDER BY receipt_id"):
                rid = str(row["receipt_id"] or "").strip()
                tid = str(row["task_id"] or "").strip()
                if rid and int(row["passed"] or 0) == 1:
                    verified_refs.add(rid)
                    if tid:
                        refs_by_task.setdefault(tid, []).append(rid)

        if "learning_experiences" in tables:
            for row in conn.execute(
                "SELECT experience_id, task_id, failure_signature, extracted_rule, strategy_after, verification_evidence_json "
                "FROM learning_experiences ORDER BY experience_id"
            ):
                decision = str(row["extracted_rule"] or row["strategy_after"] or "").strip()
                if not decision:
                    continue
                haystack = f"{row['failure_signature']} {row['extracted_rule']} {row['strategy_after']}"
                refs = list(refs_by_task.get(str(row["task_id"] or ""), []))
                try:
                    ev = json.loads(row["verification_evidence_json"] or "{}")
                    if isinstance(ev, dict):
                        for key in ("receipt_id", "evidence_ref"):
                            val = ev.get(key)
                            if isinstance(val, str) and val.strip():
                                refs.append(val.strip())
                except ValueError:
                    pass
                if not refs:
                    refs = [str(row["experience_id"])]
                candidates.append((haystack, decision, refs, f"exp:{row['experience_id']}"))

        if "skills" in tables:
            for row in conn.execute(
                "SELECT skill_id, name, domain, procedure_steps_json, source_task_ids_json, status "
                "FROM skills WHERE status = 'ACTIVE' ORDER BY skill_id"
            ):
                decision = str(row["name"] or "").strip()
                if not decision:
                    continue
                steps_txt = ""
                try:
                    steps = json.loads(row["procedure_steps_json"] or "[]")
                    if isinstance(steps, list):
                        steps_txt = " ".join(str(s) for s in steps)
                except ValueError:
                    pass
                haystack = f"{row['name']} {row['domain']} {steps_txt}"
                refs = []
                try:
                    tids = json.loads(row["source_task_ids_json"] or "[]")
                    if isinstance(tids, list):
                        for tid in tids:
                            refs.extend(refs_by_task.get(str(tid), []))
                except ValueError:
                    pass
                if not refs:
                    refs = [str(row["skill_id"])]
                candidates.append((haystack, decision, refs, f"skill:{row['skill_id']}"))

        # EVO 0017 M2 (diagnosis M1): kandidat riwayat tugas COMPLETED
        # mencemari kolam keputusan — next_action generiknya menang
        # tumpang-tindih token atas kandidat skill/pengalaman. Dengan
        # pool_cleanup, riwayat tugas keluar dari kolam keputusan
        # (perannya provenance saja); default mati agar protokol M1
        # yang tersegel tetap dapat direproduksi persis.
        if "tasks" in tables and not pool_cleanup:
            for row in conn.execute(
                "SELECT task_id, normalized_goal, next_action, status FROM tasks "
                "WHERE status = 'COMPLETED' ORDER BY task_id"
            ):
                decision = str(row["next_action"] or "").strip()
                if not decision:
                    continue
                haystack = f"{row['normalized_goal']} {row['task_id']}"
                refs = list(refs_by_task.get(str(row["task_id"]), [])) or [str(row["task_id"])]
                candidates.append((haystack, decision, refs, f"task:{row['task_id']}"))
    except sqlite3.Error as exc:
        raise ValueError(f"Kueri OperationalStore SQLite gagal: {exc}") from None
    finally:
        conn.close()

    queries = sorted({
        task["query"] for task in tasks
        if isinstance(task, dict) and isinstance(task.get("query"), str) and task["query"].strip()
    })

    # EVO 0017 M3 — peringkat semantik: kolam per query = top_k kandidat
    # terdekat secara kosinus embedding atas haystack (pengganti filter
    # tumpang-tindih token, yang membuang kandidat parafrase ber-overlap
    # nol). Embedding dihitung sekali per teks unik (deterministik).
    _emb_cache: dict[str, list[float]] = {}

    def _embed(text: str) -> list[float]:
        if text not in _emb_cache:
            _emb_cache[text] = [float(v) for v in embedder(text)]
        return _emb_cache[text]

    def _cosine(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        na = sum(x * x for x in a) ** 0.5
        nb = sum(y * y for y in b) ** 0.5
        if na == 0.0 or nb == 0.0:
            return 0.0
        return dot / (na * nb)

    def _semantic_pool(query: str) -> list[tuple]:
        qv = _embed(query)
        scored = [(_cosine(qv, _embed(haystack)), sort_key, haystack, decision, refs)
                  for haystack, decision, refs, sort_key in candidates]
        scored.sort(key=lambda item: (-item[0], item[1]))
        return scored[:top_k]

    if anchored:
        records = {}
        for query in queries:
            if semantic:
                records[query] = [
                    {"decision": decision, "based_on": sorted(set(refs))}
                    for _score, _key, _hay, decision, refs in _semantic_pool(query)
                ]
                continue
            q_toks = _tokenize_query(query)
            matched = []
            for haystack, decision, refs, sort_key in candidates:
                overlap = len(q_toks & _tokenize_query(haystack))
                if query.lower() in haystack.lower() or overlap > 0:
                    matched.append((overlap, sort_key, {"decision": decision, "based_on": sorted(set(refs))}))
            matched.sort(key=lambda item: (-item[0], item[1]))
            records[query] = [item[2] for item in matched]
        return {"records": records, "verified_refs": sorted(verified_refs)}

    plain_store = {}
    for query in queries:
        if semantic:
            plain_store[query] = [decision for _s, _k, _h, decision, _r in _semantic_pool(query)]
            continue
        q_toks = _tokenize_query(query)
        matched = []
        for haystack, decision, _refs, sort_key in candidates:
            overlap = len(q_toks & _tokenize_query(haystack))
            if query.lower() in haystack.lower() or overlap > 0:
                matched.append((overlap, sort_key, decision))
        matched.sort(key=lambda item: (-item[0], item[1]))
        plain_store[query] = [item[2] for item in matched]
    return plain_store


def fixture_recall(query, store):
    if not isinstance(store, dict):
        raise ValueError("Store fixture wajib berupa objek.")
    return store.get(query, [])


class _FixtureReferences:
    def __init__(self, store):
        refs = store.get("verified_refs") if isinstance(store, dict) else None
        if not isinstance(refs, list) or any(not isinstance(ref, str) or not ref.strip() for ref in refs):
            raise ValueError("Store anchored memerlukan verified_refs berupa daftar string.")
        self.refs = set(refs)

    def verify_ref(self, ref):
        return ref in self.refs


def _anchored_arms(query, store, recall, references, check_anchors):
    recalled = (fixture_recall(query, store.get("records")) if recall is fixture_recall
                else recall(query, deepcopy(store)))
    if not isinstance(recalled, list) or any(
        not isinstance(item, dict) or not isinstance(item.get("decision"), str)
        or not item["decision"].strip() or not isinstance(item.get("based_on"), list)
        for item in recalled
    ):
        raise ValueError("Recall anchored wajib menghasilkan objek decision dan daftar based_on.")
    active = []
    qualified = []
    for item in recalled:
        active.append(item["decision"])
        if check_anchors(item["based_on"], references)["status"] == "anchored":
            qualified.append(item["decision"])
    return (("active", active), ("off", []), ("anchored", qualified))


def _change_rate(decisions):
    if len(decisions) <= 1:
        return 0.0
    changes = sum(1 for prev, curr in zip(decisions, decisions[1:]) if prev != curr)
    return changes / (len(decisions) - 1)


def _run_multiseed_ablation(store, tasks, *, recall=fixture_recall, seed=0, seeds=1, anchored=False):
    if type(seeds) is not int or seeds <= 0:
        raise ValueError("Jumlah --seeds wajib bilangan bulat positif.")
    seed_list = [seed + offset for offset in range(seeds)]
    all_rows = []
    arm_names = ("active", "off", "anchored") if anchored else ("active", "off")
    totals = {arm: 0 for arm in arm_names}
    per_task_arm_decisions = {
        task["id"]: {arm: [] for arm in arm_names}
        for task in sorted(tasks, key=lambda t: t["id"])
    }

    if anchored:
        if __package__ in (None, ""):
            sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
        from ace_operational.memory_anchor import check_anchors
        references = _FixtureReferences(store)

    for current_seed in seed_list:
        rng = random.Random(current_seed)
        ordered = sorted(tasks, key=lambda task: task["id"])
        rng.shuffle(ordered)
        for task in ordered:
            if anchored:
                raw_arms = _anchored_arms(task["query"], store, recall, references, check_anchors)
                arms = []
                for arm, candidates in raw_arms:
                    cand_list = list(candidates)
                    if recall is fixture_recall and len(cand_list) > 1:
                        rng.shuffle(cand_list)
                    arms.append((arm, cand_list))
            else:
                recalled = recall(task["query"], deepcopy(store))
                if not isinstance(recalled, list) or not all(
                    isinstance(value, str) and value.strip() for value in recalled
                ):
                    raise ValueError("Recall wajib menghasilkan daftar string keputusan.")
                cand_list = list(recalled)
                if recall is fixture_recall and len(cand_list) > 1:
                    rng.shuffle(cand_list)
                arms = (("active", cand_list), ("off", []))
            for arm, candidates in arms:
                decision = candidates[0] if candidates else task["cold_decision"]
                score = int(decision == task["expected"])
                all_rows.append({
                    "seed": current_seed,
                    "arm": arm,
                    "task_id": task["id"],
                    "recalled_count": len(candidates),
                    "decision": decision,
                    "score": score,
                })
                totals[arm] += score
                per_task_arm_decisions[task["id"]][arm].append(decision)

    output = "".join(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n" for row in all_rows)
    data = output.encode("utf-8")
    n = len(tasks)
    denom = n * len(seed_list)

    per_task = {}
    stable_tasks = []
    seed_sensitive_tasks = []
    for task_id, arm_map in sorted(per_task_arm_decisions.items()):
        active_decisions = arm_map["active"]
        rate = _change_rate(active_decisions)
        arm_rates = {arm: _change_rate(decs) for arm, decs in arm_map.items()}
        is_sensitive = len(set(active_decisions)) > 1 or any(
            len(set(decs)) > 1 for decs in arm_map.values()
        )
        classification = "seed_sensitive" if is_sensitive else "stable"
        if is_sensitive:
            seed_sensitive_tasks.append(task_id)
        else:
            stable_tasks.append(task_id)
        per_task[task_id] = {
            "task_id": task_id,
            "classification": classification,
            "stable": not is_sensitive,
            "seed_sensitive": is_sensitive,
            "decision_change_rate": rate,
            "arm_change_rates": arm_rates,
            "unique_decisions": sorted(set(active_decisions)),
            "decisions_by_seed": {
                str(s): d for s, d in zip(seed_list, active_decisions)
            },
        }

    mean_rate = (
        sum(item["decision_change_rate"] for item in per_task.values()) / n
        if n else 0.0
    )
    summary = {
        "schema": "ace.recall-ablation.v1",
        "tasks": n,
        "seed": seed,
        "seeds": seed_list,
        "seed_count": len(seed_list),
        "scores": totals,
        "delta": (totals["active"] - totals["off"]) / denom,
        "per_task": per_task,
        "stable_tasks": stable_tasks,
        "seed_sensitive_tasks": seed_sensitive_tasks,
        "stability_counts": {
            "stable": len(stable_tasks),
            "seed_sensitive": len(seed_sensitive_tasks),
        },
        "mean_decision_change_rate": mean_rate,
        "results_sha256": hashlib.sha256(data).hexdigest(),
    }
    if anchored:
        summary["anchored_delta"] = (totals["anchored"] - totals["off"]) / denom
    return data, summary


def run_ablation(store, tasks, *, recall=fixture_recall, seed=0, anchored=False, seeds=None):
    if not isinstance(tasks, list) or not tasks:
        raise ValueError("Daftar tugas wajib berupa larik berisi.")
    ids = set()
    for task in tasks:
        if not isinstance(task, dict) or not all(
            isinstance(task.get(key), str) and task[key].strip()
            for key in ("id", "query", "cold_decision", "expected")
        ) or task["id"] in ids:
            raise ValueError("Tugas fixture tidak sah atau ID ganda.")
        ids.add(task["id"])
    if seeds is not None:
        return _run_multiseed_ablation(
            store, tasks, recall=recall, seed=seed, seeds=seeds, anchored=anchored
        )
    ordered = sorted(tasks, key=lambda task: task["id"])
    random.Random(seed).shuffle(ordered)
    rows = []
    totals = {"active": 0, "off": 0}
    if anchored:
        if __package__ in (None, ""):
            sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
        from ace_operational.memory_anchor import check_anchors

        references = _FixtureReferences(store)
        totals["anchored"] = 0
    for task in ordered:
        if anchored:
            arms = _anchored_arms(task["query"], store, recall, references, check_anchors)
        else:
            recalled = recall(task["query"], deepcopy(store))
            if not isinstance(recalled, list) or not all(
                isinstance(value, str) and value.strip() for value in recalled
            ):
                raise ValueError("Recall wajib menghasilkan daftar string keputusan.")
            arms = (("active", recalled), ("off", []))
        for arm, candidates in arms:
            decision = candidates[0] if candidates else task["cold_decision"]
            score = int(decision == task["expected"])
            rows.append({"arm": arm, "task_id": task["id"], "recalled_count": len(candidates),
                         "decision": decision, "score": score})
            totals[arm] += score
    output = "".join(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n" for row in rows)
    data = output.encode("utf-8")
    n = len(ordered)
    summary = {"schema": "ace.recall-ablation.v1", "tasks": n, "seed": seed,
               "scores": totals, "delta": (totals["active"] - totals["off"]) / n,
               "results_sha256": hashlib.sha256(data).hexdigest()}
    if anchored:
        summary["anchored_delta"] = (totals["anchored"] - totals["off"]) / n
    return data, summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--store", type=Path)
    source.add_argument("--sqlite", type=Path, help="Baca OperationalStore SQLite secara read-only.")
    parser.add_argument("--tasks", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--seeds", type=int, default=None)
    parser.add_argument("--anchored", action="store_true")
    parser.add_argument("--pool-cleanup", action="store_true",
                        help="EVO 0017 M2: keluarkan kandidat riwayat tugas dari kolam keputusan.")
    parser.add_argument("--semantic", action="store_true",
                        help="EVO 0017 M3: kolam per query = top-k terdekat kosinus embedding.")
    parser.add_argument("--top-k", type=int, default=3,
                        help="Ukuran kolam semantik per query (default 3).")
    parser.add_argument("--embedding-url", default="http://127.0.0.1:8931",
                        help="Basis URL bridge embedding (POST /v1/embeddings).")
    args = parser.parse_args(argv)
    try:
        tasks_data = json.loads(args.tasks.read_text(encoding="utf-8"))
        embedder = None
        if args.semantic:
            import urllib.request

            def embedder(text, _url=args.embedding_url.rstrip("/")):
                req = urllib.request.Request(
                    _url + "/v1/embeddings",
                    data=json.dumps({"input": text}).encode("utf-8"),
                    headers={"Content-Type": "application/json"}, method="POST")
                with urllib.request.urlopen(req, timeout=120) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))
                return payload["data"][0]["embedding"]

        store_data = (
            load_sqlite_ablation_store(args.sqlite, tasks_data, anchored=args.anchored,
                                        pool_cleanup=args.pool_cleanup,
                                        semantic=args.semantic, embedder=embedder,
                                        top_k=args.top_k)
            if args.sqlite is not None
            else json.loads(args.store.read_text(encoding="utf-8"))
        )
        data, summary = run_ablation(store_data,
                                    tasks_data,
                                    seed=args.seed, anchored=args.anchored, seeds=args.seeds)
        if args.semantic:
            summary["ranking"] = "semantic_top_k"
            summary["top_k"] = args.top_k
        if args.pool_cleanup:
            summary["pool_cleanup"] = True
        args.output_dir.mkdir()
        (args.output_dir / "results.jsonl").write_bytes(data)
        (args.output_dir / "summary.json").write_text(
            json.dumps(summary, sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
