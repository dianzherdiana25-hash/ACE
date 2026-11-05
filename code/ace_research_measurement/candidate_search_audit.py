"""R8 read-only analysis of public task-level ACE candidate-search receipts.
Run --full-source with the pinned 167 KB original JSON to verify derivation.
A compact snapshot without the full source is SECONDARY evidence, not custody.
"""
import argparse
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path

COMMIT = "08da5702828285e0bd4d0f4dd8876f331ac89fe2"
BLOB = "069b4ffdf2f0a5a363d81bcec6ddfc4f2a5e098a"
MODES = ("fixed", "fixed-list", "enumerate", "beam")
BUDGETS = ("standard", "tight")
TASKS = ("original_linear", "negative_linear", "difference", "product_offset",
         "quadratic", "constant", "outside_grammar_floor_division",
         "outside_budget_polynomial")
SCHEMA = "ace.r8.candidate-search-task-snapshot.v1"

def _no_duplicate(pairs):
    d = {}
    for k, v in pairs:
        if k in d:
            raise ValueError("duplicate JSON key")
        d[k] = v
    return d

def _bad_constant(v):
    raise ValueError("nonfinite numeric constant: " + v)

def parse(raw):
    return json.loads(raw.decode("utf-8"), object_pairs_hook=_no_duplicate,
                      parse_constant=_bad_constant)

