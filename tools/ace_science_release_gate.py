"""Independent, read-only ACE coordinator science release gate (HOLD-only).

Audits H7 public result rows without importing its learner, reconstructing
terminal inputs, target truth, and feature-prediction scores. Consumes *fixed*
pinned R1/R8 public receipts as additional negative controls. This gate
cannot authorize scientific promotion, even when all engineering audits pass.
"""
from __future__ import annotations
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import random
import sys

PINS = {
    "h7": "6cbd2d5ff2b2894bf0cca6e3cd328f28800ccbff5631331371c9f0759590b000",
    "r1": "3a63234ab34d977b98ddfa9393e0419e854d876d5b91b9d86db6624df15d4e0a",
    "r8": "ab137f587eaf134482ce745778a48cc2b81a537be525c8627d4b15e591643d7f",
}
BASES = ("equal_counts", "a_mod3", "contains_ab", "dyck")
FROZEN = ("aaaaa", "aaabb", "ababa", "bbbaa", "bbbbb")
METHODS = ("h7", "base", "fixed5", "expanded2to7")


class IntegrityHalt(Exception):
    pass


def expect(yes, reason):
    if not yes:
        raise IntegrityHalt(reason)


def sha(obj):
    return hashlib.sha256(json.dumps(obj, separators=(",", ":"), sort_keys=True).encode()).hexdigest()


def words(low, high):
    return ["".join(seq) for n in range(low, high + 1)
            for seq in itertools.product("ab", repeat=n)]


def target_patterns():
    out = []
    for b, base in enumerate(BASES):
        for n in (5, 6, 7):
            already = set()
            for pair in range(2):
                rng = random.Random(2026110601 + 100000 * b + 1000 * n + pair)
                for attempt in range(10000):
                    pat = "".join("ab"[rng.randrange(2)] for _ in range(n))
                    if pat.count("a") >= 2 and pat.count("b") >= 2 and pat not in already:
                        already.add(pat)
                        out.append((base, n, pat, attempt))
                        break
                else:
                    raise IntegrityHalt("target generator exhausted")
    expect(len(out) == 24, "wrong target count")
    return out


def splits(idx, target):
    pool = words(6, 12)
    train = random.Random(43000000 + idx).sample(pool, 128)
    remaining = sorted(set(pool) - set(train), key=lambda s: (len(s), s))
    val = random.Random(44000000 + idx).sample(remaining, 128)
    natural = random.Random(45000000 + idx).sample(words(13, 16), 256)
    selected = set(natural)
    pos, neg = [], []
    rng = random.Random(46000000 + idx)
    attempts = 0
    for attempts in range(1, 200001):
        if len(pos) == 128 and len(neg) == 128:
            break
        n = rng.randrange(13, 21)
        candidate = "".join("ab"[rng.randrange(2)] for _ in range(n))
        if candidate in selected:
            continue
        if target in candidate and len(pos) < 128:
            pos.append(candidate)
            selected.add(candidate)
        elif target not in candidate and len(neg) < 128:
            neg.append(candidate)
            selected.add(candidate)
    expect(len(pos) == len(neg) == 128, "balanced pool exhausted")
    balanced = sorted(pos + neg, key=lambda s: (len(s), s))
    expect(len(set(train + val + natural + balanced)) == 768, "train/terminal overlap")
    return train, val, natural, balanced, attempts


def fit_candidate(train, val, lengths):
    positives = [w for w in train if w[1]]
    # train items are pairs (word, label); candidate patterns appear in positive words.
    positives = [w for w, y in train if y]
    candidates = sorted({w[i:i+n] for w in positives for n in lengths
                         for i in range(len(w)-n+1)}, key=lambda s: (len(s), s))
    accepted = None
    charged = 0
    if sum(y for _, y in train) >= 2 and sum(y for _, y in val) >= 2:
        for candidate in candidates:
            charged += len(train)
            if any((candidate in w) != label for w, label in train):
                continue
            charged += len(val)
            if not any((candidate in w) != label for w, label in val):
                accepted = candidate
                break
    return accepted, len(candidates), charged


def fixed_candidate(train, val):
    best = min(FROZEN, key=lambda p: (sum((p in w) != y for w, y in train),
                                      FROZEN.index(p)))
    good = (sum(y for _, y in train) >= 2 and sum(y for _, y in val) >= 2
            and all((best in w) == y for w, y in train + val))
    return best if good else None


