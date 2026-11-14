#!/usr/bin/env python3
"""Render the frozen lm-eval screening card into llama-perplexity inputs.

Step 1 (this script, run inside the pinned lm_eval 0.4.13 venv, offline):
uses lm_eval's OWN task definitions (get_task_dict -> doc_to_text /
doc_to_choice / doc_to_target) over the pinned HF dataset revisions, and
writes, per task, a JSONL audit file {question, answers, gold} plus:
  - ARC/HellaSwag: a llama.cpp `--multiple-choice` binary datafile
    (format reverse-engineered from llama.cpp b12316 perplexity.cpp:
     u32 n_task, u32 task_pos[n], then per task: str question,
     mc1{u32 n, str answers[], i32 labels[]}, mc2{u32 0};
     str = u32 length + raw utf-8 bytes).
    Perplexity MC joins question + " " + answer, which is exactly
    lm_eval's ctx + target_delimiter(" ") + choice construction.
  - Winogrande: a CSV for llama.cpp's native `--winogrande` mode
    (idx, sentence-with-underscore, choice1, choice2, answer 1|2),
    rendered from the raw pinned dataset rows (lm_eval's winogrande
    semantics == llama.cpp's: score the suffix given prefix+option).

The eval split follows lm_eval: test_split if the task defines one
(ARC), else validation (HellaSwag, Winogrande). --limit takes the
first N docs in dataset order, exactly like lm_eval --limit.
"""
import argparse, csv, io, json, struct, sys

def s_str(s: str) -> bytes:
    b = s.encode("utf-8")
    return struct.pack("<I", len(b)) + b

def mc_binary(tasks) -> bytes:
    records = []
    for t in tasks:
        rec = s_str(t["question"])
        rec += struct.pack("<I", len(t["answers"]))
        for a in t["answers"]:
            rec += s_str(a)
        for i in range(len(t["answers"])):
            rec += struct.pack("<i", 1 if i == t["gold"] else 0)
        rec += struct.pack("<I", 0)  # mc2: no multi-answer set
        records.append(rec)
    out = struct.pack("<I", len(records))
    pos = 4 + 4 * len(records)
    for rec in records:
        out += struct.pack("<I", pos)
        pos += len(rec)
    return out + b"".join(records)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=250)
    ap.add_argument("--outdir", required=True)
    args = ap.parse_args()
    import os
    os.makedirs(args.outdir, exist_ok=True)

    from lm_eval.tasks import get_task_dict
    names = ["arc_easy", "arc_challenge", "hellaswag"]
    td = get_task_dict(names)
    summary = {}
    for name in names:
        task = td[name]
        docs = list(task.test_docs() if task.config.test_split else task.validation_docs())
        docs = docs[: args.limit]
        rows = []
        for doc in docs:
            q = task.doc_to_text(doc)
            ch = [str(c) for c in task.doc_to_choice(doc)]
            gold = int(task.doc_to_target(doc))
            assert isinstance(q, str) and 0 <= gold < len(ch), (name, q, gold)
            rows.append({"question": q, "answers": ch, "gold": gold})
        with open(f"{args.outdir}/{name}.jsonl", "w") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        with open(f"{args.outdir}/{name}.bin", "wb") as f:
            f.write(mc_binary(rows))
        summary[name] = len(rows)
        print(f"{name}: {len(rows)} tasks")

    # Winogrande via raw pinned rows (validation split)
    from datasets import load_dataset
    ds = load_dataset("allenai/winogrande", "winogrande_xl",
                      revision="01e74176c63542e6b0bcb004dcdea22d94fb67b5",
                      split="validation")
    rows = []
    buf = io.StringIO()
    w = csv.writer(buf)
    for i, doc in enumerate(ds.select(range(min(args.limit, len(ds))))):
        rows.append({"sentence": doc["sentence"], "option1": doc["option1"],
                     "option2": doc["option2"], "gold": int(doc["answer"]) - 1})
        w.writerow([i, doc["sentence"], doc["option1"], doc["option2"], doc["answer"]])
    with open(f"{args.outdir}/winogrande.jsonl", "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(f"{args.outdir}/winogrande.csv", "w", newline="") as f:
        f.write(buf.getvalue())
    summary["winogrande"] = len(rows)
    print(f"winogrande: {len(rows)} tasks")
    print("RENDER_DONE", json.dumps(summary))

if __name__ == "__main__":
    main()
