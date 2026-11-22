from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import canonical, identity
from ._journal import Journal
from .rolling_summary import summarize
from .test_dialogue_server import turn


def save(root, name, raw):
    (root / name).write_bytes(raw)
    return {"path": name, "sha256": sha256(raw).hexdigest()}


def sample(root, session="fixture", day="2025-05-01"):
    data = Journal(root / f"{session}.sqlite")
    events = [
        turn(session=session, date=f"{day}T10:00:00Z", message="Kalibrasi panel tersedia."),
        turn("reply", "assistant", "opening", "Bukti kalibrasi panel ada pada tabel.", session=session, date=f"{day}T10:01:00Z"),
        turn("next", "user", "reply", "Arsip setiap sampel.", session=session, date=f"{day}T10:02:00Z"),
        turn("ending", "assistant", "next", "Arsip lokal tersedia.", session=session, date=f"{day}T10:03:00Z"),
    ]
    for event in events:
        data.append(event)
    snapshot = data.export(session)
    return save(root, f"{session}.json", canonical(snapshot)), snapshot


class SummaryTests(unittest.TestCase):
    def test_extract_rare_and_recent_turns_with_exact_hash_and_missing_topics(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            ref, records = sample(root)
            plan = {"schema": "ace.presence.summary-plan.v1", "dialogue": ref, "max_turns": 1,
                    "max_chars": 100, "topics": [{"id": name, "terms": [term]} for name, term in (
                        ("sensor", "panel"), ("record", "sampel"), ("absent", "anggaran"))]}
            proof = summarize(plan, identity(plan), root)
            self.assertEqual(proof["selected"][0]["message"], records["events"][2]["turn"]["message"])
            self.assertEqual(proof["selected"][0]["source_turn_sha256"], records["events"][2]["sha256"])
            self.assertEqual(proof["unseen_topics"], ["absent"])
            self.assertEqual(proof["mentioned_but_omitted_topics"], ["sensor"])
