"""Fixture sintetik untuk agenda dari aset, verdict, dan prioritas."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools.agenda_candidates import prioritize, propose_asset_pairs, scan_failure_documents


ASSET_SOURCE = "handover/snapshot_assets.json"
REGISTER_SOURCE = "handover/archived_combinations.jsonl"
ASSETS = {
    "tool_a": {"kind": "tool", "name": "Perkakas A", "private": "JANGAN_SALIN"},
    "corpus_a": {"kind": "corpus", "name": "Korpus A"},
    "engine_b": {"kind": "engine", "name": "Mesin B"},
    "venue_c": {"kind": "venue", "name": "Tempat C"},
}
VERDICT = "handover/EVO_0042_KONSOLIDASI.md"
MARKDOWN = """# PROGRAM VERDICT — GATE-42: NOT_PASSED
## Tinjauan
**Gate 42: NOT_PASSED.**
Pembahasan yang menyebutkan FAIL dan NULL sebagai istilah.
> **Laporan lama: ERROR**
## Vonis: NOL
### Probe 2 (VONIS: INSTRUMEN_TIDAK_CUKUP)
- Cek bank uji: `all_green FALSE` (baris verifikasi)
~~~text
- **Fixture contoh: GAGAL**
~~~
## Bukti lama: GAGALAN
### Perbandingan terbaru: PASS
"""


def asset_pairs(assets=ASSETS, entries=()):
    return propose_asset_pairs(
        assets, entries, assets_source=ASSET_SOURCE, snapshot_source=REGISTER_SOURCE,
    )


class AgendaCandidatesTests(unittest.TestCase):
    def test_proposal_assets_respects_snapshot_and_scope(self):
        existing = [{"combination": ["tool_a", "engine_b"], "origin": "synthetic"}]
        proposals = asset_pairs(entries=existing)
        self.assertEqual([row["combination"] for row in proposals],
                         [["corpus_a", "engine_b"], ["corpus_a", "tool_a"]])
        for row in proposals:
            self.assertEqual(row["brain_of_origin"], "codex-proposal")
            self.assertEqual(row["status"], "proposal_only")
            self.assertIs(row["claim_made"], False)
            self.assertIs(row["requires_human_validation"], True)
            self.assertEqual(row["sources"][-1], {"path": REGISTER_SOURCE})
            self.assertEqual(
                [source["asset_id"] for source in row["sources"][:2]], row["combination"],
            )
        self.assertNotIn("JANGAN_SALIN", json.dumps(proposals))

    def test_asset_pair_output_is_order_independent(self):
        self.assertEqual(asset_pairs(dict(reversed(ASSETS.items()))), asset_pairs())

    def test_malformed_snapshot_does_not_silently_treat_pair_as_new(self):
        for entries in ([{}], [{"combination": ["tool_a", "tool_a"]}],
                        [{"combination": ["tool_a", 2]}]):
            with self.subTest(entries=entries), self.assertRaises(ValueError):
                asset_pairs(entries=entries)
        with self.assertRaises(ValueError):
            asset_pairs({"broken": {"kind": "tool"}})

    def test_failure_scanner_reads_declarations_and_deduplicates(self):
        proposals = scan_failure_documents({VERDICT: MARKDOWN})
        self.assertEqual(len(proposals), 4)
        self.assertEqual(
            {row["verdict"]: (row["kind"], [source["line"] for source in row["sources"]])
             for row in proposals},
            {
                "NOT_PASSED": ("failure", [1, 3]), "NOL": ("null", [6]),
                "INSTRUMEN_TIDAK_CUKUP": ("blocked", [7]),
                "ALL_GREEN_FALSE": ("failure", [8]),
            },
        )
        self.assertEqual(len({row["proposal_id"] for row in proposals}), 4)
        for row in proposals:
            self.assertEqual(row["brain_of_origin"], "codex-proposal")
            self.assertTrue(all(source["path"] == VERDICT for source in row["sources"]))

    def test_unknown_or_non_result_content_does_not_create_proposal(self):
        self.assertEqual(scan_failure_documents({
            VERDICT: "# Sebuah laporan\n## Hasil: PASS\nNarasi contoh null.\n"
                     "```\n## Probe: FAIL\n```\n## Hasil: NULLIFIED\n",
        }), [])

    def test_failure_ids_distinguish_sources_keep_identity_after_line_shift(self):
        second = "handover/SNAPSHOT_VERDICT.md"
        plain = "**Probe: FAIL**\n"
        original = scan_failure_documents({VERDICT: plain})[0]
        proposals = scan_failure_documents({second: plain, VERDICT: "\n" + plain})
        self.assertEqual(len(proposals), 2)
        self.assertNotEqual(proposals[0]["proposal_id"], proposals[1]["proposal_id"])
        revised = next(row for row in proposals if row["sources"][0]["path"] == VERDICT)
        self.assertEqual(revised["proposal_id"], original["proposal_id"])
        self.assertEqual(revised["sources"][0]["line"], 2)

    def test_priority_order_has_id_tie_break_and_ignores_previous_rank(self):
        proposals = asset_pairs() + scan_failure_documents({VERDICT: MARKDOWN})
        ranked = prioritize(proposals)
        self.assertEqual([row["kind"] for row in ranked],
                         ["blocked", "failure", "failure", "null", "asset_pair",
                          "asset_pair", "asset_pair"])
        self.assertEqual([row["priority_rank"] for row in ranked], list(range(1, 8)))
        self.assertEqual(
            [row["proposal_id"] for row in ranked[1:3]],
            sorted(row["proposal_id"] for row in ranked[1:3]),
        )
        self.assertEqual(ranked, prioritize(reversed(proposals)))
        self.assertEqual(ranked, prioritize(ranked + proposals))
        self.assertTrue(all("priority_rank" not in row for row in proposals))

    def test_prioritizer_requires_citations_and_attribution_and_rejects_conflicts(self):
        row = asset_pairs()[0]
        for field, value in (("brain_of_origin", ""), ("title", ""), ("sources", []),
                             ("sources", [{"path": "../file.md"}]), ("claim_made", True),
                             ("sources", [{"path": VERDICT, "line": True}])):
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                prioritize([{**row, field: value}])
        with self.assertRaises(ValueError):
            prioritize([row, {**row, "title": "Judul berbeda untuk ID sama"}])

    def test_cli_chain_reads_fixture_and_writes_only_stdout(self):
        script = Path(__file__).with_name("agenda_candidates.py")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "handover").mkdir()
            fixtures = {
                ASSET_SOURCE: json.dumps(ASSETS),
                REGISTER_SOURCE: json.dumps({"combination": ["tool_a", "engine_b"]}) + "\n",
                VERDICT: MARKDOWN,
            }
            for path, contents in fixtures.items():
                (root / path).write_text(contents, encoding="utf-8")

            def run(*args, check=True):
                return subprocess.run(
                    [sys.executable, str(script), "--repo", str(root), *args],
                    capture_output=True, text=True, check=check,
                )

            missing = run("assets", "--assets-file", ASSET_SOURCE,
                          "--register-snapshot", "missing.jsonl", check=False)
            self.assertEqual(missing.returncode, 2)
            self.assertEqual(missing.stdout, "")
            self.assertEqual(run("failures", "../outside.md", check=False).returncode, 2)
            proposals = run("assets", "--assets-file", ASSET_SOURCE, "--register-snapshot",
                            REGISTER_SOURCE).stdout + run("failures", VERDICT).stdout
            seen = {p.relative_to(root).as_posix(): p.read_text(encoding="utf-8")
                    for p in root.rglob("*") if p.is_file()}
            self.assertEqual(seen, fixtures)
            (root / "draft.jsonl").write_text(proposals, encoding="utf-8")
            ranked = [json.loads(line) for line in run("prioritize", "draft.jsonl").stdout.splitlines()]
            self.assertEqual((len(ranked), ranked[0]["kind"], ranked[-1]["kind"]),
                             (6, "blocked", "asset_pair"))


if __name__ == "__main__":
    unittest.main()
