#!/usr/bin/env python3
"""Build the frozen trial corpus from the ACE repo (origin/main worktree).

Deterministic: files sorted by relative path; text split into chunks of
~500 chars on paragraph/sentence boundaries (min 120 chars, hard cap 700).
Output: chunks.jsonl with {id, path, text}. Same input tree -> same ids.
"""
import json, os, re, sys

ROOT = sys.argv[1]
OUT = sys.argv[2]
exts = (".md", ".py", ".txt")
files = []
for dp, dn, fn in os.walk(ROOT):
    dn[:] = sorted(d for d in dn if d != ".git")
    for f in sorted(fn):
        if f.endswith(exts):
            files.append(os.path.relpath(os.path.join(dp, f), ROOT))
files.sort()

def chunk_text(text):
    paras = re.split(r"\n\s*\n", text)
    chunks, cur = [], ""
    for p in paras:
        p = p.strip()
        if not p:
            continue
        if len(cur) + len(p) + 1 <= 500:
            cur = (cur + "\n" + p) if cur else p
        else:
            if len(cur) >= 120:
                chunks.append(cur)
            elif cur:
                p = cur + "\n" + p
            # hard-split long paragraphs
            while len(p) > 700:
                cut = p.rfind(". ", 0, 700)
                cut = cut + 1 if cut > 200 else 700
                chunks.append(p[:cut].strip())
                p = p[cut:].strip()
            cur = p
    if len(cur) >= 120:
        chunks.append(cur)
    return [c for c in chunks if len(c) >= 120]

n = 0
with open(OUT, "w") as out:
    for rel in files:
        try:
            text = open(os.path.join(ROOT, rel), encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        for c in chunk_text(text):
            out.write(json.dumps({"id": n, "path": rel, "text": c}, ensure_ascii=False) + "\n")
            n += 1
print(f"CORPUS_DONE files={len(files)} chunks={n}")