def score(feature, target, corpus):
    expected = [(target in w) for w in corpus]
    predicted = [bool(feature and feature in w) for w in corpus]
    first = next(({"word":w, "expected_residual":int(y),
                   "predicted_residual":int(p)}
                  for w,y,p in zip(corpus, expected, predicted) if y != p), None)
    return {"correct":sum(y == p for y,p in zip(expected,predicted)),
            "total":len(corpus), "first_error":first}


def audit_h7(doc):
    expect(type(doc) is dict and doc.get("schema") == "ace.coordinator.h7.crossclass.public.v1",
           "invalid H7 schema")
    expect(doc.get("r1_source_head") == "8952c8ac55613e61b362841f4722c66a5aa990b3",
           "wrong pinned H7 source")
    expect(doc.get("protocol_commit") == "e4280bb3ebf4372a4ee69834e55dd0c8085b68b6",
           "wrong prescore source")
    expect(doc.get("scientific_decision") == "NOT_ASSESSED_NO_PROMOTION",
           "altered science status")
    rows = doc.get("rows")
    expect(type(rows) is list and len(rows) == 24, "invalid H7 world count")
    expect(doc.get("label_budget", {}).get("total_task_specific_judgments") == 18432,
           "invalid H7 budget")
    aggregates = {}
    for i, (record, (base, n, target, draw)) in enumerate(zip(rows, target_patterns())):
        expect(type(record) is dict and
               (record.get("id"),record.get("base"),record.get("length"),
                record.get("target"),record.get("target_draw_attempt")) ==
               (i,base,n,target,draw), f"target lineage mismatch: {i}")
        tr, va, natural, balanced, attempts = splits(i, target)
        for name, expected in (("query_sha256",sha(tr)),("validation_sha256",sha(va)),
                               ("natural_sha256",sha(natural)),("balanced_sha256",sha(balanced))):
            expect(record.get(name) == expected, f"{i}: source split hash {name}")
        expect(record.get("balanced_sampling_attempts") == attempts,
               f"{i}: sampling work receipt")
        tr_rows = [(word,target in word) for word in tr]
        va_rows = [(word,target in word) for word in va]
        expect(record.get("train_residual_positives") == sum(y for _,y in tr_rows)
               and record.get("validation_residual_positives") == sum(y for _,y in va_rows),
               f"{i}: query/support receipt")
        h7, count, _ = fit_candidate(tr_rows, va_rows, range(2,6))
        bigger, size, charged = fit_candidate(tr_rows, va_rows, range(2,8))
        fixed = fixed_candidate(tr_rows, va_rows)
        learned=record.get("h7_representation")
        expanded=record.get("expanded")
        expect(type(learned) is dict and type(expanded) is dict,
               f"{i}: invalid fit record")
        expect(learned.get("pattern") == h7 and learned.get("accepted") is (h7 is not None)
               and learned.get("candidates") == count and count <= 100,
               f"{i}: false source H7 feature fit")
        expect(expanded.get("pattern") == bigger and expanded.get("accepted") is (bigger is not None)
               and expanded.get("candidates") == size and
               expanded.get("comparisons_charged") == charged and
               expanded.get("comparisons_upper_bound") == size*256,
               f"{i}: false expanded feature fit")
        expect(record.get("fixed_h6") == fixed, f"{i}: false fixed control")
        features = {"h7":h7,"base":None,"fixed5":fixed,"expanded2to7":bigger}
        scores=record.get("methods")
        expect(type(scores) is dict and set(scores) == set(METHODS),
               f"{i}: method roster mismatch")
        for method, feature in features.items():
            for name, corpus in (("natural",natural),("balanced",balanced)):
                expect(scores[method][name] == score(feature,target,corpus),
                       f"{i}: forged {method}/{name} score or first error")
        false_accept = bool(h7 is not None and scores["h7"]["balanced"]["correct"] < 231)
        expect(record.get("false_accepted_feature") is false_accept,
               f"{i}: false accepted feature report")
        expect(record.get("forced_final_predictions") == 512 and
               record.get("semantic_final_abstentions") == 0,
               f"{i}: fake semantic abstention")
        k=str(n)
        aggregates.setdefault(k,[]).append((record,features))
    reported=doc.get("summary",{})
    expect(reported.get("total_forced_final_predictions") == 12288
           and reported.get("open_world_status") == "OPEN_WORLD_HOLD_FORCED_PREDICTIONS",
           "open world gate changed")
    for k,group in aggregates.items():
        reported_group=reported["by_length"][k]
        expect(reported_group["tasks"] == 8, "invalid group count")
        for method in METHODS:
            for split in ("natural","balanced"):
                total = sum(x["methods"][method][split]["correct"] for x,_ in group)
                expect(reported_group["methods"][method][split+"_correct"] == total,
                       f"{k}: aggregate {method} {split} corrupted")
                expect(reported_group["methods"][method][split+"_accuracy"] ==
                       round(total / 2048,6), f"{k}: fake precision {method}/{split}")
        expect(reported_group["h7_accept"] ==
               sum(feature["h7"] is not None for _,feature in group),
               f"{k}: incorrect h7 acceptance count")
        expect(reported_group["expanded_accept"] ==
               sum(feature["expanded2to7"] is not None for _,feature in group),
               f"{k}: incorrect comparator acceptance count")
    gates=reported.get("precommitted_gates",{})
    expect(gates == {"G1_inclass_fivegram":True,
                     "G2_outclass_abstain_from_feature_and_no_false_accept":True,
                     "G3_expanded_grammar_diagnostic":True,
                     "G4_open_world_safe_to_deploy":False},
           "science gate changed")
    # The H7 grammar has a maximum substring length of five; a positive in-class
    # result does not authorize class-level extrapolation or real-world release.
    return {"h7_worlds_independently_recomputed":24,
            "h7_terminal_predictions_recomputed":12288,
            "h7_public_methodology":"RESTRICTED_GRAMMAR_ONLY",
            "h7_scientific_status":"NOT_ASSESSED"}


