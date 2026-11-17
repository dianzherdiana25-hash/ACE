"""The ratification loop: heterogeneous proposer -> validator
-> memory write-back, as a first-class engine step.

This module carries the EXACT instrument semantics that
EVO 0003's tail and EVO 0004 Blok A measured with (the
"instrument v2" harness): the proposer/validator pair comes
from brain_endpoints.proposer_validator_pair (code episodes:
coder proposes, front validates; language episodes: front
proposes, coder validates), the proposer runs through
chat_structured (bounded thinking), the structural gate is
the harness's (code: the text must ast.parse and define the
function the instruction names in backticks; language: at
least 40 characters), and the validator is the strict JSON
judge below, also via chat_structured.

On top of the measured instrument, the loop closes the
accumulation path: a RATIFIED episode is written back into
cognitive memory as a verdict_sealed record
(memory_writeback, PR #235) whose evidence is the episode
transcript. Non-ratified episodes and unavailable organs
write NOTHING — fail-closed, aligned with the sovereign
runtime (PR #233): an episode that could not be judged is
not knowledge.

`context` is the read side of the same loop (EVO 0005's
mechanism): summaries recalled from accumulated records
(e.g. via memory_writeback.recall_context) may be supplied
and are prepended to the proposer as a system note. With no
context the proposer prompt is byte-identical to the
measured harness's.

Judge v3 (`scored=True`, the successor-to-0006 instrument,
PR #253) additionally requires the judge to return an
anchored 0-100 `score`. The score never decides
ratification — `accept` remains the verdict currency — it
exists so calibration can measure the judge's MARGIN
(binary split-hunting cannot stock a sensitivity band on
a near-deterministic organ pair, EVO 0006's finding). A
scored run whose judge omits the score or returns one
outside 0-100 is a failed measurement: the result carries
`error` and nothing is written back, fail-closed like
every other unjudged episode.

The engine drives this module through
ContinuousAutonomousEngine.execute_ratification_step; the
chat/pair functions are injectable so the loop is testable
without live organs.
"""
from __future__ import annotations

import ast
import json
import re
import time
from pathlib import Path
from typing import Any, Callable

from . import brain_endpoints as be
from .memory_writeback import record_verified_event

JUDGE_EPISODE = (
    "You are a strict validator. Judge whether the candidate fully "
    "satisfies the instruction (correctness, required form, "
    "Indonesian docstring where demanded). Reply with ONLY a JSON "
    'object, no other text: {"accept": true/false, "reasons": ["..."]}'
)
JUDGE_EPISODE_V3 = (
    "You are a strict validator. Judge whether the candidate fully "
    "satisfies the instruction (correctness, required form, "
    "Indonesian docstring where demanded). Also grade the candidate "
    "with an integer score from 0 to 100 using this anchored "
    "rubric: 0-39 fails in substance; 40-59 partly correct with "
    "real defects; 60-79 correct with small defects; 80-100 "
    "correct and clean. Reply with ONLY a JSON object, no other "
    'text: {"accept": true/false, "score": <integer 0-100>, '
    '"reasons": ["..."]}'
)
CONTEXT_HEADER = (
    "Catatan terverifikasi dari pekerjaan sebelumnya "
    "(hasil yang sudah lolos ratifikasi):"
)
WRITEBACK_EVENT = "verdict_sealed"
JUDGE_MAX_TOKENS = 300
# Scored (v3) judges write longer responses — the score plus
# reasons — and band episodes are exactly the ones whose
# judges write longest. At the v2 budget their JSON was cut
# mid-reasons and never closed (EVO 0006 successor, wave 1:
# cd-code-007, score present but unparseable). The budget is
# a ceiling, not a setting: responses that complete under
# 300 tokens are identical under either budget, so raising
# it does not invalidate completed measurements.
JUDGE_MAX_TOKENS_SCORED = 800
# Amendment 3 (hub-ratified, EVO 0006 successor wave 2):
# brain_endpoints.chat's default client timeout is 900 s,
# sized for ordinary generations. At the scored ceiling of
# 800 tokens a judge whose generation rate collapses (front
# observed at ~0.45 t/s during wave 2) needs ~1,778 s of
# wall — so two wave-2 episodes died as client timeouts
# while the judge was still generating normally, and the
# phase aborted on the error row. Scored runs therefore
# pass an extended client timeout on both chat calls. The
# generative conditions are unchanged (same prompts, same
# token ceilings, same salvage rule); only the client's
# patience moves, and only on the scored path.
SCORED_CHAT_TIMEOUT_S = 2400.0


