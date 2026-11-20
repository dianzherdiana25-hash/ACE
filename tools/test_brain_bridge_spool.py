"""Tes kontrak spool brain_bridge + bridge_relay (AG1).

Memastikan entri spool fixture dikirim berurutan melewati layanan
``tools/brain_bridge.py``, entri rusak di tengah antrean dilewati dan tercatat
tanpa menghentikan antrean, serta urutan respons cocok urutan entri sehat.
"""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools.bridge_relay import drain_spool_with_backoff, enqueue_spool
from tools.test_repo_brain_bridge import request as http_request, service


class BrainBridgeSpoolContractTest(unittest.TestCase):
    def test_spool_roundtrip_with_brain_bridge_skips_corrupt_midqueue(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "state.json"
            log = root / "calls.jsonl"
            budgets = root / "budgets.json"
            spool = root / "spool"
            budgets.write_text(
                json.dumps(
                    dict.fromkeys(("front", "coder", "validator", "embedding", "judge"), 5)
                ),
                encoding="utf-8",
            )
            helpers = root / "helpers"
            groq_bin = helpers / "custom.groq" / "bin" / "groq_call.py"
            groq_bin.parent.mkdir(parents=True)
            groq_bin.write_text(
                "import json, sys\n"
                "from pathlib import Path\n"
                "prompt = Path(sys.argv[3]).read_text(encoding='utf-8')\n"
                "print(json.dumps({'content': f'balasan:{prompt}', 'finish_reason': 'stop'}))\n",
                encoding="utf-8",
            )

            # Tulis 3 entri sehat + 1 entri JSON rusak di tengah antrean + 1 non-objek.
            enqueue_spool(
                spool,
                "call-01",
                {
                    "path": "/v1/chat/completions",
                    "request": {"role": "front", "messages": [{"role": "user", "content": "satu"}]},
                    "ts": 100.0,
                },
            )
            (spool / "req" / "call-02-corrupt.json").write_text("{corrupt-mid-json", encoding="utf-8")
            (spool / "req" / "call-02b-array.json").write_text('["not-an-object"]', encoding="utf-8")
            enqueue_spool(
                spool,
                "call-03",
                {
                    "path": "/v1/chat/completions",
                    "request": {"role": "coder", "messages": [{"role": "user", "content": "dua"}]},
                    "ts": 200.0,
                },
            )
            enqueue_spool(
                spool,
                "call-04",
                {
                    "path": "/v1/chat/completions",
                    "request": {"role": "front", "messages": [{"role": "user", "content": "tiga"}]},
                    "ts": 300.0,
                },
            )

            with service(
                "brain_bridge",
                "--state",
                state,
                "--log",
                log,
                "--helpers",
                helpers,
                "--budgets",
                budgets,
            ) as base_url:
                def send_to_bridge(entry: dict) -> dict:
                    status, body = http_request(
                        base_url,
                        entry["path"],
                        entry["request"],
                    )
                    return {"status": status, "body": body}

                report = drain_spool_with_backoff(
                    spool,
                    send_to_bridge,
                    sleep=lambda _s: None,
                )

            self.assertEqual(report["status"], "drained")
            self.assertEqual(report["delivered_ids"], ["call-01", "call-03", "call-04"])
            self.assertEqual(report["pending_count"], 0)
            self.assertEqual(
                [item["file"] for item in report["skipped_corrupt"]],
                ["call-02-corrupt.json", "call-02b-array.json"],
            )
            self.assertTrue((spool / "corrupt" / "call-02-corrupt.json").is_file())

            # Pastikan respons kembali untuk semua entri sehat dengan urutan isi persis.
            contents = []
            for cid in ("call-01", "call-03", "call-04"):
                resp = json.loads((spool / "resp" / f"{cid}.json").read_text(encoding="utf-8"))
                self.assertEqual(resp["status"], 200)
                contents.append(resp["body"]["choices"][0]["message"]["content"])
            self.assertEqual(contents, ["balasan:satu", "balasan:dua", "balasan:tiga"])


if __name__ == "__main__":
    unittest.main()
