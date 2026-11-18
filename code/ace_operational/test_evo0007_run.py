"""Tests for the EVO 0007 package runner (PR #311 S9.2).

All transports are fakes: no live organ is ever called here.
The behaviours pinned are the preregistration's own rules -
judge parsing (incl. the Gonka double-object quirk), the
one-shot band re-derivation, the composition/scope readout,
context delivery per arm, and the verdict gate.
"""
import unittest

from ace_operational.evo0007_run import (
    DEFAULT_BAND, JUDGE_ORGAN, calibrate, compute_verdict,
    first_json_object, parse_judge_output, run_episode)


def judge_returning(score_map):
    """Fake transport keyed by candidate id (thread-safe:
    calibration screens concurrently, so a shared iterator
    would assign scores nondeterministically). Screening calls
    the proposer first (prompt = the task body) and then the
    judge twice (prompt = judge prompt + the answer); proposer
    calls get a canned answer, judge calls get their (a, b)
    score pair in order."""
    import threading
    lock = threading.Lock()
    calls = {}

    def _t(provider, model, prompt, max_tokens):
        if "Candidate answer:" not in prompt:
            cid = prompt.rsplit(" ", 1)[-1]
            return f"answer for {cid}"
        head = prompt.split("\n\nCandidate answer:")[0]
        cid = head.rsplit(" ", 1)[-1]
        with lock:
            n = calls.get(cid, 0)
            calls[cid] = n + 1
        score = score_map[cid][n]
        return ('{"accept": true, "score": %s, "reasons": "fake"}'
                % score)
    return _t


def candidate(cid, kind="code"):
    return {"id": cid, "task_kind": kind,
            "prompt": f"task body {cid}",
            "judge_prompt": f"judge me {cid}"}


def uniform_scores(cands, pair):
    return {c["id"]: pair for c in cands}


class JudgeParsingTests(unittest.TestCase):
    def test_double_object_reads_first_only(self):
        text = ('{"accept": true, "score": 85, "reasons": "ok"}'
                '{"accept": false, "score": 3, "reasons": "dupe"}')
        obj = first_json_object(text)
        self.assertEqual(obj["score"], 85)

    def test_parse_validates_shape(self):
        out = parse_judge_output(
            '{"accept": false, "score": 41.5, "reasons": "thin"}')
        self.assertEqual(out, {"accept": False, "score": 41.5,
                               "reasons": "thin"})

    def test_unscored_output_fails_closed(self):
        for bad in ('{"accept": true, "reasons": "no score"}',
                    '{"score": 50, "reasons": "no accept"}',
                    '{"accept": true, "score": 140, "reasons": "x"}',
                    'no json at all'):
            with self.assertRaises(ValueError, msg=bad):
                parse_judge_output(bad)


class CalibrationTests(unittest.TestCase):
    def test_in_band_selection_by_mean(self):
        cands = [candidate(f"c{i}") for i in range(12)]
        scores = {c["id"]: ((60, 60) if i < 8 else (95, 95))
                  for i, c in enumerate(cands)}
        result = calibrate(cands, judge_returning(scores))
        self.assertTrue(result["sufficient"])
        self.assertEqual(result["probe_n"], 8)
        self.assertEqual(result["band"], list(DEFAULT_BAND))
        self.assertFalse(result["band_rederived"])

    def test_fraction_trigger_fires_and_rederives_to_same_band(self):
        # 8/10 in-band = fraction 0.80 > 0.70: the ratified S3
        # rule fires even on a clean split; the median sits
        # mid-band, so the re-derived band equals the default
        # and membership is unchanged. The flag records that
        # the rule fired, not that the band moved.
        cands = [candidate(f"c{i}") for i in range(10)]
        scores = {c["id"]: ((60, 60) if i < 8 else (95, 95))
                  for i, c in enumerate(cands)}
        result = calibrate(cands, judge_returning(scores))
        self.assertTrue(result["band_rederived"])
        self.assertEqual(result["band"], list(DEFAULT_BAND))
        self.assertEqual(result["probe_n"], 8)

    def test_one_shot_band_rederivation_on_saturation(self):
        cands = [candidate(f"c{i}") for i in range(10)]
        # everything at 90: the band does not discriminate
        result = calibrate(cands, judge_returning(
            uniform_scores(cands, (90, 90))))
        self.assertTrue(result["band_rederived"])
        self.assertEqual(result["band"], [75.0, 105.0])
        self.assertEqual(result["probe_n"], 10)

    def test_insufficient_pool_reports_instrument_verdict(self):
        cands = [candidate(f"c{i}") for i in range(4)]
        result = calibrate(cands, judge_returning(
            uniform_scores(cands, (50, 50))))
        self.assertFalse(result["sufficient"])
        self.assertEqual(result["verdict_if_stopped_here"],
                         "INSTRUMEN_TIDAK_CUKUP")

    def test_language_composition_scope(self):
        cands = ([candidate(f"cd{i}") for i in range(6)]
                 + [candidate(f"lg{i}", "language") for i in range(4)])
        result = calibrate(cands, judge_returning(
            uniform_scores(cands, (60, 60))))
        self.assertEqual(result["language_n"], 4)
        self.assertEqual(result["scope"], "mixed")

    def test_spread_flag_recorded(self):
        cands = [candidate(f"c{i}") for i in range(8)]
        scores = uniform_scores(cands, (60, 60))
        scores["c0"] = (35, 95)  # spread 60, mean 65 (in-band)
        result = calibrate(cands, judge_returning(scores))
        first = result["screened"][0]
        self.assertEqual(first["spread"], 60.0)
        self.assertTrue(first["spread_flag"])
        self.assertIn(first, result["probe_set"])  # mean is in-band


