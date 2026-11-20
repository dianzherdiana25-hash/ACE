"""Tes ketahanan spool bridge terhadap penulis bersamaan & pembaca aktif (AG5).

Memastikan:
1. ``brain_bridge_relay.spool_fetch`` maupun ``tools.bridge_relay.enqueue_spool``
   menulis via berkas sementara tersembunyi lalu mengganti nama secara atomik
   (``os.replace``), sehingga entri setengah tertulis tidak pernah muncul
   sebagai ``*.json`` utuh bagi pembaca.
2. Dua penulis bersamaan yang menulis bergantian plus satu pembaca aktif
   tidak pernah membaca JSON setengah jadi dan tidak kehilangan satu pun entri sehat.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import time
import unittest
from unittest import mock

from ace_operational import brain_bridge_relay as relay
from tools.bridge_relay import enqueue_spool


class BridgeSpoolConcurrencyTests(unittest.TestCase):
    def test_two_concurrent_writers_and_one_reader_zero_half_writes_zero_losses(self) -> None:
        with TemporaryDirectory() as tmp:
            spool = Path(tmp) / "spool"
            req_dir = spool / "req"
            resp_dir = spool / "resp"
            req_dir.mkdir(parents=True, exist_ok=True)
            resp_dir.mkdir(parents=True, exist_ok=True)

            total_per_writer = 20
            expected_ids = {
                f"w{w}-{i:02d}"
                for w in (1, 2)
                for i in range(total_per_writer)
            }
            seen_ids: set[str] = set()
            read_errors: list[str] = []
            writers_done = threading.Event()
            lock = threading.Lock()
            finished_writers = {"count": 0}

            # Berkas sementara setengah tertulis tidak pernah berakhiran .json saat antrean dibaca.
            half_tmp = req_dir / ".half_written_in_progress.json.tmp"
            half_tmp.write_text('{"call_id": "partial', encoding="utf-8")

            def reader_loop() -> None:
                while not writers_done.is_set() or len(seen_ids) < len(expected_ids):
                    for path in sorted(req_dir.glob("*.json")):
                        if path.name.startswith("."):
                            continue
                        try:
                            doc = json.loads(path.read_text(encoding="utf-8"))
                            cid = doc["call_id"]
                            seen_ids.add(cid)
                        except (OSError, ValueError, KeyError) as exc:
                            read_errors.append(f"{path.name}: {exc}")
                    time.sleep(0.001)

            def writer_worker(writer_no: int) -> None:
                try:
                    for i in range(total_per_writer):
                        cid = f"w{writer_no}-{i:02d}"
                        enqueue_spool(
                            spool,
                            cid,
                            {"path": "/v1/chat/completions", "writer": writer_no, "seq": i},
                        )
                        time.sleep(0.001)
                finally:
                    with lock:
                        finished_writers["count"] += 1
                        if finished_writers["count"] == 2:
                            writers_done.set()

            reader = threading.Thread(target=reader_loop, daemon=True)
            w1 = threading.Thread(target=writer_worker, args=(1,), daemon=True)
            w2 = threading.Thread(target=writer_worker, args=(2,), daemon=True)
            reader.start()
            w1.start()
            w2.start()
            w1.join(timeout=10)
            w2.join(timeout=10)
            reader.join(timeout=10)

        self.assertEqual(read_errors, [])
        self.assertEqual(seen_ids, expected_ids)

    def test_brain_bridge_relay_spool_fetch_uses_temp_then_replace(self) -> None:
        with TemporaryDirectory() as tmp:
            spool = Path(tmp) / "spool"
            req_dir = spool / "req"
            resp_dir = spool / "resp"
            req_dir.mkdir(parents=True, exist_ok=True)
            resp_dir.mkdir(parents=True, exist_ok=True)

            replaced_calls: list[tuple[str, str]] = []
            real_replace = os.replace

            def spy_replace(src, dst):
                replaced_calls.append((Path(src).name, Path(dst).name))
                return real_replace(src, dst)

            def respond_when_ready() -> None:
                deadline = time.time() + 5
                while time.time() < deadline:
                    files = [p for p in req_dir.glob("*.json") if not p.name.startswith(".")]
                    if files:
                        call_id = files[0].stem
                        tmp_resp = resp_dir / f".{call_id}.json.tmp"
                        tmp_resp.write_text(
                            json.dumps({"status": 200, "body": {"ok": True}}),
                            encoding="utf-8",
                        )
                        real_replace(tmp_resp, resp_dir / f"{call_id}.json")
                        return
                    time.sleep(0.01)

            with mock.patch.multiple(relay, REQ=req_dir, RESP=resp_dir, TIMEOUT_S=5), mock.patch.object(
                relay.os, "replace", side_effect=spy_replace
            ):
                responder = threading.Thread(target=respond_when_ready, daemon=True)
                responder.start()
                doc = relay.spool_fetch({"path": "/v1/chat/completions", "request": {"role": "front"}})
                responder.join(timeout=5)

        self.assertEqual(doc, {"status": 200, "body": {"ok": True}})
        self.assertEqual(len(replaced_calls), 1)
        src_name, dst_name = replaced_calls[0]
        self.assertTrue(src_name.startswith(".") and src_name.endswith(".json.tmp"))
        self.assertEqual(dst_name, src_name[1:-4])


if __name__ == "__main__":
    unittest.main()
