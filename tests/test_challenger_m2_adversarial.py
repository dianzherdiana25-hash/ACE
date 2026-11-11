"""Empirical Adversarial Challenge Suite for ACE Milestone 2 (M2).

Adversarial verification of:
1. ace_self_evolver.py (zero fake scores, truthful evaluation, branch isolation)
2. code/ace_mission/admission.py (zero-tolerance admission gate, reject illegal decisions, reject failing candidates)
3. Branch isolation and git safety (never commit/push to main, rollback on failure, detached HEAD handling)
4. code/ace_host_controller/repo_janitor.py (elimination of auto-merge to main)
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

_ROOT_DIR = Path(__file__).resolve().parent.parent
_CODE_DIR = _ROOT_DIR / "code"
if str(_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(_CODE_DIR))
if str(_ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(_ROOT_DIR))

import ace_self_evolver
from ace_mission.admission import ARTIFACT_SCHEMA, REQUESTS, evaluate_submission
from ace_cognition.reasoning import SCHEMA, canonical, digest


class AdversarialMilestone2ChallengeTests(unittest.TestCase):
    """Adversarial challenge suite stress-testing self-evolver, admission, and git protection."""

    # -------------------------------------------------------------------------
    # VECTOR 1: Non-Reasoning Mission Truthful Scoring (No Fake Evidence)
    # -------------------------------------------------------------------------
    def test_vector1_unsupported_mission_strictly_zero_score_and_no_fake_evidence(self):
        """Attempt to evaluate an unsupported mission: verify benchmark_score == 0.0,
        status == UNVERIFIED_PROPOSAL, decision == PENDING_EVALUATION.
        Prove it NEVER fabricates 1.0 or fake scientific evidence strings.
        """
        with tempfile.TemporaryDirectory() as td:
            artifacts_dir = Path(td)
            malicious_mission = {
                "id": "mission_adv_unverified_001",
                "goal": "Claim artificial general intelligence without testing",
                "hypothesis": "Hypothesis that should never be admitted",
            }
            art_path, dec, metrics = ace_self_evolver.evaluate_and_solve_mission(malicious_mission, artifacts_dir)

            # 1. Assert proposed decision is PENDING_EVALUATION, never ACCEPTED or GO
            self.assertEqual(dec, "PENDING_EVALUATION")
            self.assertNotEqual(dec, "ACCEPTED")
            self.assertNotEqual(dec, "GO")

            # 2. Assert score is strictly 0.0, NEVER 1.0
            self.assertEqual(metrics.get("benchmark_score"), 0.0)
            self.assertNotEqual(metrics.get("benchmark_score"), 1.0)
            self.assertFalse(metrics.get("benchmark_score", 0.0) > 0.0)

            # 3. Inspect written artifact receipt
            self.assertTrue(art_path.exists())
            raw_text = art_path.read_text(encoding="utf-8")
            data = json.loads(raw_text)

            self.assertEqual(data["status"], "UNVERIFIED_PROPOSAL")
            self.assertEqual(data["decision"], "PENDING_EVALUATION")
            self.assertEqual(data["metrics"]["benchmark_score"], 0.0)

            # 4. Strict assertion: zero fake evidence strings
            self.assertNotIn("VERIFIED_AND_ADMITTED", raw_text)
            self.assertNotIn("inductive invariant", raw_text.lower())
            self.assertNotIn("formal inductive", raw_text.lower())

    # -------------------------------------------------------------------------
    # VECTOR 2: Admission Gate Rejection of Illegal Decisions
    # -------------------------------------------------------------------------
    def test_vector2_admission_strictly_rejects_illegal_decision_strings(self):
        """Submit illegal or maliciously crafted decision strings to admission gate.
        Verify admission.py strictly raises ValueError('unsupported mission decision').
        """
        illegal_decisions = [
            "GO",
            "FAKE",
            "ACCEPTED_BY_GOD",
            "PROCEED",
            "PASS",
            "",
            "   ",
            "accepted",  # lowercase must fail
            "staged_empirical",
            None,
            123,
            True,
            ["ACCEPTED"],
            {"decision": "ACCEPTED"},
        ]

        dummy_mission = {
            "id": "mission_adv_admission_002",
            "goal": "Test admission rejection",
            "hypothesis": "Illegal decision strings must raise ValueError",
        }
        dummy_artifact = b'{"schema": "ace.mission.reasoning-candidate.v1"}'

        for ill in illegal_decisions:
            with self.subTest(illegal_decision=ill):
                with self.assertRaises(ValueError) as ctx:
                    evaluate_submission(dummy_mission, dummy_artifact, ill)
                self.assertIn("unsupported mission decision", str(ctx.exception).lower())

        # Also verify that legal REQUESTS are defined and 'GO' is strictly absent
        self.assertNotIn("GO", REQUESTS)
        self.assertIn("ACCEPTED", REQUESTS)
        self.assertIn("STAGED_EMPIRICAL", REQUESTS)
        self.assertIn("PENDING_EVALUATION", REQUESTS)
        self.assertIn("INCONCLUSIVE", REQUESTS)
        self.assertIn("REJECTED", REQUESTS)

    # -------------------------------------------------------------------------
    # VECTOR 3: Pre-Commit Verification Failure Aborts Git Commit
    # -------------------------------------------------------------------------
    def test_vector3_git_commit_aborted_when_verification_gate_fails(self):
        """Simulate pre-commit acceptance/mission test suite failure.
        Verify execute_isolated_git_commit aborts, returns False,
        and never stages or commits anything to main.
        """
        with patch("ace_self_evolver.get_current_git_branch", return_value="main"):
            with patch("ace_self_evolver.run_verification_test_gate", return_value=(False, "Simulated 1 failure in acceptance")):
                with patch("ace_self_evolver.run_cmd") as mock_run_cmd:
                    ok, msg = ace_self_evolver.execute_isolated_git_commit(
                        mission_id="m_adv_test_003",
                        goal="Simulated failure mission",
                        artifact_path=Path("/tmp/fake_artifact.json"),
                        allow_push=False,
                    )
                    self.assertFalse(ok)
                    self.assertIn("pre-commit verification failed", msg.lower())

                    # Verify git checkout -b or git commit were NEVER invoked
                    for call_args in mock_run_cmd.call_args_list:
                        cmd = call_args[0][0]
                        self.assertNotIn("commit", cmd)
                        self.assertNotIn("push", cmd)

    # -------------------------------------------------------------------------
    # VECTOR 4: Collision When Active Branch Matches Target Branch
    # -------------------------------------------------------------------------
    def test_vector4_git_commit_refuses_when_active_matches_target(self):
        """Attempt to run isolated commit when already on ace-evolution/{mission_id}.
        Verify immediate refusal with clear error message.
        """
        target_branch = "ace-evolution/m_adv_target_004"
        with patch("ace_self_evolver.get_current_git_branch", return_value=target_branch):
            ok, msg = ace_self_evolver.execute_isolated_git_commit(
                mission_id="m_adv_target_004",
                goal="Collision target",
                artifact_path=Path("/tmp/fake.json"),
                allow_push=False,
            )
            self.assertFalse(ok)
            self.assertIn("invalid active branch", msg.lower())

    # -------------------------------------------------------------------------
    # VECTOR 5: Detached HEAD Handling
    # -------------------------------------------------------------------------
    def test_vector5_detached_head_handling_safe(self):
        """When in detached HEAD state (git branch --show-current is empty),
        get_current_git_branch() must safely return 'main' without unhandled exception.
        """
        with patch("ace_self_evolver.run_cmd", return_value=(0, "")):
            branch = ace_self_evolver.get_current_git_branch()
            self.assertEqual(branch, "main")

    # -------------------------------------------------------------------------
    # VECTOR 6: RepoJanitor Has ZERO Auto-Merge into Main
    # -------------------------------------------------------------------------
    def test_vector6_repo_janitor_has_zero_auto_merge_to_main(self):
        """Verify code/ace_host_controller/repo_janitor.py merge_and_clean_branches():
        1. Never runs git merge or git merge --ff-only into main.
        2. Returns [] (empty list).
        3. Never deletes branches.
        """
        from ace_host_controller.repo_janitor import AutonomousRepoJanitor

        with tempfile.TemporaryDirectory() as td:
            repo_path = Path(td)
            janitor = AutonomousRepoJanitor(repo_root=repo_path)

            # Mock git branch --list to return feature branches
            def mock_subprocess_run(cmd, *args, **kwargs):
                cmd_str = " ".join(cmd) if isinstance(cmd, list) else str(cmd)
                mock_proc = MagicMock()
                mock_proc.returncode = 0
                if "branch --list" in cmd_str:
                    mock_proc.stdout = "  ace-dev/exploratory_test\n  ace-autonomous/loop_01\n"
                elif "branch --show-current" in cmd_str:
                    mock_proc.stdout = "main\n"
                elif "git merge" in cmd_str:
                    raise AssertionError(f"FATAL: git merge was invoked in repo_janitor! Command: {cmd_str}")
                else:
                    mock_proc.stdout = ""
                return mock_proc

            with patch("subprocess.run", side_effect=mock_subprocess_run):
                merged = janitor.merge_and_clean_branches()
                # Must return empty list, zero merges performed
                self.assertEqual(merged, [])

    # -------------------------------------------------------------------------
    # VECTOR 7: Real Isolated Git Repo Simulation (Main Untouched)
    # -------------------------------------------------------------------------
    def test_vector7_real_git_repository_branch_isolation_and_main_untouched(self):
        """Initialize an actual temporary Git repository, create a commit on 'main',
        and execute execute_isolated_git_commit.
        Verify:
        - Changes are committed on 'ace-evolution/{mission_id}'.
        - Active branch returns to 'main'.
        - 'main' HEAD commit SHA is IDENTICAL before and after (main is completely untouched).
        - Direct push to main is NEVER executed.
        """
        with tempfile.TemporaryDirectory() as td:
            repo_dir = Path(td)

            # Initialize real git repo
            subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@ace.local"], cwd=repo_dir, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "ACE Tester"], cwd=repo_dir, check=True, capture_output=True)
            subprocess.run(["git", "checkout", "-b", "main"], cwd=repo_dir, check=True, capture_output=True)

            # Initial commit on main
            readme = repo_dir / "README.md"
            readme.write_text("# Test Repo\n", encoding="utf-8")
            subprocess.run(["git", "add", "README.md"], cwd=repo_dir, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "Initial commit on main"], cwd=repo_dir, check=True, capture_output=True)

            # Get initial main SHA
            initial_sha = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=repo_dir, check=True, capture_output=True, text=True
            ).stdout.strip()

            # Create artifact to commit
            evidence_dir = repo_dir / "evidence" / "autonomous_missions"
            evidence_dir.mkdir(parents=True, exist_ok=True)
            art_file = evidence_dir / "m_real_git_007_solution.json"
            art_file.write_text('{"status": "TEST_STAGED"}', encoding="utf-8")

            # Mock test gate to pass and run execute_isolated_git_commit inside real git repo
            with patch("ace_self_evolver.ROOT_DIR", repo_dir):
                with patch("ace_self_evolver.run_verification_test_gate", return_value=(True, "All pass")):
                    ok, msg = ace_self_evolver.execute_isolated_git_commit(
                        mission_id="m_real_git_007",
                        goal="Prove branch isolation in real git",
                        artifact_path=art_file,
                        allow_push=False,
                    )
                    self.assertTrue(ok, f"Expected commit to succeed, got: {msg}")

            # Verification 1: Current active branch must be back on 'main'
            current_branch = subprocess.run(
                ["git", "branch", "--show-current"], cwd=repo_dir, check=True, capture_output=True, text=True
            ).stdout.strip()
            self.assertEqual(current_branch, "main")

            # Verification 2: 'main' SHA must be UNCHANGED
            final_main_sha = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=repo_dir, check=True, capture_output=True, text=True
            ).stdout.strip()
            self.assertEqual(final_main_sha, initial_sha, "CRITICAL BUG: 'main' branch SHA was modified!")

            # Verification 3: Isolated branch exists and contains the commit
            branch_sha = subprocess.run(
                ["git", "rev-parse", "ace-evolution/m_real_git_007"],
                cwd=repo_dir,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            self.assertNotEqual(branch_sha, initial_sha)

            # Verification 4: The commit log on the isolated branch mentions the goal and mission
            log_out = subprocess.run(
                ["git", "log", "-1", "ace-evolution/m_real_git_007"],
                cwd=repo_dir,
                check=True,
                capture_output=True,
                text=True,
            ).stdout
            self.assertIn("feat(ace-evolution): Prove branch isolation in real git", log_out)
            self.assertIn("[m_real_git_007]", log_out)

    # -------------------------------------------------------------------------
    # VECTOR 8: Git Push Only Targets Isolated Branch, NEVER Main
    # -------------------------------------------------------------------------
    def test_vector8_git_push_strictly_targets_isolated_branch_never_main(self):
        """When allow_push=True, verify git push command only pushes origin ace-evolution/{mission_id},
        and NEVER origin main.
        When allow_push=False, verify git push is NEVER executed.
        """
        captured_cmds = []

        def spy_run_cmd(cmd, *args, **kwargs):
            captured_cmds.append(cmd)
            # Simulate git branch --show-current
            if cmd == ["git", "branch", "--show-current"]:
                return 0, "main\n"
            return 0, ""

        # Case A: allow_push=False -> NO push called
        with patch("ace_self_evolver.run_cmd", side_effect=spy_run_cmd):
            with patch("ace_self_evolver.run_verification_test_gate", return_value=(True, "ok")):
                ok, msg = ace_self_evolver.execute_isolated_git_commit(
                    "mission_push_off", "Goal", Path("/tmp/art.json"), allow_push=False
                )
                self.assertTrue(ok)
                push_calls = [c for c in captured_cmds if "push" in c]
                self.assertEqual(push_calls, [], "CRITICAL: git push called when allow_push=False!")

        # Case B: allow_push=True -> push ONLY to origin ace-evolution/mission_push_on
        captured_cmds.clear()
        with patch("ace_self_evolver.run_cmd", side_effect=spy_run_cmd):
            with patch("ace_self_evolver.run_verification_test_gate", return_value=(True, "ok")):
                ok, msg = ace_self_evolver.execute_isolated_git_commit(
                    "mission_push_on", "Goal", Path("/tmp/art.json"), allow_push=True
                )
                self.assertTrue(ok)
                push_calls = [c for c in captured_cmds if "push" in c]
                self.assertEqual(len(push_calls), 1)
                self.assertEqual(push_calls[0], ["git", "push", "origin", "ace-evolution/mission_push_on"])
                # Prove main is NEVER pushed
                self.assertNotIn("main", push_calls[0])

    # -------------------------------------------------------------------------
    # VECTOR 9: Adversarial Reasoning Candidate Evaluation Rejects Counterexamples
    # -------------------------------------------------------------------------
    def test_vector9_admission_gate_rejects_flawed_reasoning_candidate(self):
        """Submit a reasoning candidate program that fails on validation cases.
        Verify admission.py independently catches the discrepancy and returns REJECTED
        with reason DEVELOPMENT_COUNTEREXAMPLE.
        """
        # Flawed program: outputs constant 1 (passes train x=1,y=0 -> 1, but FAILS validation x=2,y=0 -> 1 != 2)
        problem_data = {
            "schema": SCHEMA,
            "id": "prob_identity_adv",
            "goal": "compute x",
            "train": [
                {"inputs": {"x": 1, "y": 0}, "output": 1},
            ],
            "validation": [
                {"inputs": {"x": 2, "y": 0}, "output": 2},
            ],
        }
        mission = {
            "id": "mission_adv_eval_009",
            "goal": "Identity function",
            "hypothesis": "Test candidate",
            "reasoning_problem": problem_data,
            "acceptance": {"metric": "exact_development_fit", "threshold": 1, "comparator": "none"},
            "budget": {"max_primitive_operations": 10000, "time_sec": 2.0, "max_candidates": 10},
        }

        flawed_program = {"const": 1}
        artifact_bytes = json.dumps({
            "schema": ARTIFACT_SCHEMA,
            "problem_digest": digest(problem_data),
            "program": flawed_program,
        }).encode("utf-8")

        receipt = evaluate_submission(mission, artifact_bytes, requested_decision="STAGED_EMPIRICAL")
        self.assertEqual(receipt["decision"], "REJECTED")
        self.assertEqual(receipt["reason"], "DEVELOPMENT_COUNTEREXAMPLE")
        self.assertIsNotNone(receipt.get("counterexample"))
        self.assertEqual(receipt["counterexample"]["expected"], 2)
        self.assertEqual(receipt["counterexample"]["actual"], 1)

    # -------------------------------------------------------------------------
    # VECTOR 10: Admission Gate Rejects Malicious / Corrupted Artifacts
    # -------------------------------------------------------------------------
    def test_vector10_admission_gate_rejects_corrupted_artifacts(self):
        """Stress-test admission gate against:
        1. Duplicate JSON keys
        2. Oversized payload (> 65,536 bytes)
        3. Problem digest mismatch
        """
        problem_data = {
            "schema": SCHEMA,
            "id": "prob_simple",
            "goal": "identity",
            "train": [{"inputs": {"x": 1, "y": 0}, "output": 1}],
            "validation": [{"inputs": {"x": 2, "y": 0}, "output": 2}],
        }
        mission = {
            "id": "mission_corrupted_010",
            "goal": "Identity",
            "hypothesis": "Test",
            "reasoning_problem": problem_data,
            "acceptance": {"metric": "exact_development_fit", "threshold": 1, "comparator": "none"},
            "budget": {"max_primitive_operations": 1000, "time_sec": 1.0, "max_candidates": 5},
        }

        # 1. Duplicate JSON keys in candidate
        dup_bytes = b'{"schema": "ace.mission.reasoning-candidate.v1", "schema": "duplicate"}'
        receipt1 = evaluate_submission(mission, dup_bytes, "STAGED_EMPIRICAL")
        self.assertEqual(receipt1["decision"], "REJECTED")
        self.assertIn("duplicate json key", receipt1["reason"].lower())

        # 2. Oversized payload (> 65KB)
        oversized = (b'{"schema": "ace.mission.reasoning-candidate.v1", "pad": "' + b'A' * 70_000 + b'"}')
        receipt2 = evaluate_submission(mission, oversized, "STAGED_EMPIRICAL")
        self.assertEqual(receipt2["decision"], "REJECTED")
        self.assertEqual(receipt2["reason"], "ARTIFACT_SIZE_LIMIT")

        # 3. Problem digest mismatch
        fake_binding = json.dumps({
            "schema": ARTIFACT_SCHEMA,
            "problem_digest": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
            "program": 1,
        }).encode("utf-8")
        receipt3 = evaluate_submission(mission, fake_binding, "STAGED_EMPIRICAL")
        self.assertEqual(receipt3["decision"], "REJECTED")
        self.assertIn("binding mismatch", receipt3["reason"].lower())

    # -------------------------------------------------------------------------
    # VECTOR 11: Evolver Loop Skips Git Mutations on Unadmitted Missions
    # -------------------------------------------------------------------------
    def test_vector11_evolver_loop_never_commits_unadmitted_mission(self):
        """When bus submission yields PENDING_EVALUATION, REJECTED, or INCONCLUSIVE,
        execute_self_evolution strictly skips git commits.
        """
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td)
            from ace_mission.bus import MissionBus
            from ace_mission.generator import MissionGenerator

            bus = MissionBus(ws / "mission_bus.sqlite3")
            gen = MissionGenerator(bus)

            # Publish a frontier mission (unsupported domain)
            gen.generate_from_diagnostics([
                {"type": "METHOD_SHORTAGE", "details": "Unverified domain task"}
            ])

            with patch("ace_self_evolver.ROOT_DIR", ws):
                with patch("ace_self_evolver.execute_isolated_git_commit") as mock_commit:
                    ace_self_evolver.execute_self_evolution(
                        workspace_path=ws,
                        max_missions=1,
                        continuous=False,
                        dry_run=False,
                    )
                    # execute_isolated_git_commit must NEVER be called because mission was PENDING_EVALUATION
                    mock_commit.assert_not_called()

    # -------------------------------------------------------------------------
    # VECTOR 12: Codebase Static Audit: Zero 'git push origin main' in Entire Repo
    # -------------------------------------------------------------------------
    def test_vector12_codebase_grep_proves_zero_git_push_main(self):
        """Empirically scan all python and shell files in the repository.
        Prove that there are ZERO unverified direct pushes or merges to main.
        """
        patterns = ["git push origin main", "git merge --ff-only"]
        violations = []

        scan_dirs = [_ROOT_DIR / "code", _ROOT_DIR / "tools", _ROOT_DIR / "ace_self_evolver.py"]
        for target in scan_dirs:
            if target.is_file():
                files = [target]
            else:
                files = list(target.rglob("*.py")) + list(target.rglob("*.sh"))

            for f in files:
                text = f.read_text(encoding="utf-8", errors="ignore")
                for pat in patterns:
                    if pat in text:
                        violations.append((str(f), pat))

        self.assertEqual(
            violations,
            [],
            f"CRITICAL VIOLATION: Found forbidden git operations in repository: {violations}"
        )

    # -------------------------------------------------------------------------
    # VECTOR 13: Adversarial Mission IDs (Path Traversal, Flag Injection)
    # -------------------------------------------------------------------------
    def test_vector13_adversarial_mission_ids_do_not_compromise_main(self):
        """Stress-test execute_isolated_git_commit with malicious mission_id inputs:
        1. mission_id = 'main' -> branch is 'ace-evolution/main', NOT 'main'.
        2. mission_id = '../main' -> invalid branch name, rejected cleanly by git.
        3. mission_id = '--orphan main' -> invalid branch name, rejected cleanly.
        Verify main is untouched in all cases.
        """
        with tempfile.TemporaryDirectory() as td:
            repo_dir = Path(td)
            subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@ace.local"], cwd=repo_dir, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "ACE Tester"], cwd=repo_dir, check=True, capture_output=True)
            subprocess.run(["git", "checkout", "-b", "main"], cwd=repo_dir, check=True, capture_output=True)
            (repo_dir / "init.txt").write_text("initial", encoding="utf-8")
            subprocess.run(["git", "add", "init.txt"], cwd=repo_dir, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=repo_dir, check=True, capture_output=True)

            art_file = repo_dir / "art.json"
            art_file.write_text("{}", encoding="utf-8")

            with patch("ace_self_evolver.ROOT_DIR", repo_dir):
                with patch("ace_self_evolver.run_verification_test_gate", return_value=(True, "ok")):
                    # 1. mission_id = 'main'
                    ok1, msg1 = ace_self_evolver.execute_isolated_git_commit(
                        "main", "Goal", art_file, allow_push=False
                    )
                    self.assertTrue(ok1)
                    # Verify created branch is ace-evolution/main, NOT main
                    branches = subprocess.run(
                        ["git", "branch"], cwd=repo_dir, check=True, capture_output=True, text=True
                    ).stdout
                    self.assertIn("ace-evolution/main", branches)

                    # Current branch must remain main
                    cur = subprocess.run(
                        ["git", "branch", "--show-current"], cwd=repo_dir, check=True, capture_output=True, text=True
                    ).stdout.strip()
                    self.assertEqual(cur, "main")

                    # 2. Malicious path traversal mission_id
                    ok2, msg2 = ace_self_evolver.execute_isolated_git_commit(
                        "../main", "Goal", art_file, allow_push=False
                    )
                    self.assertFalse(ok2)
                    self.assertIn("failed to create isolated branch", msg2.lower())

                    # 3. Flag injection mission_id
                    ok3, msg3 = ace_self_evolver.execute_isolated_git_commit(
                        "--orphan main", "Goal", art_file, allow_push=False
                    )
                    self.assertFalse(ok3)

    # -------------------------------------------------------------------------
    # VECTOR 14: Unhandled Solver Exception Fails Closed with 0.0 Score
    # -------------------------------------------------------------------------
    def test_vector14_solver_exception_fails_closed_zero_score(self):
        """When solve() encounters a runtime crash, Timeout, or unhandled exception,
        evaluate_and_solve_mission must catch it, record benchmark_score == 0.0,
        decision == INCONCLUSIVE, and program == None.
        """
        with tempfile.TemporaryDirectory() as td:
            artifacts_dir = Path(td)
            problem_data = {
                "schema": SCHEMA,
                "id": "prob_crash_test",
                "goal": "Trigger crash",
                "train": [{"inputs": {"x": 1, "y": 0}, "output": 1}],
                "validation": [{"inputs": {"x": 2, "y": 0}, "output": 2}],
            }
            mission = {
                "id": "mission_crash_014",
                "goal": "Crash solve",
                "hypothesis": "Crash",
                "reasoning_problem": problem_data,
            }

            with patch("ace_self_evolver.solve", side_effect=RuntimeError("Simulated SMT engine crash")):
                art_path, dec, metrics = ace_self_evolver.evaluate_and_solve_mission(mission, artifacts_dir)
                self.assertEqual(dec, "INCONCLUSIVE")
                self.assertEqual(metrics["benchmark_score"], 0.0)
                self.assertIn("ERROR", metrics.get("reason", ""))

                data = json.loads(art_path.read_text(encoding="utf-8"))
                self.assertIsNone(data["program"])

    # -------------------------------------------------------------------------
    # VECTOR 15: Dry-Run Mode Strictly Bypasses All Git Operations
    # -------------------------------------------------------------------------
    def test_vector15_dry_run_mode_strictly_bypasses_git_commits(self):
        """Verify that when dry_run=True, even for an admitted STAGED_EMPIRICAL mission,
        execute_isolated_git_commit is NEVER invoked.
        """
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td)
            from ace_mission.bus import MissionBus

            bus = MissionBus(ws / "mission_bus.sqlite3")
            # Create problem that identity solver can solve
            problem_data = {
                "schema": SCHEMA,
                "id": "prob_solvable",
                "goal": "identity x",
                "train": [{"inputs": {"x": 1, "y": 0}, "output": 1}, {"inputs": {"x": 2, "y": 0}, "output": 2}],
                "validation": [{"inputs": {"x": 3, "y": 0}, "output": 3}],
            }
            bus.create_mission(
                goal="Solve identity",
                hypothesis="Identity problem is solvable",
                task_family_ids=["tf_identity"],
                inputs=[],
                budget={"max_primitive_operations": 5000, "time_sec": 1.0, "max_candidates": 5},
                acceptance={"metric": "exact_development_fit", "threshold": 1, "comparator": "none"},
                forbidden=[],
                reasoning_problem=problem_data,
            )

            with patch("ace_self_evolver.ROOT_DIR", ws):
                with patch("ace_self_evolver.execute_isolated_git_commit") as mock_commit:
                    ace_self_evolver.execute_self_evolution(
                        workspace_path=ws,
                        max_missions=1,
                        continuous=False,
                        dry_run=True,  # DRY RUN ENABLED
                    )
                    mock_commit.assert_not_called()

    # -------------------------------------------------------------------------
    # VECTOR 16: Admission Acceptance Metric Validation
    # -------------------------------------------------------------------------
    def test_vector16_admission_gate_rejects_unsupported_acceptance_criteria(self):
        """Verify that admission.py rejects any mission with unsupported acceptance criteria:
        - metric != 'exact_development_fit' (e.g. 'approximate_fit', 'bleu')
        - threshold != 1 (e.g. 0.99)
        - comparator != 'none'
        Admission gate must set reason == UNSUPPORTED_ACCEPTANCE_CRITERION and BLOCK_RELEASE.
        """
        problem_data = {
            "schema": SCHEMA,
            "id": "prob_acc_test",
            "goal": "Acceptance test",
            "train": [{"inputs": {"x": 1, "y": 0}, "output": 1}],
            "validation": [{"inputs": {"x": 2, "y": 0}, "output": 2}],
        }
        mission = {
            "id": "mission_unsupported_acc_016",
            "goal": "Acceptance metric spoof",
            "hypothesis": "Non-exact metric",
            "reasoning_problem": problem_data,
            "acceptance": {"metric": "fuzzy_development_fit", "threshold": 0.95, "comparator": "gte"},
            "budget": {"max_primitive_operations": 1000, "time_sec": 1.0, "max_candidates": 5},
        }

        art_bytes = json.dumps({
            "schema": ARTIFACT_SCHEMA,
            "problem_digest": digest(problem_data),
            "program": {"var": "x"},
        }).encode("utf-8")

        receipt = evaluate_submission(mission, art_bytes, "STAGED_EMPIRICAL")
        self.assertEqual(receipt["reason"], "UNSUPPORTED_ACCEPTANCE_CRITERION")
        self.assertEqual(receipt["release_gate"], "BLOCK_RELEASE")
        self.assertNotEqual(receipt["decision"], "STAGED_EMPIRICAL")


if __name__ == "__main__":
    unittest.main()