class EpisodeAndVerdictTests(unittest.TestCase):
    EP = {"id": "ep1", "task_kind": "code", "task_shape": "code:x",
          "prompt": "do the task", "receipt_text": "receipt body",
          "sham_text": "sham body"}
    PATTERNS = [{"task_shape": "code:x", "approach": "do it well",
                 "pitfalls": ["trap"], "source_episode": "src1"}]

    def transport(self, provider, model, prompt, max_tokens):
        if provider == JUDGE_ORGAN[0]:
            return '{"accept": true, "score": 70, "reasons": "ok"}'
        if "Validate this proposal" in prompt:
            return "RATIFY"
        return "a proposal"

    def test_pola_episode_delivers_pattern_context(self):
        row = run_episode("POLA", self.EP, self.PATTERNS,
                          self.transport)
        self.assertTrue(row["delivered"])
        self.assertEqual(row["context_ids"], ["src1"])
        self.assertTrue(row["accepted"])
        self.assertEqual(row["brain_judge"],
                         f"{JUDGE_ORGAN[0]}/{JUDGE_ORGAN[1]}")

    def test_pola_without_match_is_undelivered_not_error(self):
        row = run_episode("POLA", self.EP, [], self.transport)
        self.assertFalse(row["delivered"])
        self.assertEqual(row["context_ids"], [])

    def test_validator_rejection_skips_judge(self):
        def rejecting(provider, model, prompt, max_tokens):
            if "Validate this proposal" in prompt:
                return "REJECT: off task"
            return "a proposal"
        row = run_episode("KOSONG", self.EP, [], rejecting)
        self.assertFalse(row["accepted"])
        self.assertEqual(row["judge_skipped"], "validator_rejected")

    def _rows(self, arm, delivered, accepted, n=4):
        return [{"episode_id": f"e{i}", "arm": arm,
                 "delivered": delivered, "accepted": accepted}
                for i in range(n)]

    def test_verdict_supported(self):
        probe = [{"id": f"e{i}", "spread_flag": False}
                 for i in range(4)]
        rows = {"POLA": self._rows("POLA", True, True),
                "RECEIPT": self._rows("RECEIPT", True, False),
                "SHAM": self._rows("SHAM", True, False),
                "KOSONG": self._rows("KOSONG", True, False)}
        out = compute_verdict(rows, probe)
        self.assertEqual(out["verdict"], "TERDUKUNG")

    def test_delivery_gate_blocks_verdict(self):
        probe = [{"id": f"e{i}", "spread_flag": False}
                 for i in range(4)]
        rows = {"POLA": self._rows("POLA", False, True),
                "RECEIPT": self._rows("RECEIPT", True, False),
                "SHAM": self._rows("SHAM", True, False),
                "KOSONG": self._rows("KOSONG", True, False)}
        out = compute_verdict(rows, probe)
        self.assertEqual(out["verdict"], "TIDAK_TERANTAR")


if __name__ == "__main__":
    unittest.main()


class AdapterTests(unittest.TestCase):
    def test_adapt_frozen_corpus_row(self):
        from ace_operational.evo0007_run import adapt_candidate
        row = {"id": "w2-code-001", "kind": "episode",
               "task_kind": "code", "instruction": "Write f(x)."}
        out = adapt_candidate(row)
        self.assertEqual(out["prompt"], "Write f(x).")
        self.assertTrue(out["judge_prompt"].endswith("Write f(x)."))
        self.assertNotIn("task_shape", out)

    def test_unlabelled_episode_is_pola_undelivered(self):
        ep = {"id": "epX", "task_kind": "code",
              "prompt": "do it"}
        row = run_episode("POLA", ep, EpisodeAndVerdictTests.PATTERNS,
                          EpisodeAndVerdictTests().transport)
        self.assertFalse(row["delivered"])

    def test_judge_skipped_counts_reported_per_arm(self):
        def rows(arm, accepted, skipped=0):
            out = [{"episode_id": f"e{i}", "arm": arm,
                    "delivered": True, "accepted": accepted}
                   for i in range(4)]
            for r in out[:skipped]:
                r["judge_skipped"] = "validator_rejected"
            return out
        probe = [{"id": f"e{i}", "spread_flag": False}
                 for i in range(4)]
        arms = {"POLA": rows("POLA", True, skipped=2),
                "RECEIPT": rows("RECEIPT", False),
                "SHAM": rows("SHAM", False),
                "KOSONG": rows("KOSONG", False)}
        out = compute_verdict(arms, probe)
        self.assertEqual(out["judge_skipped_per_arm"]["POLA"], 2)
        self.assertEqual(out["judge_skipped_per_arm"]["KOSONG"], 0)