def pinned(path, which):
    body=Path(path).read_bytes()
    expect(hashlib.sha256(body).hexdigest()==PINS[which],
           f"{which}: published source evidence SHA256 mismatch")
    try:
        return json.loads(body)
    except (ValueError, UnicodeError) as exc:
        raise IntegrityHalt(f"{which}: invalid JSON") from exc


def assess(h7, r1, r8):
    detail=audit_h7(h7)
    expect(r1.get("scientific_decision") == "NOT_ASSESSED_NO_AUTOMATIC_PROMOTION",
           "R1 science verdict rewritten")
    m=r1.get("metrics",{})
    expect(m.get("clean_tasks_at_90") == 5 and m.get("noisy_tasks_at_90") == 3 and
           m.get("unprotected_drift_tasks") == 24, "R1 claimed task coverage changed")
    expect(r8.get("design",{}).get("known_true_delta") == 0 and
           r8.get("counts") == {"naive_delta_at_least_10pp":42,
                                 "public_screen_pass":9},
           "R8 null-false-discovery canary changed")
    expect(r8.get("claim") == "PUBLIC_NULL_DIAGNOSTIC_ONLY_NO_REAL_ACE",
           "R8 claim was promoted")
    return {"schema":"ace.coordinator.science_release_gate.v1",
            "engineering_evidence":"PASS_INDEPENDENT_PUBLIC_REPLAY",
            "h7":detail,
            "r1_independent_complexity":"FAIL_PREDECLARED_TRANSFER",
            "r8_null_diagnostic":"NONZERO_FALSE_PASSES_9_OF_512",
            "redteam_release_blockers":"OPEN_ISSUE_53",
            "independent_sealed_evaluator":"NOT_AVAILABLE",
            "scientific_decision":"NOT_ASSESSED",
            "promotion_decision":"BLOCK_RELEASE"}


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("--h7",required=True,type=Path)
    parser.add_argument("--r1",required=True,type=Path)
    parser.add_argument("--r8",required=True,type=Path)
    args=parser.parse_args(argv)
    try:
        result=assess(pinned(args.h7,"h7"),pinned(args.r1,"r1"),pinned(args.r8,"r8"))
    except (IntegrityHalt, KeyError, TypeError, IndexError, OSError) as exc:
        print(json.dumps({"promotion_decision":"HALT_INTEGRITY","error":str(exc)}))
        return 2
    print(json.dumps(result,indent=2,sort_keys=True))
    return 0


if __name__=="__main__":
    sys.exit(main())
