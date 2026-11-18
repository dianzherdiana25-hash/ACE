"""EVO 0009 milestone 5: the write-path event points wired.

The module-level acceptance of the write path itself lives in
test_memory_writeback.py (design S6). These tests prove the
three event points this milestone connects write through it,
end to end, on scratch stores only:

- finding_high_opened at the planner's audit surfacing,
- finding_high_closed at the verifier's ratification point
  (the same point that writes mission_ratified),
- skill_verified at the expander's receipt issuance.

Invariants asserted with them: exactly one record per verified
event, replay idempotency where the event identity is stable,
the operator seeds untouched, and the hash chain auditing
clean after every write.
"""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from ace_operational.cognitive_memory import CognitiveMemory
from ace_operational.evolution_mission_loop import (
    EvolutionPatchVerifier,
    PassiveEvolutionPlanner,
)
from ace_operational.massive_skills_expansion import (
    MassiveSkillsExpander,
)
from ace_operational.store import OperationalStore


def _records(root) -> list[dict]:
    return list(CognitiveMemory(root)._records.values())


def _by_class(root, cls: str) -> list[dict]:
    return [r for r in _records(root)
            if r["content"].get("class") == cls]


def _seed(root) -> list[str]:
    mem = CognitiveMemory(root)
    ids = []
    for text in ("seed one", "seed two"):
        ids.append(mem.remember(
            kind="episodic", content={"event": text},
            source_kind="operator", confidence=0.95,
            sensitivity="internal"))
    return ids


def _create_repo(root: Path, *, target_src: str, test_src: str) -> None:
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "code" / "ace_runtime").mkdir(parents=True, exist_ok=True)
    (root / "code" / "ace_operational").mkdir(parents=True,
                                             exist_ok=True)
    (root / "docs" / "UPSTREAM_SOURCES.json").write_text(
        json.dumps({"schema": "ace.source-integration.v1",
                    "files": {"code/ace_runtime/protected.py":
                              {"git_blob": "0"}}}),
        encoding="utf-8")
    (root / "code" / "ace_runtime" / "protected.py").write_text(
        '"""Protected."""\nVALUE = 1\n', encoding="utf-8")
    (root / "code" / "ace_operational" / "__init__.py").write_text(
        '"""Package."""\n', encoding="utf-8")
    (root / "code" / "ace_operational" / "target_mod.py").write_text(
        target_src, encoding="utf-8")
    (root / "code" / "ace_operational"
     / "test_target_mod.py").write_text(test_src, encoding="utf-8")


TARGET = (
    '"""Target module."""\n'
    "def parse_positive(raw: str) -> int:\n"
    "    try:\n"
    "        val = int(raw)\n"
    "        return max(0, val)\n"
    "    except Exception:\n"
    "        pass\n"
    "    return 0\n"
    "\n"
    "def status() -> dict:\n"
    "    return {\"verified\": True}\n"
)
TEST = (
    "import unittest\n"
    "from ace_operational.target_mod import parse_positive\n\n"
    "class TargetTests(unittest.TestCase):\n"
    "    def test_parse(self) -> None:\n"
    "        self.assertEqual(parse_positive('5'), 5)\n"
    "        self.assertEqual(parse_positive('bad'), 0)\n"
)
FIXED = TARGET.replace(
    "def status() -> dict:\n    return {\"verified\": True}\n",
    "def status(flag: bool = True) -> dict:\n"
    "    if not flag:\n"
    "        raise ValueError('unverified')\n"
    "    return {\"verified\": True}\n")


class FindingWiringTests(unittest.TestCase):
    def test_opened_then_closed_with_seeds_and_chain(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ace_m5_") as d:
            base = Path(d)
            repo, ws, mem_root = base / "repo", base / "ws", \
                base / "mem"
            _create_repo(repo, target_src=TARGET, test_src=TEST)
            seeds = _seed(mem_root)

            planner = PassiveEvolutionPlanner(
                ws, repo, scan_subpath="code/ace_operational",
                memory_root=mem_root)
            plan = planner.plan_next_evolution(
                test_modules=["ace_operational.test_target_mod"])
            self.assertEqual(plan["status"], "MISSION_EMITTED")
            self.assertEqual(plan["top_finding"]["severity"], "HIGH")
            opened = _by_class(mem_root, "finding_high_opened")
            self.assertEqual(len(opened), 1)
            self.assertEqual(opened[0]["kind"], "episodic")
            self.assertEqual(opened[0]["confidence"], 0.90)
            fkey = plan["top_finding"]["finding_key"]
            self.assertEqual(
                opened[0]["content"]["finding_key"], fkey)
            self.assertIn(fkey, plan["memory_writeback_opened"])

            # Replay: a fresh plan over the same audit state
            # writes no second opened record.
            planner.plan_next_evolution(
                test_modules=["ace_operational.test_target_mod"])
            self.assertEqual(
                len(_by_class(mem_root, "finding_high_opened")), 1)

            # Fix + ratify: mission_ratified and
            # finding_high_closed land at the same point.
            (repo / "code" / "ace_operational"
             / "target_mod.py").write_text(FIXED, encoding="utf-8")
            ver = EvolutionPatchVerifier(
                ws, repo, memory_root=mem_root
            ).verify_and_ratify_evolution()
            self.assertTrue(ver["accepted"], msg=str(ver))
            self.assertEqual(
                len(_by_class(mem_root, "mission_ratified")), 1)
            closed = _by_class(mem_root, "finding_high_closed")
            self.assertEqual(len(closed), 1)
            self.assertEqual(
                closed[0]["content"]["finding_key"], fkey)
            self.assertIsNotNone(
                ver["memory_writeback"]["closed_record_id"])

            # Seeds intact; chain audits clean.
            ids = {r["id"] for r in _records(mem_root)}
            self.assertTrue(set(seeds) <= ids)
            self.assertTrue(CognitiveMemory(mem_root).audit()
                            ["chain_ok"])

    def test_no_memory_root_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ace_m5_") as d:
            base = Path(d)
            repo, ws = base / "repo", base / "ws"
            _create_repo(repo, target_src=TARGET, test_src=TEST)
            planner = PassiveEvolutionPlanner(
                ws, repo, scan_subpath="code/ace_operational")
            plan = planner.plan_next_evolution(
                test_modules=["ace_operational.test_target_mod"])
            self.assertEqual(plan["status"], "MISSION_EMITTED")
            self.assertNotIn("memory_writeback_opened", plan)


class SkillWiringTests(unittest.TestCase):
    def test_skill_verified_at_receipt_issuance(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ace_m5_") as d:
            base = Path(d)
            mem_root = base / "mem"
            seeds = _seed(mem_root)
            store = OperationalStore(workspace=base / "ops")
            expander = MassiveSkillsExpander(
                store=store, memory_root=mem_root)
            expander.run_mass_expansion()
            records = _by_class(mem_root, "skill_verified")
            self.assertEqual(len(records), 5)
            self.assertTrue(all(r["kind"] == "procedural"
                                for r in records))
            self.assertTrue(all(r["content"].get("receipt_id")
                                for r in records))
            ids = {r["id"] for r in _records(mem_root)}
            self.assertTrue(set(seeds) <= ids)
            self.assertTrue(CognitiveMemory(mem_root).audit()
                            ["chain_ok"])


if __name__ == "__main__":
    unittest.main()
