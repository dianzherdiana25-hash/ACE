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
CONTEXT_HEADER = (
    "Catatan terverifikasi dari pekerjaan sebelumnya "
    "(hasil yang sudah lolos ratifikasi):"
)
WRITEBACK_EVENT = "verdict_sealed"


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
) -> dict[str, Any]:
    """Run one episode through the ratification loop.

    Returns the harness-shaped result dict. On a ratified
    episode with `memory_root` set, one verdict_sealed
    record is written back and its id is reported as
    `writeback_id` (None when not ratified, when no memory
    root was given, or when the write itself failed — the
    write-back layer logs its own failures). Organ
    unavailability is reported as `error`, never raised.
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
    }
    try:
        messages: list[dict] = []
        if context:
            messages.append({
                "role": "system",
                "content": CONTEXT_HEADER + "\n"
                           + "\n---\n".join(context)})
        messages.append({"role": "user", "content": instruction})
        prop = chat(pair.proposer, messages, max_tokens=1024)
        structural, why = structural_gate(task_kind, instruction,
                                          prop.content)
        judge_t0 = time.monotonic()
        judged = chat(
            pair.validator,
            [{"role": "system", "content": JUDGE_EPISODE},
             {"role": "user", "content":
              f"PROMPT/INSTRUCTION:\n{instruction}\n\n"
              f"CANDIDATE:\n{prop.content}"}],
            max_tokens=300)
        parsed = parse_json_object(judged.content)
        ratified = bool(structural) and bool(parsed) \
            and parsed.get("accept") is True
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
            "episode_wall_s": round(time.monotonic() - t0, 2),
        })
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
