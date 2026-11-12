"""Structural GGUF admission + thinking-budget failure truthfulness.

Regression context (ACE Omega, 2026-11-12): discovery admitted any file with a
GGUF magic prefix, so a truncated 1.5 GB partial download of a 7.3 GB model was
listed as a valid candidate and could be selected for inference. Separately, a
thinking model that spent its whole token budget inside reasoning_content was
reported as a generic SERVER_INFERENCE_FAILED, hiding the real cause.
"""
from __future__ import annotations

import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from ace_operational.models_backend import ModelRouter, _estimated_ram_mb, _gguf_expected_total_size
from ace_operational.store import OperationalStore


def _s(text: str) -> bytes:
    raw = text.encode()
    return struct.pack("<Q", len(raw)) + raw


def build_gguf(tensors, alignment: int = 32) -> bytes:
    """tensors: list of (name, dims, ggml_type_id, payload_bytes)."""
    header = bytearray()
    header += b"GGUF" + struct.pack("<I", 3)
    header += struct.pack("<Q", len(tensors)) + struct.pack("<Q", 1)
    header += _s("general.alignment") + struct.pack("<I", 4) + struct.pack("<I", alignment)
    offset = 0
    infos = bytearray()
    payloads = bytearray()
    for name, dims, ttype, payload in tensors:
        infos += _s(name) + struct.pack("<I", len(dims))
        for dim in dims:
            infos += struct.pack("<Q", dim)
        infos += struct.pack("<I", ttype) + struct.pack("<Q", offset)
        payloads += payload
        offset += len(payload)
    header += infos
    pad = (-len(header)) % alignment
    return bytes(header) + b"\x00" * pad + bytes(payloads)


F32_TENSOR = ("w", [2, 3], 0, b"\x00" * 24)          # 6 elems * 4 bytes
Q4K_TENSOR = ("q", [256], 12, b"\x00" * 144)         # 1 block * 144 bytes


class GgufIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ace-gguf-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.models = self.root / "models"
        self.models.mkdir()
        self.store = OperationalStore(self.root / "workspace")
        self.addCleanup(self.store.close)
        env = patch.dict(os.environ, {"ACE_MODEL_CACHE": str(self.models),
                                      "ACE_LLAMA_SERVER_URL": "http://127.0.0.1:9"})
        env.start()
        self.addCleanup(env.stop)
        self.router = ModelRouter(self.store)

    def discover(self):
        return self.router.discover_local_gguf(candidate_dirs=[self.models])

    def test_complete_gguf_is_valid_and_size_verified(self):
        blob = build_gguf([F32_TENSOR, Q4K_TENSOR])
        (self.models / "ok.gguf").write_bytes(blob)
        self.assertEqual(_gguf_expected_total_size(self.models / "ok.gguf"), len(blob))
        result = self.discover()
        self.assertEqual([m["name"] for m in result["valid_models"]], ["ok.gguf"])
        self.assertTrue(result["valid_models"][0]["size_verified"])
        self.assertEqual(result["valid_models"][0]["expected_size_bytes"], len(blob))
        self.assertEqual(result["corrupted_models"], [])

    def test_truncated_gguf_is_corrupt_not_a_candidate(self):
        blob = build_gguf([F32_TENSOR, Q4K_TENSOR])
        (self.models / "partial.gguf").write_bytes(blob[:-40])
        result = self.discover()
        self.assertEqual(result["valid_models"], [])
        self.assertEqual(len(result["corrupted_models"]), 1)
        self.assertIn("gguf_size_mismatch", result["corrupted_models"][0]["reason"])

    def test_ram_estimate_uses_measured_overhead_not_flat_markup(self):
        # Qwen3-8B Q4_K_M: 5,027,783,488 bytes = 4794 MiB -> +12.5% overhead.
        self.assertEqual(_estimated_ram_mb(5027783488), 4794 + 4794 // 8)
        self.assertLess(_estimated_ram_mb(5027783488), int(4794 * 1.25))
        self.assertEqual(_estimated_ram_mb(1024), 256)

    def test_fits_ram_follows_estimate_when_ram_is_plentiful(self):
        blob = build_gguf([F32_TENSOR])
        (self.models / "ok.gguf").write_bytes(blob)
        with patch("ace_operational.models_backend.get_available_ram_mb", return_value=64000):
            result = self.discover()
        entry = result["valid_models"][0]
        self.assertEqual(entry["estimated_ram_mb"], _estimated_ram_mb(len(blob)))
        self.assertTrue(entry["fits_ram"])

    def test_bad_magic_still_rejected(self):
        (self.models / "junk.gguf").write_bytes(b"NOPE" + b"\x00" * 64)
        result = self.discover()
        self.assertEqual(result["valid_models"], [])
        self.assertIn("invalid_gguf_magic", result["corrupted_models"][0]["reason"])

    def test_garbage_header_counts_never_crash_discovery(self):
        # Regression (found by the full-package sweep, 2026-11-12): a file
        # whose header declares absurd tensor/KV counts made the structural
        # parser raise an uncaught struct.error/OverflowError, crashing
        # discovery instead of listing the file as corrupted.
        blob = b"GGUF" + struct.pack("<I", 3) + b"\x01" * 512
        (self.models / "garbage.gguf").write_bytes(blob)
        result = self.discover()
        self.assertEqual(result["valid_models"], [])
        self.assertEqual(len(result["corrupted_models"]), 1)
        self.assertEqual(Path(result["corrupted_models"][0]["file"]).name,
                         "garbage.gguf")


class ThinkingBudgetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ace-think-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = OperationalStore(self.root / "workspace")
        self.addCleanup(self.store.close)
        env = patch.dict(os.environ, {"ACE_MODEL_CACHE": str(self.root / "models"),
                                      "ACE_DEFAULT_MODEL": "", "ACE_LLAMA_CONTEXT": "4096",
                                      "ACE_LLAMA_THREADS": "2"})
        env.start()
        self.addCleanup(env.stop)
        self.router = ModelRouter(self.store)
        discovery = {"ready": True, "llama_binary": "", "server_healthy": True,
                     "server_url": "http://127.0.0.1:8081",
                     "server_models": [{"id": "think-model"}], "valid_models": [],
                     "endpoint_error": ""}
        patched = patch.object(self.router, "discover_local_gguf", return_value=discovery)
        patched.start()
        self.addCleanup(patched.stop)
        self.messages = [{"role": "user", "content": "Jelaskan gap utama proyek ini."}]

    def test_budget_spent_in_reasoning_is_named_not_generic(self):
        payload = {"model": "think-model",
                   "choices": [{"message": {"content": "", "reasoning_content": "berpikir panjang..."},
                                "finish_reason": "length"}],
                   "usage": {"completion_tokens": 32}}
        with patch("ace_operational.models_backend._local_json", return_value=payload):
            result = self.router.generate_text(self.messages, max_tokens=32)
        self.assertFalse(result["success"])
        self.assertEqual(result["failures"][0]["code"], "THINKING_BUDGET_EXHAUSTED")
        self.assertEqual(result["text"], "")

    def test_plain_empty_response_stays_generic_failure(self):
        payload = {"model": "think-model",
                   "choices": [{"message": {"content": ""}, "finish_reason": "stop"}],
                   "usage": {"completion_tokens": 0}}
        with patch("ace_operational.models_backend._local_json", return_value=payload):
            result = self.router.generate_text(self.messages, max_tokens=32)
        self.assertFalse(result["success"])
        self.assertEqual(result["failures"][0]["code"], "SERVER_INFERENCE_FAILED")


if __name__ == "__main__":
    unittest.main()
