"""Edge-case unit tests for tools/omega_environment_probe.py (read-only target)."""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import omega_environment_probe as oep

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "tools" / "omega_environment_probe.py"


class OmegaEnvironmentProbeEdgeTests(unittest.TestCase):
    """22 edge-case tests for local read-only hardware/runtime probe."""

    def test_01_read_missing_file_returns_none(self) -> None:
        self.assertIsNone(oep._read(Path("/tmp/definitely_missing_omega_probe_file")))

    def test_02_read_invalid_utf8_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "bad.bin"
            p.write_bytes(b"\xff\xfe\xfd")
            self.assertIsNone(oep._read(p))

    def test_03_read_valid_file_strips_whitespace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "ok.txt"
            p.write_text("  hello omega \n\t ", encoding="utf-8")
            self.assertEqual(oep._read(p), "hello omega")

    def test_04_integer_handles_none_max_nonnumeric_zero_negative(self) -> None:
        self.assertIsNone(oep._integer(None))
        self.assertIsNone(oep._integer("max"))
        self.assertIsNone(oep._integer("12.5"))
        self.assertIsNone(oep._integer("abc"))
        self.assertEqual(oep._integer("0"), 0)
        self.assertEqual(oep._integer("-42"), -42)
        self.assertEqual(oep._integer("1024"), 1024)

    def test_05_model_missing_file_reports_not_present(self) -> None:
        res = oep._model(Path("/tmp/nonexistent_model.gguf"), hash_artifact=True)
        self.assertFalse(res["present"])
        self.assertEqual(res["inference_status"], "NOT_ASSESSED")
        self.assertNotIn("sha256", res)

    def test_06_model_directory_treated_as_not_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "subdir.gguf"
            d.mkdir()
            res = oep._model(d, hash_artifact=True)
            self.assertFalse(res["present"])

    def test_07_model_empty_file_not_gguf_and_hashes_when_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            m = Path(tmp) / "empty.bin"
            m.write_bytes(b"")
            res_nohash = oep._model(m, hash_artifact=False)
            self.assertTrue(res_nohash["present"])
            self.assertEqual(res_nohash["size_bytes"], 0)
            self.assertFalse(res_nohash["gguf_magic_valid"])
            self.assertNotIn("sha256", res_nohash)

            res_hash = oep._model(m, hash_artifact=True)
            self.assertEqual(res_hash["sha256"], hashlib.sha256(b"").hexdigest())

    def test_08_model_gguf_magic_valid_and_sha256_matches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            payload = b"GGUF\x03\x00\x00\x00payload"
            m = Path(tmp) / "tiny.gguf"
            m.write_bytes(payload)
            res = oep._model(m, hash_artifact=True)
            self.assertTrue(res["present"])
            self.assertTrue(res["gguf_magic_valid"])
            self.assertEqual(res["size_bytes"], len(payload))
            self.assertEqual(res["sha256"], hashlib.sha256(payload).hexdigest())

    def test_09_model_read_error_captured_gracefully(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            m = Path(tmp) / "locked.gguf"
            m.write_bytes(b"GGUFdata")
            with patch.object(Path, "open", side_effect=PermissionError("denied")):
                res = oep._model(m, hash_artifact=True)
            self.assertTrue(res["present"])
            self.assertEqual(res["read_error"], "PermissionError")

    def test_10_cgroups_skips_parent_traversal_entries(self) -> None:
        with patch.object(oep, "_read", side_effect=lambda p: "0::/../../escape" if str(p) == "/proc/self/cgroup" else None):
            records = oep._cgroups()
            self.assertEqual(records, [])

    def test_11_probe_meminfo_ignores_non_kb_units(self) -> None:
        fake_mem = "MemTotal: 100 kB\nMemFree: 50 MB\nSwapTotal: max kB\n"
        with patch.object(oep, "_read", side_effect=lambda p: fake_mem if str(p) == "/proc/meminfo" else None), patch.object(
            oep, "_cgroups", return_value=[]
        ):
            with tempfile.TemporaryDirectory() as tmp:
                snap = oep.probe(Path(tmp), [])
        self.assertEqual(snap["memory"]["host_bytes"], {"MemTotal": 100 * 1024})

    def test_12_probe_cgroup_quotas_ignores_zero_period_and_max(self) -> None:
        groups = [
            {"path": "/sys/fs/cgroup/a", "values": {"memory.max": "max", "memory.current": "10", "cpu.max": "max 100000"}},
            {"path": "/sys/fs/cgroup/b", "values": {"memory.max": "2048", "memory.current": "3000", "cpu.max": "50000 0"}},
            {"path": "/sys/fs/cgroup/c", "values": {"memory.max": "4096", "memory.current": "1024", "cpu.max": "50000 100000"}},
        ]
        with patch.object(oep, "_cgroups", return_value=groups), patch.object(oep, "_read", return_value=None):
            with tempfile.TemporaryDirectory() as tmp:
                snap = oep.probe(Path(tmp), [])
        self.assertEqual(snap["cpu"]["cgroup_quota_cores"], 0.5)
        self.assertEqual(snap["memory"]["cgroup_limit_bytes"], 2048)
        self.assertEqual(snap["memory"]["cgroup_unallocated_bytes"], 0)

    def test_13_probe_handles_sched_getaffinity_oserror(self) -> None:
        with patch("os.sched_getaffinity", side_effect=OSError("unsupported")), patch.object(
            oep, "_cgroups", return_value=[]
        ), patch.object(oep, "_read", return_value=None):
            with tempfile.TemporaryDirectory() as tmp:
                snap = oep.probe(Path(tmp), [])
        self.assertIsNone(snap["cpu"]["affinity_cpus"])

    def test_14_probe_handles_missing_workspace_disk_usage_error(self) -> None:
        with patch.object(oep, "_cgroups", return_value=[]), patch.object(oep, "_read", return_value=None):
            snap = oep.probe(Path("/tmp/no_such_omega_workspace_dir"), [])
        self.assertIn("read_error", snap["disk"])

    def test_15_probe_network_policy_malformed_json_sets_parse_error(self) -> None:
        def fake_read(path: Path) -> str | None:
            if str(path) == "/etc/codex/network-policy.json":
                return "{invalid"
            return None

        with patch.object(oep, "_read", side_effect=fake_read), patch.object(oep, "_cgroups", return_value=[]):
            with tempfile.TemporaryDirectory() as tmp:
                snap = oep.probe(Path(tmp), [])
        self.assertTrue(snap["network"].get("startup_snapshot_parse_error"))

    def test_16_probe_network_policy_list_json_sets_parse_error(self) -> None:
        def fake_read(path: Path) -> str | None:
            if str(path) == "/etc/codex/network-policy.json":
                return "[]"
            return None

        with patch.object(oep, "_read", side_effect=fake_read), patch.object(oep, "_cgroups", return_value=[]):
            with tempfile.TemporaryDirectory() as tmp:
                snap = oep.probe(Path(tmp), [])
        self.assertTrue(snap["network"].get("startup_snapshot_parse_error"))

    def test_17_probe_network_policy_valid_dict_extracted(self) -> None:
        def fake_read(path: Path) -> str | None:
            if str(path) == "/etc/codex/network-policy.json":
                return json.dumps({"http_network_policy": {"type": "allowlist"}, "vpn_configured": False})
            return None

        with patch.object(oep, "_read", side_effect=fake_read), patch.object(oep, "_cgroups", return_value=[]):
            with tempfile.TemporaryDirectory() as tmp:
                snap = oep.probe(Path(tmp), [])
        self.assertEqual(snap["network"]["startup_http_mode"], "allowlist")
        self.assertFalse(snap["network"]["vpn_configured"])

    def test_18_probe_explicit_llama_bin_unset_and_non_executable_and_executable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bin_file = Path(tmp) / "llama-cli"
            bin_file.write_text("#!/bin/sh\n", encoding="utf-8")
            os.chmod(bin_file, 0o644)
            with patch.object(oep, "_cgroups", return_value=[]), patch.object(oep, "_read", return_value=None):
                with patch.dict(os.environ, {}, clear=False):
                    os.environ.pop("ACE_LLAMA_BIN", None)
                    s1 = oep.probe(Path(tmp), [])
                    self.assertFalse(s1["explicit_llama_binary"]["configured"])
                    self.assertFalse(s1["explicit_llama_binary"]["executable_present"])

                with patch.dict(os.environ, {"ACE_LLAMA_BIN": str(bin_file)}, clear=False):
                    s2 = oep.probe(Path(tmp), [])
                    self.assertTrue(s2["explicit_llama_binary"]["configured"])
                    self.assertFalse(s2["explicit_llama_binary"]["executable_present"])

                os.chmod(bin_file, 0o755)
                with patch.dict(os.environ, {"ACE_LLAMA_BIN": str(bin_file)}, clear=False):
                    s3 = oep.probe(Path(tmp), [])
                    self.assertTrue(s3["explicit_llama_binary"]["executable_present"])

    def test_19_probe_cpuinfo_flags_and_virtualization_detection(self) -> None:
        fake_cpu = "processor\t: 0\nmodel name\t: Test EPYC\nflags\t\t: fpu hypervisor vmx\n"
        with patch.object(oep, "_read", side_effect=lambda p: fake_cpu if str(p) == "/proc/cpuinfo" else None), patch.object(
            oep, "_cgroups", return_value=[]
        ):
            with tempfile.TemporaryDirectory() as tmp:
                snap = oep.probe(Path(tmp), [])
        self.assertEqual(snap["cpu"]["model_name"], "Test EPYC")
        self.assertTrue(snap["virtualization"]["hypervisor_cpu_flag"])
        self.assertEqual(snap["virtualization"]["cpu_virtualization_flags"], ["vmx"])

    def test_20_probe_governance_and_readiness_guards_always_unassessed(self) -> None:
        with patch.object(oep, "_cgroups", return_value=[]), patch.object(oep, "_read", return_value=None):
            with tempfile.TemporaryDirectory() as tmp:
                snap = oep.probe(Path(tmp), [])
        self.assertEqual(snap["schema"], "ace.omega.environment_snapshot.v1")
        self.assertEqual(snap["status"], "ATTESTED_SNAPSHOT")
        self.assertEqual(snap["model_readiness"], "NOT_ASSESSED_REQUIRES_ACTUAL_INFERENCE")
        self.assertEqual(snap["scientific_status"], "NOT_ASSESSED")
        self.assertEqual(snap["network"]["live_access"], "NOT_ASSESSED")

    def test_21_probe_multiple_model_files_preserves_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            m1 = Path(tmp) / "a.gguf"
            m2 = Path(tmp) / "b.gguf"
            m1.write_bytes(b"GGUF\x01")
            with patch.object(oep, "_cgroups", return_value=[]), patch.object(oep, "_read", return_value=None):
                snap = oep.probe(Path(tmp), [m1, m2], hash_artifacts=False)
        self.assertEqual(len(snap["models"]), 2)
        self.assertTrue(snap["models"][0]["present"])
        self.assertFalse(snap["models"][1]["present"])

    def test_22_cli_runs_cleanly_with_workspace_and_sha256_flags(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            model = Path(tmp) / "m.gguf"
            model.write_bytes(b"GGUFtest")
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), "--workspace", tmp, "--model-file", str(model), "--sha256"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["schema"], "ace.omega.environment_snapshot.v1")
            self.assertEqual(len(payload["models"]), 1)
            self.assertEqual(payload["models"][0]["sha256"], hashlib.sha256(b"GGUFtest").hexdigest())


if __name__ == "__main__":
    unittest.main()
