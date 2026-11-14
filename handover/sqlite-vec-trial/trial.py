#!/usr/bin/env python3
"""sqlite-vec trial — ECOSYSTEM INTAKE #01 candidate #4 protocol.

Corpus: chunks.jsonl (12,282 chunks of the ACE origin/main tree, built by
build_corpus.py). Queries: 50 hand-written paraphrases (queries.jsonl),
each labeled with exactly one gold chunk id.

Arms:
  A) substring baseline — for each query, score every chunk by the number
     of distinct query content-words (len>=3) appearing as substrings of
     the lowercased chunk text; rank by (score desc, id desc as recency
     proxy). This mirrors ACE's lexical/recency retrieval character.
  B) sqlite-vec KNN — nomic-embed-text-v1.5 Q8_0 embeddings via the
     custodied llama.cpp server in embedding mode (prefixes
     "search_document: "/"search_query: " per the model's card,
     --pooling mean), stored in a vec0 table in the SAME .db file as the
     chunk text; KNN via MATCH ... k=10 (cosine via L2 on
     L2-normalized vectors — embeddings are normalized before insert).

Metrics: recall@10 per arm (gold in top-10), delta in points, and p95
wall time of the 50 KNN queries against the full 12,282-entry table.
Adoption bar (intake doc): recall@10 improvement >= +30 points over the
baseline AND p95 latency < 50 ms/query at 10k entries.
"""
import argparse, json, math, os, sqlite3, struct, sys, time
import urllib.request

def vec_bytes(v):
    return struct.pack(f"<{len(v)}f", *v)

