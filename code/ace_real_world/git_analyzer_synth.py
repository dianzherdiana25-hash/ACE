"""Git and Codebase Architecture Analytics Synthesizer.

Pure-Python analytics engine for inspecting repository history, code churn,
commit velocity, and architectural hotspots in ACE.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import subprocess
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class ChurnRecord:
    commit_sha: str
    author: str
    timestamp: str
    message: str
    files_changed: int
    insertions: int
    deletions: int


@dataclass
class CodebaseMetrics:
    total_commits: int
    active_branches: int
    total_python_files: int
    total_loc: int
    hotspot_files: List[Tuple[str, int]]
    average_churn_per_commit: float


class GitAnalyzerSynthesizer:
    """Analyzes repository development patterns and synthesizes repository health metrics."""

    def __init__(self, repo_root: str):
        self.repo_root = Path(repo_root).resolve()

    def _run_git(self, args: List[str]) -> Tuple[int, str]:
        res = subprocess.run(
            ["git"] + args,
            cwd=str(self.repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        return res.returncode, res.stdout.strip()

    def get_recent_churn(self, limit: int = 20) -> List[ChurnRecord]:
        """Parse recent git log with shortstat."""
        code, out = self._run_git([
            "log",
            f"-n{limit}",
            "--pretty=format:COMMIT:%H|%an|%cI|%s",
            "--shortstat",
        ])
        if code != 0 or not out:
            return []

        records: List[ChurnRecord] = []
        blocks = out.split("COMMIT:")
        for b in blocks:
            if not b.strip():
                continue
            lines = b.strip().split("\n")
            header = lines[0]
            parts = header.split("|")
            if len(parts) < 4:
                continue
            sha, author, ts, msg = parts[0], parts[1], parts[2], parts[3]

            files_changed, ins, dels = 0, 0, 0
            if len(lines) > 1:
                stat_line = lines[-1]
                # Format: "X files changed, Y insertions(+), Z deletions(-)"
                import re
                fc = re.search(r"(\d+)\s+file", stat_line)
                fi = re.search(r"(\d+)\s+insertion", stat_line)
                fd = re.search(r"(\d+)\s+deletion", stat_line)
                files_changed = int(fc.group(1)) if fc else 0
                ins = int(fi.group(1)) if fi else 0
                dels = int(fd.group(1)) if fd else 0

            records.append(ChurnRecord(
                commit_sha=sha,
                author=author,
                timestamp=ts,
                message=msg,
                files_changed=files_changed,
                insertions=ins,
                deletions=dels,
            ))
        return records

    def compute_codebase_metrics(self) -> CodebaseMetrics:
        """Calculate high-level architectural metrics."""
        # Count commits
        code, out = self._run_git(["rev-list", "--count", "HEAD"])
        total_commits = int(out) if code == 0 and out.isdigit() else 0

        # Count branches
        code, out = self._run_git(["branch", "-a"])
        active_branches = len(out.splitlines()) if code == 0 else 0

        # Scan python files and LOC
        py_files = list(self.repo_root.glob("code/**/*.py")) + list(self.repo_root.glob("tools/**/*.py"))
        total_loc = 0
        file_locs: List[Tuple[str, int]] = []
        for p in py_files:
            try:
                lines = len(p.read_text(encoding="utf-8", errors="ignore").splitlines())
                total_loc += lines
                rel = str(p.relative_to(self.repo_root))
                file_locs.append((rel, lines))
            except Exception:
                pass

        file_locs.sort(key=lambda x: x[1], reverse=True)
        hotspots = file_locs[:5]

        # Recent churn average
        churns = self.get_recent_churn(limit=15)
        avg_churn = sum(c.insertions + c.deletions for c in churns) / max(1, len(churns))

        return CodebaseMetrics(
            total_commits=total_commits,
            active_branches=active_branches,
            total_python_files=len(py_files),
            total_loc=total_loc,
            hotspot_files=hotspots,
            average_churn_per_commit=round(avg_churn, 2),
        )
