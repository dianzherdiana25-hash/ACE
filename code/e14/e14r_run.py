"""Test one diagnostic label for reuse of a stored artifact."""

import argparse
import gzip
import json
import os
import random
import shutil
from contextlib import contextmanager
from pathlib import Path

from e13.contract import canonical_json, input_value, integer, read_json, require_fields
from e13.evaluator.run_ledger import Arm, RunPlan, run_arms
from e13.isolation import READY_MARKER, _sandbox_python

from .e14g_audit import verify
from .e14g_bank import sha
from .e14g_isolation import validate_boundary
from .e14g_run import REPO
from .e14h_route import read
from .e14p_audit import check_lineage
from .e14p_bank import render_graph
from .e14p_graph import minimum, paths
from .e14p_run import frozen as p_frozen, prediction_metrics
from .e14q_run import frozen as q_frozen, inventory as q_inventory, stage as q_stage
from .e14r_worker import MODES, mappings

BANK = "evidence/e14/e14r_public_bank_v1.json.gz"
LOCK = "design/e1.4/E14R_LOCK_v1.json"
WORKER = "code/e14/e14r_worker.py"
SOURCE = "code/e14/e14r_run.py"
LINEAGES = "evidence/e14/e14p_public_development_v1.json.gz"
FILES = (BANK, WORKER, SOURCE, LINEAGES, "design/e1.4/E14Q_LOCK_v1.json",
         "design/e1.4/E14R_PROTOCOL_v1.md", "code/e14/e14r_audit.py", "code/e14/test_e14r.py")
SEED = 143401
CELLS = ("identity", "last_flip", "penultimate_flip", "complement", "shorter")


def lineage_artifacts():
    bank, digest, _ = p_frozen()
    source = read(REPO / LINEAGES)
    verify(source["bank_sha256"] == digest, "source report does not match E1.4p bank")
    blocks = {(str(b["slot"]), str(len(b["source_word"]))): b for b in bank["blocks"]}
    artifacts = []
    for row in source["rows"]:
        block = blocks.pop((row["block"].split(":")[1], row["episode"]))
        artifact = check_lineage(block, row)
        verify(artifact is not None, "lineage did not emit an artifact")
        artifacts.append(artifact)
    verify(not blocks and len(artifacts) == 12, "missing stored lineage")
    return artifacts


def truths(artifact):
    word = tuple(artifact["word"])
    words = (*mappings(word), tuple(3 - event for event in word), word[:-1])
    return dict(zip(CELLS, words, strict=True))


def prior_graphs():
    used = q_inventory()
    bank, _, _ = q_frozen()
    used.update(sha(canonical_json(raw)) for block in bank["blocks"] for raw in block["probes"])
    return used


def build():
    used, rng = prior_graphs(), random.Random(SEED)
    blocks = []
    for index, artifact in enumerate(lineage_artifacts()):
        words = list(truths(artifact).values())
        calibration = render_graph(rng, used, exclude=tuple(words))
        probes = []
        for i, word in enumerate(words):
            other = tuple(w for j, w in enumerate(words) if j != i and len(w) >= len(word))
            probes.extend(render_graph(rng, used, hit=word, exclude=other) for _ in range(2))
        rng.shuffle(probes)
        blocks.append({"index": index, "artifact": artifact, "calibration": calibration, "probes": probes})
    return {"version": 1, "seed": SEED, "blocks": blocks}


def manifest():
    return {"version": 1, "sha256": {p: sha((REPO / p).read_bytes()) for p in FILES}}


def frozen():
    q_frozen()
    lock = json.loads((REPO / LOCK).read_bytes())
    verify(lock == manifest(), "E1.4r freeze manifest mismatch")
    raw = gzip.decompress((REPO / BANK).read_bytes())
    return json.loads(raw), sha(raw), lock


def schedule(bank):
    arms = {Arm("G", "unrelated", "receipt", str(b["index"]), 0, "inheritance"): b for b in bank["blocks"]}
    verify(len(arms) == 12, "incorrect number of lineages")
    return arms


@contextmanager
def stage():
    with q_stage() as root:
        shutil.copyfile(REPO / WORKER, root / "e14/e14r_worker.py")
        yield root


def invoke(root, artifact, mode, *, observed=False, label=None):
    cmd = ("import sys; sys.path.insert(0,'/solver'); from e14.e14r_worker import main; "
           f"sys.stderr.buffer.write({READY_MARKER!r}); sys.stderr.flush(); main()")
    packet = {"artifact": artifact, "mode": mode, "observed": observed, "label": label}
    raw, wall = _sandbox_python(["-c", cmd], canonical_json(packet), solver=root)
    result = read_json(raw, 24_576)
    require_fields(result, "graph", "selected", "cpu_us", "rss_kib")
    meter = {"cpu_us": integer(result.pop("cpu_us"), 0, 1_000_000),
             "rss_kib": integer(result.pop("rss_kib"), 1, 131_072),
             "wall_us": integer(wall, 0, 3_000_000)}
    return result, meter


