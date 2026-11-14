import hashlib, json, sys
from pathlib import Path
man = json.loads(Path(sys.argv[1]).read_text())
root = Path(sys.argv[2])
lines, problems, total = [], [], 0
for f in man["files"]:
    p = root / f["path"]
    if not p.is_file():
        problems.append("MISSING " + f["path"])
        lines.append(f"{f['sha256']}  {f['path']}\n")
        continue
    data = p.read_bytes()
    h = hashlib.sha256(data).hexdigest()
    total += len(data)
    if h != f["sha256"]:
        problems.append("HASH " + f["path"])
    if len(data) != f["bytes"]:
        problems.append(f"SIZE {f['path']} {len(data)}!={f['bytes']}")
    lines.append(f"{h}  {f['path']}\n")
digest = hashlib.sha256("".join(lines).encode("utf-8")).hexdigest()
expected = {f["path"] for f in man["files"]}
extras = sorted(str(p.relative_to(root)) for p in root.rglob("*")
                if p.is_file() and str(p.relative_to(root)) not in expected)
print(json.dumps({"checked": len(man["files"]), "problems": problems,
                  "total_bytes": total,
                  "expected_total_bytes": man["total_bytes"],
                  "tree_digest": digest,
                  "expected_tree_digest": man["tree_digest_sha256"],
                  "digest_match": digest == man["tree_digest_sha256"],
                  "extras": extras}, indent=1))
