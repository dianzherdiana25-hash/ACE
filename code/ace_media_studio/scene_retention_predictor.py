"""Skor risiko retensi dari ciri naskah dengan koefisien yang dapat diperiksa."""
import argparse
from collections import Counter
from hashlib import sha256
from pathlib import Path
import re
import sys

from ._contracts import (ContractError, canonical, checked, decode, entries,
                         identifier, integer, obj, read, schema, text)


WORDS = re.compile(r"[^\W_]+", re.UNICODE)
WEIGHTS = {"tempo_over": -100, "repeat": -25, "no_action": -800,
           "source_hook": 600, "long_intro": -600, "returns_to_promise": 400}


def _tokens(raw):
    return [item.casefold() for item in WORDS.findall(raw) if len(item) >= 2]


def forecast(plan, expected):
    checked(plan, expected)
    schema(plan, "ace.media.retention-plan.v1", ("baseline_bp", "roles", "scenes"))
    baseline = integer(plan["baseline_bp"], "Prior asumsi", 0, 10000)
    roles = obj(plan["roles"], ("action_terms", "promise_terms"))
    verb_tokens = [_tokens(text(term, "Kata kerja", 30)) for term in entries(roles["action_terms"], 30, 1)]
    if any(len(term) != 1 for term in verb_tokens):
        raise ContractError("Istilah aksi perlu tepat satu token.")
    verbs = {term[0] for term in verb_tokens}
    promise = {word for raw in entries(roles["promise_terms"], 20, 1) for word in _tokens(text(raw, "Topik", 40))}
    if not verbs or not promise:
        raise ContractError("Kosakata aksi dan janji harus memiliki token sah.")
    scoring = []
    history = 0
    used = set()
    mentioned = set()
    for index, item in enumerate(entries(plan["scenes"], 100, 1)):
        obj(item, ("id", "source_ref", "narration", "duration_ms", "has_visual_action"))
        key = identifier(item["id"], "Adegan")
        if key in used or type(item["has_visual_action"]) is not bool:
            raise ContractError("ID adegan ganda atau penanda aksi visual tidak sah.")
        used.add(key)
        script = text(item["narration"], "Isi naskah", 1200)
        pointer = text(item["source_ref"], "Pointer naskah")
        time = integer(item["duration_ms"], "Durasi adegan", 500, 240000)
        tokens = _tokens(script)
        counts = Counter(tokens)
        speed = len(tokens) * 60_000 // time
        repeats = min(40, sum(min(times, 3) for word, times in counts.items() if word in mentioned and len(word) >= 4))
        touches = promise & counts.keys()
        features = {"tempo_over": min(40, max(0, speed - 180) // 5),
                    "repeat": repeats, "no_action": int(not (verbs & counts.keys()) and not item["has_visual_action"]),
                    "source_hook": int(index == 0 and "?" in script and bool(touches)),
                    "long_intro": int(index == 0 and time > 10_000),
                    "returns_to_promise": int(index > 0 and bool(touches))}
        gains = {name: features[name] * weight for name, weight in WEIGHTS.items()}
        history += sum(gains.values())
        score = max(0, min(10000, baseline + history))
        scoring.append({"id": key, "source_ref": pointer, "narration_sha256": sha256(script.encode()).hexdigest(),
                        "words_per_minute": speed, "features": features, "deltas_bp": gains, "proxy_score_bp": score})
        mentioned.update(tokens)
    return {"schema": "ace.media.retention-proxy.v1", "plan_sha256": expected,
            "kind": "unvalidated_script_proxy", "weights_bp": WEIGHTS, "baseline_bp": baseline, "scenes": scoring,
            "lowest_proxy_scene": min(scoring, key=lambda row: (row["proxy_score_bp"], row["id"]))["id"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        receipt = forecast(decode(read(args.plan)), args.expect_sha256)
        sys.stdout.buffer.write(canonical(receipt) + b"\n")
    except (OSError, ValueError, TypeError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
