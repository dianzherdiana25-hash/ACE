"""Stage E evidence: harness-attested server identity, fail-closed."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ace_operational import attested_server as att
from ace_operational.models_backend import ModelRouter
from ace_operational.store import OperationalStore


def make_attestation(root: Path, model_bytes: bytes = b"GGUF-fake-model",
                     url: str = "http://127.0.0.1:8081",
                     model_id: str = "server-model") -> dict:
    model = root / "model.gguf"
    model.write_bytes(model_bytes)
    binary = root / "llama-server"
    binary.write_bytes(b"fake-server-binary")
    argv = [str(binary), "-m", str(model), "--host", "127.0.0.1",
            "--port", "8081"]
    model_sha = att.sha256_file(model)
    binary_sha = att.sha256_file(binary)
    return {"schema": att.ATTESTATION_SCHEMA, "server_url": url,
            "model_id": model_id, "model_path": str(model),
            "model_sha256": model_sha, "binary_path": str(binary),
            "binary_sha256": binary_sha, "launch_argv": argv,
            "launch_param_hash": att._param_hash(model_sha, binary_sha,
                                                 argv),
            "pid": 4242, "spawned_by": "ace-harness",
            "created_at": "2026-11-12T00:00:00+00:00"}


class AttestationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ace-attest-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_wellformed_attestation_verifies_and_matches(self):
        record = make_attestation(self.root)
        self.assertTrue(att.verify_attestation(record))
        self.assertIs(att.match_attestation(
            [record], "http://127.0.0.1:8081", "server-model"), record)

    def test_changed_model_bytes_fail_closed(self):
        record = make_attestation(self.root)
        Path(record["model_path"]).write_bytes(b"GGUF-swapped-model")
        self.assertFalse(att.verify_attestation(record))
        self.assertIsNone(att.match_attestation(
            [record], "http://127.0.0.1:8081", "server-model"))

    def test_tampered_launch_params_fail_closed(self):
        record = make_attestation(self.root)
        record["launch_argv"] = record["launch_argv"] + ["--stealth"]
        self.assertFalse(att.verify_attestation(record))

    def test_url_or_advertised_id_mismatch_never_matches(self):
        record = make_attestation(self.root)
        self.assertIsNone(att.match_attestation(
            [record], "http://127.0.0.1:9999", "server-model"))
        self.assertIsNone(att.match_attestation(
            [record], "http://127.0.0.1:8081", "other-model"))

    def test_save_load_roundtrip_and_tampered_file_refused(self):
        record = make_attestation(self.root)
        path = self.root / "att.json"
        att.save_attestation(record, path)
        self.assertEqual(att.load_attestation(path), record)
        data = json.loads(path.read_text())
        data["model_sha256"] = "0" * 64
        path.write_text(json.dumps(data))
        self.assertIsNone(att.load_attestation(path))


class RouterAttestationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ace-attest-router-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = OperationalStore(self.root / "workspace")
        self.addCleanup(self.store.close)
        self.env = patch.dict(os.environ,
                              {"ACE_MODEL_CACHE": str(self.root / "models"),
                               "ACE_DEFAULT_MODEL": "",
                               "ACE_LLAMA_CONTEXT": "4096",
                               "ACE_LLAMA_THREADS": "2"})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.router = ModelRouter(self.store)
        self.discovery = {"ready": True, "llama_binary": "",
                          "server_healthy": True,
                          "server_url": "http://127.0.0.1:8081",
                          "server_models": [{"id": "server-model"}],
                          "valid_models": [], "endpoint_error": ""}
        patcher = patch.object(self.router, "discover_local_gguf",
                               return_value=self.discovery)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.payload = {"model": "server-model",
                        "choices": [{"message": {"content": "jawaban"},
                                     "finish_reason": "stop"}],
                        "usage": {}}
        self.messages = [{"role": "user", "content": "Halo"}]

    def _generate(self):
        with patch("ace_operational.models_backend._local_json",
                   return_value=self.payload):
            return self.router.generate_text(
                self.messages, target_model="server-model")

    def test_unattested_server_receipt_stays_unidentified(self):
        result = self._generate()
        self.assertTrue(result["success"])
        self.assertIsNone(result["model"]["sha256"])
        self.assertFalse(result["model"]["checksum_verified"])

    def test_attested_server_receipt_binds_to_spawn_digests(self):
        record = make_attestation(self.root)
        self.assertTrue(self.router.register_attestation(record))
        result = self._generate()
        self.assertTrue(result["success"])
        self.assertEqual(result["model"]["sha256"],
                         record["model_sha256"])
        self.assertTrue(result["model"]["checksum_verified"])
        self.assertEqual(result["model"]["attestation"]["binary_sha256"],
                         record["binary_sha256"])
        self.assertEqual(result["model"]["attestation"]
                         ["launch_param_hash"],
                         record["launch_param_hash"])

    def test_registration_refuses_a_forged_attestation(self):
        record = make_attestation(self.root)
        record["model_sha256"] = "f" * 64
        self.assertFalse(self.router.register_attestation(record))
        result = self._generate()
        self.assertIsNone(result["model"]["sha256"])


if __name__ == "__main__":
    unittest.main()
