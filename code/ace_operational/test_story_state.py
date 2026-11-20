"""Tes unit untuk code/ace_operational/story_state.py (AG87)."""

from __future__ import annotations

import ast
from pathlib import Path
import unittest

from ace_operational.story_state import SCHEMA, StoryConsistencyError, StoryStateStore


class StoryStateStoreTests(unittest.TestCase):
    def test_no_engine_imports(self) -> None:
        src_path = Path(__file__).with_name("story_state.py")
        tree = ast.parse(src_path.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        self.assertFalse(any("autonomous_engine" in name for name in imported))

    def test_crud_queries_and_roundtrip(self) -> None:
        store = StoryStateStore()
        store.upsert_character("arya", name="Arya", status="alive", status_tick=0, location="Pelabuhan")
        store.upsert_character("bima", name="Bima", status="alive", status_tick=0, location="Menara")
        store.add_event(
            "ev-1",
            tick=1,
            summary="Arya menerima peta kuno di Pelabuhan",
            participants=["arya"],
            location="Pelabuhan",
        )
        store.assert_fact(
            "fact-weather-1",
            subject="pelabuhan",
            predicate="cuaca",
            value="cerah",
            valid_from_tick=1,
            source_event_id="ev-1",
        )
        store.assert_fact(
            "fact-weather-2",
            subject="pelabuhan",
            predicate="cuaca",
            value="badai",
            valid_from_tick=4,
            supersede_prior=True,
        )
        store.add_promise(
            "prom-1",
            description="Arya berjanji mengembalikan kompas ke Bima",
            introduced_tick=2,
            due_by_tick=10,
            related_characters=["arya", "bima"],
        )
        store.add_promise(
            "prom-2",
            description="Surat tersegel belum dibuka",
            introduced_tick=3,
            due_by_tick=5,
        )
        store.resolve_promise("prom-1", status="fulfilled", resolved_tick=4)

        self.assertEqual(store.query_facts(subject="pelabuhan", at_tick=2)[0].value, "cerah")
        self.assertEqual(store.query_facts(subject="pelabuhan", at_tick=4)[0].value, "badai")
        unpaid = store.unpaid_promises()
        self.assertEqual([p.promise_id for p in unpaid], ["prom-2"])
        self.assertEqual([p.promise_id for p in store.unpaid_promises(overdue_at_tick=6)], ["prom-2"])

        exported = store.to_dict()
        self.assertEqual(exported["schema"], SCHEMA)
        reloaded = StoryStateStore.from_dict(exported)
        self.assertEqual(reloaded.to_dict(), exported)

    def test_rejects_contradicting_timeline_facts_and_postmortem_actions(self) -> None:
        store = StoryStateStore()
        store.upsert_character("kirana", name="Kirana", status="alive", status_tick=0)
        store.add_event("ev-alive", tick=2, summary="Kirana bernegosiasi", participants=["kirana"])

        # Tidak boleh mati sebelum event di mana ia sudah tercatat bertindak.
        with self.assertRaises(StoryConsistencyError):
            store.upsert_character("kirana", name="Kirana", status="dead", status_tick=2, updated_tick=2)

        # Mati di tick 5 sah.
        store.upsert_character("kirana", name="Kirana", status="dead", status_tick=5, updated_tick=5)

        # Tidak boleh berpartisipasi lagi sesudah tick 5.
        with self.assertRaises(StoryConsistencyError):
            store.add_event("ev-ghost", tick=6, summary="Kirana muncul", participants=["kirana"])

        # Fakta lokasi/hidup sesudah kematian ditolak.
        with self.assertRaises(StoryConsistencyError):
            store.assert_fact(
                "fact-dead-loc",
                subject="kirana",
                predicate="location",
                value="Pasar",
                valid_from_tick=6,
            )

        # Fakta bertabrakan pada interval tumpang-tindih ditolak bila tidak di-supersede.
        store.assert_fact(
            "fact-bridge-open",
            subject="jembatan_utara",
            predicate="kondisi",
            value="utuh",
            valid_from_tick=1,
            valid_until_tick=10,
        )
        with self.assertRaises(StoryConsistencyError):
            store.assert_fact(
                "fact-bridge-collapsed",
                subject="jembatan_utara",
                predicate="kondisi",
                value="roboh",
                valid_from_tick=4,
                valid_until_tick=8,
            )

        # Akibat tidak boleh terjadi sebelum sebabnya.
        with self.assertRaises(StoryConsistencyError):
            store.assert_fact(
                "fact-anachronism",
                subject="kota",
                predicate="gerbang",
                value="terkunci",
                valid_from_tick=1,
                source_event_id="ev-alive",
            )


if __name__ == "__main__":
    unittest.main()
