"""Post-score enumeration of shorter motifs that alias a stored E1.4r receipt."""

import argparse
import json
from collections import Counter
from itertools import product
from pathlib import Path

from e13.contract import canonical_json

from .e14g_audit import verify
from .e14g_bank import sha
from .e14h_route import read
from .e14p_graph import minimum, paths
from .e14r_audit import check_block
from .e14r_run import frozen


def enumerate_aliases(bank, report):
    blocks = {str(b["index"]): b for b in bank["blocks"]}
    totals = Counter()
    rows = []
    for row in report["rows"]:
        index = row["episode"]
        block = blocks.pop(index)
        check_block(block, row)
        packed = row["modes"]["packed"]
        routes = paths(packed["graph"])
        length = len(block["artifact"]["word"])
        labels = {v["label"] for name, v in packed["outcomes"].items()
                  if name in ("identity", "last_flip", "penultimate_flip")}
        eligible = list(word for n in range(5, length) for word in product((1, 2), repeat=n))
        alias = Counter()
        identity = packed["outcomes"]["identity"]["label"]
        for word in eligible:
            cost = minimum(routes, word)
            if cost in labels:
                alias["any"] += 1
            if cost == identity:
                alias["identity"] += 1
        record = {"lineage": int(index), "length": length, "enumerated": len(eligible),
                  "alias_any": alias["any"], "alias_identity": alias["identity"]}
        rows.append(record)
        totals.update({k: record[k] for k in ("enumerated", "alias_any", "alias_identity")})
    verify(not blocks, "missing lineage")
    return {"kind": "post_score_structural_audit", "lineages": sorted(rows, key=lambda r: r["lineage"]),
            "totals": dict(totals)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("score", type=Path)
    args = parser.parse_args()
    bank, digest, _ = frozen()
    report = read(args.score)
    verify(report["bank_sha256"] == digest and report["status"] == "completed", "wrong score report")
    audit = enumerate_aliases(bank, report)
    audit["score_sha256"] = sha(args.score.read_bytes())
    print(canonical_json(audit).decode())


if __name__ == "__main__":
    main()