def evaluate(root, block):
    artifact = block["artifact"]
    probes = [paths(raw) for raw in block["probes"]]
    modes, meters = {}, []
    for mode in MODES:
        proposal, meter = invoke(root, artifact, mode)
        meters.append(meter)
        graph = block["calibration"] if mode == "passive" else proposal["graph"]
        verify(proposal["selected"] == [], "worker released an uncalibrated motif")
        input_value("G", graph)
        verify(graph["nodes"] <= 16 and len(graph["edges"]) <= 16, "calibration graph over budget")
        routes = paths(graph)
        outcomes = {}
        for name, truth in truths(artifact).items():
            label = minimum(routes, truth)
            result, meter = invoke(root, artifact, mode, observed=True, label=label)
            meters.append(meter)
            verify(result["graph"] == proposal["graph"], "query changed after observation")
            selected = result["selected"]
            gold = [minimum(route, truth) for route in probes]
            outcomes[name] = {"selected": selected, "label": label,
                              **prediction_metrics(selected, probes, gold)}
        modes[mode] = {"graph": graph, "outcomes": outcomes}
    main = modes["packed"]["outcomes"]["identity"]
    return {"status": "scored", "total": 10, "correct": main["covered"] - main["errors"],
            "artifact_sha256": sha(canonical_json(artifact)), "modes": modes, "resources": meters}


def summary(rows):
    scores = {}
    for mode in MODES:
        results = {}
        for name in CELLS:
            outcomes = [row["modes"][mode]["outcomes"][name] for row in rows]
            results[name] = {
                "full": sum(v["covered"] == 10 and v["errors"] == 0 for v in outcomes),
                "selected": sum(bool(v["selected"]) for v in outcomes),
                "covered": sum(v["covered"] for v in outcomes),
                "errors": sum(v["errors"] for v in outcomes),
                "false_positive": sum(v["false_positive"] for v in outcomes),
            }
        graphs = [r["modes"][mode]["graph"] for r in rows]
        scores[mode] = {"cells": results, "labels": len(rows) * len(CELLS),
                        "nodes": sum(g["nodes"] for g in graphs), "edges": sum(len(g["edges"]) for g in graphs)}
    packed = scores["packed"]["cells"]
    mapped = {mode: sum(results["cells"][name]["full"] for name in CELLS[:3])
              for mode, results in scores.items()}
    go = (all(packed[name]["full"] >= 10 for name in CELLS[:3])
          and mapped["packed"] >= max(mapped["chain"], mapped["passive"]) + 6
          and packed["complement"]["covered"] == 0)
    return {"mapped": "GO" if go else "HOLD",
            "robust": "GO" if go and packed["shorter"]["errors"] == 0 else "HOLD",
            "lineages": len(rows), "worlds": len(rows) * len(CELLS), "scores": scores}


def run(ledger, output):
    bank, digest, lock = frozen()
    boundary = validate_boundary()
    arms = schedule(bank)
    plan = RunPlan(lock["sha256"][WORKER], digest, lock["sha256"][SOURCE],
                   sha(canonical_json(lock)), SEED, 10, tuple(arms))
    with stage() as root:
        raw, _ = _sandbox_python(["-c", "import importlib.util,sys; sys.path.insert(0,'/solver'); "
                                  "print(all(importlib.util.find_spec(m) is None for m in "
                                  "('e14.e14p_graph','e14.e14r_run','e14.e14r_audit')))"], solver=root)
        verify(raw.strip() == b"True", "receipt worker sees evaluator")
        boundary["checks"]["receipt_stage_without_evaluator"] = True
        rows = run_arms(ledger, plan, lambda arm: evaluate(root, arms[arm]))
    report = {"status": "completed", "version": 1, "bank_sha256": digest, "plan_sha256": plan.sha256,
              "boundary": boundary, "rows": rows, "summary": summary(rows)}
    temporary = output.with_name(output.name + ".tmp")
    temporary.write_bytes(gzip.compress(canonical_json(report), mtime=0))
    os.replace(temporary, output)
    print(json.dumps(report["summary"], sort_keys=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="mode", required=True)
    subparsers.add_parser("freeze")
    runner = subparsers.add_parser("run")
    runner.add_argument("ledger", type=Path)
    runner.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.mode == "freeze":
        (REPO / BANK).write_bytes(gzip.compress(canonical_json(build()), mtime=0))
        (REPO / LOCK).write_text(json.dumps(manifest(), indent=2, sort_keys=True) + "\n")
    else:
        run(args.ledger, args.output)


if __name__ == "__main__":
    main()
