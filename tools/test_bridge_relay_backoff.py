"""Tes fixture backoff relay: upstream gagal di awal lalu pulih, jeda menaik, urutan spool terjaga.

Kenapa: memastikan relay tidak melakukan busy-loop saat upstream belum tersedia
dan tidak menghilangkan atau mengacak urutan entri spool ketika upstream pulih.
"""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools.bridge_relay import drain_spool_with_backoff, enqueue_spool


class FakeClock:
    def __init__(self, start: float = 1000.0) -> None:
        self.current = start
        self.sleeps: list[float] = []

    def now(self) -> float:
        return self.current

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.current += seconds


class BridgeRelayBackoffTests(unittest.TestCase):
    def test_upstream_recovers_after_increasing_backoff_and_preserves_order(self) -> None:
        with TemporaryDirectory() as tmp:
            spool = Path(tmp) / "spool"
            clock = FakeClock()

            for idx, cid in enumerate(("req-01", "req-02", "req-03"), start=1):
                enqueue_spool(
                    spool,
                    cid,
                    {"path": "/v1/chat/completions", "request": {"seq": idx}, "ts": 100.0 + idx},
                    now=clock.now,
                )

            received_order: list[str] = []
            failures_remaining = 3

            def flaky_upstream(payload: dict) -> dict:
                nonlocal failures_remaining
                if failures_remaining > 0:
                    failures_remaining -= 1
                    # Pastikan tidak ada entri spool yang hilang saat upstream masih gagal
                    self.assertEqual(len(list((spool / "req").glob("*.json"))), 3)
                    raise ConnectionError("upstream belum siap")
                cid = payload["call_id"]
                received_order.append(cid)
                return {"status": 200, "body": {"ack": cid, "seq": payload["request"]["seq"]}}

            report = drain_spool_with_backoff(
                spool,
                flaky_upstream,
                base_delay=0.5,
                factor=2.0,
                max_delay=10.0,
                max_attempts=6,
                sleep=clock.sleep,
                now=clock.now,
            )

            self.assertEqual(report["status"], "drained")
            self.assertEqual(report["delivered_ids"], ["req-01", "req-02", "req-03"])
            self.assertEqual(received_order, ["req-01", "req-02", "req-03"])
            self.assertEqual(report["pending_count"], 0)

            # Jeda antar-percobaan tercatat menaik (0.5 -> 1.0 -> 2.0), bukan busy-loop
            self.assertEqual(clock.sleeps, [0.5, 1.0, 2.0])
            self.assertEqual(report["backoff_delays"], [0.5, 1.0, 2.0])
            for prev_d, next_d in zip(clock.sleeps, clock.sleeps[1:]):
                self.assertGreater(next_d, prev_d)

            # Semua berkas resp tertulis utuh dan req bersih setelah pulih
            self.assertEqual(list((spool / "req").glob("*.json")), [])
            for idx, cid in enumerate(("req-01", "req-02", "req-03"), start=1):
                resp_doc = json.loads((spool / "resp" / f"{cid}.json").read_text(encoding="utf-8"))
                self.assertEqual(resp_doc, {"status": 200, "body": {"ack": cid, "seq": idx}})

    def test_exhausted_attempts_keeps_spool_entries_intact(self) -> None:
        with TemporaryDirectory() as tmp:
            spool = Path(tmp) / "spool"
            clock = FakeClock()
            enqueue_spool(spool, "req-stay", {"path": "/v1/budget", "request": {}, "ts": 1.0}, now=clock.now)

            def dead_upstream(_payload: dict) -> dict:
                raise ConnectionError("masih mati")

            report = drain_spool_with_backoff(
                spool,
                dead_upstream,
                base_delay=1.0,
                factor=2.0,
                max_delay=8.0,
                max_attempts=3,
                sleep=clock.sleep,
                now=clock.now,
            )
            self.assertEqual(report["status"], "exhausted")
            self.assertEqual(report["delivered_ids"], [])
            self.assertEqual(report["pending_count"], 1)
            self.assertEqual(clock.sleeps, [1.0, 2.0])
            self.assertTrue((spool / "req" / "req-stay.json").is_file())


if __name__ == "__main__":
    unittest.main()