def parse_json_object(text: str) -> dict | None:
    """The harness's tolerant JSON-object extraction."""
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-z]*\n?|```$", "", text).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        value = json.loads(text[start:end + 1])
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


def parse_judge_score(parsed: dict | None) -> int | None:
    """The v3 judge's score, strictly: an integer (or an
    integral float) inside 0-100. Booleans and strings are
    not scores. Anything else returns None, which the
    caller treats as a failed measurement."""
    if not isinstance(parsed, dict):
        return None
    value = parsed.get("score")
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        score = value
    elif isinstance(value, float) and value.is_integer():
        score = int(value)
    else:
        return None
    return score if 0 <= score <= 100 else None


_SALVAGE_ACCEPT = re.compile(r'"accept"\s*:\s*(true|false)\s*[,}]')
_SALVAGE_SCORE = re.compile(r'"score"\s*:\s*(\d{1,3})\s*[,}]')


def salvage_judge_fields(raw: str) -> dict | None:
    """Recover accept + score from a truncated v3 reply.

    Scored-path only (ratified amendment, hub 2026-11-17):
    a verbose judge's reasons can outrun any sane token
    budget, leaving the JSON object unclosed while the two
    fields calibration actually consumes — accept and
    score — sit complete and delimited at its head (EVO
    0006 successor, wave 1: cd-code-007, accept=false and
    score=45 intact across three measurements, reasons
    never finished). Salvage applies ONLY when the strict
    parse already failed, the text opens as a JSON object,
    and BOTH fields are present, complete and followed by
    a delimiter (a score cut mid-digits has no delimiter
    and stays a failed measurement). The salvaged verdict
    carries empty reasons and the caller marks the run
    judge_truncated for audit.
    """
    if not raw or not raw.lstrip().startswith("{"):
        return None
    ma = _SALVAGE_ACCEPT.search(raw)
    ms = _SALVAGE_SCORE.search(raw)
    if ma is None or ms is None:
        return None
    score = int(ms.group(1))
    if not 0 <= score <= 100:
        return None
    return {"accept": ma.group(1) == "true",
            "score": score, "reasons": []}


def structural_gate_code(instruction: str,
                         text: str) -> tuple[bool, str]:
    match = re.search(r"```(?:python)?\n(.*?)```", text, re.S)
    code = match.group(1) if match else text
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return False, f"syntax:{exc}"
    demanded = re.search(r"`(\w+)\(", instruction)
    if demanded:
        names = {n.name for n in ast.walk(tree)
                 if isinstance(n, ast.FunctionDef)}
        if demanded.group(1) not in names:
            return False, f"function_missing:{demanded.group(1)}"
    return True, "ok"


def structural_gate(task_kind: str, instruction: str,
                    text: str) -> tuple[bool, str]:
    if task_kind == "code":
        return structural_gate_code(instruction, text)
    ok = len((text or "").strip()) >= 40
    return ok, "ok" if ok else "too_short"


def load_episodes(path: str | Path) -> list[dict]:
    rows = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def run_ratification_episode(
    episode: dict,
    *,
    memory_root: str | Path | None = None,
    context: list[str] | None = None,
    chat_fn: Callable | None = None,
    pair_fn: Callable | None = None,
    scored: bool = False,
) -> dict[str, Any]:
    """Run one episode through the ratification loop.

    Returns the harness-shaped result dict. On a ratified
    episode with `memory_root` set, one verdict_sealed
    record is written back and its id is reported as
    `writeback_id` (None when not ratified, when no memory
    root was given, or when the write itself failed — the
    write-back layer logs its own failures). Organ
    unavailability is reported as `error`, never raised.

    With `scored=True` the judge runs the v3 prompt and
    must return an anchored 0-100 score, reported as
    `judge_score`. A missing or out-of-range score makes
    the run a failed measurement: `error` is set, the
    episode is not ratified, and nothing is written back.
    """
    chat = chat_fn or be.chat_structured
    pair_of = pair_fn or be.proposer_validator_pair
    task_kind = episode["task_kind"]
    instruction = episode["instruction"]
    pair = pair_of(task_kind)
    t0 = time.monotonic()
    result: dict[str, Any] = {
        "id": episode["id"], "kind": "episode",
        "task_kind": task_kind, "pair": pair.as_dict(),
        "ratified": False, "writeback_id": None,
        "judge_score": None, "judge_truncated": False,
    }
    judge_prompt = JUDGE_EPISODE_V3 if scored else JUDGE_EPISODE
    # Amendment 3: scored runs carry the extended client
    # timeout; unscored calls keep the chat default exactly.
    timeout_kw = ({"timeout": SCORED_CHAT_TIMEOUT_S}
                  if scored else {})
    try:
        messages: list[dict] = []
        if context:
            messages.append({
                "role": "system",
                "content": CONTEXT_HEADER + "\n"
                           + "\n---\n".join(context)})
        messages.append({"role": "user", "content": instruction})
        prop = chat(pair.proposer, messages, max_tokens=1024,
                    **timeout_kw)
        structural, why = structural_gate(task_kind, instruction,
                                          prop.content)
        judge_t0 = time.monotonic()
        judged = chat(
            pair.validator,
            [{"role": "system", "content": judge_prompt},
             {"role": "user", "content":
              f"PROMPT/INSTRUCTION:\n{instruction}\n\n"
              f"CANDIDATE:\n{prop.content}"}],
            max_tokens=JUDGE_MAX_TOKENS_SCORED if scored
            else JUDGE_MAX_TOKENS, **timeout_kw)
        parsed = parse_json_object(judged.content)
        judge_truncated = False
        if parsed is None and scored:
            parsed = salvage_judge_fields(judged.content)
            judge_truncated = parsed is not None
        ratified = bool(structural) and bool(parsed) \
            and parsed.get("accept") is True
        score = parse_judge_score(parsed) if scored else None
        result.update({
            "output": prop.content,
            "output_chars": len(prop.content),
            "proposer_wall_s": round(judge_t0 - t0, 2),
            "proposer_tps": prop.predicted_per_second,
            "structural_gate": structural, "structural_why": why,
            "validator": {"raw": judged.content, "parsed": parsed,
                          "wall_s": round(time.monotonic()
                                          - judge_t0, 2),
                          "organ_woke": judged.organ_woke},
            "ratified": ratified,
            "judge_score": score,
            "judge_truncated": judge_truncated,
            "episode_wall_s": round(time.monotonic() - t0, 2),
        })
        if scored and score is None:
            result["ratified"] = False
            result["error"] = (
                "JudgeScoreInvalid: scored judge returned no "
                "valid 0-100 score")
    except be.BrainUnavailable as exc:
        result["error"] = f"BrainUnavailable: {exc}"
        result["episode_wall_s"] = round(time.monotonic() - t0, 2)
        return result
    if result["ratified"] and memory_root is not None:
        transcript = json.dumps(
            {"episode": episode, "result": result},
            ensure_ascii=False, sort_keys=True).encode("utf-8")
        result["writeback_id"] = record_verified_event(
            memory_root,
            event=WRITEBACK_EVENT,
            summary=(f"Ratified episode {episode['id']} "
                     f"({task_kind}) via {pair.proposer}"
                     f"->{pair.validator}"),
            evidence_bytes=transcript,
            content_extra={"episode_id": episode["id"],
                           "task_kind": task_kind,
                           "pair": pair.as_dict()})
    return result
