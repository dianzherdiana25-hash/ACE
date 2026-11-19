"""Bridge-mode wiring for the engine's generative learning paths.

Before this wiring, the dynamic technical practice, the dynamic
dialogue practice and the vocabulary paths were gated on the
local GGUF server's health and generated only through
ModelRouter — so with the local slate retired (2026-11-18) every
generative path idled forever even in bridge mode (EVO 0009).
These tests prove, on scratch stores with the bridge transport
mocked at brain_endpoints._request:

- technical practice generates via the bridge coder role, the
  generated script is verified by execution, and the pass writes
  a skill_verified record back to cognitive memory;
- dialogue practice and the vocabulary batch generate via the
  bridge front role and record bridge provenance;
- an unhealthy bridge idles every path (None / []) and records
  nothing;
- a transport failure mid-generation idles the technical path
  without creating a task, a receipt, or a false failure gap.
"""
from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from ace_operational import brain_endpoints
from ace_operational.autonomous_engine import ContinuousAutonomousEngine
from ace_operational.cognitive_memory import CognitiveMemory
from ace_operational.store import OperationalStore

BRIDGE = "http://127.0.0.1:18931"
ORIGIN = "groq/openai/gpt-oss-120b"

SCRIPT = (
    "```python\n"
    "def kurung_seimbang(teks):\n"
    "    tumpukan = []\n"
    "    pasangan = {')': '(', ']': '[', '}': '{'}\n"
    "    for ch in teks:\n"
    "        if ch in '([{':\n"
    "            tumpukan.append(ch)\n"
    "        elif ch in ')]}':\n"
    "            if not tumpukan or tumpukan.pop() != pasangan[ch]:\n"
    "                return False\n"
    "    return not tumpukan\n"
    "\n"
    "assert kurung_seimbang('(a[b]c)') is True\n"
    "assert kurung_seimbang('(a[b)') is False\n"
    "print('TECH_PRACTICE_VERIFIED_OK')\n"
    "```"
)

CHALLENGE = (
    "Implementasikan fungsi pemeriksa kurung seimbang memakai "
    "tumpukan beserta uji asersi kasus seimbang dan tidak seimbang."
)

DIALOGUE_Q = "Apa perbedaan nuansa kata melihat dan menatap dalam percakapan sehari-hari?"
DIALOGUE_A = (
    "Melihat itu netral, sekadar menangkap dengan mata. Menatap "
    "lebih lama dan intens, biasanya ada perhatian atau maksud "
    "tertentu di baliknya."
)

VOCAB = (
    "sendok: alat makan untuk menyendok kuah\n"
    "angin: udara yang bergerak di alam bebas\n"
    "ramah: bersikap baik dan mudah bergaul\n"
    "pasar: tempat jual beli kebutuhan harian\n"
)


def _chat_payload(content: str) -> dict:
    return {
        "choices": [{"message": {"content": content}}],
        "brain_of_origin": ORIGIN,
    }


def _fake_request_factory(*, health_ok=True, chat_ok=True):
    def fake_request(url, payload, timeout):
        if url.endswith("/health"):
            if health_ok:
                return {"status": "ok"}
            raise brain_endpoints.BrainUnavailable("bridge down")
        if not chat_ok:
            raise brain_endpoints.BrainUnavailable("over budget")
        max_tokens = (payload or {}).get("max_tokens", 0)
        if max_tokens <= 80:
            return _chat_payload(CHALLENGE)
        if max_tokens >= 500:
            return _chat_payload(SCRIPT if max_tokens == 512 else VOCAB)
        if max_tokens == 70:
            return _chat_payload(DIALOGUE_Q)
        return _chat_payload(DIALOGUE_A)

    return fake_request


def _by_class(root, cls: str) -> list[dict]:
    return [r for r in CognitiveMemory(root)._records.values()
            if r["content"].get("class") == cls]


class BridgePracticeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="ace-bridge-")
        self.addCleanup(self.tmp.cleanup)
        self.ws = Path(self.tmp.name) / "workspace"
        self.store = OperationalStore(self.ws)
        self.addCleanup(self.store.close)
        self.engine = ContinuousAutonomousEngine(
            store=self.store, workspace=self.ws)
        self.memory_root = self.ws / "cognitive_memory"
        env = mock.patch.dict(
            os.environ, {brain_endpoints.BRIDGE_ENV_VAR: BRIDGE})
        env.start()
        self.addCleanup(env.stop)

    def _with_transport(self, **kwargs):
        return mock.patch.object(
            brain_endpoints, "_request",
            _fake_request_factory(**kwargs))

    def test_technical_practice_via_bridge_writes_back(self) -> None:
        with self._with_transport():
            result = self.engine._generate_dynamic_technical_practice()
        self.assertIsNotNone(result)
        self.assertTrue(result["passed"])
        self.assertIsNotNone(result["writeback_id"])

        receipts = self.store.list_receipts()
        self.assertEqual(len(receipts), 1)
        self.assertTrue(receipts[0]["passed"])

        records = _by_class(self.memory_root, "skill_verified")
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record["id"], result["writeback_id"])
        self.assertEqual(
            record["content"]["learning_kind"],
            "dynamic_technical_practice")
        self.assertTrue(
            record["content"]["skill_name"].startswith("tech_practice::"))
        self.assertTrue(
            CognitiveMemory(self.memory_root).audit()["chain_ok"])

    def test_dialogue_practice_via_bridge(self) -> None:
        corpus = self.engine.corpus_file
        before = (len(corpus.read_text(encoding="utf-8").splitlines())
                  if corpus.exists() else 0)
        with self._with_transport():
            result = self.engine._generate_dynamic_language_dialogue_practice()
        self.assertIsNotNone(result)
        self.assertIn("dialogue_practice", result)
        entries = corpus.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(entries), before + 1)
        self.assertIn(f"bridge:{ORIGIN}", entries[-1])

    def test_vocab_batch_via_bridge(self) -> None:
        with self._with_transport():
            learned = self.engine._explore_vocabulary_batch(batch_size=4)
        self.assertTrue(learned)
        self.assertTrue(all(
            item["source"] == "auto_bridge_batch" for item in learned))

    def test_unhealthy_bridge_idles_everything(self) -> None:
        with self._with_transport(health_ok=False):
            self.assertIsNone(
                self.engine._generate_dynamic_technical_practice())
            self.assertIsNone(
                self.engine._generate_dynamic_language_dialogue_practice())
            self.assertEqual(self.engine._explore_vocabulary_batch(), [])
        self.assertEqual(self.store.list_receipts(), [])
        self.assertEqual(self.store.list_tasks(), [])
        self.assertEqual(
            _by_class(self.memory_root, "skill_verified"), [])

    def test_transport_failure_mid_generation_records_nothing(self) -> None:
        with self._with_transport(chat_ok=False):
            self.assertIsNone(
                self.engine._generate_dynamic_technical_practice())
        self.assertEqual(self.store.list_receipts(), [])
        self.assertEqual(self.store.list_tasks(), [])
        self.assertEqual(self.store.list_gaps(), [])
        self.assertEqual(
            _by_class(self.memory_root, "skill_verified"), [])


if __name__ == "__main__":
    unittest.main()