def git_blob(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()

def _read(path, limit):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
        raise ValueError("missing/symlink/oversize source")
    return path.read_bytes()

def from_full_source(raw, expected=BLOB):
    if len(raw) > 2_000_000 or git_blob(raw) != expected:
        raise ValueError("pinned source blob mismatch")
    doc = parse(raw)
    if (type(doc) is not dict or doc.get("schema") != 1 or
        doc.get("status") != "PUBLIC_SYNTHETIC_DEVELOPMENT_ONLY" or
        doc.get("scientific_decision") != "NOT_ASSESSED"):
        raise ValueError("unsupported source provenance")
    results = doc.get("results")
    if type(results) is not list or len(results) != 64:
        raise ValueError("incomplete source task grid")
    idx = {}
    for r in results:
        if type(r) is not dict:
            raise ValueError("malformed source row")
        key = (r.get("budget"), r.get("mode"), r.get("task"))
        if (key in idx or key[0] not in BUDGETS or
            key[1] not in MODES or key[2] not in TASKS):
            raise ValueError("duplicate/unsupported source row")
        idx[key] = r
    snap = {"schema": SCHEMA, "source": {
        "repository": "dianzherdiana25-hash/ACE", "commit": COMMIT,
        "path": "code/ace_candidate_search/results/summary.json",
        "git_blob_sha1": BLOB, "status": doc["status"],
        "scientific_decision": doc["scientific_decision"]},
        "holdout_cases_per_task": 3, "tasks": list(TASKS),
        "budgets": doc["budgets"], "arms": {}}
    for budget in BUDGETS:
        snap["arms"][budget] = {}
        for mode in MODES:
            rows = [idx[budget, mode, task] for task in TASKS]
            try:
                snap["arms"][budget][mode] = {
                    "correct": [r["result"]["holdout"]["correct"] for r in rows],
                    "absolute_error": [r["result"]["holdout"]["absolute_error"] for r in rows],
                    "total_work": [r["result"]["total_work"] for r in rows],
                    "candidates": [r["search"]["candidates"] for r in rows],
                    "cpu_seconds_total": sum(r["timing"]["cpu_seconds"] for r in rows)}
            except (KeyError, TypeError) as e:
                raise ValueError("missing source outcome field") from e
    return snap

def validate(snapshot):
    if type(snapshot) is not dict or snapshot.get("schema") != SCHEMA:
        raise ValueError("snapshot schema mismatch")
    source = snapshot.get("source")
    required = {"repository": "dianzherdiana25-hash/ACE", "commit": COMMIT,
                "path": "code/ace_candidate_search/results/summary.json",
                "git_blob_sha1": BLOB, "status": "PUBLIC_SYNTHETIC_DEVELOPMENT_ONLY",
                "scientific_decision": "NOT_ASSESSED"}
    if type(source) is not dict or any(source.get(k) != v for k,v in required.items()):
        raise ValueError("source provenance mismatch")
    if (type(snapshot.get("holdout_cases_per_task")) is not int or
        snapshot["holdout_cases_per_task"] != 3 or snapshot.get("tasks") != list(TASKS)):
        raise ValueError("task grid mismatch")
    budgets, arms = snapshot.get("budgets"), snapshot.get("arms")
    if (type(budgets) is not dict or set(budgets) != set(BUDGETS) or
        type(arms) is not dict or set(arms) != set(BUDGETS)):
        raise ValueError("budget grid mismatch")
    for budget in BUDGETS:
        cap = budgets[budget]
        if (type(cap) is not dict or set(cap) !=
            {"beam_width","max_candidates","max_depth","max_operations","max_work","shortlist"} or
            any(type(x) is not int or x <= 0 for x in cap.values())):
            raise ValueError("malformed limits")
        if (cap["max_work"] != (200000 if budget == "standard" else 300) or
            cap["max_candidates"] != (2000 if budget == "standard" else 5)):
            raise ValueError("changed budget ceiling")
        if type(arms[budget]) is not dict or set(arms[budget]) != set(MODES):
            raise ValueError("missing or extra mode")
        for mode in MODES:
            r = arms[budget][mode]
            if type(r) is not dict or set(r) != {
                "correct","absolute_error","total_work","candidates","cpu_seconds_total"}:
                raise ValueError("invalid task fields")
            for name in ("correct","absolute_error","total_work","candidates"):
                arr = r[name]
                if (type(arr) is not list or len(arr) != len(TASKS) or
                    any(type(x) is not int for x in arr)):
                    raise ValueError("noninteger or missing task observation")
            cpu = r["cpu_seconds_total"]
            if type(cpu) not in (int,float) or not math.isfinite(cpu) or cpu <= 0:
                raise ValueError("invalid CPU observation")
            for correct, err, work, count in zip(
                r["correct"],r["absolute_error"],r["total_work"],r["candidates"]):
                if not (0 <= correct <= 3 and err >= 0 and (err == 0) == (correct == 3)):
                    raise ValueError("contradictory correctness")
                if not (0 < work <= cap["max_work"] and 0 < count <= cap["max_candidates"]):
                    raise ValueError("work/candidate bound violation")

def _sign(wins, losses):
    n = wins+losses
    if n == 0: return None
    return sum(math.comb(n, k) for k in range(wins,n+1)) / (2**n)

def audit(snapshot):
    validate(snapshot)
    summaries = {}
    for budget in BUDGETS:
        summaries[budget] = {}
        for mode in MODES:
            r = snapshot["arms"][budget][mode]
            solved = [v == 3 for v in r["correct"]]
            summaries[budget][mode] = {
                "solved": sum(solved), "total_tasks": 8,
                "correct_cases": sum(r["correct"]), "total_cases": 24,
                "total_work": sum(r["total_work"]),
                "candidate_count": sum(r["candidates"]),
                "cpu_seconds_total": r["cpu_seconds_total"],
                "solved_tasks": [t for t,ok in zip(TASKS,solved) if ok]}
    comparisons = {}
    for budget in BUDGETS:
        for a,b in (("beam","enumerate"),("beam","fixed-list")):
            ra,rb = snapshot["arms"][budget][a], snapshot["arms"][budget][b]
            wins = sum(x == 3 and y != 3 for x,y in zip(ra["correct"],rb["correct"]))
            losses = sum(y == 3 and x != 3 for x,y in zip(ra["correct"],rb["correct"]))
            comparisons[budget+":"+a+"_vs_"+b] = {
                "wins":wins,"losses":losses,"ties":8-wins-losses,
                "one_sided_unadjusted_sign_p":_sign(wins,losses),
                "actual_work_ratio":summaries[budget][a]["total_work"]/summaries[budget][b]["total_work"]}
    return {"schema":"ace.r8.candidate-search-task-audit.v1",
            "source":deepcopy(snapshot["source"]),"by_budget":summaries,
            "pairwise":comparisons,"observational_unit":"8 researcher-designed tasks, 3 holdout instances each",
            "actual_compute_matched":False,"independent_mechanism_lineage_verified":False,
            "snapshot_is_signed":False,
            "science_gate":"NOT_CONFIRMED",
            "limitations":["Public synthetic evaluation, not sealed confirmatory bank.",
                "A task is not automatically an independent mechanism family.",
                "Spend differs despite the same maximum allowed budget.",
                "Sign test p-values are nominal and uncorrected for selection.",
                "Compact snapshot alone cannot verify original full-source bytes."]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--snapshot",type=Path,default=Path(__file__).with_name("candidate_search_snapshot.json"))
    p.add_argument("--full-source",type=Path)
    p.add_argument("--output",type=Path)
    args=p.parse_args()
    snapshot=parse(_read(args.snapshot,50000))
    if args.full_source and from_full_source(_read(args.full_source,2000000)) != snapshot:
        raise ValueError("snapshot disagrees with pinned original")
    result=audit(snapshot)
    result["source_validation"] = "FULL_PIN_VERIFIED" if args.full_source else "DERIVED_SNAPSHOT_ONLY"
    out=json.dumps(result,sort_keys=True,indent=2)+"\n"
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(out,encoding="utf-8")
    else: print(out,end="")

if __name__ == "__main__": main()
