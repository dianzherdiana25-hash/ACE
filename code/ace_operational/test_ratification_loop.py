"""Tests for the ratification loop + its engine step.

All organ traffic is faked: the loop's semantics (pairing,
structural gate, JSON judge, write-back discipline) are
what is under test, not the organs. Write-back discipline
is the point: ratified -> exactly one verdict_sealed
record; anything else -> no record, ever.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ace_operational import brain_endpoints as be  # noqa: E402
from ace_operational import ratification_loop as rl  # noqa: E402
from ace_operational.cognitive_memory import (  # noqa: E402
    CognitiveMemory)

CODE_EP = {
    "id": "t-code-001", "kind": "episode", "task_kind": "code",
    "instruction": "Tulis fungsi Python `jumlah_genap(angka)` "
                   "yang menjumlahkan bilangan genap. Sertakan "
                   "docstring Bahasa Indonesia."}
LANG_EP = {
    "id": "t-lang-001", "kind": "episode", "task_kind": "language",
    "instruction": "Tulis satu paragraf Bahasa Indonesia tentang "
                   "pasar pagi."}
GOOD_CODE = ("```python\n"
             "def jumlah_genap(angka):\n"
             "    \"\"\"Jumlahkan bilangan genap.\"\"\"\n"
             "    return sum(a for a in angka if a % 2 == 0)\n"
             "```")
GOOD_LANG = ("Pasar pagi di desa selalu ramai sejak subuh, "
             "dengan pedagang sayur, ikan segar, dan jajanan "
             "tradisional yang menggugah selera.")


class FakePair:
    def __init__(self, task_kind):
        self.task_kind = task_kind
        if task_kind == "code":
            self.proposer, self.validator = "coder", "front"
        else:
            self.proposer, self.validator = "front", "coder"

    def as_dict(self):
        return {"task_kind": self.task_kind,
                "proposer": self.proposer,
                "validator": self.validator}


def fake_pair(task_kind):
    return FakePair(task_kind)


def make_chat(*, accept=True, proposer_text=None, raise_unavailable=False):
    def chat(organ, messages, max_tokens=None):
        if raise_unavailable:
            raise be.BrainUnavailable("organ down (fake)")
        is_judge = any(m.get("role") == "system"
                       and "validator" in m.get("content", "")
                       for m in messages)
        if is_judge:
            body = {"accept": accept, "reasons": ["fake"]}
            return be.ChatResult(json.dumps(body), "", None,
                                 None, 10, False)
        text = proposer_text
        if text is None:
            text = GOOD_CODE if organ == "coder" else GOOD_LANG
        return be.ChatResult(text, "", None, None, 10, False)
    return chat


def sealed_records(root):
    memory = CognitiveMemory(root)
    return [r for r in memory._records.values()
            if r["content"].get("class") == "verdict_sealed"]


class RatificationLoopTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "memory"

    def tearDown(self):
        self.tmp.cleanup()

    def test_ratified_code_episode_writes_back_once(self):
        result = rl.run_ratification_episode(
            CODE_EP, memory_root=self.root,
            chat_fn=make_chat(), pair_fn=fake_pair)
        self.assertTrue(result["ratified"])
        self.assertIsNotNone(result["writeback_id"])
        records = sealed_records(self.root)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["content"]["episode_id"],
                         "t-code-001")
        self.assertEqual(records[0]["content"]["pair"]
                         ["proposer"], "coder")

    def test_ratified_language_episode_writes_back(self):
        result = rl.run_ratification_episode(
            LANG_EP, memory_root=self.root,
            chat_fn=make_chat(), pair_fn=fake_pair)
        self.assertTrue(result["ratified"])
        self.assertEqual(len(sealed_records(self.root)), 1)

    def test_validator_rejection_writes_nothing(self):
        result = rl.run_ratification_episode(
            CODE_EP, memory_root=self.root,
            chat_fn=make_chat(accept=False), pair_fn=fake_pair)
        self.assertFalse(result["ratified"])
        self.assertIsNone(result["writeback_id"])
        self.assertEqual(sealed_records(self.root), [])

    def test_structural_failure_writes_nothing(self):
        bad = "```python\ndef fungsi_lain(x):\n    return x\n```"
        result = rl.run_ratification_episode(
            CODE_EP, memory_root=self.root,
            chat_fn=make_chat(proposer_text=bad),
            pair_fn=fake_pair)
        self.assertFalse(result["structural_gate"])
        self.assertFalse(result["ratified"])
        self.assertEqual(sealed_records(self.root), [])

    def test_unavailable_organ_writes_nothing_and_reports(self):
        result = rl.run_ratification_episode(
            CODE_EP, memory_root=self.root,
            chat_fn=make_chat(raise_unavailable=True),
            pair_fn=fake_pair)
        self.assertFalse(result["ratified"])
        self.assertIn("BrainUnavailable", result["error"])
        self.assertEqual(sealed_records(self.root), [])

    def test_no_memory_root_measures_without_writing(self):
        result = rl.run_ratification_episode(
            CODE_EP, memory_root=None,
            chat_fn=make_chat(), pair_fn=fake_pair)
        self.assertTrue(result["ratified"])
        self.assertIsNone(result["writeback_id"])

    def test_context_is_prepended_to_proposer(self):
        seen = {}

        def chat(organ, messages, max_tokens=None):
            if not any(m.get("role") == "system"
                       and "validator" in m.get("content", "")
                       for m in messages):
                seen["proposer_messages"] = messages
            return make_chat()(organ, messages,
                               max_tokens=max_tokens)

        rl.run_ratification_episode(
            LANG_EP, memory_root=None,
            context=["Ringkasan terverifikasi A"],
            chat_fn=chat, pair_fn=fake_pair)
        first = seen["proposer_messages"][0]
        self.assertEqual(first["role"], "system")
        self.assertIn("Ringkasan terverifikasi A",
                      first["content"])


class EngineStepTests(unittest.TestCase):
    def test_step_advances_cursor_and_stops_at_end(self):
        from ace_operational.autonomous_engine import (
            ContinuousAutonomousEngine)
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "ws"
            source_dir = workspace / "projects" / "ratification"
            source_dir.mkdir(parents=True)
            source = source_dir / "episodes.jsonl"
            source.write_text(
                json.dumps(CODE_EP) + "\n"
                + json.dumps(LANG_EP) + "\n", encoding="utf-8")
            engine = ContinuousAutonomousEngine(
                workspace=workspace)
            chat = make_chat()
            first = engine.execute_ratification_step(
                chat_fn=chat, pair_fn=fake_pair)
            self.assertEqual(first["status"], "measured")
            self.assertTrue(first["ratified"])
            second = engine.execute_ratification_step(
                chat_fn=chat, pair_fn=fake_pair)
            self.assertEqual(second["episode_id"], "t-lang-001")
            third = engine.execute_ratification_step(
                chat_fn=chat, pair_fn=fake_pair)
            self.assertEqual(third["status"], "exhausted")
            records = sealed_records(
                workspace / "cognitive_memory")
            self.assertEqual(len(records), 2)

    def test_step_without_source_is_clean_noop(self):
        from ace_operational.autonomous_engine import (
            ContinuousAutonomousEngine)
        with tempfile.TemporaryDirectory() as tmp:
            engine = ContinuousAutonomousEngine(
                workspace=Path(tmp) / "ws")
            result = engine.execute_ratification_step(
                chat_fn=make_chat(), pair_fn=fake_pair)
            self.assertEqual(result["status"], "no_source")


if __name__ == "__main__":
    unittest.main()
