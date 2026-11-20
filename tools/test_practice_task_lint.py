"""Tes linter tugas praktik 10 keluarga: 10 sah + 3 cacat (acak, tak idempoten, bocor) — AG32."""
from __future__ import annotations

import json
from pathlib import Path
import random
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from tools.practice_task_lint import (
    PRACTICE_FAMILIES,
    SCHEMA,
    lint_practice_task,
    lint_practice_tasks,
)


SCRIPT = Path(__file__).with_name("practice_task_lint.py")


def _make_exec_evaluator(fn_name: str, cases: list[tuple[tuple, object]]) -> str:
    return (
        "def evaluate(solution, test_cases=None):\n"
        "    ns = {}\n"
        "    exec(solution, ns, ns)\n"
        f"    fn = ns.get({fn_name!r})\n"
        "    if not callable(fn):\n"
        "        return {'passed': False, 'reason': 'missing_fn'}\n"
        "    for args, expected in test_cases:\n"
        "        if fn(*args) != expected:\n"
        "            return {'passed': False, 'reason': 'mismatch'}\n"
        "    return {'passed': True, 'score': 1.0}\n"
    )


def _ten_valid_family_tasks() -> list[dict]:
    specs = [
        ("t-dedup", "dedup_csv", "Tulis `dedup_csv(rows)` menjaga urutan awal baris CSV.", "dedup_csv",
         "def dedup_csv(rows):\n    return list(dict.fromkeys(rows))\n",
         [([["a,1", "b,2", "a,1"]], ["a,1", "b,2"])]),
        ("t-tax", "progressive_tax", "Tulis `calc_tax(amount)` untuk dua bracket progresif 10%/20%.", "calc_tax",
         "def calc_tax(amount):\n    return amount * 10 // 100 if amount <= 100 else 10 + (amount - 100) * 20 // 100\n",
         [([100], 10), ([150], 20)]),
        ("t-json", "json_parser", "Tulis `parse_obj(text)` memvalidasi JSON objek.", "parse_obj",
         "import json\ndef parse_obj(text):\n    v = json.loads(text)\n    return v if isinstance(v, dict) else None\n",
         [(['{"a":1}'], {"a": 1}), (["[]"], None)]),
        ("t-bfs", "bfs", "Tulis `shortest_path(adj, s, t)` dengan BFS.", "shortest_path",
         "from collections import deque\ndef shortest_path(adj, s, t):\n    q, seen = deque([(s, 0)]), {s}\n    while q:\n        u, d = q.popleft()\n        if u == t:\n            return d\n        for v in adj.get(u, []):\n            if v not in seen:\n                seen.add(v)\n                q.append((v, d + 1))\n    return -1\n",
         [([{"a": ["b"], "b": ["c"]}, "a", "c"], 2)]),
        ("t-backoff", "backoff", "Tulis `next_delay(base, attempt, cap)` eksponensial terbatas.", "next_delay",
         "def next_delay(base, attempt, cap):\n    return min(cap, base * (2 ** attempt))\n",
         [([1, 2, 10], 4), ([2, 5, 10], 10)]),
        ("t-sim", "text_similarity", "Tulis `jaccard(a, b)` atas himpunan token.", "jaccard",
         "def jaccard(a, b):\n    sa, sb = set(a.split()), set(b.split())\n    return len(sa & sb) / len(sa | sb) if (sa | sb) else 0.0\n",
         [([ "satu dua", "dua tiga" ], 1 / 3)]),
        ("t-sec", "security_detector", "Tulis `has_secret(text)` mendeteksi prefix token rahasia.", "has_secret",
         "def has_secret(text):\n    return 'SECRET_' in text or '..' in text\n",
         [(["aman"], False), (["kunci SECRET_ABC"], True)]),
        ("t-bug", "bug_repair", "Perbaiki `safe_div(a, b)` agar mengembalikan 0 bila pembagi 0.", "safe_div",
         "def safe_div(a, b):\n    return 0 if b == 0 else a / b\n",
         [([10, 2], 5), ([10, 0], 0)]),
        ("t-bsearch", "binary_search", "Tulis `bsearch(arr, x)` mengembalikan indeks atau -1.", "bsearch",
         "def bsearch(arr, x):\n    lo, hi = 0, len(arr) - 1\n    while lo <= hi:\n        mid = (lo + hi) // 2\n        if arr[mid] == x:\n            return mid\n        lo, hi = (mid + 1, hi) if arr[mid] < x else (lo, mid - 1)\n    return -1\n",
         [([[1, 3, 5, 7], 5], 2), ([[1, 3, 5], 4], -1)]),
        ("t-lru", "lru_cache", "Tulis `lru_keys(cap, ops)` yang mempertahankan cap terbaru.", "lru_keys",
         "from collections import OrderedDict\ndef lru_keys(cap, ops):\n    od = OrderedDict()\n    for k in ops:\n        od.pop(k, None)\n        od[k] = 1\n        if len(od) > cap:\n            od.popitem(last=False)\n    return list(od.keys())\n",
         [([2, ["a", "b", "a", "c"]], ["a", "c"])]),
    ]
    return [
        {
            "id": tid,
            "family": family,
            "prompt": prompt,
            "reference_solution": code,
            "test_cases": cases,
            "evaluator_code": _make_exec_evaluator(fn_name, cases),
        }
        for tid, family, prompt, fn_name, code, cases in specs
    ]