class ScreeningSemanticsTests(unittest.TestCase):
    """Ratified amendment (2026-11-18): screening answers the
    candidate with its kind's proposer organ BEFORE judging;
    the judge scores (task + answer) twice; the validator is
    not part of screening."""

    def test_proposer_answers_then_judge_scores_the_answer(self):
        from ace_operational.evo0007_run import (
            JUDGE_ORGAN, ORGAN_ROLES, screen_candidate)
        calls = []

        def transport(provider, model, prompt, max_tokens):
            calls.append((provider, model, prompt))
            if (provider, model) == ORGAN_ROLES["code"]["proposer"]:
                return "the proposed answer"
            # judge: 0 without an answer in the prompt
            if "Candidate answer:" not in prompt:
                return ('{"accept": false, "score": 0, '
                        '"reasons": "answer missing"}')
            return ('{"accept": true, "score": 60, '
                    '"reasons": "answered"}')

        row = screen_candidate(transport, candidate("s1"))
        organs = [(p, m) for p, m, _ in calls]
        proposer = ORGAN_ROLES["code"]["proposer"]
        self.assertEqual(organs, [proposer, JUDGE_ORGAN, JUDGE_ORGAN])
        # the validator organ never appears in screening
        self.assertNotIn(ORGAN_ROLES["code"]["validator"], organs)
        for _, _, prompt in calls[1:]:
            self.assertIn("the proposed answer", prompt)
        self.assertEqual(row["mean"], 60.0)
        self.assertEqual(row["answer"], "the proposed answer")
        self.assertEqual(row["brain_proposer"],
                         "groq/qwen/qwen3.8-27b")

    def test_unanswered_task_scores_zero_control(self):
        # The defect the amendment repairs: judging the bare
        # task (no answer) can only score 0.
        from ace_operational.evo0007_run import parse_judge_output

        def judge_only(prompt):
            if "Candidate answer:" not in prompt:
                return ('{"accept": false, "score": 0, '
                        '"reasons": "answer missing"}')
            return ('{"accept": true, "score": 60, '
                    '"reasons": "answered"}')

        bare = parse_judge_output(judge_only("judge me s1"))
        self.assertEqual(bare["score"], 0)


class ConcurrencyTests(unittest.TestCase):
    """Hub tempo amendment (2026-11-18): calibration screens at
    most 4 candidates concurrently; the first error stops new
    launches globally while in-flight rows finish."""

    def test_concurrency_bounded_and_parallel(self):
        import threading, time
        lock = threading.Lock()
        state = {"in_flight": 0, "max_seen": 0}

        def slow_judge(provider, model, prompt, max_tokens):
            with lock:
                state["in_flight"] += 1
                state["max_seen"] = max(state["max_seen"],
                                        state["in_flight"])
            time.sleep(0.05)
            with lock:
                state["in_flight"] -= 1
            return '{"accept": true, "score": 60, "reasons": "x"}'

        cands = [candidate(f"c{i}") for i in range(8)]
        result = calibrate(cands, slow_judge)
        self.assertEqual(result["probe_n"], 8)
        self.assertLessEqual(state["max_seen"], 4)
        self.assertGreaterEqual(state["max_seen"], 2)

    def test_first_error_stops_new_launches_globally(self):
        import threading, time
        from ace_operational.evo0007_run import ScreeningError
        lock = threading.Lock()
        judged = []

        def flaky(provider, model, prompt, max_tokens):
            if "Candidate answer:" not in prompt:
                return "ans text"
            head = prompt.split("\n\nCandidate answer:")[0]
            cid = head.rsplit(" ", 1)[-1]
            with lock:
                judged.append(cid)
            if cid == "c0":
                raise RuntimeError("judge down")
            time.sleep(0.2)
            return '{"accept": true, "score": 60, "reasons": "x"}'

        cands = [candidate(f"c{i}") for i in range(8)]
        with self.assertRaises(ScreeningError) as ctx:
            calibrate(cands, flaky)
        self.assertEqual(ctx.exception.failed_id, "c0")
        # only the first window (4 candidates) was ever launched
        self.assertLessEqual(set(judged), {"c0", "c1", "c2", "c3"})
        # in-flight rows that finished are carried for the caller
        done_ids = {r["id"] for r in ctx.exception.completed}
        self.assertTrue(done_ids <= {"c1", "c2", "c3"})