def embed_batch(texts, base, prefix):
    # One request per batch: /v1/embeddings accepts a list input.
    body = json.dumps({"input": [prefix + t for t in texts], "model": "nomic-embed"}).encode()
    req = urllib.request.Request(base + "/v1/embeddings", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as r:
        d = json.load(r)
    return [item["embedding"] for item in sorted(d["data"], key=lambda x: x["index"])]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", required=True)
    ap.add_argument("--queries", required=True)
    ap.add_argument("--db", required=True)
    ap.add_argument("--emb-cache", required=True, help="embeddings .npy-less jsonl cache")
    ap.add_argument("--server", default="http://127.0.0.1:18082")
    ap.add_argument("--embed", action="store_true", help="run embedding pass (needs server up)")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    chunks = [json.loads(l) for l in open(args.chunks)]
    queries = [json.loads(l) for l in open(args.queries)]
    print(f"chunks={len(chunks)} queries={len(queries)}", flush=True)

    # ---- Arm A: substring baseline (pure python, deterministic)
    import re
    def qtokens(q):
        return set(w for w in re.findall(r"[a-z0-9]+", q.lower()) if len(w) >= 3)
    texts_low = [c["text"].lower() for c in chunks]
    base_ranks = {}
    for qi, q in enumerate(queries):
        toks = qtokens(q["query"])
        scored = []
        for c, tl in zip(chunks, texts_low):
            s = sum(1 for t in toks if t in tl)
            scored.append((s, c["id"]))
        scored.sort(key=lambda x: (-x[0], -x[1]))
        rank = [cid for _, cid in scored].index(q["gold"]) + 1
        base_ranks[qi] = rank
    base_recall = sum(1 for r in base_ranks.values() if r <= 10) / len(queries)
    print(f"baseline recall@10 = {base_recall:.3f}", flush=True)

    # ---- Embeddings (cached; chunks then queries)
    cache = {}
    if os.path.exists(args.emb_cache):
        for l in open(args.emb_cache):
            d = json.loads(l)
            cache[d["key"]] = d["vec"]
    def get_vecs(items, kind, prefix):
        vecs, missing = {}, []
        for it in items:
            k = f"{kind}:{it['id'] if kind=='doc' else it['gold']}:{kind=='doc' and it['id'] or ''}"
            key = f"{kind}:{it['id']}" if kind == "doc" else f"q:{it['gold']}:{it['query'][:40]}"
            if key in cache:
                vecs[key] = cache[key]
            else:
                missing.append((key, it))
        if missing:
            if not args.embed:
                print(f"MISSING {len(missing)} embeddings and --embed not set", flush=True)
                sys.exit(2)
            with open(args.emb_cache, "a") as cf:
                for i in range(0, len(missing), 50):
                    batch = missing[i:i+50]
                    vs = embed_batch([b[1]["text"] if kind == "doc" else b[1]["query"] for b in batch],
                                     args.server, prefix)
                    for (key, _), v in zip(batch, vs):
                        n = math.sqrt(sum(x * x for x in v)) or 1.0
                        v = [x / n for x in v]
                        vecs[key] = v
                        cf.write(json.dumps({"key": key, "vec": v}) + "\n")
                    print(f"embedded {kind} {i+len(batch)}/{len(missing)}", flush=True)
        return vecs

    doc_vecs = get_vecs(chunks, "doc", "search_document: ")
    q_vecs = get_vecs(queries, "q", "search_query: ")
    dim = len(next(iter(doc_vecs.values())))
    print(f"embedding dim={dim}", flush=True)

    # ---- Build the .db: chunks + vec0 in one file
    if os.path.exists(args.db):
        os.remove(args.db)
    import sqlite_vec
    db = sqlite3.connect(args.db)
    db.enable_load_extension(True)
    sqlite_vec.load(db)
    db.execute("create table chunks(id integer primary key, path text, text text)")
    db.execute(f"create virtual table vec_chunks using vec0(id integer primary key, embedding float[{dim}])")
    db.executemany("insert into chunks values (?,?,?)",
                   [(c["id"], c["path"], c["text"]) for c in chunks])
    db.executemany("insert into vec_chunks values (?,?)",
                   [(c["id"], vec_bytes(doc_vecs[f"doc:{c['id']}"])) for c in chunks])
    db.commit()

    # ---- Arm B: KNN + latency
    vec_ranks, lat = {}, []
    for qi, q in enumerate(queries):
        qv = vec_bytes(q_vecs[f"q:{q['gold']}:{q['query'][:40]}"])
        t0 = time.perf_counter()
        rows = db.execute(
            "select id, distance from vec_chunks where embedding match ? and k = 10 order by distance",
            (qv,)).fetchall()
        lat.append((time.perf_counter() - t0) * 1000)
        ids = [r[0] for r in rows]
        vec_ranks[qi] = ids.index(q["gold"]) + 1 if q["gold"] in ids else 9999
    vec_recall = sum(1 for r in vec_ranks.values() if r <= 10) / len(queries)
    lat_sorted = sorted(lat)
    p95 = lat_sorted[min(len(lat_sorted) - 1, int(0.95 * len(lat_sorted)))]
    res = {
        "chunks": len(chunks), "queries": len(queries), "dim": dim,
        "baseline_recall@10": round(base_recall, 4),
        "vec_recall@10": round(vec_recall, 4),
        "delta_points": round((vec_recall - base_recall) * 100, 1),
        "knn_p95_ms": round(p95, 2), "knn_median_ms": round(lat_sorted[len(lat_sorted)//2], 2),
        "adoption_bar": "recall@10 delta >= +30 points AND p95 < 50 ms at >=10k entries",
        "bar_met": (vec_recall - base_recall) * 100 >= 30 and p95 < 50,
        "baseline_ranks": base_ranks, "vec_ranks": {k: (v if v != 9999 else None) for k, v in vec_ranks.items()},
    }
    with open(args.out, "w") as f:
        json.dump(res, f, indent=1)
    print(json.dumps({k: res[k] for k in ("baseline_recall@10", "vec_recall@10", "delta_points", "knn_p95_ms", "bar_met")}, indent=1))
    print("TRIAL_DONE")

if __name__ == "__main__":
    main()