class PracticeTaskLintTests(unittest.TestCase):
    def test_ten_valid_families_all_pass_and_cli_exits_zero(self) -> None:
        self.assertEqual(len(PRACTICE_FAMILIES), 10)
        tasks = _ten_valid_family_tasks()
        report = lint_practice_tasks(tasks)
        self.assertEqual(report["schema"], SCHEMA)
        self.assertTrue(report["all_valid"], report)
        self.assertEqual(report["summary"]["valid_tasks"], 10)
        self.assertTrue(report["summary"]["all_ten_families_covered"])

        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "valid_10_families.json"
            path.write_text(json.dumps(tasks), encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), "--tasks", str(path), "--require-all-families"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(json.loads(proc.stdout)["summary"]["valid_tasks"], 10)

    def test_three_defects_random_non_idempotent_and_answer_leak_caught(self) -> None:
        base = _ten_valid_family_tasks()[0]

        # Cacat 1: penilai acak (non-deterministik via random)
        random_defect = {
            **base,
            "id": "bad-random",
            "evaluator": lambda sol, _cases: {"passed": random.choice([True, False]), "r": random.random()},
        }
        res_random = lint_practice_task(random_defect)
        self.assertFalse(res_random["valid"])
        self.assertIn("non_deterministic_evaluator", res_random["reasons"])

        # Cacat 2: penilai tak idempoten (memutasi state / argumen antar panggilan)
        state = {"calls": 0}

        def non_idempotent_eval(_sol, cases):
            state["calls"] += 1
            if cases:
                cases.append(("mutated", True))
            return {"passed": state["calls"] == 1, "calls": state["calls"]}

        non_idem_defect = {
            **base,
            "id": "bad-non-idempotent",
            "evaluator": non_idempotent_eval,
        }
        res_non_idem = lint_practice_task(non_idem_defect)
        self.assertFalse(res_non_idem["valid"])
        self.assertIn("non_idempotent_evaluator", res_non_idem["reasons"])

        # Cacat 3: prompt membocorkan jawaban referensi verbatim
        leak_defect = {
            **base,
            "id": "bad-leak",
            "prompt": f"Tulis dedup_csv(rows). Gunakan solusi: {base['reference_solution']}",
        }
        res_leak = lint_practice_task(leak_defect)
        self.assertFalse(res_leak["valid"])
        self.assertIn("answer_leak_in_prompt", res_leak["reasons"])


if __name__ == "__main__":
    unittest.main()
